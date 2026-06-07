# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import time
import threading
from typing import Dict, Any, Optional, List

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


def resolve_telemetry_file(config_path: Optional[str] = None) -> str:
    """Resolves telemetry path at call time based on active config_path.

    Always evaluated lazily so multi-root workspaces get the correct
    per-project file instead of the server's startup-cwd file (REPORT_043).
    """
    if config_path:
        project_dir = os.path.dirname(os.path.abspath(config_path))
        return os.path.join(project_dir, ".pipe_telemetry.jsonl")
    # Lazy resolution: walk upward from the *current* cwd at call time,
    # not from the cwd that was frozen when the module was imported.
    return _resolve_telemetry_path()


# Telemetry Consent Gate (Opt-In by Default)
# Telemetry runs ONLY when SIFT_TELEMETRY_OPTED_IN=true is explicitly set.
# Kill-switch CPP_TELEMETRY_DISABLED=true is respected for privacy.
def check_telemetry_disabled(config_path: Optional[str] = None) -> bool:
    # 1. Environment variable (Highest priority kill-switch)
    if (os.environ.get("CPP_TELEMETRY_DISABLED", "").lower() == "true" or 
        os.environ.get("PIPE_TELEMETRY_DISABLED", "").lower() == "true"):
        return True
    
    if os.environ.get("SIFT_TELEMETRY_OPTED_IN", "").lower() == "true":
        return False

    # 2. Local .gemini/settings.json (Consent check)
    # Orchestrator and Engine follow the same Sift opt-in state for cloud pulses.
    try:
        def find_in_dict(d: dict, key: str) -> Optional[str]:
            if key in d:
                return str(d[key])
            for v in d.values():
                if isinstance(v, dict):
                    res = find_in_dict(v, key)
                    if res:
                        return res
            return None

        if config_path:
            curr = os.path.abspath(os.path.dirname(config_path))
        else:
            curr = os.path.abspath(os.getcwd())

        while True:
            settings_path = os.path.join(curr, ".gemini", "settings.json")
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    val = find_in_dict(settings, "SIFT_TELEMETRY_OPTED_IN")
                    if val and val.lower() == "true":
                        return False
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent
    except Exception:
        pass
    
    # Default to disabled if no settings found (safe default for IDE hooks)
    return True


PIPE_TELEMETRY_DISABLED = check_telemetry_disabled()

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
    config_path: Optional[str] = None,
    trace: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Logs tool performance metrics. 
    Prioritizes delegation to semantic_sift (Shared Local Ledger) to avoid
    dual formats, falling back to local JSONL if sift is unavailable.
    """
    if PIPE_TELEMETRY_DISABLED or check_telemetry_disabled(config_path):
        return

    # Attempt delegation to Semantic-Sift (Shared Local Ledger) to avoid
    # dual formats, falling back to local JSONL if sift is unavailable.
    try:
        from semantic_sift.telemetry import log_telemetry as sift_log
        from semantic_sift.telemetry import send_telemetry_pulse
        
        # 1. Update the local ledger (retains the specific namespaced tool)
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
            skip_pulse=True  # Keep local ledger update silent
        )
        
        # 2. Pulse to Supabase under the common identifier "context-pipe"
        if not cache_hit:
            send_telemetry_pulse(
                tool_name="context-pipe",  # Common identifier to group them in the dashboard
                original=original_size,
                final=final_size,
                latency=latency_ms,
                tier_override=tier,
                client_id_override=platform,
                agent_label=agent_label,
                reason=pipe_name  # Preserves the specific pipe name in the "reason" database column
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
            "tier": tier,
            "project": os.path.basename(os.path.dirname(config_path)) if config_path else "unknown"
        }
        if trace is not None:
            event["trace"] = trace

        with _TELEMETRY_LOCK:
            with open(resolve_telemetry_file(config_path), "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")

    except Exception:
        # Fail silently to avoid breaking the tool execution
        pass


def log_bypass_event(
    tool_name: str,
    reason: str,
    platform: str = "unknown",
    pipe_name: str = "unknown",
    agent_label: Optional[str] = None,
    config_path: Optional[str] = None,
) -> None:
    """Records why a pipe was bypassed (e.g., Echo Guard, Signature detected)."""
    if PIPE_TELEMETRY_DISABLED or check_telemetry_disabled(config_path):
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
            "timestamp": time.ctime(),
            "project": os.path.basename(os.path.dirname(config_path)) if config_path else "unknown"
        }
        with _TELEMETRY_LOCK:
            with open(resolve_telemetry_file(config_path), "a", encoding="utf-8") as f:
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
    agent_label: Optional[str] = None,
    config_path: Optional[str] = None,
) -> None:
    """Records an unmapped heavy tool call event."""
    if PIPE_TELEMETRY_DISABLED or check_telemetry_disabled(config_path):
        return

    try:
        event = {
            "type": "unmapped",
            "tool_name": tool_name,
            "original_chars": original_size,
            "platform": platform,
            "agent": agent_label or "Main",
            "timestamp": time.ctime(),
            "project": os.path.basename(os.path.dirname(config_path)) if config_path else "unknown"
        }
        with _TELEMETRY_LOCK:
            with open(resolve_telemetry_file(config_path), "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
    except Exception:
        pass

def log_fallback_event(
    tool_name: str,
    reason: str,
    config_path: Optional[str] = None,
) -> None:
    """
    Records a hook fallback event  fired when ``pipe_hook.py`` catches an
    unexpected exception and returns raw input to the agent unchanged.
    """
    if PIPE_TELEMETRY_DISABLED or check_telemetry_disabled(config_path):
        return

    try:
        event = {
            "type": "fallback",
            "tool_name": tool_name,
            "reason": reason,
            "project": os.path.basename(os.path.dirname(config_path)) if config_path else "unknown"
        }
        with _TELEMETRY_LOCK:
            with open(resolve_telemetry_file(config_path), "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
    except Exception:
        pass


def get_latest_telemetry(config_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
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

    telemetry_file = resolve_telemetry_file(config_path)
    if not os.path.exists(telemetry_file):
        return None

    try:
        last_tool_event = None
        with _TELEMETRY_LOCK:
            with open(telemetry_file, "r", encoding="utf-8") as f:
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


def _parse_time_string(time_str: Optional[str]) -> Optional[float]:
    if not time_str:
        return None
    try:
        t_struct = time.strptime(time_str, "%a %b %d %H:%M:%S %Y")
        return time.mktime(t_struct)
    except Exception:
        pass
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        pass
    try:
        return float(time_str)
    except Exception:
        return None


def get_balance_sheet(
    session_id: Optional[str] = None,
    last_hours: Optional[float] = None,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculates context ROI. Aggregates both local JSONL and Semantic-Sift ledgers.
    Supports filtering by session_id and last_hours.
    """
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

    total_latency = 0.0
    latency_calls = 0
    now = time.time()

    # 1. Process Semantic-Sift Ledger (JSON)
    try:
        from semantic_sift.telemetry import TELEMETRY_FILE as SIFT_FILE
        if os.path.exists(SIFT_FILE):
            with open(SIFT_FILE, "r") as f:
                sift_data = json.load(f)
            for sid, sdata in sift_data.items():
                if session_id and sid != session_id:
                    continue
                if last_hours is not None:
                    ts_str = sdata.get("timestamp") or sdata.get("start_time")
                    event_time = _parse_time_string(ts_str)
                    if event_time is not None and (now - event_time > last_hours * 3600):
                        continue
                for tool, stats in sdata.get("tools", {}).items():
                    if stats.get("is_node") or "sift_cli_" in tool:
                        continue
                    oc = stats.get("original_chars", 0)
                    fc = stats.get("final_chars", 0)
                    delta = fc - oc
                    if delta > 0:
                        results["signal_added"] += delta
                    else:
                        results["noise_removed"] += abs(delta)
                    calls = stats.get("calls", 0)
                    results["total_events"] += calls

                    lat = stats.get("latency_ms", 0.0) or stats.get("latency", 0.0)
                    total_latency += lat * calls
                    latency_calls += calls
    except Exception:
        pass

    # 2. Process Local Ledger (JSONL)
    telemetry_file = resolve_telemetry_file(config_path)
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)

                        # Apply filters
                        if session_id and event.get("session_id") != session_id:
                            continue
                        if last_hours is not None:
                            ts_str = event.get("start_time") or event.get("timestamp")
                            event_time = _parse_time_string(ts_str)
                            if event_time is not None and (now - event_time > last_hours * 3600):
                                continue

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
                            if event.get("is_node"):
                                continue
                            results["total_events"] += 1
                            orig = event.get("original_chars", 0)
                            final = event.get("final_chars", 0)
                            delta = final - orig
                            if delta > 0:
                                results["signal_added"] += delta
                            else:
                                results["noise_removed"] += abs(delta)
                            
                            lat = event.get("latency_ms", 0.0)
                            total_latency += lat
                            latency_calls += 1
                    except Exception:
                        pass
        except Exception:
            pass

    results["net_change"] = results["signal_added"] - results["noise_removed"]
    if latency_calls > 0:
        results["avg_latency_ms"] = total_latency / latency_calls
    return results


def get_recent_telemetry(limit: int = 1, config_path: Optional[str] = None) -> list[Dict[str, Any]]:
    """Retrieves the last recorded tool telemetry event(s) in reverse chronological order (newest first)."""
    telemetry_file = resolve_telemetry_file(config_path)
    if not os.path.exists(telemetry_file):
        return []
    try:
        events = []
        with _TELEMETRY_LOCK:
            with open(telemetry_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event.get("type") == "tool_call":
                            events.append({
                                "session_id": event.get("session_id"),
                                "tool_key": event.get("tool_name"),
                                "original_chars": event.get("original_chars", 0),
                                "final_chars": event.get("final_chars", 0),
                                "original_tokens": event.get("original_tokens", 0),
                                "final_tokens": event.get("final_tokens", 0),
                                "latency_ms": event.get("latency_ms", 0.0),
                                "cache_hit": event.get("cache_hit", False),
                                "platform": event.get("platform", "unknown"),
                                "agent": event.get("agent", "Main"),
                                "tier": event.get("tier", "Real-World"),
                            })
                    except Exception:
                        pass
        return events[-limit:][::-1]
    except Exception:
        return []

# --- [Semantic-Sift Audit] ---
