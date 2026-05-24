# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import time
import threading
from typing import Dict, Any, Optional

# Telemetry Configuration (Unified with Studio of Two standards)
# Primary: CPP_TELEMETRY_FILE, Fallback: .pipe_telemetry.jsonl


def _resolve_telemetry_path() -> str:
    """
    Finds the project root by looking for .pipe_identity or pipes.json
    starting from the CWD and traversing upwards.
    """
    if os.environ.get("CPP_TELEMETRY_FILE") or os.environ.get("PIPE_TELEMETRY_FILE"):
        return os.environ.get("CPP_TELEMETRY_FILE") or os.environ.get("PIPE_TELEMETRY_FILE", "")

    curr = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(curr, ".pipe_identity")) or os.path.exists(os.path.join(curr, "pipes.json")):
            return os.path.join(curr, ".pipe_telemetry.jsonl")

        parent = os.path.dirname(curr)
        if parent == curr:  # Root reached
            break
        curr = parent

    return os.path.join(os.getcwd(), ".pipe_telemetry.jsonl")


TELEMETRY_FILE = _resolve_telemetry_path()

# Telemetry Consent Gate (Opt-Out by Default)
# Telemetry runs automatically to provide the Context Balance Sheet.
# Kill-switch CPP_TELEMETRY_DISABLED=true is respected for privacy.
def _check_telemetry_disabled() -> bool:
    # 1. Environment variable (Highest priority kill-switch)
    if (os.environ.get("CPP_TELEMETRY_DISABLED", "").lower() == "true" or 
        os.environ.get("PIPE_TELEMETRY_DISABLED", "").lower() == "true"):
        return True
    
    # 2. Local .gemini/settings.json (Consent check)
    # Orchestrator is opt-out, but Semantic-Sift is opt-in.
    # We follow Sift's opt-in state for the cloud pulses.
    try:
        curr = os.path.abspath(os.getcwd())
        while True:
            settings_path = os.path.join(curr, ".gemini", "settings.json")
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    # If Sift is opted in, we enable pulses.
                    if str(settings.get("SIFT_TELEMETRY_OPTED_IN", "")).lower() == "true":
                        return False
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent
    except Exception:
        pass
    
    # Default to disabled if no settings found (safe default for IDE hooks)
    return False

PIPE_TELEMETRY_DISABLED = _check_telemetry_disabled()

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
    """
    Logs tool performance metrics. 
    Prioritizes delegation to semantic_sift (Shared Local Ledger) to avoid
    dual formats, falling back to local JSONL if sift is unavailable.
    """
    if PIPE_TELEMETRY_DISABLED:
        return

    # Attempt delegation to Semantic-Sift (Studio of Two standard)
    try:
        from semantic_sift.telemetry import log_telemetry as sift_log
        sift_log(
            session_id=session_id,
            start_time=start_time,
            tool_name=f"{pipe_name}:{tool_name}",
            original_chars=original_size,
            final_chars=final_size,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
            tier_override=tier,
            client_id_override=platform,
            agent_label=agent_label,
            skip_pulse=True  # MANDATE: Orchestrator never pulses actual sifts; only Engine pulses.
        )
        return
    except (ImportError, Exception):
        pass

    # Fallback to local JSONL ledger
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


def log_bypass_event(
    tool_name: str,
    reason: str,
    platform: str = "unknown",
    pipe_name: str = "unknown",
    agent_label: Optional[str] = None
) -> None:
    """Records why a pipe was bypassed (e.g., Echo Guard, Signature detected)."""
    if PIPE_TELEMETRY_DISABLED:
        return

    # Local Ledger
    try:
        event = {
            "type": "bypass",
            "tool_name": tool_name,
            "reason": reason,
            "platform": platform,
            "pipe_name": pipe_name,
            "agent": agent_label or "Main",
            "timestamp": time.ctime()
        }
        with _TELEMETRY_LOCK:
            with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
    except Exception:
        pass

    # Cloud Pulse (Transparency Mandate)
    # Bypasses pulse immediately because they represent terminal orchestrator decisions.
    # Skip cloud pulses for normal range reads to prevent database bloat and network overhead.
    if reason and "Line range <= 50 lines" in reason:
        return

    try:
        from semantic_sift.telemetry import send_telemetry_pulse
        send_telemetry_pulse(
            tool_name=f"bypass:{tool_name}",
            original=0,
            final=0,
            latency=0,
            tier_override="Bypass",
            client_id_override=platform,
            agent_label=agent_label,
            reason=reason
        )
    except Exception:
        pass


def estimate_tokens(text: str) -> int:
    """Provides a fast, high-fidelity token estimate (4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def log_unmapped_event(
    tool_name: str,
    original_size: int,
    platform: str = "unknown",
    agent_label: Optional[str] = None
) -> None:
    """Records an unmapped heavy tool call event."""
    if PIPE_TELEMETRY_DISABLED:
        return

    try:
        event = {
            "type": "unmapped",
            "tool_name": tool_name,
            "original_chars": original_size,
            "platform": platform,
            "agent": agent_label or "Main",
            "timestamp": time.ctime()
        }
        with _TELEMETRY_LOCK:
            with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
    except Exception:
        pass

def log_fallback_event(tool_name: str, reason: str) -> None:
    """
    Records a hook fallback event  fired when ``pipe_hook.py`` catches an
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
    # Priority: Semantic-Sift ledger
    try:
        from semantic_sift.telemetry import TELEMETRY_FILE as SIFT_FILE
        if os.path.exists(SIFT_FILE):
            with open(SIFT_FILE, "r") as f:
                data = json.load(f)
            # Find newest session
            if data:
                sorted(data.keys(), key=lambda k: data[k].get("start_time", ""), reverse=True)[0]
    except Exception:
        pass

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
    """Calculates context ROI. Aggregates both local JSONL and Semantic-Sift ledgers."""
    results = {
        "signal_added": 0,
        "noise_removed": 0,
        "net_change": 0,
        "total_events": 0,
        "avg_latency_ms": 0.0,
        "fallback_events": 0,
        "bypass_events": 0,
        "unmapped_events": 0,
    }

    # 1. Process Semantic-Sift Ledger (JSON)
    try:
        from semantic_sift.telemetry import TELEMETRY_FILE as SIFT_FILE
        if os.path.exists(SIFT_FILE):
            with open(SIFT_FILE, "r") as f:
                sift_data = json.load(f)
            for sid, sdata in sift_data.items():
                for tool, stats in sdata.get("tools", {}).items():
                    oc = stats.get("original_chars", 0)
                    fc = stats.get("final_chars", 0)
                    delta = fc - oc
                    if delta > 0:
                        results["signal_added"] += delta
                    else:
                        results["noise_removed"] += abs(delta)
                    results["total_events"] += stats.get("calls", 0)
    except Exception:
        pass

    # 2. Process Local Ledger (JSONL)
    if os.path.exists(TELEMETRY_FILE):
        try:
            with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event.get("type") == "fallback":
                            results["fallback_events"] += 1
                            continue
                        if event.get("type") == "bypass":
                            results["bypass_events"] += 1
                            continue
                        if event.get("type") == "unmapped":
                            results["unmapped_events"] += 1
                            continue
                        if event.get("type") == "tool_call":
                            results["total_events"] += 1
                            orig = event.get("original_chars", 0)
                            final = event.get("final_chars", 0)
                            delta = final - orig
                            if delta > 0:
                                results["signal_added"] += delta
                            else:
                                results["noise_removed"] += abs(delta)
                    except Exception:
                        pass
        except Exception:
            pass

    results["net_change"] = results["signal_added"] - results["noise_removed"]
    return results

# --- [Semantic-Sift Audit] ---
