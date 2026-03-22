"""Command generator abstraction with configurable strategy.

Strategies:
- claude: generate via Claude CLI subprocess
- codex: generate via Codex CLI subprocess
- gemini: generate via Gemini CLI subprocess
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GenerationResult:
    success: bool
    raw_text: str = ""
    generator_used: str = ""
    error: str = ""


class CommandGenerator(ABC):
    """Base class for Minecraft command generators."""

    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str) -> GenerationResult:
        ...


class ClaudeGenerator(CommandGenerator):
    """Generate commands via Claude CLI subprocess."""

    name = "claude"

    def __init__(self, claude_bin: str = "claude", timeout: int = 180):
        self.claude_bin = claude_bin
        self.timeout = timeout

    def generate(self, prompt: str) -> GenerationResult:
        try:
            # bypassPermissions is safe here: --print only produces text output
            # without executing any file/network operations on the host.
            proc = subprocess.run(
                [self.claude_bin, "--print", "--permission-mode", "bypassPermissions", prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return GenerationResult(
                    success=False,
                    generator_used=self.name,
                    error=f"claude exited {proc.returncode}",
                )
            return GenerationResult(
                success=True,
                raw_text=proc.stdout,
                generator_used=self.name,
            )
        except subprocess.TimeoutExpired:
            return GenerationResult(
                success=False,
                generator_used=self.name,
                error=f"claude timed out after {self.timeout}s",
            )
        except FileNotFoundError:
            return GenerationResult(
                success=False,
                generator_used=self.name,
                error="claude binary not found",
            )


class CodexGenerator(CommandGenerator):
    """Generate commands via local Codex CLI subprocess."""

    name = "codex"

    def __init__(
        self,
        codex_bin: str = "codex",
        timeout: int = 180,
        model: str = "",
        cwd: Optional[Path] = None,
    ):
        self.codex_bin = codex_bin
        self.timeout = timeout
        self.model = model.strip()
        self.cwd = str(cwd) if cwd else None

    def generate(self, prompt: str) -> GenerationResult:
        args = [
            self.codex_bin,
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
        ]
        if self.model:
            args.extend(["--model", self.model])
        args.append(prompt)

        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                stderr = proc.stderr.strip()
                detail = f": {stderr}" if stderr else ""
                return GenerationResult(
                    success=False,
                    generator_used=self.name,
                    error=f"codex exited {proc.returncode}{detail}",
                )
            return GenerationResult(
                success=True,
                raw_text=proc.stdout,
                generator_used=self.name,
            )
        except subprocess.TimeoutExpired:
            return GenerationResult(
                success=False,
                generator_used=self.name,
                error=f"codex timed out after {self.timeout}s",
            )
        except FileNotFoundError:
            return GenerationResult(
                success=False,
                generator_used=self.name,
                error="codex binary not found",
            )


class GeminiGenerator(CommandGenerator):
    """Generate commands via Gemini CLI subprocess."""

    name = "gemini"

    def __init__(self, gemini_bin: str = "gemini", timeout: int = 180):
        self.gemini_bin = gemini_bin
        self.timeout = timeout

    def generate(self, prompt: str) -> GenerationResult:
        try:
            proc = subprocess.run(
                [self.gemini_bin, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return GenerationResult(
                    success=False,
                    generator_used=self.name,
                    error=f"gemini exited {proc.returncode}",
                )
            return GenerationResult(
                success=True,
                raw_text=proc.stdout,
                generator_used=self.name,
            )
        except subprocess.TimeoutExpired:
            return GenerationResult(
                success=False,
                generator_used=self.name,
                error=f"gemini timed out after {self.timeout}s",
            )
        except FileNotFoundError:
            return GenerationResult(
                success=False,
                generator_used=self.name,
                error="gemini binary not found",
            )


def build_generator(config) -> CommandGenerator:
    """Factory: build a CommandGenerator from config.

    config.command_generator_strategy:
    - "claude"
    - "codex"
    - "gemini"
    """
    strategy = getattr(config, "command_generator_strategy", "claude")
    timeout = getattr(config, "command_generation_timeout", 180)

    if strategy == "claude":
        return ClaudeGenerator(
            claude_bin=getattr(config, "claude_bin", "claude"),
            timeout=timeout,
        )
    if strategy == "codex":
        return CodexGenerator(
            codex_bin=getattr(config, "codex_bin", "codex"),
            timeout=timeout,
            model=getattr(config, "codex_model", ""),
            cwd=getattr(config, "project_root", None),
        )
    if strategy == "gemini":
        return GeminiGenerator(
            gemini_bin=getattr(config, "gemini_bin", "gemini"),
            timeout=timeout,
        )
    raise ValueError(f"unknown generator strategy: {strategy}")
