from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mc_foreman.artifacts.result_bundle import build_result_bundle
from mc_foreman.execution.generator import CommandGenerator, build_generator
from mc_foreman.execution.zone_allocator import BuildZone


_CHANGED_BLOCK_RE = re.compile(
    r"(?:Changed|Successfully\s+filled)\s+(\d+)\s+(?:blocks?|block\(s\))",
    re.IGNORECASE,
)
_SETBLOCK_CHANGED_RE = re.compile(r"Changed\s+the\s+block\s+at\b", re.IGNORECASE)
_NOT_LOADED_RE = re.compile(r"that position is not loaded", re.IGNORECASE)

# Themes that get the tighter bridge/arch prompt
_BRIDGE_THEMES = {"桥", "拱桥", "江南拱桥", "石桥", "木桥", "廊桥", "bridge"}


@dataclass
class ExecutionResult:
    success: bool
    result_ref: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class CommandAnalysis:
    command_count: int
    placement_count: int
    sampled_placements: list[dict]
    outside_zone_commands: list[str]
    build_bbox: Optional[dict] = None


class ExecutionBridge:
    """v1 execution bridge.

    Modes:
    - mock: immediately succeed
    - claude_rcon: generate commands via configurable generator, extract, send over RCON
    """

    player_selector = "@p"

    def __init__(
        self,
        config,
        generator: Optional[CommandGenerator] = None,
    ):
        self.config = config
        self._generator = generator

    @property
    def generator(self) -> CommandGenerator:
        if self._generator is None:
            self._generator = build_generator(self.config)
        return self._generator

    def execute(self, task) -> ExecutionResult:
        mode = self.config.execution_mode
        if mode == "mock":
            return self._execute_mock(task)
        if mode == "claude_rcon":
            return self._execute_via_generator_rcon(task)
        return ExecutionResult(success=False, reason=f"unsupported execution mode: {mode}")

    def _result_output_root(self) -> Path:
        return Path(getattr(self.config, "execution_tmp_dir", Path.cwd() / "data" / "execution"))

    def _execute_mock(self, task) -> ExecutionResult:
        manifest_path = build_result_bundle(
            output_root=self._result_output_root(),
            task_id=task.task_id,
            theme=task.theme,
            commands_path=f"mock://{task.task_id}",
            verification={"mode": "mock", "verified": False, "note": "simulated execution, no real Minecraft commands sent"},
        )
        return ExecutionResult(success=True, result_ref=manifest_path)

    @staticmethod
    def _is_bridge_theme(theme: str) -> bool:
        t = theme.strip().lower()
        return t in _BRIDGE_THEMES or "桥" in t or "bridge" in t.lower()

    def _build_prompt(self, task) -> str:
        zone = BuildZone.from_assignment_str(getattr(task, "zone_assignment", None))
        if zone:
            x_min, x_max = zone.origin_x, zone.origin_x + zone.size_x - 1
            z_min, z_max = zone.origin_z, zone.origin_z + zone.size_z - 1
            y_min = zone.y
            area_hint = f"x={x_min}..{x_max}, z={z_min}..{z_max}"
            y_hint = f"Y={y_min} 到 Y={y_min + 8}"
        else:
            area_hint = "x=100..120, z=200..220"
            y_hint = "Y=64 到 Y=72"

        if self._is_bridge_theme(task.theme):
            return self._build_bridge_prompt(task.theme, area_hint, y_hint)
        return self._build_general_prompt(task, area_hint, y_hint)

    def _build_general_prompt(self, task, area_hint: str, y_hint: str) -> str:
        size_hint = "小型" if task.size == "small" else "中型"
        return (
            "你是一个 Minecraft 建筑命令生成器。"
            "请只输出可直接执行的 Minecraft 原版命令，优先使用 /fill 和 /setblock。\n\n"
            f"任务：在固定测试区域中建造一个{size_hint}建筑。主题：{task.theme}。"
            "要求：\n"
            "1. 仅输出命令代码块；\n"
            "2. 使用绝对坐标；\n"
            "3. 结构尽量简单可靠；\n"
            "4. 如果不确定复杂细节，直接省略；\n"
            f"5. 使用 {y_hint} 之间的可见高度；\n"
            f"6. 建筑大致放在 {area_hint} 的区域内；\n"
            "7. 建筑必须落地，底部直接接触地面，不要悬空，不要漂浮平台；\n"
            "8. 优先从地面底座开始向上建造，第一批非 air 方块应放在最低允许 Y 附近。\n"
        )

    @staticmethod
    def _build_bridge_prompt(theme: str, area_hint: str, y_hint: str) -> str:
        """Tighter prompt for bridge/arch themes — constrains output to ~15 commands."""
        return (
            "你是 Minecraft 建筑命令生成器。仅输出命令，不要任何解释。\n\n"
            f"任务：建造一座小型{theme}。\n"
            "严格限制：\n"
            "- 总命令数 ≤ 15 条\n"
            "- 仅使用 /fill，不用 /setblock\n"
            "- 仅用这些方块：stone_bricks, dark_oak_planks, dark_oak_log, quartz_block\n"
            "- 桥面跨度 ≤ 20 格，宽度 5 格\n"
            "- 不做栏杆细节，不做水面，不做装饰\n"
            "- 使用绝对坐标\n"
            f"- 高度范围 {y_hint}\n"
            f"- 区域 {area_hint}\n\n"
            "参考结构（5 步）：\n"
            "1. 清空区域 → /fill ... air\n"
            "2. 两端桥面（低位）→ /fill ... dark_oak_planks\n"
            "3. 中段桥面（抬升）→ /fill ... dark_oak_planks\n"
            "4. 两侧护栏 → /fill ... stone_bricks\n"
            "5. 桥头标记 → /fill ... quartz_block\n\n"
            "直接输出命令代码块：\n"
        )

    @staticmethod
    def _zone_contains(zone: BuildZone, x: int, z: int) -> bool:
        return (
            zone.origin_x <= x <= zone.origin_x + zone.size_x - 1
            and zone.origin_z <= z <= zone.origin_z + zone.size_z - 1
        )

    def _analyze_commands(self, commands_path: Path, zone: Optional[BuildZone]) -> CommandAnalysis:
        commands = []
        placement_samples: list[dict] = []
        outside_zone: list[str] = []
        bbox: Optional[dict] = None

        for raw_line in commands_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            commands.append(line)
            tokens = line.lstrip("/").split()
            if not tokens:
                continue

            name = tokens[0].lower()
            if name == "setblock" and len(tokens) >= 5:
                x, y, z = tokens[1:4]
                block = tokens[4]
                if any(axis.startswith(("~", "^")) for axis in (x, y, z)):
                    outside_zone.append(line)
                    continue
                xi, yi, zi = int(x), int(y), int(z)
                if zone and not self._zone_contains(zone, xi, zi):
                    outside_zone.append(line)
                if block.lower() != "air":
                    placement_samples.append({"command": line, "x": xi, "y": yi, "z": zi, "block": block})
                    if bbox is None:
                        bbox = {"min_x": xi, "max_x": xi, "min_y": yi, "max_y": yi, "min_z": zi, "max_z": zi}
                    else:
                        bbox["min_x"] = min(bbox["min_x"], xi)
                        bbox["max_x"] = max(bbox["max_x"], xi)
                        bbox["min_y"] = min(bbox["min_y"], yi)
                        bbox["max_y"] = max(bbox["max_y"], yi)
                        bbox["min_z"] = min(bbox["min_z"], zi)
                        bbox["max_z"] = max(bbox["max_z"], zi)
                continue

            if name == "fill" and len(tokens) >= 8:
                c1 = tokens[1:4]
                c2 = tokens[4:7]
                block = tokens[7]
                if any(axis.startswith(("~", "^")) for axis in (*c1, *c2)):
                    outside_zone.append(line)
                    continue
                x1, y1, z1 = (int(v) for v in c1)
                x2, y2, z2 = (int(v) for v in c2)
                corners = ((x1, z1), (x1, z2), (x2, z1), (x2, z2))
                if zone and any(not self._zone_contains(zone, x, z) for x, z in corners):
                    outside_zone.append(line)
                if block.lower() != "air":
                    sx = min(x1, x2)
                    sy = min(y1, y2)
                    sz = min(z1, z2)
                    placement_samples.append({"command": line, "x": sx, "y": sy, "z": sz, "block": block})
                    if bbox is None:
                        bbox = {
                            "min_x": min(x1, x2), "max_x": max(x1, x2),
                            "min_y": min(y1, y2), "max_y": max(y1, y2),
                            "min_z": min(z1, z2), "max_z": max(z1, z2),
                        }
                    else:
                        bbox["min_x"] = min(bbox["min_x"], x1, x2)
                        bbox["max_x"] = max(bbox["max_x"], x1, x2)
                        bbox["min_y"] = min(bbox["min_y"], y1, y2)
                        bbox["max_y"] = max(bbox["max_y"], y1, y2)
                        bbox["min_z"] = min(bbox["min_z"], z1, z2)
                        bbox["max_z"] = max(bbox["max_z"], z1, z2)

        return CommandAnalysis(
            command_count=len(commands),
            placement_count=len(placement_samples),
            sampled_placements=placement_samples[:8],
            outside_zone_commands=outside_zone,
            build_bbox=bbox,
        )

    # Maximum fraction of commands allowed to fail while still treating the
    # build as successful.  E.g. 0.10 = up to 10 % of commands may fail.
    PARTIAL_FAIL_TOLERANCE = 0.10

    @staticmethod
    def _evaluate_partial_success(summary: dict) -> bool:
        """Return True if the summary shows an acceptable partial success.

        A build is acceptable when:
        - The error ratio is within tolerance, AND
        - At least some blocks were actually changed.
        """
        cmd_count = summary.get("command_count", 0)
        err_count = summary.get("error_count", 0)
        if cmd_count <= 0 or err_count <= 0:
            return False
        error_ratio = err_count / cmd_count
        if error_ratio > ExecutionBridge.PARTIAL_FAIL_TOLERANCE:
            return False
        changed = ExecutionBridge._changed_blocks_from_summary(summary)
        return changed > 0

    @staticmethod
    def _changed_blocks_from_summary(summary: dict) -> int:
        raw_total = summary.get("changed_blocks", 0)
        try:
            total = int(raw_total or 0)
        except (TypeError, ValueError):
            total = 0
        if total > 0:
            return total

        recomputed = 0
        for item in summary.get("results", []):
            raw_item_total = item.get("changed_blocks", 0)
            try:
                item_total = int(raw_item_total or 0)
            except (TypeError, ValueError):
                item_total = 0
            if item_total > 0:
                recomputed += item_total
                continue

            response = str(item.get("response", "") or "")
            match = _CHANGED_BLOCK_RE.search(response)
            if match:
                recomputed += int(match.group(1))
            elif _SETBLOCK_CHANGED_RE.search(response):
                recomputed += 1
        return recomputed

    @staticmethod
    def _code_dir() -> Path:
        """Locate the code/ scripts directory relative to this package."""
        return Path(__file__).resolve().parent.parent / "code"

    def _run_rcon(self, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(self._code_dir() / "rcon_send.py"),
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _forceload_args(self, zone: BuildZone, action: str) -> list[str]:
        x2 = zone.origin_x + zone.size_x - 1
        z2 = zone.origin_z + zone.size_z - 1
        return [f"forceload {action} {zone.origin_x} {zone.origin_z} {x2} {z2}"]

    @staticmethod
    def _read_summary(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _summary_indicates_not_loaded(summary: dict) -> bool:
        results = summary.get("results", []) or []
        if not results:
            return False
        had_error = False
        for item in results:
            text = f"{item.get('response', '')} {item.get('error', '')}".strip()
            if not text:
                continue
            had_error = True
            if not _NOT_LOADED_RE.search(text):
                return False
        return had_error

    @staticmethod
    def _summary_first_error(summary: dict) -> Optional[str]:
        for item in summary.get("results", []) or []:
            text = (item.get("error") or item.get("response") or "").strip()
            if text:
                return text
        return None

    def _execute_sender_with_retry(self, *, commands_path: Path, summary_path: Path, zone: Optional[BuildZone]) -> tuple[subprocess.CompletedProcess, dict, bool]:
        sender = self._run_rcon(
            "-f",
            str(commands_path),
            "--host",
            self.config.rcon_host,
            "--port",
            str(self.config.rcon_port),
            "--password",
            self.config.rcon_password,
            "--summary-json",
            str(summary_path),
            timeout=180,
        )
        summary = self._read_summary(summary_path)
        retried = False

        if sender.returncode != 0 and zone is not None and self._summary_indicates_not_loaded(summary):
            # Pragmatic recovery: give the server a moment after forceload, then retry once.
            time.sleep(1.0)
            sender = self._run_rcon(
                *self._forceload_args(zone, "add"),
                "--host",
                self.config.rcon_host,
                "--port",
                str(self.config.rcon_port),
                "--password",
                self.config.rcon_password,
                timeout=60,
            )
            if sender.returncode == 0:
                retried = True
                time.sleep(1.0)
                sender = self._run_rcon(
                    "-f",
                    str(commands_path),
                    "--host",
                    self.config.rcon_host,
                    "--port",
                    str(self.config.rcon_port),
                    "--password",
                    self.config.rcon_password,
                    "--summary-json",
                    str(summary_path),
                    timeout=180,
                )
                summary = self._read_summary(summary_path)

        return sender, summary, retried

    @classmethod
    def _player_teleport_command(cls, zone: Optional[BuildZone]) -> Optional[str]:
        if zone is None:
            return None
        x = zone.origin_x + zone.size_x // 2
        y = zone.y + 1
        z = zone.origin_z - 4
        return f"/tp {cls.player_selector} {x} {y} {z} 0 0"

    @classmethod
    def _prepend_player_teleport(cls, commands_path: Path, zone: Optional[BuildZone]) -> None:
        command = cls._player_teleport_command(zone)
        if not command:
            return
        original = commands_path.read_text(encoding="utf-8")
        commands_path.write_text(command + "\n" + original, encoding="utf-8")

    def _execute_via_generator_rcon(self, task) -> ExecutionResult:
        tmp_dir = Path(self.config.execution_tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        raw_path = tmp_dir / f"{task.task_id}.raw.md"
        commands_path = tmp_dir / f"{task.task_id}.commands.txt"
        summary_path = tmp_dir / f"{task.task_id}.rcon_summary.json"
        prompt = self._build_prompt(task)
        zone = BuildZone.from_assignment_str(getattr(task, "zone_assignment", None))

        gen_result = self.generator.generate(prompt)
        if not gen_result.success:
            return ExecutionResult(
                success=False,
                reason=f"generation_failed ({gen_result.generator_used}): {gen_result.error}",
            )
        raw_path.write_text(gen_result.raw_text, encoding="utf-8")

        extractor = subprocess.run(
            [
                sys.executable,
                str(self._code_dir() / "extract_fawe_commands.py"),
                str(raw_path),
                str(commands_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if extractor.returncode != 0 or not commands_path.exists():
            return ExecutionResult(success=False, reason="command_extraction_failed")

        analysis = self._analyze_commands(commands_path, zone)
        if analysis.command_count == 0 or analysis.placement_count == 0:
            return ExecutionResult(success=False, reason="command_verification_failed:no_place_commands")
        if analysis.outside_zone_commands:
            return ExecutionResult(success=False, reason="command_verification_failed:outside_zone")
        if zone is not None and analysis.build_bbox is not None and analysis.build_bbox.get("min_y", zone.y) > zone.y + 1:
            return ExecutionResult(success=False, reason="command_verification_failed:floating_build")

        self._prepend_player_teleport(commands_path, zone)

        forceload_added = False
        if zone is not None:
            preload = self._run_rcon(
                *self._forceload_args(zone, "add"),
                "--host",
                self.config.rcon_host,
                "--port",
                str(self.config.rcon_port),
                "--password",
                self.config.rcon_password,
                timeout=60,
            )
            if preload.returncode != 0:
                return ExecutionResult(success=False, reason="zone_preload_failed")
            forceload_added = True

        try:
            sender, summary, retried_not_loaded = self._execute_sender_with_retry(
                commands_path=commands_path,
                summary_path=summary_path,
                zone=zone,
            )
        finally:
            if forceload_added:
                self._run_rcon(
                    *self._forceload_args(zone, "remove"),
                    "--host",
                    self.config.rcon_host,
                    "--port",
                    str(self.config.rcon_port),
                    "--password",
                    self.config.rcon_password,
                    timeout=60,
                )

        if not summary_path.exists():
            stderr_hint = (sender.stderr or "").strip()[:200]
            retry_hint = ", retry=after_forceload" if retried_not_loaded else ""
            return ExecutionResult(
                success=False,
                reason=f"rcon_send_failed:no_summary (exit={sender.returncode}{retry_hint}, stderr={stderr_hint})",
            )

        summary = summary or json.loads(summary_path.read_text(encoding="utf-8"))

        if sender.returncode != 0:
            ok = self._evaluate_partial_success(summary)
            if not ok:
                err_count = summary.get("error_count", "?")
                cmd_count = summary.get("command_count", "?")
                first_error = self._summary_first_error(summary) or ""
                retry_hint = ":retry_after_forceload" if retried_not_loaded else ""
                return ExecutionResult(
                    success=False,
                    reason=f"rcon_send_failed{retry_hint}:{err_count}/{cmd_count} errors [{first_error}]",
                )

        changed_blocks = self._changed_blocks_from_summary(summary)
        if changed_blocks <= 0:
            return ExecutionResult(success=False, reason="build_verification_failed:no_block_change")

        manifest_path = build_result_bundle(
            output_root=self._result_output_root(),
            task_id=task.task_id,
            theme=task.theme,
            commands_path=str(commands_path),
            verification={
                "mode": "claude_rcon",
                "verified": True,
                "changed_blocks": changed_blocks,
                "placement_samples": analysis.sampled_placements,
                "build_bbox": analysis.build_bbox,
                "summary_path": str(summary_path),
            },
        )
        return ExecutionResult(success=True, result_ref=manifest_path)
