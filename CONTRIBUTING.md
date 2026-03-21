# Contributing to mc-foreman

## Principles

- Keep the repository standalone.
- Keep CORE free of host-specific integrations.
- Avoid coupling to chat adapters, external platform integrations, or other host-only features.
- Prefer small, testable changes.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Before opening a PR

Run:

```bash
uv run python tests/test_import_boundary.py
uv run pytest -q
uv run mc-foreman build "测试亭" --mode mock
```

## Scope rules

Allowed in CORE:
- workflow logic
- task/queue/worker logic
- command generation abstraction
- RCON execution
- result bundle / verification

Not allowed in CORE:
- chat/channel adapters
- external delivery integrations
- host-only runtime glue

## Style

- Keep dependencies light.
- Preserve CLI usability.
- If a new integration is host-specific, place it outside this core repo.
