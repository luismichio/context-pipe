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
        "ZED_SESSION": "Zed"
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
    
    if platform in ["Gemini CLI", "VSCode", "OpenCode"]:
        content = data.get("tool_response", {}).get("llmContent", "")
    elif platform == "Cursor" or platform == "Claude Desktop":
        content = data.get("result", "")
    else:
        # Fallback search for common content keys
        content = data.get("llmContent") or data.get("result") or data.get("content") or ""
        
    # If content is still empty, maybe it's the whole data as a string
    if not content and isinstance(data, str):
        content = data
        
    return content, tool_name

def inject_content(data: Dict, content: str, platform: str) -> Dict:
    """
    Injects processed content back into the platform-specific JSON payload.
    """
    if platform in ["Gemini CLI", "VSCode", "OpenCode"]:
        if "tool_response" not in data: data["tool_response"] = {}
        data["tool_response"]["llmContent"] = content
    elif platform == "Cursor" or platform == "Claude Desktop":
        data["result"] = content
    else:
        # Fallback: if 'result' exists, update it, otherwise set it
        if "result" in data: data["result"] = content
        elif "llmContent" in data: data["llmContent"] = content
        else: data["processed_content"] = content
        
    return data
