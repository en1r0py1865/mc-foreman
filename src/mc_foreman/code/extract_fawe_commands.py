#!/usr/bin/env python3
"""
extract_fawe_commands.py — 从 LLM 输出中提取 FAWE/Minecraft 命令。

链路：LLM 输出 → 本脚本提取 → 保存 txt → rcon_send.py 发送。

用法：
  python extract_fawe_commands.py input.md output.txt
"""

import re
import sys


COMMAND_PREFIXES = ("//", "/fill ", "/fill\t", "/setblock ", "/setblock\t")


def is_command(line: str) -> bool:
    stripped = line.strip()
    return any(stripped.startswith(p) for p in COMMAND_PREFIXES)


def extract_from_codeblocks(text: str) -> list[str]:
    """从 Markdown 代码块中提取命令。只保留含命令的代码块。"""
    blocks = re.findall(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    if not blocks:
        return []

    result = []
    for block in blocks:
        lines = block.strip().splitlines()
        if not any(is_command(l) for l in lines):
            continue
        for line in lines:
            stripped = line.strip()
            if is_command(stripped) or stripped.startswith("#"):
                result.append(stripped)
    return result


def extract_by_line_scan(text: str) -> list[str]:
    """回退：逐行扫描，只提取命令行。"""
    return [line.strip() for line in text.splitlines() if is_command(line)]


def extract(text: str) -> list[str]:
    """主提取：先尝试代码块，回退到逐行扫描。"""
    result = extract_from_codeblocks(text)
    if any(is_command(line) for line in result):
        return result
    return extract_by_line_scan(text)


def main():
    if len(sys.argv) != 3:
        print("用法: python extract_fawe_commands.py <input.md> <output.txt>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        text = f.read()

    lines = extract(text)
    cmd_count = sum(1 for l in lines if is_command(l))

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"提取: {cmd_count} 条命令, {len(lines)} 行总计 → {sys.argv[2]}")

    if cmd_count == 0:
        print("⚠ 未提取到任何命令")
        sys.exit(1)


if __name__ == "__main__":
    main()
