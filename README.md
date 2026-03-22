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
  - a Minecraft server with RCON enabled
  - at least one LLM CLI on PATH: `claude`, `codex`, or `gemini`

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
uv run mc-foreman build "小石亭" --mode live
```

Before sending build commands, the runtime first teleports the player to the front of the assigned build zone so the player starts from a predictable viewing position.

For a successful real build you should expect:
- task submission succeeds
- LLM generates commands
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

## Generator 选择

Use `--generator` to choose which LLM CLI generates the Minecraft commands:

| `--generator` | CLI tool | Invocation |
|---|---|---|
| `claude` (default) | `claude` | `claude --print --permission-mode bypassPermissions "<prompt>"` |
| `codex` | `codex` | `codex exec --sandbox read-only --skip-git-repo-check "<prompt>"` |
| `gemini` | `gemini` | `gemini -p "<prompt>"` |

Examples:

```bash
# Use Claude (default)
uv run mc-foreman build "小石亭" --mode live

# Use Gemini
uv run mc-foreman build "小石亭" --mode live --generator gemini

# Use Codex
uv run mc-foreman build "小石亭" --mode live --generator codex
```

You can also override the binary path:

```bash
uv run mc-foreman build "小石亭" --mode live --generator claude --claude-bin /usr/local/bin/claude
uv run mc-foreman build "小石亭" --mode live --generator gemini --gemini-bin /usr/local/bin/gemini
```

## World type configuration

mc-foreman adjusts the building base Y-level according to your Minecraft world type.
Use `--world-type` to match your server's world:

| `--world-type` | Base Y | Suitable for |
|---|---|---|
| `superflat` (default) | -59 | Default superflat world |
| `normal` | 64 | Standard terrain (plains, ocean) |

Examples:

```bash
# Default: superflat world (Y=-59)
uv run mc-foreman build "喷泉" --mode live

# Normal world
uv run mc-foreman build "喷泉" --mode live --world-type normal
```

> **Note:** For normal worlds with hilly/mountainous terrain, Y=64 may still
> be below the local surface. A future version may add runtime terrain detection.

## Environment notes

Primary runtime env var:
- `MC_FOREMAN_EXECUTION_MODE`

Current execution modes:
- `mock`
- `live`

This core runtime does not include screenshot capture.

## Development notes

This project is intentionally stdlib-heavy and low-dependency.

When contributing:
- keep CORE free of host/runtime-specific imports
- do not reintroduce external channel/platform dependencies into core
- prefer simple Python CLI flows over framework-heavy runtime coupling

## License

MIT
