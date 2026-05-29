# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
context_pipe/cli.py  mcp-pipe CLI

A lightweight terminal runner for the Context-Pipe ecosystem.
Executes pipes, lists capabilities, and reports ROI  all without
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
import asyncio
import json
import os
import sys
import logging
from typing import Optional

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

from .config_loader import load_pipes_config, resolve_placeholders
from .dynamic import run_dynamic_pipe
from .onboarding import inject_shell_aliases, remove_shell_aliases
from .orchestrator import run_pipe, _run_mcp_node, get_env_with_venv_path
from .shadow import list_shadow_tools
from .telemetry import get_balance_sheet, log_telemetry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_input(input_file: Optional[str]) -> str:
    """
    Reads input text from ``--input-file`` path or stdin.

    Returns empty string (and exits 0 silently) when stdin is a TTY and no
    file is provided  consistent with the orchestrator's behaviour.
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
    """Writes result to stdout; optionally logs telemetry to stderr if verbose."""
    if verbose:
        sys.stderr.write(f"\n[Context-Pipe Verbose: {pipe_name} executed in {latency_ms:.1f}ms]\n")
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
            f"  Available: {', '.join(available) if available else '(none  check your pipes.json or ~/.mcp-pipe.json)'}"
        )

    input_text = _read_input(getattr(args, "input_file", None))
    if not input_text:
        return 0

    # Line Range Slicing
    start_line = getattr(args, "start_line", None)
    end_line = getattr(args, "end_line", None)
    if start_line is not None or end_line is not None:
        lines = input_text.splitlines(keepends=True)
        start_idx = (start_line - 1) if start_line is not None else 0
        end_idx = end_line if end_line is not None else len(lines)
        start_idx = max(0, min(start_idx, len(lines)))
        end_idx = max(0, min(end_idx, len(lines)))
        input_text = "".join(lines[start_idx:end_idx])

    t0 = time.monotonic()
    assert pipe is not None  # _die() exits above if pipe is None
    vars_dict = {}
    for v in getattr(args, "var", []) or []:
        if "=" in v:
            k, val = v.split("=", 1)
            vars_dict[k] = val
        else:
            _die(f"Invalid var format '{v}'. Expected KEY=VALUE.")

    result, trace = asyncio.run(run_pipe(pipe, input_text, tool_name="cli:run", server_registry=config.get("servers", {}), vars=vars_dict, manifest_path=getattr(args, "manifest", None)))
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
        result, trace = asyncio.run(run_dynamic_pipe(
            nodes,
            input_text,
            tool_name="cli:run-dynamic",
            allow_shell=getattr(args, "allow_shell", False)
        ))
    except ValueError as exc:
        _die(str(exc))
    latency_ms = (time.monotonic() - t0) * 1000

    _print_audit(result, trace, "dynamic", latency_ms, verbose=getattr(args, "verbose", False))
    return 0


def _cmd_handoff(args: argparse.Namespace) -> int:
    """Executes agent handoff distillation."""
    from .a2a import pipe_agent_handoff

    input_text = args.output
    if not input_text:
        input_text = _read_input(None)
    if not input_text:
        return 0

    result = pipe_agent_handoff(
        output=input_text,
        pipe_name=args.pipe_name,
        from_agent=args.from_agent,
        to_agent=args.to_agent,
        config_path=args.config,
    )
    sys.stdout.write(result)
    if result and not result.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Verifies the health of the context-pipe + semantic-sift installation."""
    import context_pipe.server as cp_server
    
    cp_server.CONFIG_PATH = args.config
    result = cp_server.pipe_verify()
    print(result)
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
            nodes_str = " | ".join(t["nodes"]) if t["nodes"] else ""
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
    if sheet.get("bypass_events", 0) > 0:
        print(f"  Hook Bypasses:       {sheet['bypass_events']} (opted for Native Execution)")
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
    shells = getattr(args, "shells", None)  # None  auto-detect platform defaults

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
            print("cpipe alias already up-to-date  no changes made.")
    elif action == "remove":
        results = remove_shell_aliases()
        if results:
            for r in results:
                print(r)
        else:
            print("No cpipe alias block found in any profile  nothing removed.")
    return 0

def _parse_tool_args(raw: list[str]) -> dict:
    """
    Parses ``--arg KEY=VALUE`` entries into a dict.

    ``--arg key=value``  ``{"key": "value"}``
    ``--arg key=a=b``    ``{"key": "a=b"}`` (splits on first ``=`` only)

    Raises SystemExit on malformed entries (missing ``=``).
    """
    result: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            _die(f"--arg must be in KEY=VALUE format, got: '{entry}'")
        key, _, value = entry.partition("=")
        result[key.strip()] = value
    return result


async def _list_server_tools(server_cfg: dict, env: dict) -> list[dict]:
    """
    Introspects an MCP server and returns its tool list.

    Returns a list of dicts: ``[{"name": str, "description": str, "inputSchema": dict}]``
    """
    resolved_env = resolve_placeholders(server_cfg.get("env", {}), env)
    child_env = {**env, **resolved_env}
    cmd: list[str] = server_cfg["command"]

    server_params = StdioServerParameters(
        command=cmd[0], args=cmd[1:], env=child_env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema or {},
                }
                for t in tools_result.tools
            ]


def _cmd_tool(args: argparse.Namespace) -> int:
    """Directly invokes an MCP tool from the shell (Phase 7.6)."""
    import time

    # 1. Resolve config and server registry
    config = load_pipes_config(args.config)
    server_registry = config.get("servers", {})

    if args.server not in server_registry:
        available = list(server_registry.keys())
        _die(
            f"Server '{args.server}' not found in servers registry.\n"
            f"  Available: {', '.join(available) if available else '(none  add a servers block to pipes.json or ~/.mcp-pipe.json)'}"
        )

    server_cfg = server_registry[args.server]
    env = get_env_with_venv_path()

    # 2. --list-tools: introspect and print, then exit
    if getattr(args, "list_tools", False):
        try:
            tools = asyncio.run(_list_server_tools(server_cfg, env))
        except Exception as exc:
            _die(f"Failed to list tools on '{args.server}': {exc}")
        if not tools:
            print(f"No tools found on server '{args.server}'.")
            return 0
        print(f"\nTools on '{args.server}':")
        for t in tools:
            print(f"  {t['name']:<32} {t['description']}")
        print()
        return 0

    if args.tool_name is None:
        _die("tool_name is required unless --list-tools is given.")

    # 3. Read input
    input_text = _read_input(getattr(args, "input_file", None))
    # Note: unlike run/run-dynamic, we don't exit on empty  some tools don't need input.

    # 4. Parse static args
    static_args = _parse_tool_args(args.arg or [])

    # 5. Construct synthetic node and execute
    node = {
        "type": "mcp",
        "server": args.server,
        "tool": args.tool_name,
        "input_key": args.input_key,
        "args": static_args,
    }

    t0 = time.monotonic()
    try:
        result = asyncio.run(_run_mcp_node(node, input_text or "", server_registry, env))
    except ValueError as exc:
        _die(str(exc))
    except asyncio.TimeoutError:
        timeout_ms = os.environ.get("PIPE_NODE_TIMEOUT_MS", "30000")
        _die(f"Tool call timed out after {int(timeout_ms) / 1000:.1f}s.")

    latency_ms = (time.monotonic() - t0) * 1000

    # 6. Telemetry accounting (Phase 7.6-C)
    try:
        import datetime
        log_telemetry(
            session_id=os.environ.get("PIPE_SESSION_ID", "cli"),
            start_time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            tool_name=args.tool_name,
            original_size=len(input_text or ""),
            final_size=len(result),
            latency_ms=latency_ms,
            pipe_name=f"{args.server}/{args.tool_name}",
        )
    except Exception:
        pass  # Telemetry must never block the main flow

    # 7. Output
    sys.stdout.write(result)
    if result and not result.endswith("\n"):
        sys.stdout.write("\n")

    if getattr(args, "verbose", False):
        sys.stderr.write(
            f"[mcp-pipe tool] {args.server}/{args.tool_name} | "
            f"{len(input_text or ''):,}  {len(result):,} chars | {latency_ms:.1f}ms\n"
        )
    return 0


def _cmd_onboard(args: argparse.Namespace) -> int:
    """Initializes Context-Pipe hooks and commands."""
    from .onboarding import inject_hooks
    target_dir = getattr(args, "target_dir", None) or os.getcwd()
    environment = getattr(args, "environment", None)
    
    if not environment:
        from .platforms import detect_client_id
        environment = detect_client_id()
        print(f"Auto-detected environment: {environment}")

    actions = inject_hooks(target_dir, environment)
    if not actions:
        print(f"Context-Pipe is already active or no targets found in {target_dir}.")
        return 0
    
    print("Onboarding Successful:")
    for a in actions:
        print(f"- {a}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-pipe",
        description=(
            "mcp-pipe  Terminal runner for the Context-Pipe ecosystem.\n"
            "Execute pipes, list capabilities, and report ROI without an IDE."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="mcp-pipe 0.4.5 (context-pipe)",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # --- run ---
    run_p = sub.add_parser("run", help="Run a named pipe on stdin or a file.")
    run_p.add_argument("pipe_name", help="Name of the pipe (from pipes.json or ~/.mcp-pipe.json).")
    run_p.add_argument("--config", default="pipes.json", metavar="PATH",
                       help="Path to local pipes.json (default: pipes.json).")
    run_p.add_argument("--input-file", "--input_file", dest="input_file", metavar="PATH",
                       help="Read input from this file instead of stdin.")
    run_p.add_argument("--start-line", "--start_line", dest="start_line", type=int, metavar="N",
                       help="1-indexed start line (inclusive) to slice from input.")
    run_p.add_argument("--end-line", "--end_line", dest="end_line", type=int, metavar="N",
                       help="1-indexed end line (inclusive) to slice from input.")
    run_p.add_argument("-v", "--verbose", action="store_true",
                       help="Prepend audit header (node trace + latency) to output.")

    # --- run-dynamic ---
    dyn_p = sub.add_parser("run-dynamic", help="Run an ad-hoc node array on stdin or a file.")
    dyn_p.add_argument("nodes_json",
                       help='JSON array of node objects, e.g. \'[{"cmd":"jq","args":["."]}]\'')
    dyn_p.add_argument("--input-file", "--input_file", dest="input_file", metavar="PATH",
                       help="Read input from this file instead of stdin.")
    dyn_p.add_argument("-v", "--verbose", action="store_true",
                       help="Prepend audit header to output.")
    dyn_p.add_argument("--allow-shell", "--allow_shell", dest="allow_shell", action="store_true",
                       help="Allow shell utilities as dynamic pipe nodes.")

    # --- list ---
    list_p = sub.add_parser("list", help="List configured pipes and PATH tools.")
    list_p.add_argument("--config", default="pipes.json", metavar="PATH",
                        help="Path to local pipes.json (default: pipes.json).")

    # --- stats ---
    sub.add_parser("stats", help="Print the Context Balance Sheet (ROI).")

    # --- tool (Phase 7.6) ---
    tool_p = sub.add_parser("tool", help="Directly invoke an MCP tool from the shell.")
    tool_p.add_argument("server", help="MCP server registry key.")
    tool_p.add_argument("tool_name", nargs="?", default=None,
                        help="Name of the tool to call. Required unless --list-tools is given.")
    tool_p.add_argument("--arg", action="append", metavar="K=V",
                        help="Static arguments (key=value). May be repeated.")
    tool_p.add_argument("--input-key", default="content", metavar="KEY",
                        help="Argument key for stdin content (default: 'content').")
    tool_p.add_argument("--input-file", metavar="PATH",
                        help="Read input from this file instead of stdin.")
    tool_p.add_argument("--config", default="pipes.json", metavar="PATH",
                        help="Path to local pipes.json (default: pipes.json).")
    tool_p.add_argument("--list-tools", action="store_true",
                        help="List all tools available on the named server and exit.")
    tool_p.add_argument("-v", "--verbose", action="store_true",
                        help="Print timing/telemetry to stderr.")

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

    # --- verify ---
    verify_p = sub.add_parser("verify", help="Verify the health of the context-pipe + semantic-sift installation.")
    verify_p.add_argument("--config", default="pipes.json", metavar="PATH",
                          help="Path to local pipes.json (default: pipes.json).")

    # --- onboard ---
    onb_p = sub.add_parser("onboard", help="Initialize Context-Pipe hooks and commands.")
    onb_p.add_argument("environment", nargs="?", default=None,
                       help="The IDE/CLI environment (e.g., 'Cursor', 'VSCode', 'Gemini'). If omitted, auto-detection is performed.")
    onb_p.add_argument("--target-dir", "--target_dir", dest="target_dir", metavar="PATH",
                       help="Optional directory to onboard (default: current directory).")

    # --- handoff ---
    handoff_p = sub.add_parser("handoff", help="Distil agent output before passing it to another agent.")
    handoff_p.add_argument("--from", "--from-agent", "--from_agent", dest="from_agent", default="a2a",
                           help="Label for the producing agent.")
    handoff_p.add_argument("--to", "--to-agent", "--to_agent", dest="to_agent", default="a2a",
                           help="Label for the consuming agent.")
    handoff_p.add_argument("--output", help="The raw output to distil.")
    handoff_p.add_argument("--pipe-name", "--pipe_name", dest="pipe_name", default=None,
                           help="Explicit pipe name to use.")
    handoff_p.add_argument("--config", default="pipes.json", metavar="PATH",
                           help="Path to local pipes.json (default: pipes.json).")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _reconfigure_io() -> None:
    """Forces all std* streams to UTF-8 on Windows to prevent encoding crashes.

    Uses ``surrogateescape`` error handler (matching ``orchestrator.py``) so that
    non-decodable stdin bytes are safely round-tripped instead of producing
    lone surrogates that crash ``sys.stdout.write()`` downstream.
    """
    import sys
    if os.name == "nt":
        for stream in (sys.stdout, sys.stderr, sys.stdin):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="surrogateescape")


def main() -> None:
    _reconfigure_io()
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "run": _cmd_run,
        "run-dynamic": _cmd_run_dynamic,
        "list": _cmd_list,
        "stats": _cmd_stats,
        "serve": _cmd_serve,
        "aliases": _cmd_aliases,
        "tool": _cmd_tool,
        "handoff": _cmd_handoff,
        "verify": _cmd_verify,
        "onboard": _cmd_onboard,
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
