"""Verify the standalone/core import boundary for mc-foreman.

Boundary contract
-----------------
CORE:
    mc_foreman.artifacts, .bot, .domain, .execution, .handlers,
    .infra, .reply, .repositories, .runtime, .services, .workers

Optional host/platform packages may exist outside this repo. If present, CORE
must not statically import them.

Rules enforced:
1. CORE modules must NOT have top-level imports from optional host modules.
2. Optional host modules may import from CORE.
3. Optional host modules must NOT import from each other.
4. No hardcoded absolute user paths in CORE source.
"""
import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src" / "mc_foreman"

HOST_PREFIXES = (
    "mc_foreman.app.",
    "mc_foreman.app",
    "mc_foreman.platforms.",
    "mc_foreman.platforms",
)

CORE_DIRS = [
    SRC_ROOT / "artifacts",
    SRC_ROOT / "bot",
    SRC_ROOT / "domain",
    SRC_ROOT / "execution",
    SRC_ROOT / "handlers",
    SRC_ROOT / "infra",
    SRC_ROOT / "reply",
    SRC_ROOT / "repositories",
    SRC_ROOT / "runtime",
    SRC_ROOT / "services",
    SRC_ROOT / "workers",
]

HOST_DIRS = [
    SRC_ROOT / "app",
    SRC_ROOT / "platforms",
]

_ABS_USER_PATH_RE = re.compile(r"/Users/\w+/")


def _top_level_imports(filepath: Path) -> list[tuple[int, str]]:
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    results = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                results.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            results.append((node.lineno, node.module))
    return results


def _is_host_module(module: str) -> bool:
    return any(module.startswith(p) or module == p for p in HOST_PREFIXES)


def _host_package_of(filepath: Path) -> str:
    rel = filepath.relative_to(SRC_ROOT)
    parts = rel.parts
    if parts[0] == "platforms" and len(parts) > 1:
        return parts[1].replace(".py", "")
    return parts[0]


def _collect_py_files(dirs):
    result = []
    for d in dirs:
        if d.exists():
            result.extend(sorted(d.rglob("*.py")))
    return [f for f in result if "__pycache__" not in str(f)]


def check_core_no_host_imports():
    violations = []
    files = _collect_py_files(CORE_DIRS)
    for py_file in files:
        for lineno, module in _top_level_imports(py_file):
            if _is_host_module(module):
                rel = py_file.relative_to(SRC_ROOT)
                violations.append(f"  {rel}:{lineno} imports {module}")
    return files, violations


def check_host_no_cross_host_imports():
    violations = []
    files = _collect_py_files(HOST_DIRS)
    for py_file in files:
        own_pkg = _host_package_of(py_file)
        for lineno, module in _top_level_imports(py_file):
            if not _is_host_module(module):
                continue
            if own_pkg == "app" and module.startswith("mc_foreman.app"):
                continue
            if own_pkg != "app" and module.startswith(f"mc_foreman.platforms.{own_pkg}"):
                continue
            rel = py_file.relative_to(SRC_ROOT)
            violations.append(f"  {rel}:{lineno} imports {module} (cross-host)")
    return files, violations


def check_no_hardcoded_user_paths():
    violations = []
    files = _collect_py_files(CORE_DIRS)
    for py_file in files:
        for lineno, line in enumerate(py_file.read_text().splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if _ABS_USER_PATH_RE.search(line):
                rel = py_file.relative_to(SRC_ROOT)
                violations.append(f"  {rel}:{lineno} has hardcoded user path")
    return violations


def main():
    ok = True

    core_files, v1 = check_core_no_host_imports()
    if v1:
        print("FAIL rule 1: CORE modules statically import host modules:\n" + "\n".join(v1))
        ok = False
    else:
        print(f"  rule 1 ok: {len(core_files)} CORE files, 0 host imports")

    host_files, v3 = check_host_no_cross_host_imports()
    if v3:
        print("FAIL rule 3: host cross-package imports:\n" + "\n".join(v3))
        ok = False
    else:
        print(f"  rule 3 ok: {len(host_files)} host files, 0 cross-host imports")

    v4 = check_no_hardcoded_user_paths()
    if v4:
        print("FAIL rule 4: hardcoded user paths in CORE:\n" + "\n".join(v4))
        ok = False
    else:
        print("  rule 4 ok: no hardcoded user paths in CORE")

    if ok:
        total = len(core_files) + len(host_files)
        print(f"\nimport boundary ok ({total} files checked, all rules pass)")
    else:
        print("\nimport boundary FAILED")
        sys.exit(1)


def test_main():
    main()


if __name__ == "__main__":
    main()
