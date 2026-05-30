# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
import sys
import json
import hashlib
import time
import argparse
import re
import os
import shutil
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from .config_loader import resolve_placeholders

logger = logging.getLogger(__name__)

# Metadata Signatures
# Orchestrator is silent in the Sift-Centric model. Identity is handled by engine nodes.
SIFT_SIGNATURE = "--- [Semantic-Sift Audit] ---"


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
    1. Absolute path that already exists on disk  used as-is.
    2. shutil.which()  resolves from the active PATH (covers venv Scripts/bin, system PATH).
    3. Common user-level install locations (~/.local/bin, pipx).
    4. Bare command returned unchanged  FileNotFoundError surfaces naturally via Popen,
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

    # 4. Return bare command  Popen will raise FileNotFoundError, help_msg surfaces the error
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
    Errors are silently swallowed  a tee failure must never interrupt the main chain.
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



class _StdoutToleranceWrapper:
    """Wraps an anyio ObjectReceiveStream to silently drop non-JSON lines."""

    def __init__(self, original_stream, verbose: bool):
        self._orig = original_stream
        self.verbose = verbose
        self.skipped_count = 0
        self.max_skip = 50

    async def __aenter__(self):
        await self._orig.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self._orig.__aexit__(*args)

    def __aiter__(self):
        return self

    async def __anext__(self):
        import anyio
        try:
            return await self.receive()
        except anyio.EndOfStream:
            raise StopAsyncIteration

    async def receive(self):
        while True:
            chunk = await self._orig.receive()
            if isinstance(chunk, Exception):
                self.skipped_count += 1
                if self.verbose:
                    import sys
                    sys.stderr.write(f"[cpipe] MCP server stdout (non-JSON): {str(chunk)}\n")
                if self.skipped_count > self.max_skip:
                    return chunk  # give up
                continue
            return chunk

    async def aclose(self):
        await self._orig.aclose()

    @property
    def statistics(self):
        return self._orig.statistics if hasattr(self._orig, "statistics") else None

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
    static_args: dict = resolve_placeholders(node.get("args", {}), env)

    server_cfg = server_registry.get(server_key)
    if not server_cfg:
        raise ValueError(
            f"MCP server '{server_key}' not found in servers registry. "
            f"Available: {list(server_registry.keys()) or '(none)'}"
        )

    resolved_env = resolve_placeholders(server_cfg.get("env", {}), env)
    child_env = {**env, **resolved_env}

    cmd_raw = server_cfg["command"]
    if isinstance(cmd_raw, str):
        import shlex
        cmd = shlex.split(cmd_raw)
    else:
        cmd = list(cmd_raw)

    cmd = resolve_placeholders(cmd, child_env)
    
    if not cmd:
        raise ValueError(f"Server '{server_key}' has an empty command list.")

    server_params = StdioServerParameters(
        command=cmd[0],
        args=cmd[1:],
        env=child_env,
        encoding='utf-8',
        encoding_error_handler='replace',
    )

    node_timeout_override = node.get("timeout")
    if node_timeout_override is not None:
        timeout_s = float(node_timeout_override)
    else:
        raw_timeout = os.environ.get("PIPE_NODE_TIMEOUT_MS", "30000")
        timeout_s = int(raw_timeout) / 1000.0

    is_verbose = server_cfg.get("verbose", False)
    async with stdio_client(server_params) as (read, write):
        if not is_verbose:
            read = _StdoutToleranceWrapper(read, verbose=False)
        else:
            read = _StdoutToleranceWrapper(read, verbose=True)
        async with ClientSession(read, write) as session:  # type: ignore[arg-type]
            await session.initialize()
            arguments = {input_key: stdin_data, **static_args}
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=timeout_s,
            )
            return _extract_text(result)


def _build_vars(pipe_config: dict, invocation_vars: dict) -> dict:
    merged = {}
    pipe_defaults = {}

    # Validate and load defaults
    vars_block = pipe_config.get("vars") or {}
    for k, v in vars_block.items():
        if not re.match(r"^[A-Z0-9_]+$", k):
            raise ValueError(f"Invalid pipe variable name: '{k}' (must be [A-Z0-9_]+)")
        pipe_defaults[k] = str(v)

    for k in invocation_vars.keys():
        if not re.match(r"^[A-Z0-9_]+$", k):
            raise ValueError(f"Invalid invocation variable name: '{k}' (must be [A-Z0-9_]+)")

    # 1. Pipe defaults
    for k, v in pipe_defaults.items():
        merged[k] = v

    # 2. os.environ
    for k in pipe_defaults.keys():
        if k in os.environ:
            merged[k] = os.environ[k]

    # 3. Invocation vars always win
    for k, v in invocation_vars.items():
        merged[k] = str(v)

    # Fail-fast for required empty vars
    for k, default_val in pipe_defaults.items():
        if not default_val:  # empty default
            # Check if it was provided/overridden
            val = merged.get(k)
            if not val:
                raise ValueError(f"Missing pipe variable: {k}")

    return merged


def _write_manifest(
    manifest_path: str,
    pipe_config: dict,
    vars_used: dict,
    trace: list,
    result: str,
    status: str,
    started_at: str,
) -> None:
    pipe_name = pipe_config.get("name", "unknown")
    if manifest_path == "auto":
        cache_dir = os.path.join(os.getcwd(), ".pipe_cache")
        os.makedirs(cache_dir, exist_ok=True)
        iso_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        resolved_path = os.path.join(cache_dir, f"{pipe_name}-{iso_date}.json")
    else:
        resolved_path = manifest_path

    steps = []
    for i, entry in enumerate(trace):
        step = {
            "index": i + 1,
            "cmd": entry.get("node", "unknown"),
        }
        if "error" in entry:
            step["ok"] = False
            step["error"] = entry["error"]
            step["status"] = 1
        else:
            step["ok"] = True
            step["status"] = 0
            step["inputSize"] = entry.get("input_size", 0)
            step["outputSize"] = entry.get("output_size", 0)

        if "validator_code" in entry:
            step["validatorExitCode"] = entry["validator_code"]
            if "branch" in entry:
                step["branch"] = entry["branch"]
        steps.append(step)

    final_out = result[:2000] if len(result) > 2000 else result

    manifest = {
        "pipe": pipe_name,
        "vars": vars_used,
        "startedAt": started_at,
        "completedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "steps": steps,
        "finalOutput": final_out,
    }

    parent = os.path.dirname(resolved_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    try:
        with open(resolved_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception:
        pass


def _evaluate_condition(predicate: str, input_data: str) -> bool:
    predicate = predicate.strip()
    if not predicate:
        return True

    if predicate.startswith("size:>"):
        try:
            val = int(predicate[6:].strip())
            return len(input_data) > val
        except ValueError:
            logger.warning(f"Malformed size predicate: {predicate}")
            return True
    elif predicate.startswith("size:<"):
        try:
            val = int(predicate[6:].strip())
            return len(input_data) < val
        except ValueError:
            logger.warning(f"Malformed size predicate: {predicate}")
            return True
    elif predicate.startswith("artifact:missing:"):
        path = predicate[17:].strip()
        if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]
        return not os.path.exists(path)
    elif predicate.startswith("artifact:exists:"):
        path = predicate[16:].strip()
        if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]
        return os.path.exists(path)
    elif predicate.startswith("contains:"):
        sub = predicate[9:].strip()
        if (sub.startswith('"') and sub.endswith('"')) or (sub.startswith("'") and sub.endswith("'")):
            sub = sub[1:-1]
        leading = input_data[:300]
        return sub in leading

    logger.warning(f"Unknown condition predicate: {predicate}")
    return True


def _emit_pipe_log(
    pipe_config: dict,
    event: str,
    node_name: str,
    tool_name: Optional[str],
    input_size: int,
    output_size: int,
    latency_ms: float,
    error: bool,
) -> None:
    logging_cfg = pipe_config.get("logging") or {}
    enabled = logging_cfg.get("enabled")
    
    is_enabled = enabled if enabled is not None else ("PIPE_LOG_LEVEL" in os.environ)
    if not is_enabled:
        return
        
    prefix = logging_cfg.get("prefix") or os.environ.get("PIPE_LOG_PREFIX", "[PIPE]")
    level = (logging_cfg.get("level") or os.environ.get("PIPE_LOG_LEVEL", "compact")).lower()
    
    if level == "compact" and event == "entry":
        return
        
    fields = logging_cfg.get("fields") or ["trigger", "node", "tokens", "timing"]
    
    parts = []
    for field in fields:
        if field == "trigger":
            if tool_name:
                parts.append(f"trigger:{tool_name}")
        elif field == "node":
            if event == "entry":
                parts.append(f"→ {node_name}")
            else:
                status_icon = "✗" if error else "✓"
                parts.append(f"{status_icon} {node_name}")
        elif field == "tokens":
            if event == "exit":
                delta = output_size - input_size
                reduction_pct = (delta / input_size * 100.0) if input_size > 0 else 0.0
                delta_sign = "+" if delta >= 0 else "-"
                parts.append(f"{input_size:,} → {output_size:,} chars ({delta_sign}{abs(delta):,} | {reduction_pct:.1f}%)")
        elif field == "timing":
            if event == "exit":
                latency_s = latency_ms / 1000.0
                timing_str = f"{latency_s:.2f}s" if latency_s < 1.0 else f"{latency_s:.1f}s"
                parts.append(timing_str)
                
    if parts:
        import sys
        sys.stderr.write(f"{prefix} {' | '.join(parts)}\n")
        sys.stderr.flush()


async def run_pipe(
    pipe_config: Dict[str, Any],
    input_data: str,
    tool_name: Optional[str] = None,
    agent_label: Optional[str] = None,
    server_registry: Dict[str, Any] | None = None,
    vars: Optional[Dict[str, str]] = None,
    manifest_path: Optional[str] = None,
) -> tuple[str, List[Dict[str, Any]]]:
    """Executes a chain of nodes and tracks context deltas with a timeout guard."""
    # 0. Early Bypass (Sift-Centric)
    if SIFT_SIGNATURE in input_data:
        return input_data, []

    started_at_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    try:
        run_vars = _build_vars(pipe_config, vars or {})
    except ValueError as exc:
        return f"--- [Context-Pipe: Variable Error] ---\n{exc}", []

    def write_manifest_if_needed(res: str, tr: list):
        m_path = manifest_path or pipe_config.get("manifest")
        if m_path:
            status = "fail" if (res.startswith("--- [Context-Pipe:") or res.startswith("Error") or "error" in (tr[-1] if tr else {})) else "pass"
            _write_manifest(m_path, pipe_config, run_vars, tr, res, status, started_at_str)

    current_input = input_data
    trace: List[Dict[str, Any]] = []

    # 1. Prepare Environment (Self-Aware Venv Path + Metadata)
    process_env = get_env_with_venv_path()
    for k, v in run_vars.items():
        process_env[k] = v

    if tool_name:
        process_env["SIFT_TOOL_NAME"] = tool_name
    if agent_label:
        process_env["SIFT_AGENT_LABEL"] = agent_label

    # ── DAG Traversal Engine ──
    ordered_nodes = []
    nodes_list = pipe_config.get("nodes", [])
    for i, node in enumerate(nodes_list):
        auto_id = f"__node_{i}__"
        node_id = node.get("id") or auto_id
        natural_next = None
        if i + 1 < len(nodes_list):
            next_node = nodes_list[i + 1]
            natural_next = next_node.get("id") or f"__node_{i+1}__"
        ordered_nodes.append((node_id, node, natural_next))

    # Parse branch_sequences top-level dict
    branch_seq_map = {}
    sequences = pipe_config.get("branch_sequences") or {}
    for seq_name, seq_nodes in sequences.items():
        seq_ordered = []
        for i, node in enumerate(seq_nodes):
            auto_id = f"__branch_{seq_name}_{i}__"
            node_id = node.get("id") or auto_id
            natural_next = None
            if i + 1 < len(seq_nodes):
                next_node = seq_nodes[i + 1]
                natural_next = next_node.get("id") or f"__branch_{seq_name}_{i+1}__"
            seq_ordered.append((node_id, node, natural_next))
        branch_seq_map[seq_name] = seq_ordered

    # Flatten into a lookup map: node_id -> (node_dict, natural_next_id)
    node_map = {}
    node_index_map = {}
    counter = 0
    for node_id, node, next_id in ordered_nodes:
        node_map[node_id] = (node, next_id)
        node_index_map[node_id] = counter
        counter += 1
    for seq_nodes in branch_seq_map.values():
        for node_id, node, next_id in seq_nodes:
            node_map[node_id] = (node, next_id)
            node_index_map[node_id] = counter
            counter += 1

    # Determine start node ID
    start_id = ordered_nodes[0][0] if ordered_nodes else None
    current_node_id = start_id
    step_count = 0
    max_steps = 100

    # Global timeout for the entire pipe execution (default 30s to allow model warmup)
    raw_timeout = os.environ.get("PIPE_NODE_TIMEOUT_MS", "30000")
    node_timeout = int(raw_timeout) / 1000.0

    while current_node_id is not None:
        if step_count >= max_steps:
            error_text = f"--- [Context-Pipe: Loop Guard] ---\nMaximum pipe execution steps ({max_steps}) exceeded. Possible infinite loop."
            write_manifest_if_needed(error_text, trace)
            return error_text, trace
        step_count += 1

        if current_node_id not in node_map:
            # Maybe it is a branch target referencing a sequence name
            if current_node_id in branch_seq_map:
                seq = branch_seq_map[current_node_id]
                if seq:
                    current_node_id = seq[0][0]
                    continue
            logger.warning(f"Unknown node ID: {current_node_id}")
            break

        node, natural_next = node_map[current_node_id]
        node_timeout_override = node.get("timeout")
        active_timeout = float(node_timeout_override) if node_timeout_override is not None else node_timeout

        # Check condition
        cond_str = node.get("condition")
        if cond_str:
            if not _evaluate_condition(cond_str, current_input):
                current_node_id = natural_next
                continue

        # Echo Guard: skip node if input was recently processed
        node_idx = node_index_map.get(current_node_id, 0)
        if check_echo(current_input, pipe_name=pipe_config.get("name", "unknown"), node_index=node_idx):
            current_node_id = natural_next
            continue

        node_type = node.get("type", "binary")
        is_optional = node.get("optional", False)

        node_name = node.get("cmd", "")
        if node_type == "mcp":
            node_name = f"mcp:{node.get('server')}/{node.get('tool')}"
        elif node_type == "script":
            node_name = f"script:{node.get('cmd')}"

        _emit_pipe_log(pipe_config, "entry", node_name, tool_name, 0, 0, 0.0, False)
        t_start = time.monotonic()

        if node_type == "mcp":
            # --- MCP tool path ---
            start_size = len(current_input)
            tee_path = None
            tee_config = node.get("tee")
            if tee_config:
                tee_path = _write_tee(tee_config, current_input, f"mcp:{node['server']}/{node['tool']}", tool_name)
            try:
                stdout = await _run_mcp_node(node, current_input, server_registry or {}, process_env)
            except asyncio.TimeoutError:
                latency_ms = (time.monotonic() - t_start) * 1000
                _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, 0, latency_ms, True)
                error_text = f"--- [Context-Pipe: Timeout] ---\nMCP node {node['server']}/{node['tool']} exceeded {active_timeout}s."
                trace.append({"node": f"mcp:{node['server']}/{node['tool']}", "error": "Timeout"})
                if is_optional:
                    current_node_id = natural_next
                    continue
                write_manifest_if_needed(error_text, trace)
                return error_text, trace
            except ValueError as exc:
                latency_ms = (time.monotonic() - t_start) * 1000
                _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, 0, latency_ms, True)
                error_text = f"--- [Context-Pipe: MCP Error] ---\n{exc}"
                trace.append({"node": f"mcp:{node['server']}/{node['tool']}", "error": str(exc)})
                if is_optional:
                    current_node_id = natural_next
                    continue
                write_manifest_if_needed(error_text, trace)
                return error_text, trace
            except Exception as exc:
                latency_ms = (time.monotonic() - t_start) * 1000
                _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, 0, latency_ms, True)
                error_text = f"--- [Context-Pipe: MCP Unexpected Error] ---\n{exc}"
                trace.append({"node": f"mcp:{node['server']}/{node['tool']}", "error": str(exc)})
                if is_optional:
                    current_node_id = natural_next
                    continue
                write_manifest_if_needed(error_text, trace)
                return error_text, trace

            end_size = len(stdout)
            entry = {
                "node": f"mcp:{node['server']}/{node['tool']}",
                "input_size": start_size,
                "output_size": end_size,
                "delta": end_size - start_size,
            }
            if tee_path is not None:
                entry["tee_path"] = tee_path
            trace.append(entry)
            current_input = stdout
            latency_ms = (time.monotonic() - t_start) * 1000
            _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, end_size, latency_ms, False)
            current_node_id = node.get("next") or natural_next
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
                raw_args = [py_script] + [str(a) for a in node.get("args", [])]
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
                latency_ms = (time.monotonic() - t_start) * 1000
                _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, end_size, latency_ms, False)
                current_input = stdout
                current_node_id = node.get("next") or natural_next
                continue
            else:
                # Fallback to binary resolution if script not found
                resolved_cmd = resolve_node_cmd(node["cmd"])
                raw_args = [str(a) for a in node.get("args", [])]
            
            cmd = resolve_placeholders([resolved_cmd] + raw_args, process_env)
        else:
            # --- Existing subprocess path ---
            resolved_cmd = resolve_node_cmd(node["cmd"])
            raw_args = [resolved_cmd] + [str(a) for a in node.get("args", [])]
            cmd = resolve_placeholders(raw_args, process_env)

        start_size = len(current_input)
        tee_config = node.get("tee")

        async def do_tee() -> Optional[str]:
            if tee_config:
                return await asyncio.to_thread(_write_tee, tee_config, current_input, node["cmd"], tool_name)
            return None

        async def do_process() -> tuple[str, str, int, Optional[str]]:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=process_env,
                )

                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        process.communicate(input=current_input.encode("utf-8", errors="replace")),
                        timeout=active_timeout
                    )
                except asyncio.TimeoutError:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    stdout_bytes, stderr_bytes = await process.communicate()
                    return "", "", -1, "Timeout"

                return (
                    stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else "",
                    stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "",
                    process.returncode if process.returncode is not None else 0,
                    None
                )
            except FileNotFoundError:
                return "", "", -1, "FileNotFound"
            except Exception as e:
                return "", "", -1, f"Unexpected error: {str(e)}"

        tee_result, proc_result = await asyncio.gather(do_tee(), do_process())
        tee_path = tee_result
        stdout, stderr, returncode, err_reason = proc_result
        latency_ms = (time.monotonic() - t_start) * 1000

        if err_reason == "Timeout":
            _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, 0, latency_ms, True)
            error_text = f"--- [Context-Pipe: Timeout] ---\nNode {node['cmd']} exceeded {active_timeout}s."
            trace.append({"node": node["cmd"], "error": "Timeout"})
            if is_optional:
                current_node_id = natural_next
                continue
            write_manifest_if_needed(error_text, trace)
            return error_text, trace
        elif err_reason == "FileNotFound":
            _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, 0, latency_ms, True)
            help_msg = node.get("help_msg", f"Command '{node['cmd']}' not found in system PATH.")
            error_text = f"--- [Context-Pipe: Dependency Error] ---\n{help_msg}"
            trace.append({"node": node["cmd"], "error": "FileNotFound"})
            if is_optional:
                current_node_id = natural_next
                continue
            write_manifest_if_needed(error_text, trace)
            return error_text, trace
        elif err_reason:
            _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, 0, latency_ms, True)
            error_text = f"--- [Context-Pipe: Error] ---\n{err_reason}"
            trace.append({"node": node["cmd"], "error": err_reason})
            if is_optional:
                current_node_id = natural_next
                continue
            write_manifest_if_needed(error_text, trace)
            return error_text, trace

        # ── Validator Node Branching logic ──
        if node_type == "validator":
            branches = node.get("branches")
            if branches:
                code_key = str(returncode)
                branch_target = branches.get(code_key) or branches.get("default")
                if branch_target:
                    _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, len(stdout), latency_ms, False)
                    entry = {
                        "node": node["cmd"],
                        "exit_code": returncode,
                        "branch": branch_target,
                    }
                    if tee_path is not None:
                        entry["tee_path"] = tee_path
                    trace.append(entry)
                    if stdout:
                        current_input = stdout
                    current_node_id = branch_target
                    continue
                else:
                    _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, 0, latency_ms, True)
                    error_text = f"Error in node {node['cmd']}: Validator exited {returncode} with no matching branch"
                    trace.append({"node": node["cmd"], "error": f"Validator exited {returncode} with no matching branch"})
                    if is_optional:
                        current_node_id = natural_next
                        continue
                    write_manifest_if_needed(error_text, trace)
                    return error_text, trace

        if returncode != 0:
            _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, 0, latency_ms, True)
            trace.append({"node": node["cmd"], "error": stderr.strip()})
            if is_optional:
                current_node_id = natural_next
                continue
            error_text = f"Error in node {node['cmd']}: {stderr}"
            write_manifest_if_needed(error_text, trace)
            return error_text, trace

        end_size = len(stdout)
        entry = {
            "node": node["cmd"],
            "input_size": start_size,
            "output_size": end_size,
            "delta": end_size - start_size,
        }
        if tee_path is not None:
            entry["tee_path"] = tee_path
        trace.append(entry)

        _emit_pipe_log(pipe_config, "exit", node_name, tool_name, start_size, end_size, latency_ms, False)
        current_input = stdout
        current_node_id = node.get("next") or natural_next

    write_manifest_if_needed(current_input, trace)
    return current_input, trace

def load_config(config_path: str = "pipes.json") -> Dict[str, Any]:
    """
    Loads ``pipes.json`` with a robust traversal discovery.

    Resolution order:
    1. ``config_path`` as given (absolute or relative to CWD).
    2. Upward traversal from CWD until ``pipes.json`` or ``.git`` is found.
    3. The package root directory (parent of ``context_pipe/``).

    Returns an empty scaffold if the file is not found.
    """
    config: Dict[str, Any] = {"pipes": [], "mappings": []}
    search_paths = [config_path]
    
    # 2. Upward Traversal Discovery
    if not os.path.isabs(config_path):
        curr = os.path.abspath(os.getcwd())
        while True:
            candidate = os.path.join(curr, config_path)
            if os.path.exists(candidate):
                search_paths.append(candidate)
                break
            # Stop at root or .git boundary
            if os.path.exists(os.path.join(curr, ".git")):
                break
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent

    # 3. Package Root Fallback
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


def _reconfigure_io() -> None:
    """Forces stdout/stderr to UTF-8 on Windows to prevent emoji rendering crashes."""
    import sys
    if os.name == "nt":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="surrogateescape")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="surrogateescape")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="surrogateescape")


def main():
    _reconfigure_io()
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
                print(f"  Hook Fallbacks: {sheet['fallback_events']} (pipe failed; raw input passed through)")
            if sheet.get("unmapped_events", 0) > 0:
                print(f"  Unmapped Heavy Calls: {sheet['unmapped_events']} (leaking raw tokens; update pipes.json)")
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
