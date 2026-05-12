# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import threading
from typing import Dict, Any, List, Optional

# Telemetry Configuration (Unified with Studio of Two standards)
# Primary: CPP_TELEMETRY_FILE, Fallback: .pipe_telemetry.json
TELEMETRY_FILE = os.environ.get("CPP_TELEMETRY_FILE") or os.environ.get("PIPE_TELEMETRY_FILE", ".pipe_telemetry.json")

# Telemetry Consent Gate (Opt-Out by Default)
# Telemetry runs automatically to provide the Context Balance Sheet.
# Kill-switch CPP_TELEMETRY_DISABLED=true is respected for privacy.
PIPE_TELEMETRY_DISABLED = (
    os.environ.get("CPP_TELEMETRY_DISABLED", "").lower() == "true"
    or os.environ.get("PIPE_TELEMETRY_DISABLED", "").lower() == "true"
)

# Locks for concurrent file access
_TELEMETRY_LOCK = threading.Lock()


def log_telemetry(
    session_id: str,
    start_time: str,
    tool_name: str,
    original_size: int,
    final_size: int,
    latency_ms: float,
    cache_hit: bool = False,
    platform: str = "unknown",
    agent_label: Optional[str] = None,
    pipe_name: str = "unknown",
    tier: str = "Real-World",
) -> None:
    """Logs tool performance metrics locally using the unified session-keyed schema."""
    if PIPE_TELEMETRY_DISABLED:
        return

    try:
        with _TELEMETRY_LOCK:
            data = {}
            if os.path.exists(TELEMETRY_FILE):
                try:
                    with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    data = {}

            # Ensure session entry exists
            if session_id not in data:
                data[session_id] = {"start_time": start_time, "tools": {}}

            # Track by tool (convention: pipe:tool)
            composite_tool = f"{pipe_name}:{tool_name}"

            tool_stats = data[session_id]["tools"].get(
                composite_tool,
                {
                    "calls": 0,
                    "original_chars": 0,
                    "final_chars": 0,
                    "original_tokens": 0,
                    "final_tokens": 0,
                    "total_latency_ms": 0,
                    "cache_hits": 0,
                    "platform": platform,
                    "agent": agent_label or "Main",
                    "tier": tier,
                },
            )

            orig_tokens = estimate_tokens(" " * original_size)
            final_tokens = estimate_tokens(" " * final_size)

            tool_stats["calls"] += 1
            tool_stats["original_chars"] += original_size
            tool_stats["final_chars"] += final_size
            tool_stats["original_tokens"] += orig_tokens
            tool_stats["final_tokens"] += final_tokens
            tool_stats["total_latency_ms"] += latency_ms
            if cache_hit:
                tool_stats["cache_hits"] = tool_stats.get("cache_hits", 0) + 1

            data[session_id]["tools"][composite_tool] = tool_stats

            with open(TELEMETRY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    except Exception:
        # Fail silently to avoid breaking the tool execution
        pass


def estimate_tokens(text: str) -> int:
    """Provides a fast, high-fidelity token estimate (4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def generate_audit_header(pipe_name: str, trace: List[Dict[str, Any]], latency_ms: float) -> str:
    """Generates a Markdown audit header showing cumulative ROI and node latency."""
    if not trace:
        return ""

    start_size = trace[0].get("input_size", 0)
    end_size = trace[-1].get("output_size", 0)

    # Calculate Net ROI
    reduction = (1 - (end_size / start_size)) * 100 if start_size > 0 else 0
    reduction_label = f"{reduction:.1f}% Reduction" if reduction >= 0 else f"{abs(reduction):.1f}% Augmentation"

    header = [
        f"--- [Context-Pipe: {pipe_name}] ---",
        f"📊 Context: {reduction_label} ({start_size / 1024:.1f}KB -> {end_size / 1024:.1f}KB)",
        f"⚡ Latency: {latency_ms:.1f}ms",
        "Nodes: " + " → ".join([n["node"] for n in trace if "node" in n]),
        "-----------------------------\n",
    ]
    return "\n".join(header)


def log_fallback_event(tool_name: str, reason: str) -> None:
    """
    Records a hook fallback event — fired when ``pipe_hook.py`` catches an
    unexpected exception and returns raw input to the agent unchanged.

    Events are stored under the reserved ``"__fallbacks__"`` session key so
    they never pollute tool-level ROI accounting.  They are surfaced as a
    warning count in the Balance Sheet.
    """
    if PIPE_TELEMETRY_DISABLED:
        return

    try:
        with _TELEMETRY_LOCK:
            data: Dict[str, Any] = {}
            if os.path.exists(TELEMETRY_FILE):
                try:
                    with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    data = {}

            fb = data.setdefault("__fallbacks__", {"events": []})
            fb["events"].append({"tool": tool_name, "reason": reason})

            with open(TELEMETRY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    except Exception:
        pass


def get_latest_telemetry() -> Optional[Dict[str, Any]]:
    """Retrieves the absolute last recorded telemetry event across all sessions."""
    if not os.path.exists(TELEMETRY_FILE):
        return None

    try:
        with _TELEMETRY_LOCK:
            with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data:
                return None

            # 1. Get the most recent session (last key in the dict)
            session_keys = list(data.keys())
            if not session_keys:
                return None
            
            # Filter out fallback sentinel
            session_keys = [k for k in session_keys if k != "__fallbacks__"]
            if not session_keys:
                return None
                
            last_session_id = session_keys[-1]
            last_session = data[last_session_id]

            # 2. Get the most recent tool call in that session
            tools = last_session.get("tools", {})
            if not tools:
                return None

            last_tool_key = list(tools.keys())[-1]
            result = tools[last_tool_key].copy()
            result["tool_key"] = last_tool_key
            result["session_id"] = last_session_id
            return result

    except Exception:
        return None


def get_balance_sheet() -> Dict[str, Any]:
    """Calculates context ROI by aggregating all sessions.
    Filters out 'node' level events to prevent double counting with 'mcp' protocol events.
    """
    if not os.path.exists(TELEMETRY_FILE):
        return {
            "signal_added": 0,
            "noise_removed": 0,
            "net_change": 0,
            "total_events": 0,
            "avg_latency_ms": 0.0,
            "fallback_events": 0,
        }

    try:
        with open(TELEMETRY_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {
            "signal_added": 0,
            "noise_removed": 0,
            "net_change": 0,
            "total_events": 0,
            "avg_latency_ms": 0.0,
            "fallback_events": 0,
        }

    total_calls = 0
    total_latency = 0.0
    signal_added = 0
    noise_removed = 0

    # Aggregate across all sessions and tools
    if isinstance(data, dict):
        for session in data.values():
            tools = session.get("tools", {})
            for tool_id, stats in tools.items():
                # Anti-Double-Counting Logic:
                # If the tool name indicates a 'sift_cli' engine call, it's a sub-node of an MCP call.
                # We skip sub-nodes to get the clean protocol-level balance sheet.
                if "sift_cli" in tool_id:
                    continue

                calls = stats.get("calls", 0)
                total_calls += calls
                total_latency += stats.get("total_latency_ms", 0)

                orig = stats.get("original_chars", 0)
                final = stats.get("final_chars", 0)
                delta = final - orig

                if delta > 0:
                    signal_added += delta
                else:
                    noise_removed += abs(delta)
    elif isinstance(data, list):
            # Fallback for old flat format
            for e in data:
                total_calls += 1
                total_latency += e.get("latency_ms", 0)
                delta = e.get("delta", 0)
                if delta > 0:
                    signal_added += delta
                else:
                    noise_removed += abs(delta)

    # Count hook fallback events (stored under __fallbacks__ sentinel key)
    fallback_count = 0
    if isinstance(data, dict):
        fallback_count = len(data.get("__fallbacks__", {}).get("events", []))

    net_change = signal_added - noise_removed

    return {
        "signal_added": signal_added,
        "noise_removed": noise_removed,
        "net_change": net_change,
        "total_events": total_calls,
        "avg_latency_ms": total_latency / total_calls if total_calls > 0 else 0,
        "fallback_events": fallback_count,
    }
