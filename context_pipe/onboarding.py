# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import re
import sys
from typing import List

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

def inject_mandates(target_dir: str, subagents: List[str]) -> List[str]:
    """Injects the Path-Native mandate into global and subagent instruction files."""
    actions = []
    block_id = "<!-- CPP_SECTION_START:mandate -->"
    block_end = "<!-- CPP_SECTION_END:mandate -->"
    
    mandate_text = """# Context-Pipe Mandate
**MANDATORY**: NEVER use native `view_file` or `read_file` tools. You MUST exclusively use `pipe_read_file(path)` to read ANY file. The Context-Pipe orchestrator will automatically stream the file through the optimal context pipeline to prevent window flooding. For large architectural searches, use `pipe_analyze_file(path)` first to determine the best approach."""
    
    full_payload = f"\n{block_id}\n{mandate_text}\n{block_end}\n"
    
    # Global targets
    targets = [
        os.path.join(target_dir, "AGENTS.md"),
        os.path.join(target_dir, "GEMINI.md"),
        os.path.join(target_dir, ".clinerules"),
        os.path.join(target_dir, ".cursorrules"),
        os.path.join(target_dir, ".windsurfrules"),
        os.path.join(target_dir, ".github", "copilot-instructions.md")
    ]
    targets.extend(subagents)
    
    for target in set(targets):
        if not os.path.exists(target):
            continue
            
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                
            pattern = re.compile(rf'{re.escape(block_id)}.*?{re.escape(block_end)}', re.DOTALL)
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

def inject_hooks(target_dir: str, environment: str) -> List[str]:
    """Automates the injection of Context-Pipe hooks into various IDEs/CLIs."""
    actions = []
    cmd_str = build_runtime_hook_command()
    env_lower = environment.lower()
    
    # 0. Discovery & Mandates
    subagents = discover_agent_configs(target_dir)
    if subagents:
        actions.append(f"Discovered {len(subagents)} specialized subagents.")
        
    mandate_actions = inject_mandates(target_dir, subagents)
    actions.extend(mandate_actions)

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
                with open(oc_path, "r") as f:
                    oc_data = json.load(f)
                
                # 4.1 Update MCP entry
                if "mcp" not in oc_data:
                    oc_data["mcp"] = {}
                oc_data["mcp"]["context-pipe"] = {
                    "type": "local",
                    "command": [os.path.abspath(sys.executable), "-m", "context_pipe.server"],
                    "environment": {
                        "PIPE_CONFIG_PATH": os.path.abspath(os.path.join(target_dir, "pipes.json"))
                    }
                }
                
                # 4.2 Update Commands
                if "commands" not in oc_data:
                    oc_data["commands"] = {}
                oc_data["commands"]["/pipe-stats"] = {
                    "description": "View Context-Pipe ROI",
                    "action": "run_mcp_tool",
                    "server": "context-pipe",
                    "tool": "get_pipe_stats"
                }
                
                with open(oc_path, "w") as f:
                    json.dump(oc_data, f, indent=2)
                actions.append("Updated Context-Pipe MCP and /pipe-stats in opencode.json.")
                
                # 4.3 Native Plugin
                oc_plugin_dir = os.path.join(target_dir, ".opencode", "plugins")
                os.makedirs(oc_plugin_dir, exist_ok=True)
                oc_plugin_path = os.path.join(oc_plugin_dir, "context-pipe.ts")
                
                oc_plugin_content = f"""/**
 * Context-Pipe Native OpenCode Plugin
 */
export default function (api: any) {{
  api.on("tool.execute.after", async (event: any) => {{
    const rawContent = event.result;
    if (typeof rawContent !== 'string' || rawContent.length < 500) return;
    if (rawContent.includes("--- [Context-Pipe: Native Execution] ---")) return;
    try {{
      const pythonExe = "{os.path.abspath(sys.executable)}";
      const payload = {{ hook_event_name: "AfterTool", tool_name: event.toolName, result: rawContent }};
      const {{ execSync }} = require('child_process');
      const response = execSync(`"${{pythonExe}}" -m context_pipe.orchestrator wrap`, {{ input: JSON.stringify(payload), encoding: 'utf-8' }});
      const siftedData = JSON.parse(response);
      if (siftedData?.result) {{
         event.result = siftedData.result;
      }}
    }} catch (error) {{ console.error("[Context-Pipe Plugin] failed:", error); }}
  }});
}};
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
            if merge_hook_json(c_path, "PostToolUse", {"matcher": "mcp__.*__.*", "hooks": [{"type": "command", "command": cmd_str}]}):
                actions.append(f"Merged into Claude Code hooks at {c_path}.")

    # 8. Qwen CLI Injection
    if "qwen" in env_lower:
        qwen_paths = [
            os.path.join(os.path.expanduser("~"), ".qwen", "settings.json"),
            os.path.join(target_dir, ".qwen", "settings.json"),
        ]
        for q_path in qwen_paths:
            if merge_hook_json(q_path, "PostToolUse", {"matcher": "mcp__.*__.*", "hooks": [{"type": "command", "command": cmd_str}]}):
                actions.append(f"Merged into Qwen CLI hooks at {q_path}.")

    # 9. Codex CLI Injection
    if "codex" in env_lower:
        codex_paths = [
            os.path.join(os.path.expanduser("~"), ".codex", "settings.json"),
            os.path.join(target_dir, ".codex", "settings.json"),
        ]
        for co_path in codex_paths:
            if merge_hook_json(co_path, "PostToolUse", {"matcher": "mcp__.*__.*", "hooks": [{"type": "command", "command": cmd_str}]}):
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
            f.write("# Context-Pipe Kilo Code Constraints\n\nEnsure that all raw file reads use the `pipe_read_file` tool to prevent context flooding.")
        actions.append("Injected Kilo Code workspace rules.")

    return actions
