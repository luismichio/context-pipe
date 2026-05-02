# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import time
import hashlib
from typing import Dict, Any, Optional

# Telemetry Configuration
TELEMETRY_FILE = os.environ.get("PIPE_TELEMETRY_FILE", ".pipe_telemetry.json")

def get_machine_id() -> str:
    """Generates a stable, anonymous ID for this machine."""
    import socket
    import uuid
    identity = f"{socket.gethostname()}:{uuid.getnode()}"
    return hashlib.sha256(identity.encode()).hexdigest()[:12]

def log_telemetry(
    pipe_name: str,
    tool_name: str,
    original_size: int,
    final_size: int,
    latency_ms: float,
    platform: str = "unknown",
    agent_label: Optional[str] = None
) -> None:
    """Records a context transformation event (reduction or augmentation)."""
    
    delta = final_size - original_size
    
    event = {
        "timestamp": time.time(),
        "date": time.ctime(),
        "machine_id": get_machine_id(),
        "platform": platform,
        "agent": agent_label or "Main",
        "pipe": pipe_name,
        "tool": tool_name,
        "original_size": original_size,
        "final_size": final_size,
        "delta": delta, # Positive = Augmentation, Negative = Reduction
        "latency_ms": round(latency_ms, 2)
    }
    
    events = []
    if os.path.exists(TELEMETRY_FILE):
        try:
            with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                events = json.load(f)
        except (json.JSONDecodeError, OSError):
            events = []
            
    events.append(event)
    events = events[-1000:]
    
    try:
        with open(TELEMETRY_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
    except OSError:
        pass

def get_balance_sheet() -> Dict[str, Any]:
    """Calculates context ROI as a Balance Sheet of signal vs noise."""
    if not os.path.exists(TELEMETRY_FILE):
        return {"signal_added": 0, "noise_removed": 0, "net_change": 0, "events": 0}
        
    try:
        with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
            events = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"signal_added": 0, "noise_removed": 0, "net_change": 0, "events": 0}
        
    signal_added = sum(e["delta"] for e in events if e["delta"] > 0)
    noise_removed = sum(abs(e["delta"]) for e in events if e["delta"] < 0)
    net_change = signal_added - noise_removed
    
    return {
        "signal_added": signal_added,
        "noise_removed": noise_removed,
        "net_change": net_change,
        "total_events": len(events),
        "avg_latency_ms": sum(e["latency_ms"] for e in events) / len(events) if events else 0
    }
