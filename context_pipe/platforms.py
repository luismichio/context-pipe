# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import psutil
from typing import Dict, Optional

def detect_client_id() -> str:
    """
    Infers the calling IDE/CLI from environment variables and parent process name.
    Prioritized for accurate attribution.
    """
    # 1. Environment Variable Fingerprints
    _ENV_MAP = [
        ("ANTIGRAVITY_AGENT", "Google Antigravity"),
        ("OPENCODE", "OpenCode"),
        ("OPENCODE_PID", "OpenCode"),
        ("CURSOR_TRACE_ID", "Cursor"),
        ("VSCODE_PID", "VSCode"),
        ("WINDSURF_TOOL_ARGS", "Windsurf"),
        ("__KIRO_MCP", "Kiro"),
        ("CONTINUE_SERVER_PORT", "Continue"),
        ("JETBRAINS_IDE_URL", "JetBrains"),
        ("CLINE_TASK_ID", "Cline"),
        ("CLAUDE_TOOL_NAME", "Claude Desktop"),
        ("GEMINI_SESSION_ID", "Gemini CLI")
    ]
    
    for var, label in _ENV_MAP:
        if os.environ.get(var):
            return label
            
    # 2. Parent Process Heuristics
    _PROC_MAP = [
        ("antigravity", "Google Antigravity"),
        ("opencode", "OpenCode"),
        ("cursor", "Cursor"),
        ("windsurf", "Windsurf"),
        ("claude", "Claude Desktop"),
        ("gemini", "Gemini CLI"),
        ("cline", "Cline"),
        ("jetbrains", "JetBrains"),
        ("zed", "Zed")
    ]
    
    try:
        proc = psutil.Process(os.getpid())
        for ancestor in [proc] + proc.parents():
            try:
                name = ancestor.name().lower()
                for fragment, label in _PROC_MAP:
                    if fragment in name:
                        return label
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
        
    return "Generic CLI"

def extract_content(data: Dict, platform: str) -> tuple[str, Optional[str], Optional[str]]:
    """
    Extracts raw text, tool name, and agent label from a payload.
    Agent labels identify sub-threads or specialized agent types.
    """
    tool_name = data.get("tool_name") or data.get("tool") or "unknown"
    agent_label = None
    content = ""
    
    # Platform-specific subagent detection
    if platform == "Cursor":
        res = data.get("result", "")
        if isinstance(res, str):
            if res.startswith("[Explore]"): agent_label = "Explore"
            elif res.startswith("[Bash]"): agent_label = "Bash"
    elif platform == "Gemini CLI":
        agent_label = data.get("hookSpecificOutput", {}).get("threadLabel")
    
    # Shape-Aware Extraction
    if "tool_response" in data and isinstance(data["tool_response"], dict):
        content = data["tool_response"].get("llmContent", "")
    if not content:
        content = data.get("result", "")
    if not content:
        content = data.get("llmContent") or data.get("content") or ""
        
    return content, tool_name, agent_label

def inject_content(data: Dict, content: str, platform: str) -> Dict:
    """
    Injects processed content back into the platform-specific JSON payload.
    """
    # 1. Standard MCP / VSCode / Gemini / OpenCode Shape
    if "tool_response" in data and isinstance(data["tool_response"], dict):
        data["tool_response"]["llmContent"] = content
        return data
        
    # 2. Cursor / Claude Desktop / CLI Shape
    if "result" in data:
        data["result"] = content
        return data
        
    # 3. Fallback: if 'llmContent' exists directly
    if "llmContent" in data:
        data["llmContent"] = content
    else:
        # 4. Universal key for unrecognized shapes
        data["processed_content"] = content
        
    return data
