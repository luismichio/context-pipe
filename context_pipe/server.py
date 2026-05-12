# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import time
import uuid
from typing import Optional
from mcp.server.fastmcp import FastMCP
from .orchestrator import run_pipe, CPP_SIGNATURE
from .telemetry import get_balance_sheet, log_telemetry, generate_audit_header
from .platforms import detect_client_id
from .onboarding import inject_hooks, verify_installation, resolve_pipes_config, inject_shell_aliases, remove_shell_aliases
from .a2a import pipe_agent_handoff as _pipe_agent_handoff
from .dynamic import run_dynamic_pipe
from .shadow import list_shadow_tools
from . import config_loader

# Initialize FastMCP server
mcp = FastMCP("Context-Pipe")

# Session Identity
SESSION_ID = f"mcp-{uuid.uuid4().hex[:8]}"
START_TIME = time.ctime()

# Configuration
CONFIG_PATH = os.environ.get("PIPE_CONFIG_PATH", "pipes.json")


def load_config() -> dict:
    return config_loader.load_pipes_config(CONFIG_PATH)


@mcp.tool()
def list_pipes() -> str:
    """Lists all available context pipes and their descriptions."""
    config = load_config()
    pipes = config.get("pipes", [])
    if not pipes:
        return f"No pipes configured.\n\n{CPP_SIGNATURE}"

    summary = ["Available Context Pipes:"]
    for p in pipes:
        summary.append(f"- {p['name']}: {p.get('description', 'No description')}")

    return "\n".join(summary) + f"\n\n{CPP_SIGNATURE}"


@mcp.tool()
async def pipe_run(pipe_name: str, input_text: str) -> str:
    """
    Executes a specific context pipe on the provided input text.

    Args:
        pipe_name: The name of the pipe to run (e.g., 'standard-distill', 'semantic-refinery').
        input_text: The raw text to be processed through the pipe.
    """
    config = load_config()
    pipe = next((p for p in config.get("pipes", []) if p["name"] == pipe_name), None)

    if not pipe:
        return f"Error: Pipe '{pipe_name}' not found.\n\n{CPP_SIGNATURE}"

    start_t = time.time()
    try:
        result, trace = await run_pipe(pipe, input_text)
        latency_ms = (time.time() - start_t) * 1000

        # Log Telemetry for ROI tracking
        platform = detect_client_id()
        log_telemetry(
            session_id=SESSION_ID,
            start_time=START_TIME,
            pipe_name=pipe_name,
            tool_name="mcp:pipe_run",
            original_size=len(input_text),
            final_size=len(result),
            latency_ms=latency_ms,
            platform=platform,
        )

        # Prepend Audit Header
        header = generate_audit_header(pipe_name, trace, latency_ms)
        return f"{header}{result}\n\n{CPP_SIGNATURE}"

    except Exception as e:
        return f"Error executing pipe: {str(e)}\n\n{CPP_SIGNATURE}"


def _resolve_safe_path(path: str) -> str:
    """Validates the path is within the allowed workspace."""
    import os

    allow_global = os.environ.get("SIFT_ALLOW_GLOBAL_READS", "false").lower() == "true"
    resolved_path = os.path.realpath(path)

    if allow_global:
        return resolved_path

    workspace_root = os.environ.get("SIFT_WORKSPACE_ROOT", os.getcwd())
    if not resolved_path.startswith(os.path.realpath(workspace_root)):
        raise PermissionError(
            f"Access denied for path: {path}. Use a file path inside the current workspace or set SIFT_ALLOW_GLOBAL_READS=true to override."
        )

    return resolved_path


@mcp.tool()
async def pipe_read_file(path: str, pipe_name: str = "standard-distill") -> str:
    """
    Reads a local file safely and streams it directly through a context pipe.
    Use this instead of native file readers to prevent context window flooding.

    Args:
        path: Absolute or relative path to the file.
        pipe_name: The name of the pipe to run (e.g., 'standard-distill', 'full-refinery').
    """
    try:
        resolved_path = _resolve_safe_path(path)
        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}\n\n{CPP_SIGNATURE}"

    return await pipe_run(pipe_name, content)


@mcp.tool()
def pipe_analyze_file(path: str) -> str:
    """
    Analyzes a file's size and structure to recommend the optimal context pipe,
    without flooding the context window.

    Call this BEFORE pipe_read_file when you are unsure which pipe to use.
    The recommendation tells you exactly which pipe_name to pass to pipe_read_file.

    Decision guide:
      - < 10KB  → 'standard-distill'  (fast heuristic sifting)
      - >= 10KB → 'semantic-refinery' (neural compression)

    Args:
        path: Absolute or relative path to the file.
    """
    try:
        resolved_path = _resolve_safe_path(path)
        size = os.path.getsize(resolved_path)
    except Exception as e:
        return f"Error analyzing file: {str(e)}\n\n{CPP_SIGNATURE}"

    recommendation = "standard-distill"
    if size > 10000:
        recommendation = "semantic-refinery"

    return f"File: {os.path.basename(path)}\nSize: {size} bytes\nRecommendation: Use pipe_read_file with pipe_name='{recommendation}'.\n\n{CPP_SIGNATURE}"


@mcp.tool()
def get_pipe_stats() -> str:
    """Returns the Context Balance Sheet (ROI) for the entire pipeline ecosystem."""
    sheet = get_balance_sheet()

    # Format the Net Change string
    net_label = "Saved" if sheet["net_change"] < 0 else "Added"

    return f"""
## 📊 Context-Pipe Balance Sheet

- **Signal Injected (Augmentation):** +{sheet["signal_added"]:,} chars
- **Noise Incinerated (Reduction):** -{sheet["noise_removed"]:,} chars
- **Net Context {net_label}:** {abs(sheet["net_change"]):,} chars
- **Platform Events:** {sheet["total_events"]}
- **Avg Node Latency:** {sheet["avg_latency_ms"]:.2f}ms

{CPP_SIGNATURE}
    """


@mcp.tool()
def pipe_verify() -> str:
    """
    Verifies the context-pipe + semantic-sift installation health.
    Reports what is working, what is missing, and how to fix it.
    Automatically resolves and links semantic-sift-cli in pipes.json if found.
    """
    # Auto-resolve pipes.json nodes first
    pipes_path = CONFIG_PATH
    resolve_result = resolve_pipes_config(pipes_path)

    report = verify_installation(pipes_path)

    lines = ["## Context-Pipe Installation Report", ""]

    # context-pipe
    cp = report["context_pipe"]
    lines.append(f"{'✅' if cp['ok'] else '❌'} **context-pipe**: {cp['detail']}")

    # pipes.json
    pc = report["pipes_config"]
    lines.append(f"{'✅' if pc['ok'] else '❌'} **pipes.json** (`{pc['path']}`): {pc['detail']}")

    # semantic-sift
    ss = report["semantic_sift"]
    if ss["ok"]:
        lines.append(f"✅ **semantic-sift-cli**: {ss['version']} — `{ss['path']}`")
        if resolve_result["updated"]:
            lines.append("   > pipes.json nodes updated to use absolute path.")
    else:
        lines.append(f"❌ **semantic-sift-cli**: {ss['detail']}")

    # node resolution
    if report["nodes"]:
        lines.append("")
        lines.append("### Pipe Node Resolution")
        for node in report["nodes"]:
            icon = "✅" if node["ok"] else "❌"
            resolved = f"`{node['resolved']}`" if node["resolved"] else "not found in PATH"
            lines.append(f"{icon} `{node['cmd']}` → {resolved}")

    # overall
    lines.append("")
    if report["overall"]:
        lines.append("**Overall: ✅ All systems operational.**")
    else:
        lines.append("**Overall: ❌ Action required — see items above.**")

    return "\n".join(lines) + f"\n\n{CPP_SIGNATURE}"


@mcp.tool()
def pipe_audit_last() -> str:
    """
    Returns the absolute last recorded telemetry event for manual auditing.
    Use this to 'Trust but Verify' that the context reduction reported in
    an audit header matches the actual data committed to the ledger.
    """
    from .telemetry import get_latest_telemetry
    last = get_latest_telemetry()
    if not last:
        return f"No telemetry events found in the ledger.\n\n{CPP_SIGNATURE}"

    reduction = (1 - (last["final_chars"] / last["original_chars"])) * 100 if last["original_chars"] > 0 else 0

    return f"""
## 🔍 Context-Pipe Audit: Last Event

- **Tool Call:** `{last['tool_key']}`
- **Original Size:** {last['original_chars']:,} chars
- **Final Size:** {last['final_chars']:,} chars
- **Net Reduction:** {reduction:.1f}%
- **Latency:** {last['total_latency_ms']:.1f}ms
- **Platform:** {last['platform']}
- **Agent Label:** {last['agent']}
- **Session ID:** `{last['session_id']}`

{CPP_SIGNATURE}
    """


@mcp.tool()
def pipe_onboard(environment: str, target_dir: Optional[str] = None) -> str:
    """
    Initializes Context-Pipe hooks and commands in the current project.

    Args:
        environment: The IDE/CLI environment (e.g., 'Cursor', 'VSCode', 'Gemini').
        target_dir: Optional directory to onboard. Defaults to current directory.
    """
    path = target_dir or os.getcwd()
    actions = inject_hooks(path, environment)
    if not actions:
        return f"Context-Pipe is already active or no targets found in {path}.\n\n{CPP_SIGNATURE}"

    return "Onboarding Successful:\n" + "\n".join([f"- {a}" for a in actions]) + f"\n\n{CPP_SIGNATURE}"


@mcp.tool()
def pipe_agent_handoff(
    output: str,
    pipe_name: str = "",
    from_agent: str = "",
    to_agent: str = "",
) -> str:
    """
    Distil Agent A's output before passing it to Agent B's context window.

    ALWAYS call this at agent-to-agent handoff boundaries to prevent context
    flooding regardless of framework (CrewAI, Google ADK, LangGraph, custom).
    Returns unchanged output on any error — the agent chain is never interrupted.

    When to call:
      - Any time one agent's output becomes another agent's input.
      - Before injecting a tool's large response into a subagent prompt.
      - At task boundaries in multi-step agentic workflows.

    Routing:
      - Pass pipe_name explicitly when you know the content type
        (e.g. pipe_name="semantic-refinery" for code/docs,
               pipe_name="standard-distill" for logs).
      - Omit pipe_name to let pipes.json mappings decide automatically.

    Args:
        output:     The raw output from Agent A.
        pipe_name:  Optional explicit pipe name. Auto-routed if omitted.
        from_agent: Label for the producing agent (e.g. 'researcher'). Used for telemetry.
        to_agent:   Label for the consuming agent (e.g. 'writer'). Used for telemetry.

    Returns:
        Distilled text safe to inject into Agent B's context.
        Returns original output unchanged on any error.
    """
    return _pipe_agent_handoff(
        output=output,
        pipe_name=pipe_name or None,
        from_agent=from_agent or None,
        to_agent=to_agent or None,
    ) + f"\n\n{CPP_SIGNATURE}"


@mcp.prompt()
def pipe_dashboard() -> str:
    """Returns a dashboard overview of the current context-pipe configuration."""
    return f"""
# ⛓️ Context-Pipe Dashboard

You are currently connected to the Context-Pipe Orchestrator.

## Active Pipes
{list_pipes()}

## Current ROI (Balance Sheet)
{get_pipe_stats()}

## Instructions
To protect your context window, always consider streaming large tool outputs through the optimal pipe.

{CPP_SIGNATURE}
    """


@mcp.tool()
async def pipe_run_dynamic(nodes_json: str, input_text: str, allow_shell: bool = False) -> str:
    """
    Executes an ad-hoc context pipe defined as a JSON array of node objects.
    Use this when no named pipe in pipes.json fits and you need to compose a
    one-off processing graph on the fly.

    Mandatory workflow — always follow this sequence:
      1. Call pipe_list_shadow_tools() to discover available nodes.
      2. Construct nodes_json from those capabilities.
      3. Call this tool.

    Rules for nodes_json:
      - Every array MUST end with a sifting node to guarantee context safety:
        [{"cmd": "semantic-sift-cli", "args": ["semantic"]}]
      - Shell utilities (grep, awk, jq, rg, etc.) require allow_shell=True.
      - Never put shell metacharacters (|, ;, &, $, `) in a cmd value — use args[] instead.
      - Each node must have a "cmd" key; "args" is optional.

    Examples:
      Filter errors then distil:
        nodes_json = '[{"cmd":"grep","args":["ERROR"]},{"cmd":"semantic-sift-cli","args":["logs"]}]'
        allow_shell = True

      Process JSON then distil:
        nodes_json = '[{"cmd":"jq","args":[".[]"]},{"cmd":"semantic-sift-cli","args":["semantic"]}]'
        allow_shell = True

      Single-node distil (no shell required):
        nodes_json = '[{"cmd":"semantic-sift-cli","args":["semantic","--rate","0.4"]}]'

    Args:
        nodes_json:  JSON array of node objects. Each must have "cmd"; "args" is optional.
        input_text:  The raw text to process through the graph.
        allow_shell: When True, shell utilities from SHELL_UTILITY_ALLOWLIST are permitted.
                     The final node MUST be semantic-sift-cli. Default False.
    """
    try:
        nodes = json.loads(nodes_json)
    except json.JSONDecodeError as exc:
        return f"Error: nodes_json is not valid JSON — {exc}\n\n{CPP_SIGNATURE}"

    start_t = time.time()
    try:
        result, trace = await run_dynamic_pipe(nodes, input_text, allow_shell=allow_shell)
        latency_ms = (time.time() - start_t) * 1000
        platform = detect_client_id()
        log_telemetry(
            session_id=SESSION_ID,
            start_time=START_TIME,
            pipe_name="dynamic",
            tool_name="mcp:pipe_run_dynamic",
            original_size=len(input_text),
            final_size=len(result),
            latency_ms=latency_ms,
            platform=platform,
        )
        header = generate_audit_header("dynamic", trace, latency_ms)
        return f"{header}{result}\n\n{CPP_SIGNATURE}"
    except ValueError as exc:
        return f"Error: {exc}\n\n{CPP_SIGNATURE}"
    except Exception as exc:
        return f"Error executing dynamic pipe: {exc}\n\n{CPP_SIGNATURE}"


@mcp.tool()
def pipe_list_shadow_tools() -> str:
    """
    Lists all available context-processing tools: configured pipes from pipes.json
    and well-known CLI tools discovered on PATH (jq, yq, markitdown, pandoc, rg, fd, bat).

    ALWAYS call this before pipe_run_dynamic to discover what nodes are available
    for constructing an ad-hoc processing graph. This is the just-in-time RAG
    step that ensures your nodes_json references real, resolvable commands.

    Workflow:
      1. pipe_list_shadow_tools()          ← discover available nodes
      2. Construct nodes_json array        ← must end with semantic-sift-cli
      3. pipe_run_dynamic(nodes_json, ...) ← execute the graph
    """
    tools = list_shadow_tools(CONFIG_PATH)
    if not tools:
        return f"No context-processing tools found (no pipes.json and no known CLI tools on PATH).\n\n{CPP_SIGNATURE}"

    lines = ["| Name | Source | Description | Nodes |", "|---|---|---|---|"]
    for t in tools:
        nodes_str = ", ".join(f"`{n}`" for n in t["nodes"]) if t["nodes"] else "—"
        lines.append(f"| {t['name']} | {t['source']} | {t['description']} | {nodes_str} |")

    return "\n".join(lines) + f"\n\n{CPP_SIGNATURE}"


@mcp.tool()
def pipe_install_aliases(shells: str = "") -> str:
    """
    Installs the cpipe shell alias into the user's profile file(s).

    cpipe is a convenience alias for mcp-pipe. On POSIX systems it is added
    to ~/.bashrc and/or ~/.zshrc; on Windows it targets the PowerShell profile.
    Safe to run multiple times — the alias block is idempotently updated.

    Args:
        shells: Optional space-separated list of shells to target
                (bash, zsh, pwsh). Leave empty for platform auto-detection.
    """
    shell_list = shells.split() if shells.strip() else None
    results = inject_shell_aliases(shells=shell_list)
    if not results:
        return f"cpipe alias already up-to-date — no profile files were modified.\n\n{CPP_SIGNATURE}"
    lines = ["cpipe alias installed:"] + [f"  - {r}" for r in results]
    lines.append("\nRestart your shell (or source the profile) to activate `cpipe`.")
    return "\n".join(lines) + f"\n\n{CPP_SIGNATURE}"


@mcp.tool()
def pipe_remove_aliases() -> str:
    """
    Removes the managed cpipe alias block from all known shell profile files.

    Safe to call before installing the Phase 8 Rust cpipe binary, which
    takes over the name without requiring an alias.
    """
    results = remove_shell_aliases()
    if not results:
        return f"No cpipe alias block found in any profile — nothing removed.\n\n{CPP_SIGNATURE}"
    return "cpipe alias removed:\n" + "\n".join(f"  - {r}" for r in results) + f"\n\n{CPP_SIGNATURE}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
