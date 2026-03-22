"""Focused tests for real-placement verification hardening."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.execution.generator import CommandGenerator, GenerationResult


class StubGenerator(CommandGenerator):
    def __init__(self, text: str):
        self.text = text

    def generate(self, prompt: str) -> GenerationResult:
        return GenerationResult(success=True, raw_text=self.text, generator_used="stub")


class StubScreenshots:
    def capture_views(self, task_id, output_dir, zone=None, build_bbox=None):
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(3):
            p = output_dir / f"shot-{i}.png"
            p.write_text("x", encoding="utf-8")
            paths.append(str(p))
        return paths


def _task(zone_assignment="zone:0@100,64,200/64x64"):
    return SimpleNamespace(task_id="t1", theme="小石桥", size="small", zone_assignment=zone_assignment)


def _config(tmp_dir: Path):
    project_root = Path(__file__).resolve().parents[1]
    return SimpleNamespace(
        execution_mode="live",
        execution_tmp_dir=tmp_dir,
        project_root=project_root,
        rcon_host="127.0.0.1",
        rcon_port=25575,
        rcon_password="pw",
    )


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_changed_blocks_parser_handles_real_rcon_fill_and_setblock_responses():
    summary = {
        "success": True,
        "changed_blocks": 0,
        "results": [
            {"response": "No blocks were filled", "changed_blocks": 0},
            {"response": "Successfully filled 121 block(s)", "changed_blocks": 0},
            {"response": "Changed the block at 1475, 73, 231", "changed_blocks": 0},
        ],
    }

    assert ExecutionBridge._changed_blocks_from_summary(summary) == 122
    print("  bridge recomputes changed blocks from real rcon responses ok")


def test_bridge_rejects_commands_outside_zone():
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        bridge = ExecutionBridge(_config(tmp_dir), generator=StubGenerator("""```mcfunction\n/fill 10 64 10 12 64 12 stone\n```"""))
        result = bridge.execute(_task())
        assert not result.success
        assert result.reason == "command_verification_failed:outside_zone"
        print("  bridge rejects outside-zone commands ok")


def test_bridge_requires_real_block_change_before_success():
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        bridge = ExecutionBridge(_config(tmp_dir), generator=StubGenerator("""```mcfunction\n/fill 100 64 200 102 64 202 stone\n```"""))
        summary_path = tmp_dir / "t1.rcon_summary.json"

        def fake_run(cmd, capture_output=True, text=True, timeout=60):
            args = list(cmd)
            if str(args[1]).endswith("extract_fawe_commands.py"):
                raw = Path(args[2]).read_text(encoding="utf-8")
                Path(args[3]).write_text("/fill 100 64 200 102 64 202 stone\n", encoding="utf-8")
                return _Proc(0, raw, "")
            if str(args[1]).endswith("rcon_send.py"):
                if "--summary-json" in args:
                    idx = args.index("--summary-json")
                    Path(args[idx + 1]).write_text(json.dumps({"success": True, "changed_blocks": 0}), encoding="utf-8")
                return _Proc(0, "ok", "")
            raise AssertionError(args)

        with patch("mc_foreman.execution.bridge.subprocess.run", side_effect=fake_run):
            result = bridge.execute(_task())

        assert not result.success
        assert result.reason == "build_verification_failed:no_block_change"
        print("  bridge requires changed blocks ok")


def test_bridge_accepts_zeroed_top_level_summary_when_results_show_real_changes():
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        bridge = ExecutionBridge(_config(tmp_dir), generator=StubGenerator("""```mcfunction\n/fill 100 64 200 102 64 202 stone_bricks\n```"""))

        def fake_run(cmd, capture_output=True, text=True, timeout=60):
            args = list(cmd)
            if str(args[1]).endswith("extract_fawe_commands.py"):
                Path(args[3]).write_text("/fill 100 64 200 102 64 202 stone_bricks\n", encoding="utf-8")
                return _Proc(0, "extract ok", "")
            if str(args[1]).endswith("rcon_send.py"):
                if "--summary-json" in args:
                    idx = args.index("--summary-json")
                    Path(args[idx + 1]).write_text(
                        json.dumps(
                            {
                                "success": True,
                                "changed_blocks": 0,
                                "results": [
                                    {
                                        "response": "Successfully filled 27 block(s)",
                                        "changed_blocks": 0,
                                    }
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )
                return _Proc(0, "ok", "")
            raise AssertionError(args)

        with patch("mc_foreman.execution.bridge.subprocess.run", side_effect=fake_run):
            result = bridge.execute(_task())

        assert result.success
        manifest = json.loads(Path(result.result_ref).read_text(encoding="utf-8"))
        assert manifest["verification"]["changed_blocks"] == 27
        print("  bridge accepts recomputed changed blocks from per-command results ok")


def test_bridge_success_manifest_records_verification_details():
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        bridge = ExecutionBridge(_config(tmp_dir), generator=StubGenerator("""```mcfunction\n/fill 100 64 200 102 64 202 stone_bricks\n```"""))

        def fake_run(cmd, capture_output=True, text=True, timeout=60):
            args = list(cmd)
            if str(args[1]).endswith("extract_fawe_commands.py"):
                Path(args[3]).write_text("/fill 100 64 200 102 64 202 stone_bricks\n", encoding="utf-8")
                return _Proc(0, "extract ok", "")
            if str(args[1]).endswith("rcon_send.py"):
                if "--summary-json" in args:
                    idx = args.index("--summary-json")
                    Path(args[idx + 1]).write_text(json.dumps({"success": True, "changed_blocks": 27}), encoding="utf-8")
                return _Proc(0, "ok", "")
            raise AssertionError(args)

        with patch("mc_foreman.execution.bridge.subprocess.run", side_effect=fake_run):
            result = bridge.execute(_task())

        assert result.success
        manifest = json.loads(Path(result.result_ref).read_text(encoding="utf-8"))
        assert manifest["verification"]["verified"] is True
        assert manifest["verification"]["changed_blocks"] == 27
        assert manifest["verification"]["placement_samples"][0]["block"] == "stone_bricks"
        print("  bridge success manifest includes verification ok")


def test_player_is_teleported_to_front_of_zone_before_build_commands():
    task = _task()
    from mc_foreman.execution.zone_allocator import BuildZone as _BuildZone

    zone = _BuildZone.from_assignment_str(task.zone_assignment)
    command = ExecutionBridge._player_teleport_command(zone)
    assert command == "/tp @p 132 65 196 0 0"
    print("  bridge computes pre-build player teleport ok")



def test_bridge_prepends_player_teleport_before_rcon_send():
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        bridge = ExecutionBridge(_config(tmp_dir), generator=StubGenerator("""```mcfunction\n/fill 100 64 200 102 64 202 stone\n```"""))
        seen = {"commands": None}

        def fake_run(cmd, capture_output=True, text=True, timeout=60):
            args = list(cmd)
            if str(args[1]).endswith("extract_fawe_commands.py"):
                Path(args[3]).write_text("/fill 100 64 200 102 64 202 stone\n", encoding="utf-8")
                return _Proc(0, "extract ok", "")
            if str(args[1]).endswith("rcon_send.py"):
                if args[2] == "forceload add 100 200 163 263":
                    return _Proc(0, "forceload ok", "")
                if args[2] == "forceload remove 100 200 163 263":
                    return _Proc(0, "forceload remove ok", "")
                if "-f" in args:
                    seen["commands"] = Path(args[args.index("-f") + 1]).read_text(encoding="utf-8")
                if "--summary-json" in args:
                    idx = args.index("--summary-json")
                    Path(args[idx + 1]).write_text(json.dumps({"success": True, "changed_blocks": 27}), encoding="utf-8")
                return _Proc(0, "ok", "")
            raise AssertionError(args)

        with patch("mc_foreman.execution.bridge.subprocess.run", side_effect=fake_run):
            result = bridge.execute(_task())

        assert result.success
        assert seen["commands"] is not None
        assert seen["commands"].splitlines()[0] == "/tp @p 132 65 196 0 0"
        print("  bridge prepends pre-build player teleport to command file ok")



def test_bridge_retries_once_when_all_commands_fail_with_not_loaded():
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        bridge = ExecutionBridge(_config(tmp_dir), generator=StubGenerator("""```mcfunction\n/fill 100 64 200 102 64 202 stone\n```"""))
        calls = {"send": 0}

        def fake_run(cmd, capture_output=True, text=True, timeout=60):
            args = list(cmd)
            if str(args[1]).endswith("extract_fawe_commands.py"):
                Path(args[3]).write_text("/fill 100 64 200 102 64 202 stone\n", encoding="utf-8")
                return _Proc(0, "extract ok", "")
            if str(args[1]).endswith("rcon_send.py"):
                if args[2] == "forceload add 100 200 163 263":
                    return _Proc(0, "forceload ok", "")
                if args[2] == "forceload remove 100 200 163 263":
                    return _Proc(0, "forceload remove ok", "")
                if "--summary-json" in args:
                    idx = args.index("--summary-json")
                    calls["send"] += 1
                    if calls["send"] == 1:
                        Path(args[idx + 1]).write_text(json.dumps({
                            "success": False,
                            "command_count": 1,
                            "error_count": 1,
                            "results": [{"ok": False, "response": "That position is not loaded", "error": "That position is not loaded"}],
                        }), encoding="utf-8")
                        return _Proc(1, "", "")
                    Path(args[idx + 1]).write_text(json.dumps({
                        "success": True,
                        "changed_blocks": 27,
                        "command_count": 1,
                        "error_count": 0,
                        "results": [{"ok": True, "response": "Successfully filled 27 block(s)", "changed_blocks": 27}],
                    }), encoding="utf-8")
                    return _Proc(0, "ok", "")
            raise AssertionError(args)

        with patch("mc_foreman.execution.bridge.subprocess.run", side_effect=fake_run):
            result = bridge.execute(_task())

        assert result.success
        assert calls["send"] == 2
        print("  bridge retries once after not-loaded summary ok")


if __name__ == "__main__":
    test_changed_blocks_parser_handles_real_rcon_fill_and_setblock_responses()
    test_bridge_rejects_commands_outside_zone()
    test_bridge_requires_real_block_change_before_success()
    test_bridge_accepts_zeroed_top_level_summary_when_results_show_real_changes()
    test_bridge_success_manifest_records_verification_details()
    test_bridge_retries_once_when_all_commands_fail_with_not_loaded()
    print("real build verification tests passed")
