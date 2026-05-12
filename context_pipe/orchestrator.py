# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
import sys
import json
import hashlib
import time
import subprocess
import argparse
import re
import os
import shutil
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from .config_loader import _resolve_env_placeholders

# Metadata Signatures
CPP_SIGNATURE = "--- [Context-Pipe: Native Execution] ---"


def get_env_with_venv_path() -> Dict[str, str]:
    """Ensures the current venv's bin/Scripts directory is in the PATH for child processes."""
    env = os.environ.copy()

    # Detect if we are running in a virtual environment
    if sys.prefix != sys.base_prefix:
        venv_bin = os.path.join(sys.prefix, "Scripts" if os.name == "nt" else "bin")
        if os.path.exists(venv_bin):
            path_sep = ";" if os.name == "nt" else ":"
            current_path = env.get("PATH", "")
            if venv_bin not in current_path:
                env["PATH"] = f"{venv_bin}{path_sep}{current_path}"

    return env


def resolve_node_cmd(cmd: str) -> str:
    """
    Resolves a pipe node command to an executable path at runtime.

    Resolution order (most specific to least):
    1. Absolute path that already exists on disk — used as-is.
    2. shutil.which() — resolves from the active PATH (covers venv Scripts/bin, system PATH).
    3. Common user-level install locations (~/.local/bin, pipx).
    4. Bare command returned unchanged — FileNotFoundError surfaces naturally via Popen,
       and the node's help_msg is shown to the user.
    """
    # 1. Already an absolute path that exists
    if os.path.isabs(cmd) and os.path.isfile(cmd):
        return cmd

    # 2. PATH lookup (covers venv Scripts/bin injected by get_env_with_venv_path)
    env_path = get_env_with_venv_path().get("PATH")
    which_result = shutil.which(cmd, path=env_path)
    if which_result:
        return which_result

    # 3. Common user-level locations (uv tool install, pipx)
    exe_name = f"{cmd}.exe" if os.name == "nt" else cmd
    user_candidates = [
        Path.home() / ".local" / "bin" / exe_name,
        Path(os.environ.get("PIPX_BIN_DIR", str(Path.home() / ".local" / "bin"))) / exe_name,
    ]
    for candidate in user_candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    # 4. Return bare command — Popen will raise FileNotFoundError, help_msg surfaces the error
    return cmd


def check_echo(text: str, pipe_name: str = "", node_index: int = 0) -> bool:
    """Checks if the content was processed recently to prevent loops (30s TTL)."""
    if not text or len(text) < 500:
        return False

    # Unified with Context-Pipe (.pipe_cache)
    cache_dir = os.path.join(os.getcwd(), ".pipe_cache")
    os.makedirs(cache_dir, exist_ok=True)

    # Scoped hash: (pipe_name, node_index, content)
    raw_key = f"{pipe_name}:{node_index}:{text}"
    content_hash = hashlib.sha256(raw_key.encode()).hexdigest()[:16]
    echo_path = os.path.join(cache_dir, f"echo_{content_hash}.tmp")
    now = time.time()

    if os.path.exists(echo_path):
        try:
            with open(echo_path, "r") as f:
                expiry = float(f.read().strip())
            if now < expiry:
                return True
        except (OSError, ValueError):
            pass

    # Write new marker
    try:
        with open(echo_path, "w") as f:
            f.write(str(now + 30))
    except OSError:
        pass

    return False


def resolve_pipe_from_context(config: Dict[str, Any], tool_name: str, content_len: int) -> Optional[str]:
    """Resolves a pipe name based on mapping triggers."""
    mappings = config.get("mappings", [])

    for m in mappings:
        trigger = m.get("trigger", "")

        # 1. Tool Trigger (tool:regex)
        if trigger.startswith("tool:"):
            pattern = trigger.replace("tool:", "")
            if re.search(pattern, tool_name, re.IGNORECASE):
                return m["pipe"]

        # 2. Size Trigger (size:>num)
        if trigger.startswith("size:>"):
            try:
                threshold = int(trigger.replace("size:>", ""))
                if content_len > threshold:
                    return m["pipe"]
            except ValueError:
                continue

        # 3. Default Trigger
        if trigger == "default":
            return m["pipe"]

    return None


def _write_tee(tee_config: Dict[str, Any], data: str, node_cmd: str, tool_name: Optional[str]) -> Optional[str]:
    """
    Writes data to a local-file tee sink before the node processes it.

    Supports path tokens: {iso_date} (YYYY-MM-DD), {tool_name} (sanitised tool name).
    Mode: "append" (default) or "overwrite".

    Returns the resolved path on success, None on any failure.
    Errors are silently swallowed — a tee failure must never interrupt the main chain.
    """
    try:
        sink = tee_config.get("sink", "file")
        if sink != "file":
            return None  # Only local-file sinks supported in v0.3.0

        raw_path: str = tee_config.get("path", "")
        if not raw_path:
            return None

        # Token substitution
        iso_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        safe_tool = re.sub(r"[^\w\-]", "_", tool_name or "unknown")
        resolved_path = raw_path.replace("{iso_date}", iso_date).replace("{tool_name}", safe_tool)

        mode_str = tee_config.get("mode", "append")
        file_mode = "w" if mode_str == "overwrite" else "a"

        os.makedirs(os.path.dirname(os.path.abspath(resolved_path)), exist_ok=True)

        timestamp = datetime.now(tz=timezone.utc).isoformat()
        separator = f"\n--- [Context-Pipe: Tee @ {node_cmd} | {timestamp}] ---\n"

        with open(resolved_path, file_mode, encoding="utf-8") as f:
            f.write(data)
            f.write(separator)

        return resolved_path
    except Exception:
        return None


def _extract_text(result: object) -> str:
    """
    Extracts text content from a CallToolResult.

    Iterates result.content (list of TextContent / ImageContent / etc.),
    concatenates all TextContent items. Falls back to str(result) if none found.
    """
    try:
        parts = [item.text for item in result.content if hasattr(item, "text")]  # type: ignore[attr-defined]
        return "\n".join(parts) if parts else str(result)
    except Exception:
        return str(result)


async def _run_mcp_node(
    node: dict,
    stdin_data: str,
    server_registry: dict,
    env: dict,
) -> str:
    """
    Executes a single MCP node by spawning the server, calling the tool,
    and returning the text result.

    Args:
        node:            Node config dict (must have ``server`` and ``tool``).
        stdin_data:      Text to pass as the tool's primary input argument.
        server_registry: Merged servers dict from ``load_pipes_config()``.
        env:             Resolved environment variables for child processes.

    Returns:
        Text output from the tool call.

    Raises:
        ValueError: if the server key is not found in the registry.
        asyncio.TimeoutError: if the tool call exceeds ``PIPE_NODE_TIMEOUT_MS``.
    """
    server_key = node["server"]
    tool_name = node["tool"]
    input_key = node.get("input_key", "content")
    static_args: dict = {k: v for k, v in node.get("args", {}).items()}

    server_cfg = server_registry.get(server_key)
    if not server_cfg:
        raise ValueError(
            f"MCP server '{server_key}' not found in servers registry. "
            f"Available: {list(server_registry.keys()) or '(none)'}"
        )

    resolved_env = _resolve_env_placeholders(server_cfg.get("env", {}))
    child_env = {**env, **resolved_env}

    cmd: list[str] = server_cfg["command"]
    if isinstance(cmd, str):
        import shlex
        cmd = shlex.split(cmd)
    if not cmd:
        raise ValueError(f"Server '{server_key}' has an empty command list.")

    server_params = StdioServerParameters(
        command=cmd[0],
        args=cmd[1:],
        env=child_env,
    )

    raw_timeout = os.environ.get("PIPE_NODE_TIMEOUT_MS", "30000")
    timeout_s = int(raw_timeout) / 1000.0

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            arguments = {input_key: stdin_data, **static_args}
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=timeout_s,
            )
            return _extract_text(result)


async def run_pipe(
    pipe_config: Dict[str, Any],
    input_data: str,
    tool_name: Optional[str] = None,
    agent_label: Optional[str] = None,
    server_registry: Dict[str, Any] | None = None,
) -> tuple[str, List[Dict[str, Any]]]:
    """Executes a chain of nodes and tracks context deltas with a timeout guard."""
    current_input = input_data
    trace: List[Dict[str, Any]] = []

    # 1. Prepare Environment (Self-Aware Venv Path + Metadata)
    process_env = get_env_with_venv_path()
    if tool_name:
        process_env["SIFT_TOOL_NAME"] = tool_name
    if agent_label:
        process_env["SIFT_AGENT_LABEL"] = agent_label

    # Global timeout for the entire pipe execution (default 30s to allow model warmup)
    raw_timeout = os.environ.get("PIPE_NODE_TIMEOUT_MS", "30000")
    node_timeout = int(raw_timeout) / 1000.0

    for node_index, node in enumerate(pipe_config.get("nodes", [])):
        # Echo Guard: skip node if input was recently processed by THIS node in THIS pipe
        if check_echo(current_input, pipe_name=pipe_config.get("name", "unknown"), node_index=node_index):
            continue

        node_type = node.get("type", "binary")

        if node_type == "mcp":
            # ... (mcp logic)
            start_size = len(current_input)
            tee_path: Optional[str] = None
            tee_config = node.get("tee")
            if tee_config:
                tee_path = _write_tee(tee_config, current_input, f"mcp:{node['server']}/{node['tool']}", tool_name)
            try:
                stdout = await _run_mcp_node(node, current_input, server_registry or {}, process_env)
            except asyncio.TimeoutError:
                error_text = f"--- [Context-Pipe: Timeout] ---\nMCP node {node['server']}/{node['tool']} exceeded {node_timeout}s."
                trace.append({"node": f"mcp:{node['server']}/{node['tool']}", "error": "Timeout"})
                return error_text, trace
            except ValueError as exc:
                error_text = f"--- [Context-Pipe: MCP Error] ---\n{exc}"
                trace.append({"node": f"mcp:{node['server']}/{node['tool']}", "error": str(exc)})
                return error_text, trace
            except Exception as exc:
                error_text = f"--- [Context-Pipe: MCP Unexpected Error] ---\n{exc}"
                trace.append({"node": f"mcp:{node['server']}/{node['tool']}", "error": str(exc)})
                return error_text, trace

            end_size = len(stdout)
            entry: Dict[str, Any] = {
                "node": f"mcp:{node['server']}/{node['tool']}",
                "input_size": start_size,
                "output_size": end_size,
                "delta": end_size - start_size,
            }
            if tee_path is not None:
                entry["tee_path"] = tee_path
            trace.append(entry)
            current_input = stdout
            continue

        if node_type == "script":
            # --- Local Script/Mandate path ---
            script_name = node["cmd"]
            script_dir = os.environ.get("PIPE_SCRIPT_DIR", ".gemini/scripts")
            
            # Resolution: .py -> .md (Mandate) -> raw
            py_script = os.path.join(script_dir, f"{script_name}.py")
            md_mandate = os.path.join(script_dir, f"{script_name}.md")
            
            if os.path.exists(py_script):
                # Execute Python script
                resolved_cmd = sys.executable
                args = [py_script] + [str(a) for a in node.get("args", [])]
            elif os.path.exists(md_mandate):
                # Mandate Prepend Logic
                with open(md_mandate, "r", encoding="utf-8") as f:
                    mandate_text = f.read()
                stdout = f"--- [Context-Pipe: Mandate ({script_name})] ---\n{mandate_text}\n\n[Content]\n{current_input}"
                
                # Mock a trace entry for the mandate
                start_size = len(current_input)
                end_size = len(stdout)
                trace.append({
                    "node": f"script:{script_name} (mandate)",
                    "input_size": start_size,
                    "output_size": end_size,
                    "delta": end_size - start_size,
                })
                current_input = stdout
                continue
            else:
                # Fallback to binary resolution if script not found
                resolved_cmd = resolve_node_cmd(node["cmd"])
                args = [str(a) for a in node.get("args", [])]
            
            cmd = [resolved_cmd] + args
        else:
            # --- Existing subprocess path ---
            resolved_cmd = resolve_node_cmd(node["cmd"])
            cmd = [resolved_cmd] + [str(a) for a in node.get("args", [])]

        start_size = len(current_input)

        # T-Pipe: write raw input to sink before node processes it
        tee_path: Optional[str] = None  # type: ignore[no-redef]
        tee_config = node.get("tee")
        if tee_config:
            tee_path = _write_tee(tee_config, current_input, node["cmd"], tool_name)

        try:
            # High-Fidelity OS Piping (shell=False enforced — no injection surface)
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                env=process_env,
            )

            try:
                stdout, stderr = process.communicate(input=current_input, timeout=node_timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                error_text = f"--- [Context-Pipe: Timeout] ---\nNode {node['cmd']} exceeded {node_timeout}s."
                trace.append({"node": node["cmd"], "error": "Timeout"})
                return error_text, trace

            if process.returncode != 0:
                # Record error in trace
                trace.append({"node": node["cmd"], "error": stderr.strip()})
                return f"Error in node {node['cmd']}: {stderr}", trace

        except FileNotFoundError:
            help_msg = node.get("help_msg", f"Command '{node['cmd']}' not found in system PATH.")
            error_text = f"--- [Context-Pipe: Dependency Error] ---\n{help_msg}"
            trace.append({"node": node["cmd"], "error": "FileNotFound"})
            return error_text, trace

        end_size = len(stdout)
        entry: Dict[str, Any] = {  # type: ignore[no-redef]
            "node": node["cmd"],
            "input_size": start_size,
            "output_size": end_size,
            "delta": end_size - start_size,
        }
        if tee_path is not None:
            entry["tee_path"] = tee_path
        trace.append(entry)

        current_input = stdout

    return current_input, trace


def load_config(config_path: str = "pipes.json") -> Dict[str, Any]:
    """
    Loads ``pipes.json`` with a two-location fallback.

    Resolution order:
    1. ``config_path`` as given (absolute or relative to CWD).
    2. The package root directory (parent of ``context_pipe/``), which is
       where ``pipes.json`` lives in both installed and editable layouts.

    Returns an empty scaffold ``{"pipes": [], "mappings": []}`` if the file
    is not found or is not valid JSON.
    """
    config: Dict[str, Any] = {"pipes": [], "mappings": []}
    search_paths = [config_path]
    if not os.path.isabs(config_path):
        search_paths.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config_path))

    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                break
            except (json.JSONDecodeError, OSError):
                continue

    return config


def main():
    # 1. Capture raw input immediately for safety fallback
    raw_input = None
    if not sys.stdin.isatty():
        try:
            raw_input = sys.stdin.read()
        except EOFError:
            pass

    try:
        parser = argparse.ArgumentParser(description="Context-Pipe Orchestrator")
        subparsers = parser.add_subparsers(dest="command", help="Subcommands")

        # 1. 'run' command (default)
        run_parser = subparsers.add_parser("run", help="Run a specific pipe")
        run_parser.add_argument("pipe_name", help="Name of the pipe to execute from pipes.json")
        run_parser.add_argument("--config", default="pipes.json", help="Path to pipes.json")

        # 2. 'wrap' command (JSON polyfill)
        wrap_parser = subparsers.add_parser("wrap", help="Wrap a JSON-RPC payload")
        wrap_parser.add_argument("--config", default="pipes.json", help="Path to pipes.json")

        # 3. 'stats' command (Balance Sheet)
        subparsers.add_parser("stats", help="Display Context-Pipe ROI Balance Sheet")

        # Compatibility with old behavior (no subcommand)
        if len(sys.argv) > 1 and sys.argv[1] not in ["run", "wrap", "stats"]:
            # Handle common aliases for stats
            if sys.argv[1] in ["get_pipe_stats", "pipe-stats"]:
                sys.argv[1] = "stats"
            else:
                sys.argv.insert(1, "run")

        args = parser.parse_args()

        # Load Config
        config_path = getattr(args, "config", "pipes.json")
        config = load_config(config_path)

        if args.command == "run":
            if not raw_input:
                sys.exit(0)
            # Find the requested pipe
            pipe = next((p for p in config.get("pipes", []) if p["name"] == args.pipe_name), None)

            if not pipe:
                sys.stdout.write(raw_input)
                sys.exit(0)

            # Run the pipe
            result, trace = asyncio.run(run_pipe(pipe, raw_input))
            sys.stdout.write(result)

        elif args.command == "wrap":
            if not raw_input:
                sys.exit(0)
            from .wrapper import wrap_payload

            result = wrap_payload(raw_input, config)
            sys.stdout.write(result)

        elif args.command == "stats":
            from .telemetry import get_balance_sheet

            sheet = get_balance_sheet()
            net_label = "Saved" if sheet["net_change"] < 0 else "Added"

            print("\n--- [Context-Pipe: ROI Balance Sheet] ---")
            print(f"Signal Injected:  +{sheet['signal_added']:,} chars")
            print(f"Noise Incinerated: -{sheet['noise_removed']:,} chars")
            print(f"Net Context {net_label}: {abs(sheet['net_change']):,} chars")
            print(f"Platform Events:   {sheet['total_events']}")
            print(f"Avg Node Latency:  {sheet['avg_latency_ms']:.2f}ms")
            if sheet.get("fallback_events", 0) > 0:
                print(f"⚠️  Hook Fallbacks: {sheet['fallback_events']} (pipe failed; raw input passed through)")
            print("-----------------------------------------\n")

    except Exception as e:
        # ABSOLUTE SAFETY: Never crash the hook.
        if raw_input:
            # Gemini CLI strictly requires a Decision Object schema even on error.
            if os.environ.get("GEMINI_SESSION_ID"):
                sys.stdout.write(json.dumps({
                    "decision": "allow",
                    "reason": f"Context-Pipe fallback (Error: {type(e).__name__})"
                }))
            else:
                sys.stdout.write(raw_input)
        sys.exit(0)


if __name__ == "__main__":
    main()
