"""Tests for command generator selection, fallback, and bridge prompt hardening."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from mc_foreman.execution.generator import (
    ClaudeGenerator,
    CodexGenerator,
    CommandGenerator,
    FallbackGenerator,
    GenerationResult,
    build_generator,
)
from mc_foreman.execution.bridge import ExecutionBridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class StubGenerator(CommandGenerator):
    """Deterministic generator for testing."""

    def __init__(self, name: str, succeed: bool = True, text: str = "ok", error: str = "stub_fail"):
        self.name = name
        self._succeed = succeed
        self._text = text
        self._error = error
        self.call_count = 0
        self.last_prompt = None

    def generate(self, prompt: str) -> GenerationResult:
        self.call_count += 1
        self.last_prompt = prompt
        if self._succeed:
            return GenerationResult(success=True, raw_text=self._text, generator_used=self.name)
        return GenerationResult(success=False, generator_used=self.name, error=self._error)


@dataclass
class _MinimalTask:
    task_id: str = "t1"
    theme: str = "凉亭"
    size: str = "small"
    zone_assignment: str = "zone_0"


# ---------------------------------------------------------------------------
# 1. Generator selection via build_generator
# ---------------------------------------------------------------------------

def test_build_generator_claude():
    cfg = SimpleNamespace(command_generator_strategy="claude", claude_bin="claude", command_generation_timeout=60)
    gen = build_generator(cfg)
    assert isinstance(gen, ClaudeGenerator)
    print("  build_generator claude ok")


def test_build_generator_codex():
    cfg = SimpleNamespace(
        command_generator_strategy="codex",
        claude_bin="claude",
        codex_bin="codex",
        codex_model="",
        command_generation_timeout=60,
        project_root="/tmp",
    )
    gen = build_generator(cfg)
    assert isinstance(gen, CodexGenerator)
    print("  build_generator codex ok")


def test_build_generator_fallback():
    cfg = SimpleNamespace(
        command_generator_strategy="claude_then_codex",
        claude_bin="claude",
        codex_bin="codex",
        codex_model="",
        command_generation_timeout=60,
        project_root="/tmp",
    )
    gen = build_generator(cfg)
    assert isinstance(gen, FallbackGenerator)
    assert isinstance(gen.primary, ClaudeGenerator)
    assert isinstance(gen.secondary, CodexGenerator)
    print("  build_generator claude_then_codex ok")


def test_build_generator_legacy_aliases_map_to_codex():
    direct = build_generator(
        SimpleNamespace(
            command_generator_strategy="chatgpt",
            claude_bin="claude",
            codex_bin="codex",
            codex_model="",
            command_generation_timeout=60,
            project_root="/tmp",
        )
    )
    fallback = build_generator(
        SimpleNamespace(
            command_generator_strategy="claude_then_chatgpt",
            claude_bin="claude",
            codex_bin="codex",
            codex_model="",
            command_generation_timeout=60,
            project_root="/tmp",
        )
    )
    assert isinstance(direct, CodexGenerator)
    assert isinstance(fallback, FallbackGenerator)
    assert isinstance(fallback.secondary, CodexGenerator)
    print("  build_generator legacy aliases ok")


def test_build_generator_invalid():
    cfg = SimpleNamespace(command_generator_strategy="unknown")
    try:
        build_generator(cfg)
        assert False, "should have raised"
    except ValueError as e:
        assert "unknown" in str(e)
    print("  build_generator invalid strategy ok")


# ---------------------------------------------------------------------------
# 2. Fallback behaviour
# ---------------------------------------------------------------------------

def test_fallback_uses_primary_when_ok():
    primary = StubGenerator("p", succeed=True, text="primary_output")
    secondary = StubGenerator("s", succeed=True, text="secondary_output")
    fb = FallbackGenerator(primary, secondary)
    result = fb.generate("test")
    assert result.success
    assert result.raw_text == "primary_output"
    assert result.generator_used == "p"
    assert primary.call_count == 1
    assert secondary.call_count == 0
    print("  fallback primary ok")


def test_fallback_uses_secondary_on_failure():
    primary = StubGenerator("claude", succeed=False, error="claude timed out after 60s")
    secondary = StubGenerator("codex", succeed=True, text="fallback_output")
    fb = FallbackGenerator(primary, secondary)
    result = fb.generate("test")
    assert result.success
    assert result.raw_text == "fallback_output"
    assert result.generator_used == "codex"
    assert primary.call_count == 1
    assert secondary.call_count == 1
    assert "primary (claude) failed: claude timed out" in result.error
    print("  fallback secondary ok")


def test_fallback_both_fail():
    primary = StubGenerator("claude", succeed=False, error="claude timed out")
    secondary = StubGenerator("codex", succeed=False, error="codex exited 1")
    fb = FallbackGenerator(primary, secondary)
    result = fb.generate("test")
    assert not result.success
    assert result.generator_used == "codex"
    assert result.error == "codex exited 1"
    assert primary.call_count == 1
    assert secondary.call_count == 1
    print("  fallback both fail ok")


# ---------------------------------------------------------------------------
# 3. Bridge prompt hardening
# ---------------------------------------------------------------------------

def test_bridge_theme_detection():
    assert ExecutionBridge._is_bridge_theme("桥")
    assert ExecutionBridge._is_bridge_theme("江南拱桥")
    assert ExecutionBridge._is_bridge_theme("拱桥")
    assert ExecutionBridge._is_bridge_theme("stone bridge")
    assert ExecutionBridge._is_bridge_theme("Bridge")
    assert not ExecutionBridge._is_bridge_theme("凉亭")
    assert not ExecutionBridge._is_bridge_theme("花园")
    print("  bridge theme detection ok")


def test_bridge_prompt_is_constrained():
    cfg = SimpleNamespace(execution_mode="mock", execution_tmp_dir="/tmp/test")
    bridge = ExecutionBridge(cfg)
    task = _MinimalTask(theme="江南拱桥")
    prompt = bridge._build_prompt(task)
    assert "≤ 15" in prompt
    assert "仅使用 /fill" in prompt
    assert "不做栏杆细节" in prompt
    assert "stone_bricks" in prompt
    print("  bridge prompt constrained ok")


def test_general_prompt_for_non_bridge():
    cfg = SimpleNamespace(execution_mode="mock", execution_tmp_dir="/tmp/test")
    bridge = ExecutionBridge(cfg)
    task = _MinimalTask(theme="凉亭")
    prompt = bridge._build_prompt(task)
    assert "≤ 15" not in prompt
    assert "小型" in prompt
    print("  general prompt for non-bridge ok")


def test_bridge_prompt_smaller_than_general():
    cfg = SimpleNamespace(execution_mode="mock", execution_tmp_dir="/tmp/test")
    bridge = ExecutionBridge(cfg)
    bridge_prompt = bridge._build_prompt(_MinimalTask(theme="拱桥"))
    general_prompt = bridge._build_prompt(_MinimalTask(theme="凉亭"))
    assert "≤ 15" in bridge_prompt
    assert "≤ 15" not in general_prompt
    print("  bridge prompt vs general ok")


# ---------------------------------------------------------------------------
# 4. Bridge uses injected generator / prompt path
# ---------------------------------------------------------------------------

def test_bridge_uses_injected_generator():
    cfg = SimpleNamespace(execution_mode="mock", execution_tmp_dir="/tmp/test")
    stub = StubGenerator("test_gen", succeed=True, text="commands here")
    bridge = ExecutionBridge(cfg, generator=stub)
    assert bridge.generator is stub
    print("  bridge accepts injected generator ok")


def test_bridge_prompt_reaches_fallback_generator_for_bridge_theme():
    cfg = SimpleNamespace(execution_mode="mock", execution_tmp_dir="/tmp/test")
    primary = StubGenerator("claude", succeed=False, error="claude timed out after 30s")
    secondary = StubGenerator("codex", succeed=True, text="```mcfunction\n/fill 1 2 3 4 5 6 stone_bricks\n```")
    bridge = ExecutionBridge(cfg, generator=FallbackGenerator(primary, secondary))
    task = _MinimalTask(theme="江南拱桥")

    prompt = bridge._build_prompt(task)
    result = bridge.generator.generate(prompt)

    assert result.success
    assert result.generator_used == "codex"
    assert primary.call_count == 1
    assert secondary.call_count == 1
    assert secondary.last_prompt is not None
    assert "仅使用 /fill" in secondary.last_prompt
    assert "stone_bricks" in secondary.last_prompt
    assert "跨度 ≤ 20 格" in secondary.last_prompt
    print("  bridge prompt reaches codex fallback ok")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    test_build_generator_claude()
    test_build_generator_codex()
    test_build_generator_fallback()
    test_build_generator_legacy_aliases_map_to_codex()
    test_build_generator_invalid()
    test_fallback_uses_primary_when_ok()
    test_fallback_uses_secondary_on_failure()
    test_fallback_both_fail()
    test_bridge_theme_detection()
    test_bridge_prompt_is_constrained()
    test_general_prompt_for_non_bridge()
    test_bridge_prompt_smaller_than_general()
    test_bridge_uses_injected_generator()
    test_bridge_prompt_reaches_fallback_generator_for_bridge_theme()
    print("\ngenerator tests passed ✅")


if __name__ == "__main__":
    main()
