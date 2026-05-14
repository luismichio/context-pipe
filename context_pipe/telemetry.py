# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import threading
from typing import Dict, Any, List, Optional

# Telemetry Configuration (Unified with Studio of Two standards)
# Primary: CPP_TELEMETRY_FILE, Fallback: .pipe_telemetry.jsonl
TELEMETRY_FILE = os.environ.get("CPP_TELEMETRY_FILE") or os.environ.get("PIPE_TELEMETRY_FILE", ".pipe_telemetry.jsonl")

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
    """Logs tool performance metrics locally using an append-only JSONL schema."""
    if PIPE_TELEMETRY_DISABLED:
        return

    try:
        orig_tokens = estimate_tokens(" " * original_size)
        final_tokens = estimate_tokens(" " * final_size)

        event = {
            "type": "tool_call",
            "session_id": session_id,
            "start_time": start_time,
            "tool_name": f"{pipe_name}:{tool_name}",
            "original_chars": original_size,
            "final_chars": final_size,
            "original_tokens": orig_tokens,
            "final_tokens": final_tokens,
            "latency_ms": latency_ms,
            "cache_hit": cache_hit,
            "platform": platform,
            "agent": agent_label or "Main",
            "pipe_name": pipe_name,
            "tier": tier
        }

        with _TELEMETRY_LOCK:
            with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")

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
    """
    if PIPE_TELEMETRY_DISABLED:
        return

    try:
        event = {
            "type": "fallback",
            "tool_name": tool_name,
            "reason": reason
        }
        with _TELEMETRY_LOCK:
            with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
    except Exception:
        pass


def get_latest_telemetry() -> Optional[Dict[str, Any]]:
    """Retrieves the absolute last recorded tool telemetry event."""
    if not os.path.exists(TELEMETRY_FILE):
        return None

    try:
        last_tool_event = None
        with _TELEMETRY_LOCK:
            with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event.get("type") == "tool_call":
                            last_tool_event = event
                    except json.JSONDecodeError:
                        pass
                        
        if last_tool_event:
            return {
                "session_id": last_tool_event.get("session_id"),
                "tool_key": last_tool_event.get("tool_name"),
                "original_chars": last_tool_event.get("original_chars", 0),
                "final_chars": last_tool_event.get("final_chars", 0),
                "original_tokens": last_tool_event.get("original_tokens", 0),
                "final_tokens": last_tool_event.get("final_tokens", 0),
                "latency_ms": last_tool_event.get("latency_ms", 0),
                "cache_hit": last_tool_event.get("cache_hit", False),
                "platform": last_tool_event.get("platform", "unknown"),
                "agent": last_tool_event.get("agent", "Main"),
                "tier": last_tool_event.get("tier", "Real-World"),
            }
        return None
    except Exception:
        return None


def get_balance_sheet() -> Dict[str, Any]:
    """Calculates context ROI by aggregating all sessions from the JSONL file."""
    if not os.path.exists(TELEMETRY_FILE):
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
    fallback_count = 0

    try:
        with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    
                    if event.get("type") == "fallback":
                        fallback_count += 1
                        continue
                        
                    if event.get("type") == "tool_call":
                        tool_id = event.get("tool_name", "")
                        if "sift_cli" in tool_id:
                            continue
                            
                        total_calls += 1
                        total_latency += event.get("latency_ms", 0)
                        
                        orig = event.get("original_chars", 0)
                        final = event.get("final_chars", 0)
                        delta = final - orig
                        
                        if delta > 0:
                            signal_added += delta
                        else:
                            noise_removed += abs(delta)
                            
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass

    net_change = signal_added - noise_removed

    return {
        "signal_added": signal_added,
        "noise_removed": noise_removed,
        "net_change": net_change,
        "total_events": total_calls,
        "avg_latency_ms": total_latency / total_calls if total_calls > 0 else 0,
        "fallback_events": fallback_count,
    }
