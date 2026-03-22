"""Tests for command generator selection and bridge prompt hardening."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from mc_foreman.execution.generator import (
    ClaudeGenerator,
    CodexGenerator,
    CommandGenerator,
    GeminiGenerator,
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


def test_build_generator_gemini():
    cfg = SimpleNamespace(
        command_generator_strategy="gemini",
        gemini_bin="gemini",
        command_generation_timeout=60,
    )
    gen = build_generator(cfg)
    assert isinstance(gen, GeminiGenerator)
    print("  build_generator gemini ok")


def test_build_generator_invalid():
    cfg = SimpleNamespace(command_generator_strategy="unknown")
    try:
        build_generator(cfg)
        assert False, "should have raised"
    except ValueError as e:
        assert "unknown" in str(e)
    print("  build_generator invalid strategy ok")


# ---------------------------------------------------------------------------
# 2. Bridge prompt hardening
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
# 3. Bridge uses injected generator / prompt path
# ---------------------------------------------------------------------------

def test_bridge_uses_injected_generator():
    cfg = SimpleNamespace(execution_mode="mock", execution_tmp_dir="/tmp/test")
    stub = StubGenerator("test_gen", succeed=True, text="commands here")
    bridge = ExecutionBridge(cfg, generator=stub)
    assert bridge.generator is stub
    print("  bridge accepts injected generator ok")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    test_build_generator_claude()
    test_build_generator_codex()
    test_build_generator_gemini()
    test_build_generator_invalid()
    test_bridge_theme_detection()
    test_bridge_prompt_is_constrained()
    test_general_prompt_for_non_bridge()
    test_bridge_prompt_smaller_than_general()
    test_bridge_uses_injected_generator()
    print("\ngenerator tests passed ✅")


if __name__ == "__main__":
    main()
