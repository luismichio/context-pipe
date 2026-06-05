# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
import os
import json
import time
import uuid
from typing import Optional
from mcp.server.fastmcp import FastMCP, Context
from .orchestrator import run_pipe
from .telemetry import get_balance_sheet, log_telemetry
from .platforms import detect_client_id
from .onboarding import inject_hooks, verify_installation, resolve_pipes_config, inject_shell_aliases, remove_shell_aliases
from .a2a import pipe_agent_handoff as _pipe_agent_handoff
from .dynamic import run_dynamic_pipe
from .shadow import list_shadow_tools
from . import config_loader
import logging

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Context-Pipe")

# Session Identity
SESSION_ID = f"mcp-{uuid.uuid4().hex[:8]}"
START_TIME = time.ctime()

# Configuration
CONFIG_PATH = os.environ.get("PIPE_CONFIG_PATH", "pipes.json")


def load_config(config_path: Optional[str] = None) -> dict:
    path = config_path or CONFIG_PATH
    return config_loader.load_pipes_config(path)


def _find_config_upward(file_path: str) -> Optional[str]:
    """Finds pipes.json by walking up the directory tree from file_path."""
    try:
        curr = os.path.dirname(os.path.abspath(file_path))
        while True:
            candidate = os.path.join(curr, "pipes.json")
            if os.path.exists(candidate):
                return candidate
            if os.path.exists(os.path.join(curr, ".pipe_identity")):
                return os.path.join(curr, "pipes.json")
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent
    except Exception:
        pass
    return None


@mcp.tool()
def list_pipes(config_path: Optional[str] = None) -> str:
    """Lists all available context pipes and their descriptions."""
    config = load_config(config_path)
    pipes = config.get("pipes", [])
    if not pipes:
        return "No pipes configured.\n"
    summary = ["Available Context Pipes:"]
    for p in pipes:
        summary.append(f"- {p['name']}: {p.get('description', 'No description')}")
    return "\n".join(summary)


@mcp.tool()
async def pipe_run(
    pipe_name: str,
    input_text: str,
    vars: Optional[dict] = None,
    manifest_path: Optional[str] = None,
    config_path: Optional[str] = None,
) -> str:
    """
    Executes a specific context pipe on the provided input text.
    Args:
        pipe_name:     The name of the pipe to run (e.g., 'standard-distill', 'semantic-refinery').
        input_text:    The raw text to be processed through the pipe.
        vars:          Optional key-value pairs for variable substitution.
        manifest_path: Optional path to write a run manifest JSON.
        config_path:   Optional path to pipes.json.
    """
    config = load_config(config_path)
    pipe = next((p for p in config.get("pipes", []) if p["name"] == pipe_name), None)
    if not pipe:
        return f"Error: Pipe '{pipe_name}' not found.\n"

    start_t = time.time()
    try:
        result, trace = await run_pipe(pipe, input_text, vars=vars, manifest_path=manifest_path, config_path=config_path)
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
            config_path=config_path,
        )

        # Silent Orchestrator: No headers or signatures added here.
        # Identity and headers are now handled by engine nodes.
        return result
    except Exception as e:
        return f"Error executing pipe: {str(e)}\n"


async def _resolve_safe_path(path: str, ctx: Optional[Context] = None, config_path: Optional[str] = None) -> str:
    """Validates the path is within the authorized workspace roots.

    Roots are sourced from (in merge order):
    1. ``PIPE_AUTHORIZED_ROOT`` env var (client-injected, semicolon-separated).
    2. ``authorized_roots`` key in the pipes config file (pipes.json).
    3. MCP session roots reported by the client.
    4. CWD fallback when no roots are provided.
    """
    import os
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    resolved_path = os.path.realpath(path)
    workspace_roots: list[str] = []

    # 1. Env-var roots (may be overridden/narrowed by the client at spawn time).
    if os.environ.get("PIPE_AUTHORIZED_ROOT"):
        for part in os.environ["PIPE_AUTHORIZED_ROOT"].split(os.pathsep):
            part = part.strip()
            if part:
                workspace_roots.append(os.path.realpath(part))

    # 2. Config-file roots  survives client env-var override because the
    #    client can only inject env vars, not rewrite file contents.
    try:
        cfg = load_config(config_path)
        for root in cfg.get("authorized_roots", []):
            root = root.strip()
            if root:
                workspace_roots.append(os.path.realpath(root))
    except Exception as e:
        logger.warning(f"Could not load authorized_roots from config: {e}")

    if ctx and hasattr(ctx, "session"):
        try:
            roots_result = await ctx.session.list_roots()
            if roots_result and hasattr(roots_result, "roots"):
                for r in roots_result.roots:
                    parsed = urlparse(str(r.uri))
                    local_path = url2pathname(parsed.path)
                    workspace_roots.append(os.path.realpath(local_path))
        except Exception as e:
            logger.warning(f"Failed to fetch roots from client: {e}")

    # Fallback to CWD if no roots provided by client
    if not workspace_roots:
        workspace_roots = [os.path.realpath(os.getcwd())]

    for root in workspace_roots:
        if resolved_path.startswith(root):
            return resolved_path

    raise PermissionError(
        f"Access denied for path: {path}. The path must be within the authorized workspace roots."
    )


@mcp.tool()
async def pipe_read_file(
    path: str,
    pipe_name: str = "standard-distill",
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    ctx: Optional[Context] = None,
    config_path: Optional[str] = None,
) -> str:
    """
    Reads a local file safely and streams it directly through a context pipe.
    Supports reading a specific range of lines (start_line to end_line, 1-indexed).
    Use this instead of native file readers to prevent context window flooding.

    Args:
        path: Absolute or relative path to the file.
        pipe_name: The name of the pipe to run (e.g., 'standard-distill', 'full-refinery').
        start_line: 1-indexed start line (inclusive).
        end_line: 1-indexed end line (inclusive).
        config_path: Optional path to pipes.json.
    """
    try:
        resolved_path = await _resolve_safe_path(path, ctx, config_path=config_path)

        if not config_path:
            config_path = _find_config_upward(resolved_path)

        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            if start_line is not None or end_line is not None:
                lines = f.readlines()
                start_idx = (start_line - 1) if start_line is not None else 0
                end_idx = end_line if end_line is not None else len(lines)
                start_idx = max(0, min(start_idx, len(lines)))
                end_idx = max(0, min(end_idx, len(lines)))
                content = "".join(lines[start_idx:end_idx])
            else:
                content = f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}\n"
    return await pipe_run(pipe_name, content, config_path=config_path)


@mcp.tool()
async def pipe_analyze_file(
    path: str,
    ctx: Optional[Context] = None,
    config_path: Optional[str] = None,
) -> str:
    """
    Analyzes a file's size and structure to recommend the optimal context pipe,
    without flooding the context window.
    Call this BEFORE pipe_read_file when you are unsure which pipe to use.
    The recommendation tells you exactly which pipe_name to pass to pipe_read_file.
    Decision guide:
      - < 10KB  -> 'standard-distill'  (fast heuristic sifting)
      - >= 10KB -> 'semantic-refinery' (neural compression)
    Args:
        path: Absolute or relative path to the file.
        config_path: Optional path to pipes.json.
    """
    try:
        resolved_path = await _resolve_safe_path(path, ctx, config_path=config_path)
        size = os.path.getsize(resolved_path)
    except Exception as e:
        return f"Error analyzing file: {str(e)}\n"

    recommendation = "standard-distill"
    if size > 10000:
        recommendation = "semantic-refinery"

    return f"File: {os.path.basename(path)}\nSize: {size} bytes\nRecommendation: Use pipe_read_file with pipe_name='{recommendation}'."


@mcp.tool()
def get_pipe_stats(
    session_id: Optional[str] = None,
    last_hours: Optional[float] = None,
    config_path: Optional[str] = None,
) -> str:
    """Returns the Context Balance Sheet (ROI) for the entire pipeline ecosystem.

    Args:
        session_id: Optional session ID to filter stats to a specific run.
        last_hours: Optional number of hours to look back (e.g. 1.0 for last hour, 24.0 for last day).
        config_path: Optional path to pipes.json.
    """
    sheet = get_balance_sheet(session_id=session_id, last_hours=last_hours, config_path=config_path)
    # Format the Net Change string
    net_label = "Saved" if sheet["net_change"] < 0 else "Added"
    return f"""
##  Context-Pipe Balance Sheet
- **Signal Injected (Augmentation):** +{sheet["signal_added"]:,} chars
- **Noise Incinerated (Reduction):** -{sheet["noise_removed"]:,} chars
- **Net Context {net_label}:** {abs(sheet["net_change"]):,} chars
- **Platform Events:** {sheet["total_events"]}
- **Avg Node Latency:** {sheet["avg_latency_ms"]:.2f}ms
"""


@mcp.tool()
def pipe_verify(config_path: Optional[str] = None) -> str:
    """
    Verifies the context-pipe + semantic-sift installation health.
    Reports what is working, what is missing, and how to fix it.
    Automatically resolves and links semantic-sift-cli in pipes.json if found.
    """
    # Auto-resolve pipes.json nodes first
    pipes_path = config_path or CONFIG_PATH
    resolve_result = resolve_pipes_config(pipes_path)
    report = verify_installation(pipes_path)

    lines = ["## Context-Pipe Installation Report", ""]

    # context-pipe
    cp = report["context_pipe"]
    lines.append(f"{'' if cp['ok'] else ''} **context-pipe**: {cp['detail']}")

    # pipes.json
    pc = report["pipes_config"]
    lines.append(f"{'' if pc['ok'] else ''} **pipes.json** (`{pc['path']}`): {pc['detail']}")

    # semantic-sift
    ss = report["semantic_sift"]
    if ss["ok"]:
        lines.append(f" **semantic-sift-cli**: {ss['version']}  `{ss['path']}`")
        if resolve_result["updated"]:
            lines.append("   > pipes.json nodes updated to use absolute path.")
    else:
        lines.append(f" **semantic-sift-cli**: {ss['detail']}")

    # node resolution
    if report["nodes"]:
        lines.append("")
        lines.append("### Pipe Node Resolution")
        for node in report["nodes"]:
            icon = "" if node["ok"] else ""
            resolved = f"`{node['resolved']}`" if node["resolved"] else "not found in PATH"
            lines.append(f"{icon} `{node['cmd']}` -> {resolved}")

    # overall
    lines.append("")
    if report.get("update_warning"):
        lines.append(report["update_warning"])
        lines.append("")

    if report["overall"]:
        lines.append("**Overall:  All systems operational.**")
    else:
        lines.append("**Overall:  Action required  see items above.**")

    return "\n".join(lines)


@mcp.tool()
def pipe_audit_last(limit: int = 1) -> str:
    """
    Returns the last recorded telemetry event(s) for manual auditing.
    Use this to 'Trust but Verify' that the context reduction reported in
    an audit header matches the actual data committed to the ledger.

    Args:
        limit: The number of recent events to retrieve (default 1).
    """
    from .telemetry import get_recent_telemetry
    events = get_recent_telemetry(limit=limit)
    if not events:
        return "No telemetry events found in the ledger.\n"

    lines = [f"##  Context-Pipe Audit (Last {len(events)} Events)"]
    for i, last in enumerate(events):
        reduction = (1 - (last["final_chars"] / last["original_chars"])) * 100 if last["original_chars"] > 0 else 0
        lines.append(f"""
### Event {i+1}
- **Tool Call:** `{last['tool_key']}`
- **Original Size:** {last['original_chars']:,} chars
- **Final Size:** {last['final_chars']:,} chars
- **Net Reduction:** {reduction:.1f}%
- **Latency:** {last['latency_ms']:.1f}ms
- **Platform:** {last['platform']}
- **Agent Label:** {last['agent']}
- **Session ID:** `{last['session_id']}`
""")
    return "\n".join(lines)


@mcp.tool()
def pipe_onboard(environment: Optional[str] = None, target_dir: Optional[str] = None) -> str:
    """
    Initializes Context-Pipe hooks and commands in the current project.
    Args:
        environment: The IDE/CLI environment (e.g., 'Cursor', 'VSCode', 'Gemini').
                     If omitted, auto-detection is performed.
        target_dir:  Optional directory to onboard. Defaults to current directory.
    """
    path = target_dir or os.getcwd()
    env = environment
    if not env:
        env = detect_client_id()
        logger.info(f"Auto-detected environment for onboarding: {env}")

    actions = inject_hooks(path, env)
    if not actions:
        return f"Context-Pipe is already active or no targets found in {path} (Environment: {env}).\n"
    return f"Onboarding Successful (Environment: {env}):\n" + "\n".join([f"- {a}" for a in actions])



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
    Returns unchanged output on any error  the agent chain is never interrupted.

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
    )


@mcp.prompt()
def pipe_dashboard() -> str:
    """Returns a dashboard overview of the current context-pipe configuration."""
    return f"""
#  Context-Pipe Dashboard
You are currently connected to the Context-Pipe Orchestrator.

## Active Pipes
{list_pipes()}

## Current ROI (Balance Sheet)
{get_pipe_stats()}

## Instructions
To protect your context window, always consider streaming large tool outputs through the optimal pipe.
"""


@mcp.tool()
async def pipe_run_dynamic(nodes_json: str, input_text: str, allow_shell: bool = False, config_path: Optional[str] = None) -> str:
    """
    Executes an ad-hoc context pipe defined as a JSON array of node objects.
    
    IMPORTANT: ALWAYS prefer this over running raw terminal command pipes (e.g., using grep, jq, rg)
    via shell execution. Raw shell commands dump all intermediate outputs directly into your main
    context window, causing context flooding. This tool executes the pipeline in a safe background
    subprocess, ensuring only the final, highly-sifted output is returned to your context.

    Mandatory workflow - always follow this sequence:
      1. Call pipe_list_shadow_tools() to discover available nodes.
      2. Construct nodes_json from those capabilities.
      3. Call this tool.

    Rules for nodes_json:
      - Every array MUST end with a sifting node to guarantee context safety:
        [{"cmd": "semantic-sift-cli", "args": ["semantic"]}]
      - Shell utilities (grep, awk, jq, rg, etc.) require allow_shell=True.
      - Never put shell metacharacters (|, ;, &, $, `) in a cmd value - use args[] instead.
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
        config_path: Optional path to pipes.json.
    """
    try:
        nodes = json.loads(nodes_json)
    except json.JSONDecodeError as exc:
        return f"Error: nodes_json is not valid JSON  {exc}\n"

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
            config_path=config_path,
        )

        return result
    except ValueError as exc:
        return f"Error: {exc}\n"
    except Exception as exc:
        return f"Error executing dynamic pipe: {exc}\n"


@mcp.tool()
def pipe_list_shadow_tools(config_path: Optional[str] = None) -> str:
    """
    Lists all available context-processing capabilities, including configured pipes from pipes.json
    and well-known CLI tools discovered on the system PATH (e.g., jq, yq, markitdown, pandoc, rg, fd, bat).

    ALWAYS call this before composing custom pipelines (with pipe_run_dynamic) to discover what 
    processing nodes are available on the current host. This provides just-in-time discovery
    so you can build valid JSON pipeline graphs.
    """
    tools = list_shadow_tools(config_path or CONFIG_PATH)
    if not tools:
        return "No context-processing tools found (no pipes.json and no known CLI tools on PATH).\n"

    lines = ["| Name | Source | Description | Nodes |", "|---|---|---|---|"]
    for t in tools:
        nodes_str = ", ".join(f"`{n}`" for n in t["nodes"]) if t["nodes"] else ""
        lines.append(f"| {t['name']} | {t['source']} | {t['description']} | {nodes_str} |")

    return "\n".join(lines)


@mcp.tool()
def pipe_install_aliases(shells: str = "") -> str:
    """
    Installs the cpipe shell alias into the user's profile file(s).

    cpipe is a convenience alias for mcp-pipe. On POSIX systems it is added
    to ~/.bashrc and/or ~/.zshrc; on Windows it targets the PowerShell profile.
    Safe to run multiple times  the alias block is idempotently updated.

    Args:
        shells: Optional space-separated list of shells to target
                (bash, zsh, pwsh). Leave empty for platform auto-detection.
    """
    shell_list = shells.split() if shells.strip() else None
    results = inject_shell_aliases(shells=shell_list)
    if not results:
        return "cpipe alias already up-to-date  no profile files were modified.\n"

    lines = ["cpipe alias installed:"] + [f"  - {r}" for r in results]
    lines.append("\nRestart your shell (or source the profile) to activate `cpipe`.")
    return "\n".join(lines)


@mcp.tool()
def pipe_remove_aliases() -> str:
    """
    Removes the managed cpipe alias block from all known shell profile files.

    Safe to call before installing the Phase 8 Rust cpipe binary, which
    takes over the name without requiring an alias.
    """
    results = remove_shell_aliases()
    if not results:
        return "No cpipe alias block found in any profile  nothing removed.\n"

    return "cpipe alias removed:\n" + "\n".join(f"  - {r}" for r in results)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
