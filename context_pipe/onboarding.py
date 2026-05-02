# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import re
import sys
import psutil
from typing import List, Dict, Any, Optional

def build_runtime_hook_command() -> str:
    """Builds the absolute command string to invoke the context-pipe wrapper."""
    python_exe = os.path.abspath(sys.executable)
    # We use 'python -m context_pipe.orchestrator wrap' for reliability
    return f'"{python_exe}" -m context_pipe.orchestrator wrap'

def get_security_gateway_command() -> str:
    """Generates a proactive inhibitor command to block large native file reads."""
    if sys.platform == "win32":
        return (
            'pwsh -NoProfile -Command "$p=$env:WINDSURF_TOOL_ARGS; '
            'if (Test-Path $p) { '
            'if ((Get-Item $p).Length -gt 1024) { '
            '[Console]::Error.WriteLine(\"[BLOCKED by Context-Pipe] File > 1KB. Use pipe_read_file instead.\"); '
            'exit 2 } }"'
        )
    return (
        'SIZE=$(stat -c %s "$WINDSURF_TOOL_ARGS" 2>/dev/null || stat -f %z "$WINDSURF_TOOL_ARGS" 2>/dev/null || wc -c < "$WINDSURF_TOOL_ARGS" 2>/dev/null); '
        'if [ "$SIZE" -gt 1024 ] 2>/dev/null; then '
        'echo "[BLOCKED by Context-Pipe] File > 1KB. Use pipe_read_file instead." > /dev/stderr; '
        'exit 2; fi'
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
        depth = root[len(target_dir):].count(os.sep)
        if depth > 3: continue
        if "AGENTS.md" in files and root != target_dir:
            found_paths.append(os.path.join(root, "AGENTS.md"))

    return found_paths

def merge_hook_json(path: str, hook_key: str, new_hook: dict, version: int | None = None) -> bool:
    """Safely merges a new hook into a JSON configuration file."""
    data: dict = {"hooks": {}}
    if version: data["version"] = version
    
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass

    if "hooks" not in data: data["hooks"] = {}
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

def inject_hooks(target_dir: str, environment: str) -> List[str]:
    """Automates the injection of Context-Pipe hooks into various IDEs/CLIs."""
    actions = []
    cmd_str = build_runtime_hook_command()
    env_lower = environment.lower()
    
    # 0. Discovery
    subagents = discover_agent_configs(target_dir)
    if subagents:
        actions.append(f"Discovered {len(subagents)} specialized subagents.")

    # 1. Cursor Injection
    if "cursor" in env_lower:
        cursor_path = os.path.join(target_dir, ".cursor", "hooks.json")
        if merge_hook_json(cursor_path, "postToolUse", {"command": cmd_str}, version=1):
            actions.append("Injected Context-Pipe into Cursor hooks.")

    # 2. VS Code / GitHub Injection
    if "vscode" in env_lower or "github" in env_lower:
        vscode_path = os.path.join(target_dir, ".github", "hooks", "context-pipe.json")
        if merge_hook_json(vscode_path, "PostToolUse", {"type": "command", "command": cmd_str}):
            actions.append("Injected Context-Pipe into VS Code/GitHub hooks.")

    # 3. Gemini CLI Injection
    if "gemini" in env_lower:
        gemini_dir = os.path.join(target_dir, ".gemini", "commands")
        os.makedirs(gemini_dir, exist_ok=True)
        stats_cmd = """description = "View Context-Pipe ROI Balance Sheet"
prompt = \"\"\"
!{context-pipe-server get_pipe_stats}
\"\"\"
"""
        with open(os.path.join(gemini_dir, "pipe-stats.toml"), "w") as f:
            f.write(stats_cmd)
        actions.append("Added /pipe-stats command to Gemini CLI.")

    # 4. OpenCode Injection
    if "opencode" in env_lower:
        oc_path = os.path.join(target_dir, "opencode.json")
        if os.path.exists(oc_path):
            try:
                with open(oc_path, "r") as f: oc_data = json.load(f)
                if "commands" not in oc_data: oc_data["commands"] = {}
                oc_data["commands"]["/pipe-stats"] = {
                    "description": "View Context-Pipe ROI",
                    "action": "run_mcp_tool",
                    "server": "context-pipe",
                    "tool": "get_pipe_stats"
                }
                with open(oc_path, "w") as f: json.dump(oc_data, f, indent=2)
                actions.append("Injected /pipe-stats into opencode.json.")
            except Exception: pass

    # 5. Windsurf Security Gateway
    if "windsurf" in env_lower:
        windsurf_path = os.path.join(target_dir, ".windsurf", "hooks.json")
        gateway_cmd = get_security_gateway_command()
        if merge_hook_json(windsurf_path, "pre_mcp_tool_use", {
            "matcher": "mcp__.*__(read_file|view_file)",
            "type": "command",
            "command": gateway_cmd
        }):
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
        actions.append("Injected Security Gateway into Cline hooks.")

    return actions
