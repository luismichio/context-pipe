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


def build_runtime_hook_command() -> str:
    """Builds the absolute command string to invoke the context-pipe wrapper."""
    python_exe = os.path.abspath(sys.executable)
    # We use 'python -m context_pipe.orchestrator wrap' for reliability
    return f'"{python_exe}" -m context_pipe.orchestrator wrap'


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
        - 'sift_path': str | None — resolved path or None
        - 'updated': bool — whether pipes.json was modified
        - 'pipes_path': str — path that was read/written
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
            # Cold-start timeout — binary exists and is linked, treat as a warning not a failure
            report["semantic_sift"]["ok"] = True
            report["semantic_sift"]["version"] = "installed (cold-start timeout on version check)"
            report["semantic_sift"]["detail"] = f"Found at {sift_exe} — binary is linked correctly"
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

    # 5. Overall
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
            'exit 2 } }"'
        )
    return (
        'SIZE=$(stat -c %s "$WINDSURF_TOOL_ARGS" 2>/dev/null || stat -f %z "$WINDSURF_TOOL_ARGS" 2>/dev/null || wc -c < "$WINDSURF_TOOL_ARGS" 2>/dev/null); '
        'if [ "$SIZE" -gt 1024 ] 2>/dev/null; then '
        'echo "[BLOCKED by Context-Pipe] File > 1KB. Use pipe_read_file instead." > /dev/stderr; '
        "exit 2; fi"
    )


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

    # Prevent duplicates
    exists = any(h.get("command") == new_hook.get("command") for h in hooks_list)
    if not exists:
        data["hooks"][hook_key] = [new_hook] + hooks_list
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    return False


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


def inject_mandates(target_dir: str, subagents: List[str], environment: str = "unknown") -> List[str]:
    """Injects the Path-Native mandate into global and subagent instruction files."""
    actions = []
    env_tools = get_env_tool_names(environment)

    if not env_tools:
        # Environment is shielded. No text mandates needed.
        return []

    block_id = "<!-- CPP_SECTION_START:mandate -->"
    block_end = "<!-- CPP_SECTION_END:mandate -->"

    mandate_text = f"""# Context-Pipe Mandate

## 1. File & Large-Output I/O (MANDATORY)
- NEVER use native `{env_tools["read"]}`, `{env_tools["search"]}`, or `{env_tools["list"]}` for outputs > 1KB.
- ALWAYS use `pipe_read_file(path)` to read files — it streams through a sifting pipe automatically.
- For files where you are unsure of the best pipe, call `pipe_analyze_file(path)` first — it recommends the optimal `pipe_name` to pass to `pipe_read_file`.
- NEVER read raw outputs from `{env_tools["web"]}` or search tools. Pipe them through `pipe_run("rerank-and-sift", raw_output)`.
- For ANY tool output exceeding 100 lines (logs, API responses, search results), route through a context pipe before presenting to the user.

## 2. Named Pipes — When to Use `pipe_run`
- Call `list_pipes()` first to see all available named pipes in this project.
- Use `pipe_run(pipe_name, input_text)` when:
  - A named pipe exists that matches the content type (e.g. `semantic-refinery` for code, `standard-distill` for logs).
  - You want a reproducible, audited transformation that is tracked in the Balance Sheet.
- After every `pipe_run`, the audit header shows compression ratio and latency — include this in your response to the user.

## 3. Dynamic Pipes — When to Use `pipe_run_dynamic`
- Use `pipe_run_dynamic` when no named pipe fits and you need to compose a one-off processing graph.
- **Workflow** (always follow this sequence):
  1. Call `pipe_list_shadow_tools()` to discover available nodes (configured pipes + PATH tools like `jq`, `rg`, `markitdown`).
  2. Construct a `nodes_json` array from those capabilities.
  3. Call `pipe_run_dynamic(nodes_json, input_text)`.
- **Rules**:
  - Every `nodes_json` array MUST end with `{{"cmd": "semantic-sift-cli", "args": ["semantic"]}}` or equivalent sifting node.
  - Shell utilities (`grep`, `awk`, `jq`, `rg`, etc.) require `allow_shell=True` — only use when the final node is a sifter.
  - Never put shell metacharacters (`|`, `;`, `&`, `$`) in a `cmd` value — use `args` instead.
- **Example** — extract ERROR lines then distil:
  ```json
  [{{"cmd": "grep", "args": ["ERROR"]}}, {{"cmd": "semantic-sift-cli", "args": ["logs"]}}]
  ```

## 4. A2A Agent Handoff — When to Use `pipe_agent_handoff`
- ALWAYS call `pipe_agent_handoff(output, from_agent="X", to_agent="Y")` when passing one agent's output to another agent's context window.
- This prevents context flooding at multi-agent boundaries regardless of framework (CrewAI, ADK, LangGraph, custom).
- If you know the content type, pass `pipe_name` explicitly (e.g. `pipe_name="semantic-refinery"`). Otherwise omit it and routing is automatic.

## 5. Observability — Balance Sheet
- Call `get_pipe_stats()` at any time to see cumulative ROI: chars saved, chars added, avg latency, total events.
- After significant processing sessions, proactively report the Balance Sheet to the user so they can see the value delivered."""

    full_payload = f"\n{block_id}\n{mandate_text}\n{block_end}\n"

    # Global targets
    targets = [
        os.path.join(target_dir, "AGENTS.md"),
        os.path.join(target_dir, "GEMINI.md"),
        os.path.join(target_dir, ".clinerules"),
        os.path.join(target_dir, ".cursorrules"),
        os.path.join(target_dir, ".windsurfrules"),
        os.path.join(target_dir, ".github", "copilot-instructions.md"),
    ]
    targets.extend(subagents)

    for target in set(targets):
        if not os.path.exists(target):
            continue

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            pattern = re.compile(rf"{re.escape(block_id)}.*?{re.escape(block_end)}", re.DOTALL)
            if pattern.search(content):
                new_content = pattern.sub(full_payload.strip(), content)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(new_content)
                actions.append(f"Updated mandate in `{os.path.basename(target)}`.")
            else:
                with open(target, "a", encoding="utf-8") as f:
                    f.write(full_payload)
                actions.append(f"Injected mandate into `{os.path.basename(target)}`.")
        except OSError as e:
            actions.append(f"Error updating `{target}`: {str(e)}")

    return actions



# ---------------------------------------------------------------------------
# Shell alias injection (Phase 2 — Standard Shell Aliases)
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

def inject_hooks(target_dir: str, environment: str) -> List[str]:
    """Automates the injection of Context-Pipe hooks into various IDEs/CLIs."""
    actions = []
    cmd_str = build_runtime_hook_command()
    env_lower = environment.lower()

    # 0. Discovery & Mandates
    subagents = discover_agent_configs(target_dir)
    if subagents:
        actions.append(f"Discovered {len(subagents)} specialized subagents.")
    mandate_actions = inject_mandates(target_dir, subagents, environment=environment)
    actions.extend(mandate_actions)

    # 0b. Auto-resolve semantic-sift-cli in pipes.json
    pipes_json_path = os.path.join(target_dir, "pipes.json")
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

    # 1. Cursor Injection
    if "cursor" in env_lower:
        cursor_path = os.path.join(target_dir, ".cursor", "hooks.json")
        if merge_hook_json(cursor_path, "postToolUse", {"command": cmd_str}, version=1):
            actions.append("Injected Context-Pipe into Cursor hooks.")

        # 1b. Cursor Slash Commands — injected as .cursor/rules/*.mdc agent rules
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
   - Never put shell metacharacters (|, ;, &, $) in a `cmd` value — use `args` instead.
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
        for path, content in [
            (stats_path, pipe_stats_mdc),
            (run_path, pipe_run_mdc),
            (dynamic_path, pipe_dynamic_mdc),
            (handoff_path, pipe_handoff_mdc),
        ]:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        actions.append("Added /pipe-stats, /pipe-run, /pipe-dynamic, /pipe-handoff rules to Cursor (.cursor/rules/).")

    # 2. VS Code / GitHub Injection
    if "vscode" in env_lower or "github" in env_lower:
        vscode_path = os.path.join(target_dir, ".github", "hooks", "context-pipe.json")
        if merge_hook_json(vscode_path, "PostToolUse", {"type": "command", "command": cmd_str}):
            actions.append("Injected Context-Pipe into VS Code/GitHub hooks.")

    # 3. Gemini CLI Injection
    if "gemini" in env_lower:
        gemini_dir = os.path.join(target_dir, ".gemini", "commands")
        os.makedirs(gemini_dir, exist_ok=True)
        gemini_commands = {
            "pipe-stats.toml": (
                "View Context-Pipe ROI Balance Sheet",
                "Call get_pipe_stats from the context-pipe MCP server. "
                "Display chars saved, chars added, avg latency, total events, and net ROI.",
            ),
            "pipe-run.toml": (
                "Run a named Context-Pipe on the current context",
                "Call list_pipes() to show available pipes. Ask the user to choose one and confirm the input text. "
                "Then call pipe_run(pipe_name, input_text) and display the audit header and distilled result.",
            ),
            "pipe-dynamic.toml": (
                "Build and run an ad-hoc Context-Pipe from available tools",
                "Call pipe_list_shadow_tools() to discover available nodes. "
                "Construct a nodes_json array ending with a semantic-sift-cli node. "
                "Show the user the proposed graph, confirm, then call pipe_run_dynamic(nodes_json, input_text).",
            ),
            "pipe-handoff.toml": (
                "Distil agent output before passing it to another agent",
                "Call pipe_agent_handoff(output, from_agent='A', to_agent='B') from the context-pipe MCP server "
                "to prevent context flooding at A2A handoff boundaries.",
            ),
        }
        for filename, (description, prompt) in gemini_commands.items():
            content = f'description = "{description}"\nprompt = """\n{prompt}\n"""\n'
            with open(os.path.join(gemini_dir, filename), "w") as f:
                f.write(content)
        actions.append("Added /pipe-stats, /pipe-run, /pipe-dynamic, /pipe-handoff commands to Gemini CLI.")

    # 4. OpenCode Injection
    if "opencode" in env_lower:
        oc_path = os.path.join(target_dir, "opencode.json")
        if os.path.exists(oc_path):
            try:
                with open(oc_path, "r") as f:
                    oc_data = json.load(f)

                # 4.1 Update MCP entry
                if "mcp" not in oc_data:
                    oc_data["mcp"] = {}
                oc_data["mcp"]["context-pipe"] = {
                    "type": "local",
                    "command": [os.path.abspath(sys.executable), "-m", "context_pipe.server"],
                    "environment": {"PIPE_CONFIG_PATH": os.path.abspath(os.path.join(target_dir, "pipes.json"))},
                }

                # 4.2 Update Commands
                if "command" not in oc_data:
                    oc_data["command"] = {}
                oc_data["command"]["pipe-stats"] = {
                    "description": "View Context-Pipe ROI Balance Sheet",
                    "template": "Call get_pipe_stats from the context-pipe MCP server. "
                    "Display chars saved, chars added, avg latency, total events, and net ROI. "
                    "If net savings > 0, name the top contributing pipe.",
                }
                oc_data["command"]["pipe-run"] = {
                    "description": "Run a named pipe from pipes.json on the current context",
                    "template": "Call list_pipes() to show available pipes. "
                    "Ask the user to choose a pipe name and confirm the input text. "
                    "Then call pipe_run(pipe_name, input_text) and display the audit header and distilled result.",
                }
                oc_data["command"]["pipe-dynamic"] = {
                    "description": "Build and run an ad-hoc Context-Pipe from available tools",
                    "template": "Call pipe_list_shadow_tools() to discover available nodes (configured pipes + PATH tools). "
                    "Construct a nodes_json array ending with semantic-sift-cli. "
                    "Show the proposed node graph to the user, confirm, then call pipe_run_dynamic(nodes_json, input_text). "
                    "Use allow_shell=True if the graph includes shell utilities (grep, awk, jq, rg).",
                }
                oc_data["command"]["pipe-handoff"] = {
                    "description": "Distil agent output before passing it to another agent",
                    "template": "Call pipe_agent_handoff(output, from_agent='<A>', to_agent='<B>') "
                    "from the context-pipe MCP server to prevent context flooding at A2A handoff boundaries. "
                    "Pass pipe_name explicitly if you know the content type (e.g. 'semantic-refinery').",
                }

                with open(oc_path, "w") as f:
                    json.dump(oc_data, f, indent=2)
                actions.append("Updated Context-Pipe MCP and /pipe-stats, /pipe-run, /pipe-dynamic, /pipe-handoff in opencode.json.")

                # 4.3 Native Plugin
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
    // Hook placeholder — will be activated once OpenCode triggers tool.execute.after
    // "tool.execute.after": async (input: any, output: any) => { ... }
  };
};
"""
                with open(oc_plugin_path, "w", encoding="utf-8") as f:
                    f.write(oc_plugin_content)
                actions.append("Configured OpenCode native plugin.")

            except Exception as e:
                actions.append(f"Failed to update opencode.json: {str(e)}")

    # 5. Windsurf Security Gateway
    if "windsurf" in env_lower:
        windsurf_path = os.path.join(target_dir, ".windsurf", "hooks.json")
        gateway_cmd = get_security_gateway_command()
        if merge_hook_json(
            windsurf_path,
            "pre_mcp_tool_use",
            {"matcher": "mcp__.*__(read_file|view_file)", "type": "command", "command": gateway_cmd},
        ):
            actions.append("Injected Security Gateway into Windsurf hooks.")

    # 6. Cline Security Gateway
    if "cline" in env_lower:
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

    # 7. Claude Code Injection
    if "claude" in env_lower:
        claude_paths = [
            os.path.join(os.path.expanduser("~"), ".claude", "settings.json"),
            os.path.join(target_dir, ".claude", "settings.json"),
        ]
        for c_path in claude_paths:
            if merge_hook_json(
                c_path, "PostToolUse", {"matcher": "mcp__.*__.*", "hooks": [{"type": "command", "command": cmd_str}]}
            ):
                actions.append(f"Merged into Claude Code hooks at {c_path}.")

    # 8. Qwen CLI Injection
    if "qwen" in env_lower:
        qwen_paths = [
            os.path.join(os.path.expanduser("~"), ".qwen", "settings.json"),
            os.path.join(target_dir, ".qwen", "settings.json"),
        ]
        for q_path in qwen_paths:
            if merge_hook_json(
                q_path, "PostToolUse", {"matcher": "mcp__.*__.*", "hooks": [{"type": "command", "command": cmd_str}]}
            ):
                actions.append(f"Merged into Qwen CLI hooks at {q_path}.")

    # 9. Codex CLI Injection
    if "codex" in env_lower:
        codex_paths = [
            os.path.join(os.path.expanduser("~"), ".codex", "settings.json"),
            os.path.join(target_dir, ".codex", "settings.json"),
        ]
        for co_path in codex_paths:
            if merge_hook_json(
                co_path, "PostToolUse", {"matcher": "mcp__.*__.*", "hooks": [{"type": "command", "command": cmd_str}]}
            ):
                actions.append(f"Merged into Codex CLI hooks at {co_path}.")

    # 10. OpenClaw Injection
    if "openclaw" in env_lower:
        openclaw_plugin_path = os.path.join(target_dir, ".openclaw", "plugins", "context-pipe.ts")
        os.makedirs(os.path.dirname(openclaw_plugin_path), exist_ok=True)
        openclaw_plugin_content = f"""/**
 * Context-Pipe Native OpenClaw Plugin
 */
export default function (api) {{
  api.on("tool:after", async (event, ctx) => {{
    const rawContent = ctx.result;
    if (typeof rawContent !== 'string' || rawContent.length < 500) return;
    if (rawContent.includes("--- [Context-Pipe: Native Execution] ---")) return;
    try {{
      const pythonExe = "{os.path.abspath(sys.executable)}";
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

    # 11. Kilo Code Injection
    if "kilocode" in env_lower:
        kilo_rule_dir = os.path.join(target_dir, ".kilocode", "rules")
        os.makedirs(kilo_rule_dir, exist_ok=True)
        kilo_rule_path = os.path.join(kilo_rule_dir, "context.md")
        with open(kilo_rule_path, "w", encoding="utf-8") as f:
            f.write(
                "# Context-Pipe Kilo Code Constraints\n\nEnsure that all raw file reads use the `pipe_read_file` tool to prevent context flooding."
            )
        actions.append("Injected Kilo Code workspace rules.")

    return actions
