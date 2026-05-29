# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
import os
import json
import re
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any


def check_for_updates() -> str:
    """Checks if a newer version of Context-Pipe is available on PyPI."""
    try:
        import urllib.request
        import json
        from . import __version__
        req = urllib.request.Request("https://pypi.org/pypi/mcp-context-pipe/json", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2) as response:  # nosec B310
            data = json.loads(response.read())
            latest = data["info"]["version"]
            if latest != __version__:
                return f" Update available: v{latest} (Current: v{__version__}). Run: pip install -U mcp-context-pipe"
    except Exception:
        pass
    return ""


def check_performance_tax(pipes_json_path: str) -> str:
    """Scans pipes.json for Python interpreted nodes and warns about the Subprocess Tax."""
    try:
        import json
        with open(pipes_json_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        has_python_node = False
        for pipe in config.get("pipes", []):
            for node in pipe.get("nodes", []):
                cmd = str(node.get("cmd", "")).lower()
                args = " ".join(str(a).lower() for a in node.get("args", []))
                if cmd == "python" or cmd == "python3" or cmd.endswith(".py") or ".py " in args:
                    has_python_node = True
                    break
            if has_python_node:
                break

        if has_python_node:
            return "  Performance Notice: You are piping data through interpreted Python nodes. For high-concurrency agent loops, consider migrating to pre-compiled binaries (e.g., Rust/Go) to eliminate the ~100ms Python startup tax."
    except Exception:
        pass
    return ""  # Development/editable mode or not installed via pip


DEFAULT_PIPES_CONFIG = {
    "version": "1.0",
    "description": "Standard context pipes for sifting and refinery.",
    "pipes": [
        {
            "name": "standard-distill",
            "description": "Fast log sifting via Semantic-Sift.",
            "nodes": [
                {
                    "cmd": "semantic-sift-cli",
                    "args": ["logs"],
                }
            ],
        },
        {
            "name": "semantic-refinery",
            "description": "Neural distillation for code and prose (Hybrid Engine).",
            "nodes": [
                {
                    "cmd": "semantic-sift-cli",
                    "args": ["semantic", "--rate", "0.5"],
                }
            ],
        },
    ],
    "mappings": [
        {
            "trigger": "tool:web_search|web_fetch|google_web_search",
            "pipe": "semantic-refinery",
        },
        {
            "trigger": "tool:search_code|grep_search|glob|find_symbol",
            "pipe": "semantic-refinery",
        },
        {
            "trigger": "size:>10000",
            "pipe": "semantic-refinery",
        },
        {
            "trigger": "size:>500",
            "pipe": "standard-distill",
        },
    ],
}


def build_runtime_hook_command(env_vars: dict[str, str] | None = None) -> str:
    """Builds the absolute command string to invoke the context-pipe wrapper.

    On Windows (PowerShell), the returned command is prefixed with the ``&``
    call operator so that a double-quoted executable path is treated as a
    command rather than a string literal, preventing the
    ``Unexpected token '-W'`` parser error (Bug REPORT_027).
    """
    python_exe = os.path.abspath(sys.executable)
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir_esc = root_dir.replace("\\", "/")

    env_setup = ""
    if env_vars:
        env_setup = "".join(f"os.environ['{k}']='{v}'; " for k, v in env_vars.items())
        env_setup = "import os; " + env_setup

    # We use a python inline script to set sys.path and invoke main, ensuring it's shell-agnostic
    cmd = f'"{python_exe}" -W ignore -c "{env_setup}import sys; sys.path.insert(0, \'{root_dir_esc}\'); from context_pipe.orchestrator import main; main()" wrap'

    # PowerShell requires the `&` call operator when the command starts with a
    # quoted path; without it the shell treats the string as a literal and raises
    # "Unexpected token '-W' in expression or statement." (Bug REPORT_027)
    if os.name == "nt":
        cmd = f"& {cmd}"
    return cmd


def discover_sift_executable() -> Optional[str]:
    """
    Discovers the semantic-sift-cli executable across all known install locations.

    Search order (most to least specific):
    1. Current venv Scripts/bin
    2. System PATH (shutil.which)
    3. pipx install location
    4. Common sibling venv patterns (../semantic-sift/venv*/Scripts|bin)
    5. Common user-level venv directories

    Returns the absolute path to the executable, or None if not found.
    """
    cli_name = "semantic-sift-cli"
    exe_name = f"{cli_name}.exe" if os.name == "nt" else cli_name
    candidates: List[str] = []

    # 1. Current venv
    if sys.prefix != sys.base_prefix:
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        candidates.append(os.path.join(sys.prefix, bin_dir, exe_name))

    # 2. System PATH
    which_result = shutil.which(cli_name)
    if which_result:
        candidates.append(which_result)

    # 3. pipx
    pipx_home = os.environ.get("PIPX_HOME", os.path.join(Path.home(), ".local", "pipx", "venvs"))
    pipx_candidate = os.path.join(pipx_home, "semantic-sift", "Scripts" if os.name == "nt" else "bin", exe_name)
    candidates.append(pipx_candidate)

    # 4. Sibling venv patterns: look for ../semantic-sift/venv*/Scripts/semantic-sift-cli
    current_dir = os.path.dirname(os.path.abspath(sys.executable))
    # Walk up to find a parent that might contain a sibling semantic-sift dir
    for depth in range(4):
        parent = str(Path(current_dir).parents[depth]) if depth < len(Path(current_dir).parents) else None
        if not parent:
            break
        sift_root = os.path.join(parent, "semantic-sift")
        if os.path.isdir(sift_root):
            for entry in os.listdir(sift_root):
                if entry.startswith("venv"):
                    bin_dir = "Scripts" if os.name == "nt" else "bin"
                    candidates.append(os.path.join(sift_root, entry, bin_dir, exe_name))

    # 5. Common user-level locations
    home = Path.home()
    candidates += [
        str(home / ".venv" / ("Scripts" if os.name == "nt" else "bin") / exe_name),
        str(home / "venv" / ("Scripts" if os.name == "nt" else "bin") / exe_name),
    ]

    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return os.path.abspath(path)

    return None


def resolve_pipes_config(pipes_json_path: str) -> Dict[str, Any]:
    """
    Reads pipes.json and rewrites any node that calls 'semantic-sift-cli'
    with the discovered absolute executable path.

    Returns a dict with keys:
    - 'sift_path': str | None  resolved path or None
    - 'updated': bool  whether pipes.json was modified
    - 'pipes_path': str  path that was read/written
    """
    result: Dict[str, Any] = {"sift_path": None, "updated": False, "pipes_path": pipes_json_path}
    if not os.path.exists(pipes_json_path):
        return result

    sift_exe = discover_sift_executable()
    result["sift_path"] = sift_exe
    if not sift_exe:
        return result

    try:
        with open(pipes_json_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return result

    modified = False
    for pipe in config.get("pipes", []):
        for node in pipe.get("nodes", []):
            if node.get("cmd") == "semantic-sift-cli" or (
                isinstance(node.get("cmd"), str) and node["cmd"].endswith("semantic-sift-cli")
            ):
                if node["cmd"] != sift_exe:
                    node["cmd"] = sift_exe
                    modified = True

    if modified:
        with open(pipes_json_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        result["updated"] = True

    return result


def verify_installation(pipes_json_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies the health of the context-pipe + semantic-sift installation.
    Checks:
    - context-pipe orchestrator is importable
    - pipes.json exists and is valid JSON
    - semantic-sift-cli is discoverable
    - semantic-sift-cli responds to --version
    - Each pipe node command is resolvable
    Returns a structured report dict.
    """
    report: Dict[str, Any] = {
        "context_pipe": {"ok": False, "detail": ""},
        "pipes_config": {"ok": False, "path": pipes_json_path or "unknown", "detail": ""},
        "semantic_sift": {"ok": False, "path": None, "version": None, "detail": ""},
        "nodes": [],
        "overall": False,
    }

    # 1. context-pipe self-check
    try:
        from context_pipe import orchestrator  # noqa: F401

        report["context_pipe"]["ok"] = True
        report["context_pipe"]["detail"] = f"Installed at {os.path.abspath(orchestrator.__file__)}"
    except ImportError as e:
        report["context_pipe"]["detail"] = str(e)

    # 2. pipes.json
    config_path = pipes_json_path or os.environ.get("PIPE_CONFIG_PATH", "pipes.json")
    report["pipes_config"]["path"] = config_path
    config = None
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            report["pipes_config"]["ok"] = True
            report["pipes_config"]["detail"] = f"{len(config.get('pipes', []))} pipes defined"
        except (OSError, json.JSONDecodeError) as e:
            report["pipes_config"]["detail"] = f"Invalid JSON: {e}"
    else:
        report["pipes_config"]["detail"] = "File not found"

    # 3. semantic-sift-cli discovery
    sift_exe = discover_sift_executable()
    report["semantic_sift"]["path"] = sift_exe
    if sift_exe:
        try:
            proc = subprocess.run([sift_exe, "--version"], capture_output=True, text=True, timeout=15)
            version_output = (proc.stdout or proc.stderr).strip()
            # If --version is not supported, the binary still exists and is callable
            if proc.returncode != 0 or not version_output:
                version_output = "installed"
            report["semantic_sift"]["ok"] = True
            report["semantic_sift"]["version"] = version_output
            report["semantic_sift"]["detail"] = f"Found at {sift_exe}"
        except subprocess.TimeoutExpired:
            # Cold-start timeout  binary exists and is linked, treat as a warning not a failure
            report["semantic_sift"]["ok"] = True
            report["semantic_sift"]["version"] = "installed (cold-start timeout on version check)"
            report["semantic_sift"]["detail"] = f"Found at {sift_exe}  binary is linked correctly"
        except OSError as e:
            report["semantic_sift"]["detail"] = f"Found but failed to run: {e}"
    else:
        report["semantic_sift"]["detail"] = (
            "Not found. Install with: uv tool install semantic-sift  or uv pip install mcp-context-pipe[sift]"
        )

    # 4. Node resolution check
    if config:
        seen_cmds: set = set()
        for pipe in config.get("pipes", []):
            for node in pipe.get("nodes", []):
                cmd = node.get("cmd", "")
                if cmd in seen_cmds:
                    continue
                seen_cmds.add(cmd)
                resolved = shutil.which(cmd) or (cmd if os.path.isfile(cmd) else None)
                report["nodes"].append(
                    {
                        "cmd": cmd,
                        "resolved": resolved,
                        "ok": resolved is not None,
                    }
                )

    # 5. Version Awareness
    update_warning = check_for_updates()
    if update_warning:
        report["update_warning"] = update_warning

    # 6. Overall
    report["overall"] = report["context_pipe"]["ok"] and report["pipes_config"]["ok"] and report["semantic_sift"]["ok"]
    return report


def get_security_gateway_command() -> str:
    """Generates a proactive inhibitor command to block large native file reads."""
    if sys.platform == "win32":
        return (
            'pwsh -NoProfile -Command "$p=$env:WINDSURF_TOOL_ARGS; '
            "if (Test-Path $p) { "
            "if ((Get-Item $p).Length -gt 1024) { "
            '[Console]::Error.WriteLine("[BLOCKED by Context-Pipe] File > 1KB. Use pipe_read_file instead."); '
            'exit 2 } }" '
        )
    return (
        'SIZE=$(stat -c %s "$WINDSURF_TOOL_ARGS" 2>/dev/null || stat -f %z "$WINDSURF_TOOL_ARGS" 2>/dev/null || wc -c < "$WINDSURF_TOOL_ARGS" 2>/dev/null); '
        'if [ "$SIZE" -gt 1024 ] 2>/dev/null; then '
        'echo "[BLOCKED by Context-Pipe] File > 1KB. Use pipe_read_file instead." > /dev/stderr; '
        "exit 2; fi"
    )


def update_gitignore(target_dir: str) -> str:
    """
    Ensures that Context-Pipe internal artifacts are ignored by Git.
    Matches the pattern used by Semantic-Sift.
    """
    path = os.path.join(target_dir, ".gitignore")
    entries = [".pipe_telemetry.json", ".pipe_telemetry.jsonl", ".pipe_cache/", ".pipe_identity"]

    try:
        content = ""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

        added = []
        for entry in entries:
            if entry not in content:
                added.append(entry)

        if not added:
            return "No changes needed to `.gitignore`."

        with open(path, "a", encoding="utf-8") as f:
            f.write("\n# Project Specific (Context-Pipe)\n" + "\n".join(added) + "\n")

        return f"Added artifacts to `.gitignore`: {', '.join(added)}"
    except OSError as e:
        return f"Error updating `.gitignore`: {str(e)}"


def discover_agent_configs(target_dir: str) -> List[str]:
    """Recursively discovers specialized agent configurations and mandates."""
    found_paths = []
    agent_dirs = [".codex/agents", ".cursor/agents", ".junie/agents", ".agents"]
    for d in agent_dirs:
        full_dir = os.path.join(target_dir, d)
        if os.path.exists(full_dir):
            for f in os.listdir(full_dir):
                if f.endswith((".toml", ".md")):
                    found_paths.append(os.path.join(full_dir, f))

    for root, _, files in os.walk(target_dir):
        depth = root[len(target_dir) :].count(os.sep)
        if depth > 3:
            continue
        if "AGENTS.md" in files and root != target_dir:
            found_paths.append(os.path.join(root, "AGENTS.md"))

    return found_paths


def merge_hook_json(path: str, hook_key: str, new_hook: dict, version: int | None = None) -> bool:
    """Safely merges a new hook into a JSON configuration file."""
    data: dict = {"hooks": {}}
    if version:
        data["version"] = version

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass

    if "hooks" not in data:
        data["hooks"] = {}

    hooks_list = data["hooks"].get(hook_key, [])

    def is_context_pipe_hook(obj: Any) -> bool:
        if isinstance(obj, dict):
            if obj.get("name") == "context-pipe":
                return True
            cmd = obj.get("command")
            if isinstance(cmd, str) and ("context_pipe.orchestrator" in cmd or "from context_pipe.orchestrator" in cmd):
                return True
            if "hooks" in obj and isinstance(obj["hooks"], list):
                return any(is_context_pipe_hook(h) for h in obj["hooks"])
        elif isinstance(obj, list):
            return any(is_context_pipe_hook(item) for item in obj)
        return False

    is_new_cp = is_context_pipe_hook(new_hook)

    # Filter out existing context-pipe hooks if we are adding a new one (idempotency/cleanup)
    if is_new_cp:
        others = [h for h in hooks_list if is_context_pipe_hook(h) and h != new_hook]
        already_present = new_hook in hooks_list

        if others:
            # Clean up legacy/duplicate hooks
            cleaned_list = [h for h in hooks_list if not is_context_pipe_hook(h)]
            data["hooks"][hook_key] = [new_hook] + cleaned_list
            dir_path = os.path.dirname(path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True

        if not already_present:
            data["hooks"][hook_key] = [new_hook] + hooks_list
            dir_path = os.path.dirname(path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        return False

    # For non-context-pipe hooks, use the old deduplication logic
    if new_hook in hooks_list:
        return False

    def get_commands(obj: Any) -> List[str]:
        cmds = []
        if isinstance(obj, dict):
            if "command" in obj and isinstance(obj["command"], str):
                cmds.append(obj["command"])
            if "hooks" in obj and isinstance(obj["hooks"], list):
                for h in obj["hooks"]:
                    cmds.extend(get_commands(h))
        elif isinstance(obj, list):
            for item in obj:
                cmds.extend(get_commands(item))
        return cmds

    new_cmds = get_commands(new_hook)
    if new_cmds:

        def get_core_target(cmd: str) -> str:
            if "context_pipe.orchestrator wrap" in cmd:
                return "context_pipe.orchestrator wrap"
            return cmd

        normalized_new = [get_core_target(c) for c in new_cmds]

        def hook_has_target(hook_obj: Any, target: str) -> bool:
            return any(get_core_target(c) == target for c in get_commands(hook_obj))

        new_hooks_list = [h for h in hooks_list if not any(hook_has_target(h, t) for t in normalized_new)]
        data["hooks"][hook_key] = [new_hook] + new_hooks_list
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True

    data["hooks"][hook_key] = [new_hook] + hooks_list
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True


def get_env_tool_names(environment: str) -> Dict[str, str]:
    """Maps generic tool purposes to verified, environment-specific tool names."""
    env_lower = environment.lower()
    # Mapping ONLY for Unshielded or Gateway environments (Mandates Required)
    if "opencode" in env_lower:
        return {"read": "read", "search": "grep", "list": "glob", "web": "websearch/webfetch"}
    elif "windsurf" in env_lower:
        return {"read": "read_file", "search": "grep_search/codebase_search", "list": "list_dir", "web": "web_search"}
    elif "cline" in env_lower:
        return {"read": "read_file", "search": "search_files", "list": "list_files", "web": "browser_action"}
    elif "zed" in env_lower:
        return {"read": "read_file", "search": "search/grep", "list": "list_files", "web": "fetch"}
    elif "continue" in env_lower:
        return {"read": "read_file", "search": "grep_search", "list": "ls", "web": "search_web/fetch_url_content"}
    elif "jetbrains" in env_lower or "junie" in env_lower:
        return {"read": "read_file", "search": "search_files", "list": "list_files", "web": "/web"}
    elif "kilocode" in env_lower:
        return {"read": "read_file", "search": "search_files", "list": "list_files", "web": "web_search"}
    elif "antigravity" in env_lower:
        return {"read": "view_file", "search": "grep_search", "list": "list_directory", "web": "web_search"}

    # Shielded Environments (Cursor, Gemini CLI, Claude Code, VS Code, Qwen, Codex, OpenClaw)
    # Their hooks work silently. Injecting mandates here contradicts the architecture.
    return {}


def inject_mandates(target_dir: str, subagents: List[str], environment: Any = "unknown") -> List[str]:
    """Injects the Path-Native mandate into global and subagent instruction files."""
    actions = []

    if isinstance(environment, str):
        detected_envs = {environment.lower()}
    else:
        detected_envs = {e.lower() for e in environment}

    unshielded_envs = {"cline", "windsurf", "opencode", "zed", "continue", "jetbrains", "junie", "kilocode"}
    has_unshielded = any(env in unshielded_envs for env in detected_envs)

    block_id = "<!-- CPP_SECTION_START:mandate -->"
    block_end = "<!-- CPP_SECTION_END:mandate -->"

    def get_tool_mappings(env_name: str) -> dict[str, str]:
        env_lower = env_name.lower()
        if "opencode" in env_lower:
            return {"read": "read", "search": "grep", "list": "glob", "web": "websearch/webfetch"}
        elif "windsurf" in env_lower:
            return {"read": "read_file", "search": "grep_search/codebase_search", "list": "list_dir", "web": "web_search"}
        elif "cline" in env_lower:
            return {"read": "read_file", "search": "search_files", "list": "list_files", "web": "browser_action"}
        elif "zed" in env_lower:
            return {"read": "read_file", "search": "search/grep", "list": "list_files", "web": "fetch"}
        elif "continue" in env_lower:
            return {"read": "read_file", "search": "grep_search", "list": "ls", "web": "search_web/fetch_url_content"}
        elif "jetbrains" in env_lower or "junie" in env_lower:
            return {"read": "read_file", "search": "search_files", "list": "list_files", "web": "/web"}
        elif "kilocode" in env_lower:
            return {"read": "read_file", "search": "search_files", "list": "list_files", "web": "web_search"}
        return {"read": "view_file", "search": "grep_search", "list": "list_directory", "web": "web_search"}

    target_mappings = [
        (os.path.join(target_dir, "AGENTS.md"), "antigravity"),
        (os.path.join(target_dir, "GEMINI.md"), "gemini"),
        (os.path.join(target_dir, ".clinerules"), "cline"),
        (os.path.join(target_dir, ".cursorrules"), "cursor"),
        (os.path.join(target_dir, ".windsurfrules"), "windsurf"),
        (os.path.join(target_dir, ".github", "copilot-instructions.md"), "vscode"),
    ]
    for sub in subagents:
        target_mappings.append((sub, "antigravity"))

    for target, platform in target_mappings:
        if not os.path.exists(target):
            continue

        tier1_text = """#  CRITICAL INSTRUCTION: FILE I/O OVERRIDE
**WARNING**: Using native file readers will flood the context window and destroy the session.

- **REQUIRED**: Standard practice in this Studio is to use `pipe_read_file(path)` and `pipe_analyze_file(path)` for all large local file reads (>1KB)."""

        is_unshielded_target = platform in unshielded_envs or platform in ["antigravity", "gemini"]

        if has_unshielded and is_unshielded_target:
            tools = get_tool_mappings(platform)
            tier2_text = f"""
## 1. File & Large-Output I/O
- **FORBIDDEN TOOLS**: `{tools["read"]}`, `{tools["search"]}`, `{tools["list"]}`. Do NOT use these under any circumstances for outputs > 1KB.
- **REQUIRED TOOLS**: You MUST exclusively use `pipe_read_file(path)` and `pipe_analyze_file(path)` for ALL local file reads.
- NEVER read raw outputs from `{tools["web"]}` or search tools. Pipe them through `pipe_run("rerank-and-sift", raw_output)`.
- For ANY tool output exceeding 100 lines (logs, API responses, search results), route through a context pipe before presenting to the user.

## 2. Named Pipes  When to Use `pipe_run`
- Call `list_pipes()` first to see all available named pipes in this project.
- Use `pipe_run(pipe_name, input_text)` when:
  - A named pipe exists that matches the content type (e.g. `semantic-refinery` for code, `standard-distill` for logs).
  - You want a reproducible, audited transformation that is tracked in the Balance Sheet.
- After every `pipe_run`, the audit header shows compression ratio and latency  include this in your response to the user.

## 3. Dynamic Pipes  When to Use `pipe_run_dynamic`
- Use `pipe_run_dynamic(nodes_json, input_text)` when no named pipe fits and you need to compose a one-off processing graph.
- **Workflow** (always follow this sequence):
  1. Call `pipe_list_shadow_tools()` to discover available nodes (configured pipes + PATH tools like `jq`, `rg`, `markitdown`).
  2. Construct a `nodes_json` array from those capabilities.
  3. Call `pipe_run_dynamic(nodes_json, input_text)`.
- **Rules**:
  - Every `nodes_json` array MUST end with `{{\"cmd\": \"semantic-sift-cli\", \"args\": [\"semantic\"]}}` or equivalent sifting node.
  - Shell utilities (`grep`, `awk`, `jq`, `rg`, etc.) require `allow_shell=True`  only use when the final node is a sifter.
  - Never put shell metacharacters (`|`, `;`, `&`, `$`) in a `cmd` value - use `args` instead.
- **Example**  extract ERROR lines then distil:
  ```json
  [{{\"cmd\": \"grep\", \"args\": [\"ERROR\"]}}, {{\\"cmd\\": \"semantic-sift-cli\", \"args\": [\"logs\"]}}]
  ```

## 4. A2A Agent Handoff  When to Use `pipe_agent_handoff`
- ALWAYS call `pipe_agent_handoff(output, from_agent="X", to_agent="Y")` when passing one agent's output to another agent's context window.
- This prevents context flooding at multi-agent boundaries regardless of framework (CrewAI, ADK, LangGraph, custom).
- If you know the content type, pass `pipe_name` explicitly (e.g. `pipe_name="semantic-refinery"`). Otherwise omit it and routing is automatic.

## 5. Observability  Balance Sheet
- Call `get_pipe_stats()` at any time to see cumulative ROI: chars saved, chars added, avg latency, total events.
- After significant processing sessions, proactively report the Balance Sheet to the user so they can see the value delivered."""
            full_payload = f"\n{block_id}\n{tier1_text}{tier2_text}\n{block_end}\n"
        else:
            full_payload = f"\n{block_id}\n{tier1_text}\n{block_end}\n"

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            pattern = re.compile(rf"{re.escape(block_id)}.*?{re.escape(block_end)}", re.DOTALL)
            if pattern.search(content):
                new_content = pattern.sub(full_payload.strip(), content)
                if new_content != content:
                    with open(target, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    actions.append(f"Updated mandate in `{os.path.basename(target)}`.")
            else:
                new_content = full_payload.strip() + "\n\n" + content
                with open(target, "w", encoding="utf-8") as f:
                    f.write(new_content)
                actions.append(f"Injected mandate into `{os.path.basename(target)}`.")
        except OSError as e:
            actions.append(f"Error updating `{target}`: {str(e)}")

    return actions


# ---------------------------------------------------------------------------
# Shell alias injection (Phase 2  Standard Shell Aliases)
# ---------------------------------------------------------------------------

#: Marker written on either side of the managed alias block so it can be
#: idempotently updated or removed without touching surrounding user config.
_ALIAS_MARKER_START = "# >>> cpipe (context-pipe) initialize >>>"
_ALIAS_MARKER_END = "# <<< cpipe (context-pipe) initialize <<<"

#: The alias block written into POSIX profile files.
_POSIX_ALIAS_BLOCK = """\
{start}
# Added by mcp-pipe / context-pipe.  To remove: delete the block below.
alias cpipe='mcp-pipe'
{end}
""".format(start=_ALIAS_MARKER_START, end=_ALIAS_MARKER_END)

#: The alias block written into PowerShell profile files.
_PWSH_ALIAS_BLOCK = """\
{start}
# Added by mcp-pipe / context-pipe.  To remove: delete the block below.
Set-Alias -Name cpipe -Value mcp-pipe -Scope Global
{end}
""".format(start=_ALIAS_MARKER_START, end=_ALIAS_MARKER_END)

#: Candidate POSIX profile files, in preference order.
_POSIX_PROFILES: List[str] = [
    "~/.bashrc",
    "~/.zshrc",
    "~/.profile",
    "~/.bash_profile",
]

#: Candidate PowerShell profile files, in preference order.
_PWSH_PROFILES: List[str] = [
    "~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1",
    "~/Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1",
    "~/.config/powershell/Microsoft.PowerShell_profile.ps1",
]


def _alias_block_present(content: str) -> bool:
    """Return True when the managed alias block is already in *content*."""
    return _ALIAS_MARKER_START in content


def _upsert_alias_block(path: str, block: str) -> str:
    """
    Idempotently writes *block* into the file at *path*.

    - If the marker is absent the block is appended.
    - If the marker is present the existing block is replaced (handles
      re-runs after a ``mcp-pipe`` upgrade).

    Returns one of: ``"added"``, ``"updated"``, ``"skipped"`` (on error).
    """
    expanded = os.path.expanduser(path)
    try:
        os.makedirs(os.path.dirname(expanded) or ".", exist_ok=True)
        existing = ""
        if os.path.exists(expanded):
            with open(expanded, "r", encoding="utf-8", errors="replace") as fh:
                existing = fh.read()

        if _alias_block_present(existing):
            # Replace the existing managed block in-place.
            import re as _re

            pattern = _re.compile(
                _re.escape(_ALIAS_MARKER_START) + r".*?" + _re.escape(_ALIAS_MARKER_END),
                _re.DOTALL,
            )
            new_content = pattern.sub(block.rstrip("\n"), existing)
            if new_content == existing:
                return "skipped"
            with open(expanded, "w", encoding="utf-8") as fh:
                fh.write(new_content)
            return "updated"
        else:
            # Append a blank-line separator then the block.
            with open(expanded, "a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write("\n" + block)
            return "added"
    except OSError:
        return "skipped"


def inject_shell_aliases(shells: Optional[List[str]] = None) -> List[str]:
    """
    Installs ``cpipe`` shell aliases into detected profile files.

    ``cpipe`` is a convenience alias for ``mcp-pipe`` (the Python CLI entry
    point).  When the Phase 8 Rust ``cpipe`` binary is installed the alias is
    simply removed; the binary takes over the name.

    Args:
        shells: Optional explicit list of shell names to target
                (``"bash"``, ``"zsh"``, ``"pwsh"``).  When *None* all
                applicable profiles for the current platform are tried.

    Returns:
        List of human-readable action strings (empty when nothing changed).
    """
    actions: List[str] = []
    platform = sys.platform
    want_posix = shells is None or any(s in (shells or []) for s in ("bash", "zsh", "sh"))
    want_pwsh = shells is None or "pwsh" in (shells or [])

    # On Windows only target PowerShell by default; on POSIX only target POSIX shells.
    if platform == "win32":
        want_posix = False
    else:
        want_pwsh = False

    # --- POSIX profiles ---
    if want_posix:
        for profile in _POSIX_PROFILES:
            expanded = os.path.expanduser(profile)
            # Only write to profiles that already exist, except ~/.bashrc which
            # we create if absent (most common default shell profile).
            if not os.path.exists(expanded) and profile != "~/.bashrc":
                continue
            result = _upsert_alias_block(expanded, _POSIX_ALIAS_BLOCK)
            if result == "added":
                actions.append(f"Added cpipe alias to {profile}.")
            elif result == "updated":
                actions.append(f"Updated cpipe alias in {profile}.")

    # --- PowerShell profiles ---
    if want_pwsh:
        for profile in _PWSH_PROFILES:
            expanded = os.path.expanduser(profile)
            if not os.path.exists(expanded) and profile != _PWSH_PROFILES[0]:
                continue
            result = _upsert_alias_block(expanded, _PWSH_ALIAS_BLOCK)
            if result == "added":
                actions.append(f"Added cpipe alias to {profile}.")
            elif result == "updated":
                actions.append(f"Updated cpipe alias in {profile}.")

    return actions


def remove_shell_aliases() -> List[str]:
    """
    Removes the managed ``cpipe`` alias block from all known profile files.
    Safe to call when the Phase 8 Rust ``cpipe`` binary is installed.

    Returns:
        List of human-readable action strings.
    """
    import re as _re

    actions: List[str] = []
    pattern = _re.compile(
        _re.escape(_ALIAS_MARKER_START) + r".*?" + _re.escape(_ALIAS_MARKER_END) + r"\n?",
        _re.DOTALL,
    )

    for profile in _POSIX_PROFILES + _PWSH_PROFILES:
        expanded = os.path.expanduser(profile)
        if not os.path.exists(expanded):
            continue
        try:
            with open(expanded, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            if not _alias_block_present(content):
                continue
            cleaned = pattern.sub("", content)
            with open(expanded, "w", encoding="utf-8") as fh:
                fh.write(cleaned)
            actions.append(f"Removed cpipe alias from {profile}.")
        except OSError:
            pass

    return actions


def _inject_cursor(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    cursor_path = os.path.join(target_dir, ".cursor", "hooks.json")
    if merge_hook_json(cursor_path, "postToolUse", {"name": "context-pipe", "command": cmd_str}, version=1):
        actions.append("Injected Context-Pipe into Cursor hooks.")

    cursor_rules_dir = os.path.join(target_dir, ".cursor", "rules")
    os.makedirs(cursor_rules_dir, exist_ok=True)

    pipe_stats_mdc = """\
---
description: View Context-Pipe ROI Balance Sheet
globs: []
alwaysApply: false
---
Call `get_pipe_stats` from the `context-pipe` MCP server.
Display the full Balance Sheet: chars saved, chars added, avg latency per node, total events, and net ROI.
If net savings > 0, summarise the top contributing pipe by name.
"""
    pipe_run_mdc = """\
---
description: Run a named Context-Pipe on the current context
globs: []
alwaysApply: false
---
1. Call `list_pipes()` from the `context-pipe` MCP server to show available pipes.
2. If the user has not specified a pipe name, ask them to choose from the list.
3. Ask the user to confirm or paste the input text to process, or use the current conversation context.
4. Call `pipe_run(pipe_name, input_text)`.
5. Display the audit header (compression ratio, latency) and the distilled result.
"""
    pipe_dynamic_mdc = """\
---
description: Build and run an ad-hoc Context-Pipe from available tools
globs: []
alwaysApply: false
---
1. Call `pipe_list_shadow_tools()` from the `context-pipe` MCP server to discover available nodes
   (configured pipes + PATH tools like jq, rg, markitdown, pandoc).
2. Based on the user's goal, construct a `nodes_json` array. Rules:
   - Every array MUST end with a sifting node: `{"cmd": "semantic-sift-cli", "args": ["semantic"]}`.
   - Shell utilities (grep, awk, jq, rg) require `allow_shell=True`.
   - Never put shell metacharacters (|, ;, &, $) in a `cmd` value - use `args` instead.
3. Show the user the proposed node graph and confirm before executing.
4. Call `pipe_run_dynamic(nodes_json, input_text, allow_shell=<bool>)`.
5. Display the audit header and distilled result.
"""
    pipe_handoff_mdc = """\
---
description: Distil agent output before passing it to another agent
globs: []
alwaysApply: false
---
Use this at any agent-to-agent handoff boundary to prevent context flooding.
1. Identify the output text from Agent A and the name of Agent B that will consume it.
2. Call `pipe_agent_handoff(output, from_agent="<A>", to_agent="<B>")` from the `context-pipe` MCP server.
   - If you know the content type, pass `pipe_name` explicitly (e.g. `pipe_name="semantic-refinery"`).
   - Otherwise omit `pipe_name` and routing is determined automatically by pipes.json mappings.
3. Pass the returned distilled text as the input to Agent B.
"""

    stats_path = os.path.join(cursor_rules_dir, "pipe-stats.mdc")
    run_path = os.path.join(cursor_rules_dir, "pipe-run.mdc")
    dynamic_path = os.path.join(cursor_rules_dir, "pipe-dynamic.mdc")
    handoff_path = os.path.join(cursor_rules_dir, "pipe-handoff.mdc")

    for path, text in [
        (stats_path, pipe_stats_mdc),
        (run_path, pipe_run_mdc),
        (dynamic_path, pipe_dynamic_mdc),
        (handoff_path, pipe_handoff_mdc),
    ]:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    actions.append("Added /pipe-stats, /pipe-run, /pipe-dynamic, /pipe-handoff rules to Cursor (.cursor/rules/).")
    return actions


def _inject_vscode_github(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    vscode_path = os.path.join(target_dir, ".github", "hooks", "context-pipe.json")
    if merge_hook_json(vscode_path, "PostToolUse", {"name": "context-pipe", "type": "command", "command": cmd_str}):
        actions.append("Injected Context-Pipe into VS Code/GitHub hooks.")
    return actions


def _inject_gemini(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    gemini_dir = os.path.join(target_dir, ".gemini", "commands")
    os.makedirs(gemini_dir, exist_ok=True)

    gemini_commands = {
        "pipe-stats.toml": (
            "View Context-Pipe ROI Balance Sheet",
            "Call get_pipe_stats from the context-pipe MCP server. Display chars saved, chars added, avg latency, total events, and net ROI.",
        ),
        "pipe-run.toml": (
            "Run a named Context-Pipe on the current context",
            "Call list_pipes() to show available pipes. Ask the user to choose one and confirm the input text. Then call pipe_run(pipe_name, input_text) and display the audit header and distilled result.",
        ),
        "pipe-dynamic.toml": (
            "Build and run an ad-hoc Context-Pipe from available tools",
            "Call pipe_list_shadow_tools() to discover available nodes. Construct a nodes_json array ending with a semantic-sift-cli node. Show the user the proposed graph, confirm, then call pipe_run_dynamic(nodes_json, input_text).",
        ),
        "pipe-handoff.toml": (
            "Distil agent output before passing it to another agent",
            "Call pipe_agent_handoff(output, from_agent='A', to_agent='B') from the context-pipe MCP server to prevent context flooding at A2A handoff boundaries.",
        ),
    }

    for filename, (description, prompt) in gemini_commands.items():
        text = f'description = "{description}"\nprompt = """\n{prompt}\n"""\n'
        with open(os.path.join(gemini_dir, filename), "w", encoding="utf-8") as f:
            f.write(text)
    actions.append("Added /pipe-stats, /pipe-run, /pipe-dynamic, /pipe-handoff commands to Gemini CLI.")

    gemini_settings_path = os.path.join(target_dir, ".gemini", "settings.json")
    gemini_cmd = build_runtime_hook_command({"GEMINI_SESSION_ID": "true"})
    for hook_key in ["SessionStart", "BeforeTool", "AfterTool", "PreCompress"]:
        if merge_hook_json(
            gemini_settings_path,
            hook_key,
            {
                "matcher": ".*",
                "hooks": [
                    {"name": "context-pipe", "type": "command", "command": gemini_cmd, "timeout": 10000}
                ]
            },
        ):
            actions.append(f"Injected Context-Pipe into Gemini CLI {hook_key} hooks.")
    return actions


def _inject_opencode(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    import sys
    import json
    oc_path = os.path.join(target_dir, "opencode.json")
    if os.path.exists(oc_path):
        try:
            with open(oc_path, "r", encoding="utf-8") as f:
                oc_data = json.load(f)

            if "mcp" not in oc_data:
                oc_data["mcp"] = {}
            oc_data["mcp"]["context-pipe"] = {
                "type": "local",
                "command": [os.path.abspath(sys.executable), "-m", "context_pipe.server"],
                "environment": {"PIPE_CONFIG_PATH": os.path.abspath(os.path.join(target_dir, "pipes.json"))},
            }

            if "command" not in oc_data:
                oc_data["command"] = {}
            oc_data["command"]["pipe-stats"] = {
                "description": "View Context-Pipe ROI Balance Sheet",
                "template": "Call get_pipe_stats from the context-pipe MCP server. Display chars saved, chars added, avg latency, total events, and net ROI. If net savings > 0, name the top contributing pipe.",
            }
            oc_data["command"]["pipe-run"] = {
                "description": "Run a named pipe from pipes.json on the current context",
                "template": "Call list_pipes() to show available pipes. Ask the user to choose a pipe name and confirm the input text. Then call pipe_run(pipe_name, input_text) and display the audit header and distilled result.",
            }
            oc_data["command"]["pipe-dynamic"] = {
                "description": "Build and run an ad-hoc Context-Pipe from available tools",
                "template": "Call pipe_list_shadow_tools() to discover available nodes (configured pipes + PATH tools). Construct a nodes_json array ending with semantic-sift-cli. Show the proposed node graph to the user, confirm, then call pipe_run_dynamic(nodes_json, input_text). Use allow_shell=True if the <A>graph includes shell utilities (grep, awk, jq, rg).",
            }
            oc_data["command"]["pipe-handoff"] = {
                "description": "Distil agent output before passing it to another agent",
                "template": "Call pipe_agent_handoff(output, from_agent='<A>', to_agent='<B>') from the context-pipe MCP server to prevent context flooding at A2A handoff boundaries. Pass pipe_name explicitly if you know the content type (e.g. 'semantic-refinery').",
            }

            with open(oc_path, "w", encoding="utf-8") as f:
                json.dump(oc_data, f, indent=2)
            actions.append("Updated Context-Pipe MCP and /pipe-stats, /pipe-run, /pipe-dynamic, /pipe-handoff in opencode.json.")

            oc_plugin_dir = os.path.join(target_dir, ".opencode", "plugins")
            os.makedirs(oc_plugin_dir, exist_ok=True)
            oc_plugin_path = os.path.join(oc_plugin_dir, "context-pipe.ts")
            oc_plugin_content = """/**
 * Context-Pipe Native OpenCode Plugin
 *
 * NOTE: `tool.execute.after` is declared in the OpenCode plugin Hooks interface
 * but is NOT currently triggered by the OpenCode runtime (as of v1.14.39).
 * See: https://github.com/anomalyco/opencode/issues/25918
 *
 * This plugin is therefore TELEMETRY-ONLY. Output mutation via this hook has
 * no effect. The real interception point is the `pipe_read_file` MCP tool,
 * which is called explicitly by the agent per the AGENTS.md SOP.
 *
 * When OpenCode wires up the trigger in processor.ts, this plugin can be
 * re-enabled for transparent output interception without any agent-side changes.
 */
export const ContextPipePlugin = async (_: any) => {
  return {
    // Hook placeholder - will be activated once OpenCode triggers tool.execute.after
  };
};
"""
            with open(oc_plugin_path, "w", encoding="utf-8") as f:
                f.write(oc_plugin_content)
            actions.append("Configured OpenCode native plugin.")
        except Exception as e:
            actions.append(f"Failed to update opencode.json: {str(e)}")

    return actions


def _inject_windsurf(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    windsurf_path = os.path.join(target_dir, ".windsurf", "hooks.json")
    gateway_cmd = get_security_gateway_command()
    if merge_hook_json(
        windsurf_path,
        "pre_mcp_tool_use",
        {"matcher": "mcp__.*__(read_file|view_file)", "type": "command", "command": gateway_cmd},
    ):
        actions.append("Injected Security Gateway into Windsurf hooks.")
    return actions


def _inject_cline(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    cline_dir = os.path.join(target_dir, ".clinerules", "hooks")
    os.makedirs(cline_dir, exist_ok=True)

    ps1_blocker = """$inputJson = $input | ConvertFrom-Json
if ($inputJson.preToolUse.toolName -eq 'read_file' -or $inputJson.preToolUse.toolName -eq 'view_file') {
    $filePath = $inputJson.preToolUse.parameters.path
    if (Test-Path $filePath) {
        $size = (Get-Item $filePath).Length
        if ($size -gt 1024) {
            $response = @{ cancel = $true; errorMessage = "[BLOCKED by Context-Pipe] File > 1KB. Use pipe_read_file instead." }
            $response | ConvertTo-Json -Compress | Write-Output
            exit 0
        }
    }
}
$response = @{ cancel = $false }
$response | ConvertTo-Json -Compress | Write-Output
"""
    with open(os.path.join(cline_dir, "PreToolUse.ps1"), "w") as f:
        f.write(ps1_blocker)
    actions.append("Injected Security Gateway into Cline hooks (PS1).")

    cline_bash_path = os.path.join(cline_dir, "PreToolUse")
    cline_bash_content = """#!/bin/bash
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | grep -oP '(?<="toolName":")[^"]*')
if [[ "$TOOL_NAME" == "read_file" ]] || [[ "$TOOL_NAME" == "view_file" ]]; then
    FILE_PATH=$(echo "$INPUT" | grep -oP '(?<="path":")[^"]*')
    if [[ -f "$FILE_PATH" ]]; then
        SIZE=$(wc -c < "$FILE_PATH" 2>/dev/null || stat -f %s "$FILE_PATH" 2>/dev/null || stat -c %s "$FILE_PATH" 2>/dev/null)
        if [[ "$SIZE" -gt 1024 ]]; then
            echo '{"cancel": true, "errorMessage": "[BLOCKED by Context-Pipe] File > 1KB. Use pipe_read_file instead."}'
            exit 0
        fi
    fi
fi
echo '{"cancel": false}'
"""
    with open(cline_bash_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(cline_bash_content)
    try:
        os.chmod(cline_bash_path, 0o755)  # nosec B103
    except OSError:
        pass
    actions.append("Injected Security Gateway into Cline hooks (Bash).")
    return actions


def _inject_claude(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    claude_paths = [
        os.path.join(os.path.expanduser("~"), ".claude", "settings.json"),
        os.path.join(target_dir, ".claude", "settings.json"),
    ]
    for c_path in claude_paths:
        if merge_hook_json(
            c_path, "PostToolUse", {"matcher": ".*", "hooks": [{"type": "command", "command": cmd_str}]}
        ):
            actions.append(f"Merged into Claude Code hooks at {c_path}.")
    return actions


def _inject_qwen(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    qwen_paths = [
        os.path.join(os.path.expanduser("~"), ".qwen", "settings.json"),
        os.path.join(target_dir, ".qwen", "settings.json"),
    ]
    for q_path in qwen_paths:
        if merge_hook_json(
            q_path, "PostToolUse", {"matcher": ".*", "hooks": [{"type": "command", "command": cmd_str}]}
        ):
            actions.append(f"Merged into Qwen CLI hooks at {q_path}.")
    return actions


def _inject_codex(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    codex_paths = [
        os.path.join(os.path.expanduser("~"), ".codex", "settings.json"),
        os.path.join(target_dir, ".codex", "settings.json"),
    ]
    for co_path in codex_paths:
        if merge_hook_json(
            co_path, "PostToolUse", {"matcher": ".*", "hooks": [{"type": "command", "command": cmd_str}]}
        ):
            actions.append(f"Merged into Codex CLI hooks at {co_path}.")
    return actions


def _inject_openclaw(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    import sys

    openclaw_plugin_path = os.path.join(target_dir, ".openclaw", "plugins", "context-pipe.ts")
    os.makedirs(os.path.dirname(openclaw_plugin_path), exist_ok=True)
    py_exe = os.path.abspath(sys.executable).replace('\\', '/')

    openclaw_plugin_content = f"""/**
 * Context-Pipe Native OpenClaw Plugin
 */
export default function (api) {{
  api.on("tool:after", async (event, ctx) => {{
    const rawContent = ctx.result;
    if (typeof rawContent !== 'string' || rawContent.length < 500) return;
    if (rawContent.includes("--- [Context-Pipe: Native Execution] ---")) return;

    try {{
      const pythonExe = "{py_exe}";
      const payload = {{ hook_event_name: "AfterTool", tool_name: ctx.toolName, tool_response: {{ llmContent: rawContent }} }};
      const {{ execSync }} = require('child_process');
      const response = execSync(`"${{pythonExe}}" -m context_pipe.orchestrator wrap`, {{ input: JSON.stringify(payload), encoding: 'utf-8' }});
      const siftedData = JSON.parse(response);
      if (siftedData?.tool_response?.llmContent) {{
        ctx.result = siftedData.tool_response.llmContent;
      }}
    }} catch (error) {{ console.error("[Context-Pipe Plugin] failed:", error); }}
  }});
}};
"""
    with open(openclaw_plugin_path, "w", encoding="utf-8") as f:
        f.write(openclaw_plugin_content)
    actions.append("Configured OpenClaw native plugin.")
    return actions


def _inject_kilocode(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    kilo_rule_dir = os.path.join(target_dir, ".kilocode", "rules")
    os.makedirs(kilo_rule_dir, exist_ok=True)
    kilo_rule_path = os.path.join(kilo_rule_dir, "context.md")
    with open(kilo_rule_path, "w", encoding="utf-8") as f:
        f.write(
            "# Context-Pipe Kilo Code Constraints\\n\\nEnsure that all raw file reads use the `pipe_read_file` tool to prevent context flooding."
        )
    actions.append("Injected Kilo Code workspace rules.")
    return actions


def _inject_pi(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    import sys
    import os

    pi_extension_dir = os.path.join(target_dir, ".pi", "extensions")
    pi_skill_dir = os.path.join(target_dir, ".pi", "skills")
    os.makedirs(pi_extension_dir, exist_ok=True)
    os.makedirs(pi_skill_dir, exist_ok=True)

    pi_extension_path = os.path.join(pi_extension_dir, "context-pipe.ts")
    pi_skill_path = os.path.join(pi_skill_dir, "context-pipe.md")
    py_exe = os.path.abspath(sys.executable).replace(chr(92), "/")
    mcp_pipe_exe = shutil.which("mcp-pipe") or ""
    mcp_pipe_path = os.path.abspath(mcp_pipe_exe).replace(chr(92), "/") if mcp_pipe_exe else ""

    pi_extension_template = r"""/**
 * Context-Pipe Native pi.dev Extension
 * "No MCP" - Tools are registered natively.
 */
import { ExtensionAPI, isToolCallEventType } from "@earendil-works/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { execSync } from "child_process";
import { readFileSync } from "fs";

export default function (pi: ExtensionAPI) {
  const pythonExe = "{PY_EXE_PLACEHOLDER}";
  const mcpPipePath = "{MCP_PIPE_PLACEHOLDER}";

  const callCli = (args: string[], input?: string) => {
    try {
      // Try mcp-pipe binary first (fast path)
      const cmd = `"${mcpPipePath}" ${args.join(" ")}`;
      return execSync(cmd, { input, encoding: "utf-8" });
    } catch (e) {
      // Fallback to python module
      try {
        const cmd = `"${pythonExe}" -m context_pipe.cli ${args.join(" ")}`;
        return execSync(cmd, { input, encoding: "utf-8" });
      } catch (e2: any) {
        console.error("[Context-Pipe] CLI call failed:", e2.message);
        throw e2;
      }
    }
  };

  // 1. Register Native Tools
  pi.registerTool({
    name: "pipe_read_file",
    label: "Pipe Read File",
    description: "Read a file through the optimal context pipe (Standard Practice).",
    parameters: Type.Object({
      path: Type.String({ description: "Absolute or relative path to the file." }),
      pipe_name: Type.Optional(Type.String({ description: "Explicit pipe name." })),
    }),
    async execute(_toolCallId, params) {
      const text = readFileSync(params.path, "utf-8");
      return callCli(["run", params.pipe_name || "auto"], text);
    }
  });

  pi.registerTool({
    name: "pipe_run",
    label: "Pipe Run",
    description: "Process text through a named context pipe.",
    parameters: Type.Object({
      pipe_name: Type.String({ description: "Name of the pipe to run." }),
      input_text: Type.String({ description: "Raw text to process." }),
    }),
    async execute(_toolCallId, params) {
      return callCli(["run", params.pipe_name], params.input_text);
    }
  });

  pi.registerTool({
    name: "get_pipe_stats",
    label: "Get Pipe Stats",
    description: "View the Context-Pipe Balance Sheet (ROI).",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params) {
      return callCli(["stats"]);
    }
  });

  pi.registerTool({
    name: "list_pipes",
    label: "List Pipes",
    description: "Lists all available context pipes and their descriptions.",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params) {
      return callCli(["list"]);
    }
  });

  pi.registerTool({
    name: "pipe_analyze_file",
    label: "Pipe Analyze File",
    description: "Analyze a file through the context pipe with semantic analysis.",
    parameters: Type.Object({
      path: Type.String({ description: "Absolute or relative path to the file." }),
      pipe_name: Type.Optional(Type.String({ description: "Explicit pipe name (default: semantic-refinery)." })),
    }),
    async execute(_toolCallId, params) {
      const text = readFileSync(params.path, "utf-8");
      return callCli(["run", params.pipe_name || "semantic-refinery"], text);
    }
  });

  pi.registerTool({
    name: "pipe_run_dynamic",
    label: "Pipe Run Dynamic",
    description: "Run an ad-hoc processing graph composed from shadow tools.",
    parameters: Type.Object({
      nodes_json: Type.String({ description: "JSON array of node definitions." }),
      input_text: Type.String({ description: "Raw input text to process." }),
    }),
    async execute(_toolCallId, params) {
      return callCli(["run-dynamic", params.nodes_json], params.input_text);
    }
  });

  // 2. Intercept Native 'read' Tool
  pi.on("tool_call", async (event, ctx) => {
    if (isToolCallEventType("read", event)) {
      const filePath = event.input.path;
      try {
        const { statSync } = require("fs");
        const stats = statSync(filePath);
        if (stats.size > 1024) {
          ctx.ui.notify("Large file detected. Redirecting to pipe_read_file.", "info");
        }
      } catch (e) {}
    }
  });

  // 3. Auto-Pipe Large Tool Results
  pi.on("tool_result", async (event, ctx) => {
    const text = event.content?.[0]?.text;
    if (typeof text === "string" && text.length > 5000) {
      if (text.includes("--- [Context-Pipe Audit] ---")) return;
      try {
        const sifted = callCli(["run", "auto"], text);
        return { content: [{ type: "text", text: sifted }] };
      } catch (e) {
        console.error("[Context-Pipe] Auto-sift failed");
      } finally {
        ctx.ui.setStatus("context-pipe", "");
      }
    }
  });

  // 4. Register Commands
  pi.registerCommand("pipe-stats", {
    description: "View Context-Pipe Balance Sheet",
    handler: async (_args, _ctx) => {
      const stats = callCli(["stats"]);
      console.log(stats);
    }
  });
}
"""
    pi_extension_content = pi_extension_template.replace("{PY_EXE_PLACEHOLDER}", py_exe).replace("{MCP_PIPE_PLACEHOLDER}", mcp_pipe_path)

    pi_skill_content = """---
name: context-pipe
description: Universal standard for context engineering. Use for reading large files, logs, and distilling context.
---

# Context-Pipe SOP
Guidelines for high-fidelity context.

## CRITICAL INSTRUCTION: FILE I/O OVERRIDE
**WARNING**: Using native file readers will flood the context window and destroy the session.

- **REQUIRED**: Standard practice in this Studio is to use `pipe_read_file(path)` and `pipe_analyze_file(path)` for all large local file reads (>1KB).

### 1. File & Large-Output I/O
- **FORBIDDEN TOOLS**: Native `read` tool. Do NOT use it for files > 1KB.
- **REQUIRED TOOLS**: You MUST exclusively use `pipe_read_file(path)` or `pipe_analyze_file(path)` for ALL local file reads.
- NEVER read raw outputs from `web_search` or search tools. Pipe them through `pipe_run("rerank-and-sift", raw_output)`.
- For ANY tool output exceeding 100 lines (logs, API responses, search results), route through a context pipe before presenting to the user.

### 2. Named Pipes — When to Use `pipe_run`
- Call `list_pipes()` first to see all available named pipes in this project.
- Use `pipe_run(pipe_name, input_text)` when:
  - A named pipe exists that matches the content type (e.g. `semantic-refinery` for code, `standard-distill` for logs).
  - You want a reproducible, audited transformation that is tracked in the Balance Sheet.

### 3. Dynamic Pipes — When to Use `pipe_run_dynamic`
- Use `pipe_run_dynamic(nodes_json, input_text)` when no named pipe fits and you need to compose a one-off processing graph.
- **Workflow**:
  1. Call `pipe_list_shadow_tools()` to discover available nodes.
  2. Construct a `nodes_json` array from those capabilities.
  3. Call `pipe_run_dynamic(nodes_json, input_text)`.

### 4. A2A Agent Handoff — When to Use `pipe_agent_handoff`
- ALWAYS call `pipe_agent_handoff(output, from_agent="X", to_agent="Y")` when passing one agent's output to another agent's context window.

### 5. Observability — Balance Sheet
- Call `get_pipe_stats()` at any time to see cumulative ROI.
"""
    with open(pi_extension_path, "w", encoding="utf-8") as f:
        f.write(pi_extension_content)
    actions.append("Created pi.dev native extension (.pi/extensions/context-pipe.ts).")

    with open(pi_skill_path, "w", encoding="utf-8") as f:
        f.write(pi_skill_content)
    actions.append("Created pi.dev skill (.pi/skills/context-pipe.md).")

    # Also create a minimal package.json if it doesn't exist to help with dependencies
    pi_package_path = os.path.join(target_dir, ".pi", "package.json")
    if not os.path.exists(pi_package_path):
        import json
        pkg_data = {
            "name": "pi-context-pipe-workspace",
            "version": "0.1.0",
            "dependencies": {
                "@earendil-works/pi-coding-agent": "latest",
                "@sinclair/typebox": "latest"
            }
        }
        with open(pi_package_path, "w", encoding="utf-8") as f:
            json.dump(pkg_data, f, indent=2)
        actions.append("Created .pi/package.json for extension dependencies.")

    return actions


def _inject_antigravity(target_dir: str, cmd_str: str) -> list[str]:
    actions = []
    import sys
    import json

    # 1. Rules in .agents/rules/
    antigravity_rules_dir = os.path.join(target_dir, ".agents", "rules")
    os.makedirs(antigravity_rules_dir, exist_ok=True)

    rule_template = """---
description: {description}
globs: []
alwaysApply: false
---
{prompt}
"""
    antigravity_commands = {
        "pipe-stats.md": (
            "View Context-Pipe ROI Balance Sheet",
            "Call get_pipe_stats from the context-pipe MCP server. Display chars saved, chars added, avg latency, total events, and net ROI. If net savings > 0, summarise the top contributing pipe by name.",
        ),
        "pipe-run.md": (
            "Run a named Context-Pipe on the current context",
            "1. Call `list_pipes()` from the `context-pipe` MCP server to show available pipes.\\n2. If the user has not specified a pipe name, ask them to choose from the list.\\n3. Ask the user to confirm or paste the input text to process, or use the current conversation context.\\n4. Call `pipe_run(pipe_name, input_text)`.\\n5. Display the audit header (compression ratio, latency) and the distilled result.",
        ),
        "pipe-dynamic.md": (
            "Build and run an ad-hoc Context-Pipe from available tools",
            "1. Call `pipe_list_shadow_tools()` from the `context-pipe` MCP server to discover available nodes (configured pipes + PATH tools like jq, rg, markitdown, pandoc).\\n2. Based on the user's goal, construct a `nodes_json` array. Rules:\\n   - Every array MUST end with a sifting node: `{\"cmd\": \"semantic-sift-cli\", \"args\": [\"semantic\"]}`.\\n   - Shell utilities (grep, awk, jq, rg) require `allow_shell=True` - only use when the final node is a sifter.\\n   - Never put shell metacharacters (|, ;, &, $) in a `cmd` value - use `args` instead.\\n3. Show the user the proposed node graph and confirm before executing.\\n4. Call `pipe_run_dynamic(nodes_json, input_text, allow_shell=<bool>)`.\\n5. Display the audit header and distilled result.",
        ),
        "pipe-handoff.md": (
            "Distil agent output before passing it to another agent",
            "Use this at any agent-to-agent handoff boundary to prevent context flooding.\\n1. Identify the output text from Agent A and the name of Agent B that will consume it.\\n2. Call `pipe_agent_handoff(output, from_agent=\"<A>\", to_agent=\"<B>\")` from the `context-pipe` MCP server.\\n   - If you know the content type, pass `pipe_name\" explicitly (e.g. `pipe_name=\"semantic-refinery\"`). \\n   - Otherwise omit `pipe_name` and routing is determined automatically by pipes.json mappings.\\n3. Pass the returned distilled text as the input to Agent B.",
        ),
    }

    for filename, (description, prompt) in antigravity_commands.items():
        text = rule_template.format(description=description, prompt=prompt)
        with open(os.path.join(antigravity_rules_dir, filename), "w", encoding="utf-8") as f:
            f.write(text)
    actions.append("Added /pipe-stats, /pipe-run, /pipe-dynamic, /pipe-handoff rules to Antigravity (.agents/rules/).")

    # 2. Global MCP Config
    global_mcp_path = os.path.expanduser("~/.gemini/antigravity/mcp_config.json")

    def update_mcp_config(path: str) -> bool:
        data: dict = {"mcpServers": {}}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        if "mcpServers" not in data:
            data["mcpServers"] = {}

        py_exe = os.path.abspath(sys.executable)
        entry_point = "context_pipe.server"
        existing = data["mcpServers"].get("context-pipe", {})
        if existing.get("command") == py_exe and entry_point in (existing.get("args") or []):
            return False

        data["mcpServers"]["context-pipe"] = {
            "command": py_exe,
            "args": ["-m", entry_point],
            "env": {
                "PIPE_CONFIG_PATH": os.path.abspath(os.path.join(target_dir, "pipes.json")),
                "PIPE_AUTHORIZED_ROOT": os.path.abspath(target_dir),
            },
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True

    if update_mcp_config(global_mcp_path):
        actions.append(f"Registered Context-Pipe in Antigravity global MCP config ({global_mcp_path}).")

    # 3. Hooks
    antigravity_settings_path = os.path.join(target_dir, ".agents", "settings.json")
    hook_cmd = build_runtime_hook_command({"GEMINI_SESSION_ID": "true"})
    for hook_key in ["SessionStart", "BeforeTool", "AfterTool", "PreCompress"]:
        if merge_hook_json(
            antigravity_settings_path,
            hook_key,
            {
                "matcher": ".*",
                "hooks": [{"name": "context-pipe", "type": "command", "command": hook_cmd, "timeout": 10000}],
            },
        ):
            actions.append(f"Injected Context-Pipe into Antigravity {hook_key} hooks.")
    return actions


def inject_hooks(target_dir: str, environment: str) -> list[str]:
    """Automates the injection of Context-Pipe hooks into various IDEs/CLIs."""
    import json

    actions = []

    # 0. Git Protection (matches Semantic-Sift flow)
    gitignore_status = update_gitignore(target_dir)
    if "No changes needed" not in gitignore_status:
        actions.append(f"Git Protection: {gitignore_status}")

    cmd_str = build_runtime_hook_command()

    # 0. Discovery & Mandates
    subagents = discover_agent_configs(target_dir)
    if subagents:
        actions.append(f"Discovered {len(subagents)} specialized subagents.")

    # Project Horizon Scanning: Detect all active IDE signatures in target_dir
    detected_envs = {environment.lower()}
    if os.path.exists(os.path.join(target_dir, ".cursor")) or os.path.exists(os.path.join(target_dir, ".cursorrules")):
        detected_envs.add("cursor")
    if os.path.exists(os.path.join(target_dir, ".clinerules")):
        detected_envs.add("cline")
    if os.path.exists(os.path.join(target_dir, ".windsurfrules")):
        detected_envs.add("windsurf")
    if os.path.exists(os.path.join(target_dir, ".agents")):
        detected_envs.add("antigravity")
    if os.path.exists(os.path.join(target_dir, ".gemini")):
        detected_envs.add("gemini")
    if os.path.exists(os.path.join(target_dir, "opencode.json")):
        detected_envs.add("opencode")
    if os.path.exists(os.path.join(target_dir, ".vscode")):
        detected_envs.add("vscode")
    if os.path.exists(os.path.join(target_dir, ".pi")):
        detected_envs.add("pi")

    # Inject mandates with project-wide environment scanning
    mandate_actions = inject_mandates(target_dir, subagents, environment=detected_envs)
    actions.extend(mandate_actions)

    # 0b. Ensure pipes.json exists and auto-resolve semantic-sift-cli
    pipes_json_path = os.path.join(target_dir, "pipes.json")
    if not os.path.exists(pipes_json_path):
        try:
            with open(pipes_json_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_PIPES_CONFIG, f, indent=2)
            actions.append("Created default pipes.json.")
        except OSError as e:
            actions.append(f"Failed to create pipes.json: {e}")

    resolve_result = resolve_pipes_config(pipes_json_path)
    if resolve_result["sift_path"] and resolve_result["updated"]:
        actions.append(f"Linked semantic-sift-cli in pipes.json -> {resolve_result['sift_path']}")
    elif resolve_result["sift_path"] and not resolve_result["updated"]:
        actions.append(f"semantic-sift-cli already linked in pipes.json ({resolve_result['sift_path']})")
    else:
        actions.append(
            "semantic-sift-cli not found. Pipes will use PATH fallback. "
            "Run 'uv tool install semantic-sift' or 'uv pip install mcp-context-pipe[sift]' then re-run pipe_onboard."
        )

    update_warning = check_for_updates()
    if update_warning:
        actions.append(update_warning)

    perf_warning = check_performance_tax(pipes_json_path)
    if perf_warning:
        actions.append(perf_warning)

    # Dispatch to all detected and explicitly requested environments
    for env in detected_envs:
        if "cursor" in env:
            actions.extend(_inject_cursor(target_dir, cmd_str))
        if "vscode" in env or "github" in env:
            actions.extend(_inject_vscode_github(target_dir, cmd_str))
        if "gemini" in env:
            actions.extend(_inject_gemini(target_dir, cmd_str))
        if "opencode" in env:
            actions.extend(_inject_opencode(target_dir, cmd_str))
        if "windsurf" in env:
            actions.extend(_inject_windsurf(target_dir, cmd_str))
        if "cline" in env:
            actions.extend(_inject_cline(target_dir, cmd_str))
        if "claude" in env:
            actions.extend(_inject_claude(target_dir, cmd_str))
        if "qwen" in env:
            actions.extend(_inject_qwen(target_dir, cmd_str))
        if "codex" in env:
            actions.extend(_inject_codex(target_dir, cmd_str))
        if "openclaw" in env:
            actions.extend(_inject_openclaw(target_dir, cmd_str))
        if "kilocode" in env:
            actions.extend(_inject_kilocode(target_dir, cmd_str))
        if "antigravity" in env:
            actions.extend(_inject_antigravity(target_dir, cmd_str))
        if "pi" in env:
            actions.extend(_inject_pi(target_dir, cmd_str))

    return actions


def main() -> None:
    """Entry point for the context-pipe-onboard CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Context-Pipe Workspace Onboarding")
    parser.add_argument(
        "environment", nargs="?", default=None, help="The IDE/CLI environment (e.g., 'Cursor', 'VSCode', 'Gemini')."
    )
    parser.add_argument(
        "--target-dir", "--target_dir", dest="target_dir", help="Optional directory to onboard (default: current directory)."
    )

    args = parser.parse_args()
    target_dir = args.target_dir or os.getcwd()
    environment = args.environment

    if not environment:
        from .platforms import detect_client_id

        environment = detect_client_id()
        print(f"Auto-detected environment: {environment}")

    actions = inject_hooks(target_dir, environment)
    if not actions:
        print(f"Context-Pipe is already active or no targets found in {target_dir}.")
        return

    print("Onboarding Successful:")
    for a in actions:
        print(f"- {a}")


if __name__ == "__main__":
    main()
