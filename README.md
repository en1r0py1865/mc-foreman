# mc-foreman

A standalone Minecraft building workflow engine.

`mc-foreman` takes a build request, uses an LLM to generate Minecraft commands, executes them through RCON, and produces structured results for verification.

## What this repo is

This repository is the standalone core build pipeline.

Included here:
- workflow / task / queue / worker
- command generation
- RCON execution
- result bundle / verification
- CLI entrypoint

Not included here:
- chat/channel delivery adapters
- external platform integrations
- host/runtime-specific glue

## Requirements

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/)
- Optional for real builds:
  - `claude` CLI on PATH
  - a Minecraft server with RCON enabled

## Quick start

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Mock build

```bash
uv run mc-foreman build "测试亭" --mode mock
```

Expected outcome:
- task is submitted
- task reaches `completed`
- output clearly says it is a mock execution
- no real Minecraft world change is required

## Check task status

```bash
uv run mc-foreman status <task_id>
```

## Run tests

```bash
uv run pytest -q
uv run python tests/test_import_boundary.py
```

Run the repo-local tests to verify the current baseline in your environment.

## Real build path

Set your RCON password first:

```bash
export MC_RCON_PASSWORD="your-rcon-password"
```

Then verify prerequisites:

```bash
uv run claude --print "hello"
uv run python src/mc_foreman/code/rcon_send.py --host 127.0.0.1 --port 25575 "list"
```

Then run a real build:

```bash
uv run mc-foreman build "小石亭" --mode claude_rcon
```

Before sending build commands, the runtime first teleports the player to the front of the assigned build zone so the player starts from a predictable viewing position.

For a successful real build you should expect:
- task submission succeeds
- Claude generates commands
- RCON execution succeeds
- task ends in `completed`
- verification/result bundle is written

## Repository layout

```text
src/mc_foreman/
  artifacts/      result bundles
  bot/            command entry and routing
  domain/         models and errors
  execution/      command generation + execution bridge
  handlers/       build/status/help/etc.
  infra/          sqlite setup
  reply/          reply formatting
  repositories/   task/queue/event repos
  runtime/        bootstrap + gateway + notifier
  services/       task lifecycle
  workers/        queue worker
  code/           utility scripts such as rcon_send.py

tests/            repo-local tests
```

## Environment notes

Primary runtime env var:
- `MC_FOREMAN_EXECUTION_MODE`

Current execution modes:
- `mock`
- `claude_rcon`

This core runtime does not include screenshot capture.

## Development notes

This project is intentionally stdlib-heavy and low-dependency.

When contributing:
- keep CORE free of host/runtime-specific imports
- do not reintroduce external channel/platform dependencies into core
- prefer simple Python CLI flows over framework-heavy runtime coupling

## License

MIT
