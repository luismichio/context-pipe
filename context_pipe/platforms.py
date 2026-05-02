# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import psutil
from typing import Dict, Optional

def detect_client_id() -> str:
    """
    Detects which AI client/IDE is currently calling the hook.
    Returns a human-readable label for telemetry and routing.
    """
    
    # 1. Environment Variable Detection (Highest Priority)
    env_map = {
        "ANTIGRAVITY_AGENT": "Google Antigravity",
        "CLAUDE_TOOL_NAME": "Claude Desktop",
        "CURSOR_SESSION_ID": "Cursor",
        "VSCODE_PID": "VSCode",
        "GEMINI_SESSION_ID": "Gemini CLI",
        "OPENCODE_ENV": "OpenCode",
        "ZED_SESSION": "Zed",
        "CONTINUE": "Continue",
        "WINDSURF_AGENT": "Windsurf"
    }
    
    for var, label in env_map.items():
        if os.environ.get(var):
            return label
            
    # 2. Parent Process Detection
    try:
        parent = psutil.Process(os.getppid())
        parent_name = parent.name().lower()
        
        if "cursor" in parent_name: return "Cursor"
        if "code" in parent_name: return "VSCode"
        if "claude" in parent_name: return "Claude Desktop"
        if "zed" in parent_name: return "Zed"
        if "continue" in parent_name: return "Continue"
        if "windsurf" in parent_name: return "Windsurf"
        if "py" in parent_name or "python" in parent_name: return "Python Script"
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
        
    return "Generic CLI"

def extract_content(data: Dict, platform: str) -> tuple[str, Optional[str]]:
    """
    Extracts raw text content and tool name from a platform-specific JSON payload.
    """
    tool_name = data.get("tool_name") or data.get("tool") or "unknown"
    content = ""
    
    # 1. Standard MCP / VSCode / Gemini / OpenCode Shape
    if "tool_response" in data and isinstance(data["tool_response"], dict):
        content = data["tool_response"].get("llmContent", "")
        
    # 2. Cursor / Claude Desktop / CLI Shape
    if not content:
        content = data.get("result", "")
        
    # 3. Fallback search for common content keys
    if not content:
        content = data.get("llmContent") or data.get("content") or ""
        
    # 4. Final fallback: whole data if it's a string
    if not content and isinstance(data, str):
        content = data
        
    return content, tool_name

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
