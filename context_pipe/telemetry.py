# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import time
from typing import Dict, Any, List, Optional

# Telemetry Configuration (Unified with Studio of Two standards)
# Primary: CPP_TELEMETRY_FILE, Fallback: .pipe_telemetry.json
TELEMETRY_FILE = os.environ.get("CPP_TELEMETRY_FILE") or os.environ.get("PIPE_TELEMETRY_FILE", ".pipe_telemetry.json")

# Privacy Kill-Switch
# Primary: CPP_TELEMETRY_DISABLED, Fallback: PIPE_TELEMETRY_DISABLED
PIPE_TELEMETRY_DISABLED = (
    os.environ.get("CPP_TELEMETRY_DISABLED", "").lower() == "true"
    or os.environ.get("PIPE_TELEMETRY_DISABLED", "false").lower() == "true"
)

IDENTITY_FILE = ".pipe_identity"


def _ensure_identity_ignored() -> None:
    """Proactively ensures .pipe_identity and the telemetry file are in .gitignore."""
    gitignore_path = os.path.join(os.getcwd(), ".gitignore")
    try:
        content = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

        additions = []
        if IDENTITY_FILE not in content:
            additions.append(IDENTITY_FILE)
        if TELEMETRY_FILE not in content:
            additions.append(TELEMETRY_FILE)

        if additions:
            prefix = "\n" if content and not content.endswith("\n") else ""
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write(prefix + "\n".join(additions) + "\n")
    except OSError:
        pass


def get_machine_id() -> str:
    """Generates a stable, anonymous ID for this machine, ensuring it isn't committed."""
    if PIPE_TELEMETRY_DISABLED:
        return "anonymous-user"

    _ensure_identity_ignored()

    path = os.path.join(os.getcwd(), IDENTITY_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        except OSError:
            pass

    import uuid

    new_id = str(uuid.uuid4())
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_id)
    except OSError:
        pass
    return new_id


def log_telemetry(
    pipe_name: str,
    tool_name: str,
    original_size: int,
    final_size: int,
    latency_ms: float,
    platform: str = "unknown",
    agent_label: Optional[str] = None,
) -> None:
    """Records a context transformation event (reduction or augmentation)."""
    if PIPE_TELEMETRY_DISABLED:
        return

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
        "delta": delta,  # Positive = Augmentation, Negative = Reduction
        "latency_ms": round(latency_ms, 2),
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


def estimate_tokens(text: str) -> int:
    """Provides a fast, high-fidelity token estimate (4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def generate_audit_header(pipe_name: str, trace: List[Dict[str, Any]], latency_ms: float) -> str:
    """Generates a Markdown audit header showing cumulative ROI and node latency."""
    if not trace:
        return ""

    start_size = trace[0]["input_size"]
    end_size = trace[-1]["output_size"]

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


def get_balance_sheet() -> Dict[str, Any]:
    """Calculates context ROI as a Balance Sheet of signal vs noise."""
    if not os.path.exists(TELEMETRY_FILE):
        return {"signal_added": 0, "noise_removed": 0, "net_change": 0, "total_events": 0, "avg_latency_ms": 0.0}

    try:
        with open(TELEMETRY_FILE, "r") as f:
            events = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"signal_added": 0, "noise_removed": 0, "net_change": 0, "total_events": 0, "avg_latency_ms": 0.0}

    signal_added = sum(e["delta"] for e in events if e["delta"] > 0)
    noise_removed = sum(abs(e["delta"]) for e in events if e["delta"] < 0)
    net_change = signal_added - noise_removed

    return {
        "signal_added": signal_added,
        "noise_removed": noise_removed,
        "net_change": net_change,
        "total_events": len(events),
        "avg_latency_ms": sum(e["latency_ms"] for e in events) / len(events) if events else 0,
    }
