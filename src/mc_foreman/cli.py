"""mc-foreman CLI — run builds from the command line.

Usage:
    mc-foreman build "小石亭" --rcon-host 127.0.0.1 --rcon-port 25575
    mc-foreman build "石桥" --mode mock
    mc-foreman status <task-id>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def _build_config(args):
    """Construct a config object from CLI args."""

    class CLIConfig:
        execution_mode = args.mode
        execution_tmp_dir = Path(args.data_dir) / "execution"
        project_root = Path(args.project_root)
        rcon_host = args.rcon_host
        rcon_port = args.rcon_port
        rcon_password = args.rcon_password
        claude_bin = args.claude_bin
        command_generator_strategy = args.generator
        command_generation_timeout = args.timeout
        world_type = args.world_type

    CLIConfig.execution_tmp_dir.mkdir(parents=True, exist_ok=True)
    return CLIConfig()


def cmd_build(args):
    from mc_foreman.runtime.bootstrap import bootstrap_worker

    if args.mode != "mock" and not args.rcon_password:
        print("ERROR: --rcon-password or MC_RCON_PASSWORD is required for non-mock builds")
        return 1

    config = _build_config(args)
    db_path = Path(args.data_dir) / "mc_foreman.sqlite3"

    delivered = []

    def on_delivery(d):
        delivered.append(d)
        print(d.reply_text)

    from mc_foreman.runtime.completion_notifier import CompletionNotifier
    notifier = CompletionNotifier(deliver_fn=on_delivery)

    worker, task_service = bootstrap_worker(
        db_path=db_path,
        completion_notifier=notifier,
        config=config,
    )

    task = task_service.submit_task(
        theme=args.theme,
        submitter_id=args.user or "cli",
        size=args.size,
    )
    print(f"Task submitted: {task.task_id} (theme={args.theme}, mode={config.execution_mode})")

    completed = worker.tick()
    if completed is None:
        print("ERROR: worker returned None")
        return 1

    print(f"Result: {completed.state}")
    if completed.result_ref:
        bundle = json.loads(Path(completed.result_ref).read_text())
        v = bundle.get("verification", {})
        print(f"  mode={v.get('mode')}  verified={v.get('verified')}  blocks={v.get('changed_blocks', 'n/a')}")

    return 0 if completed.state == "completed" else 1


def cmd_status(args):
    from mc_foreman.runtime.bootstrap import bootstrap_worker

    db_path = Path(args.data_dir) / "mc_foreman.sqlite3"
    _, task_service = bootstrap_worker(db_path=db_path)
    task = task_service.get_task(args.task_id)
    if task is None:
        print(f"Task not found: {args.task_id}")
        return 1
    print(f"Task {task.task_id}: state={task.state} theme={task.theme}")
    return 0


def _add_common_args(parser):
    """Add arguments shared by all subcommands."""
    parser.add_argument("--data-dir", default="./data", help="Data/DB directory")
    parser.add_argument("--project-root", default=".", help="Project root for code/ scripts")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mc-foreman",
        description="Minecraft building workflow engine",
    )
    # Accept common args at top level too, for flexibility
    _add_common_args(parser)

    sub = parser.add_subparsers(dest="command")

    build_p = sub.add_parser("build", help="Submit and execute a build")
    _add_common_args(build_p)
    build_p.add_argument("theme", help="Build theme (e.g. '小石亭')")
    build_p.add_argument("--mode", default="claude_rcon", choices=["mock", "claude_rcon"])
    build_p.add_argument("--size", default="small", choices=["small", "medium"])
    build_p.add_argument("--user", default="cli")
    build_p.add_argument("--rcon-host", default="127.0.0.1")
    build_p.add_argument("--rcon-port", type=int, default=25575)
    build_p.add_argument("--rcon-password", default=os.environ.get("MC_RCON_PASSWORD"))
    build_p.add_argument("--claude-bin", default="claude")
    build_p.add_argument("--generator", default="claude")
    build_p.add_argument("--timeout", type=int, default=180)
    build_p.add_argument("--world-type", default="superflat", choices=["superflat", "normal"],
                         help="Minecraft world type (affects build base Y-level)")

    status_p = sub.add_parser("status", help="Check task status")
    _add_common_args(status_p)
    status_p.add_argument("task_id", help="Task ID to check")

    args = parser.parse_args(argv)
    if args.command == "build":
        sys.exit(cmd_build(args))
    elif args.command == "status":
        sys.exit(cmd_status(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
