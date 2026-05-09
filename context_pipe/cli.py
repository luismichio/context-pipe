# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
context_pipe/cli.py — mcp-pipe CLI

A lightweight terminal runner for the Context-Pipe ecosystem.
Executes pipes, lists capabilities, and reports ROI — all without
requiring an IDE or MCP client.

Entry point: ``mcp-pipe`` (registered in pyproject.toml)

Subcommands
-----------
  run <pipe_name>        Run a named pipe on stdin (or --input-file).
  run-dynamic '<json>'   Run an ad-hoc node array on stdin (or --input-file).
  list                   List all configured pipes and shadow tools on PATH.
  stats                  Print the Context Balance Sheet (ROI).
  serve                  Start the MCP server (stdio transport).
  aliases install        Install cpipe shell alias into profile files.
  aliases remove         Remove the managed cpipe alias block.
"""

import argparse
import json
import os
import sys
import logging
from typing import Optional

from .config_loader import load_pipes_config
from .dynamic import run_dynamic_pipe
from .onboarding import inject_shell_aliases, remove_shell_aliases
from .orchestrator import run_pipe
from .shadow import list_shadow_tools
from .telemetry import get_balance_sheet, generate_audit_header

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_input(input_file: Optional[str]) -> str:
    """
    Reads input text from ``--input-file`` path or stdin.

    Returns empty string (and exits 0 silently) when stdin is a TTY and no
    file is provided — consistent with the orchestrator's behaviour.
    """
    if input_file:
        try:
            with open(input_file, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError as exc:
            _die(f"Cannot read input file '{input_file}': {exc}")
    if sys.stdin.isatty():
        return ""
    try:
        return sys.stdin.read()
    except EOFError:
        return ""


def _die(message: str, code: int = 1) -> None:
    """Prints an error to stderr and exits."""
    print(f"mcp-pipe: error: {message}", file=sys.stderr)
    sys.exit(code)


def _print_audit(result: str, trace: list, pipe_name: str, latency_ms: float, verbose: bool) -> None:
    """Writes result to stdout; optionally prepends the audit header."""
    if verbose:
        header = generate_audit_header(pipe_name, trace, latency_ms)
        sys.stdout.write(header)
    sys.stdout.write(result)
    if result and not result.endswith("\n"):
        sys.stdout.write("\n")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _cmd_run(args: argparse.Namespace) -> int:
    """Executes a named pipe from config."""
    import time

    config = load_pipes_config(args.config)
    pipe = next((p for p in config.get("pipes", []) if p["name"] == args.pipe_name), None)
    if pipe is None:
        available = [p.get("name", "?") for p in config.get("pipes", [])]
        _die(
            f"Pipe '{args.pipe_name}' not found.\n"
            f"  Available: {', '.join(available) if available else '(none — check your pipes.json or ~/.mcp-pipe.json)'}"
        )

    input_text = _read_input(getattr(args, "input_file", None))
    if not input_text:
        return 0

    t0 = time.monotonic()
    assert pipe is not None  # _die() exits above if pipe is None
    result, trace = run_pipe(pipe, input_text, tool_name="cli:run")
    latency_ms = (time.monotonic() - t0) * 1000

    _print_audit(result, trace, args.pipe_name, latency_ms, verbose=getattr(args, "verbose", False))
    return 0


def _cmd_run_dynamic(args: argparse.Namespace) -> int:
    """Executes an ad-hoc node array."""
    import time

    try:
        nodes = json.loads(args.nodes_json)
    except json.JSONDecodeError as exc:
        _die(f"nodes_json is not valid JSON: {exc}")

    input_text = _read_input(getattr(args, "input_file", None))
    if not input_text:
        return 0

    t0 = time.monotonic()
    try:
        result, trace = run_dynamic_pipe(nodes, input_text, tool_name="cli:run-dynamic")
    except ValueError as exc:
        _die(str(exc))
    latency_ms = (time.monotonic() - t0) * 1000

    _print_audit(result, trace, "dynamic", latency_ms, verbose=getattr(args, "verbose", False))
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    """Lists configured pipes and discovered PATH tools."""
    config_path = getattr(args, "config", "pipes.json")
    tools = list_shadow_tools(config_path)

    if not tools:
        print("No pipes configured and no known CLI tools found on PATH.")
        print(f"  Config searched: {os.path.abspath(config_path)}  |  ~/.mcp-pipe.json")
        return 0

    # Group by source
    pipe_tools = [t for t in tools if t["source"] == "pipes.json"]
    path_tools = [t for t in tools if t["source"] == "PATH"]

    if pipe_tools:
        print("\nConfigured Pipes (pipes.json / ~/.mcp-pipe.json):")
        for t in pipe_tools:
            nodes_str = " | ".join(t["nodes"]) if t["nodes"] else "—"
            print(f"  {t['name']:<28} {t.get('description', '')}")
            print(f"  {'':28} nodes: {nodes_str}")

    if path_tools:
        print("\nDiscovered CLI Tools (PATH):")
        for t in path_tools:
            print(f"  {t['name']:<28} {t.get('description', '')}")

    print()
    return 0


def _cmd_stats(_args: argparse.Namespace) -> int:
    """Prints the Context Balance Sheet."""
    sheet = get_balance_sheet()
    net_label = "Saved" if sheet["net_change"] < 0 else "Added"

    print("\n--- [mcp-pipe: Context Balance Sheet] ---")
    print(f"  Signal Injected:    +{sheet['signal_added']:,} chars")
    print(f"  Noise Incinerated:  -{sheet['noise_removed']:,} chars")
    print(f"  Net Context {net_label}:  {abs(sheet['net_change']):,} chars")
    print(f"  Platform Events:     {sheet['total_events']}")
    print(f"  Avg Node Latency:    {sheet['avg_latency_ms']:.2f}ms")
    if sheet.get("fallback_events", 0) > 0:
        print(f"  Hook Fallbacks:      {sheet['fallback_events']} (pipe failed; raw input passed through)")
    print("-----------------------------------------\n")
    return 0


def _cmd_serve(_args: argparse.Namespace) -> int:
    """Starts the MCP server (stdio transport)."""
    from .server import main as server_main

    server_main()
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _cmd_aliases(args: argparse.Namespace) -> int:
    """Installs or removes the cpipe shell alias."""
    action = getattr(args, "alias_action", "install")
    shells = getattr(args, "shells", None)  # None → auto-detect platform defaults

    if action == "install":
        results = inject_shell_aliases(shells=shells)
        if results:
            for r in results:
                print(r)
            print(
                "\nRestart your shell (or run `source ~/.bashrc` / `. $PROFILE`) "
                "to activate the cpipe alias."
            )
        else:
            print("cpipe alias already up-to-date — no changes made.")
    elif action == "remove":
        results = remove_shell_aliases()
        if results:
            for r in results:
                print(r)
        else:
            print("No cpipe alias block found in any profile — nothing removed.")
    return 0

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-pipe",
        description=(
            "mcp-pipe — Terminal runner for the Context-Pipe ecosystem.\n"
            "Execute pipes, list capabilities, and report ROI without an IDE."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="mcp-pipe 0.4.0 (context-pipe)",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # --- run ---
    run_p = sub.add_parser("run", help="Run a named pipe on stdin or a file.")
    run_p.add_argument("pipe_name", help="Name of the pipe (from pipes.json or ~/.mcp-pipe.json).")
    run_p.add_argument("--config", default="pipes.json", metavar="PATH",
                       help="Path to local pipes.json (default: pipes.json).")
    run_p.add_argument("--input-file", metavar="PATH",
                       help="Read input from this file instead of stdin.")
    run_p.add_argument("-v", "--verbose", action="store_true",
                       help="Prepend audit header (node trace + latency) to output.")

    # --- run-dynamic ---
    dyn_p = sub.add_parser("run-dynamic", help="Run an ad-hoc node array on stdin or a file.")
    dyn_p.add_argument("nodes_json",
                       help='JSON array of node objects, e.g. \'[{"cmd":"jq","args":["."]}]\'')
    dyn_p.add_argument("--input-file", metavar="PATH",
                       help="Read input from this file instead of stdin.")
    dyn_p.add_argument("-v", "--verbose", action="store_true",
                       help="Prepend audit header to output.")

    # --- list ---
    list_p = sub.add_parser("list", help="List configured pipes and PATH tools.")
    list_p.add_argument("--config", default="pipes.json", metavar="PATH",
                        help="Path to local pipes.json (default: pipes.json).")

    # --- stats ---
    sub.add_parser("stats", help="Print the Context Balance Sheet (ROI).")

    # --- serve ---
    sub.add_parser("serve", help="Start the MCP server (stdio transport).")

    # --- aliases ---
    alias_p = sub.add_parser("aliases", help="Install or remove the cpipe shell alias.")
    alias_sub = alias_p.add_subparsers(dest="alias_action", metavar="<action>")
    alias_sub.required = True

    install_p = alias_sub.add_parser("install", help="Add cpipe alias to shell profile(s).")
    install_p.add_argument(
        "--shells",
        nargs="+",
        metavar="SHELL",
        choices=["bash", "zsh", "sh", "pwsh"],
        help="Explicit shell(s) to target (default: auto-detect from platform).",
    )

    alias_sub.add_parser("remove", help="Remove the managed cpipe alias block.")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "run": _cmd_run,
        "run-dynamic": _cmd_run_dynamic,
        "list": _cmd_list,
        "stats": _cmd_stats,
        "serve": _cmd_serve,
        "aliases": _cmd_aliases,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    try:
        sys.exit(handler(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
