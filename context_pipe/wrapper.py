# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import json
import time
import hashlib
import os
from typing import Dict, Any
from .platforms import detect_client_id, extract_content, inject_content
from .orchestrator import run_pipe, resolve_pipe_from_context, CPP_SIGNATURE
from .telemetry import log_telemetry, generate_audit_header


def check_echo(text: str) -> bool:
    """Checks if the content was processed recently to prevent loops (30s TTL)."""
    if not text or len(text) < 500:
        return False

    # Store echo markers in project temp dir
    cache_dir = os.path.join(os.getcwd(), ".pipe_cache")
    os.makedirs(cache_dir, exist_ok=True)

    content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    echo_path = os.path.join(cache_dir, f"echo_{content_hash}.tmp")
    now = time.time()

    if os.path.exists(echo_path):
        try:
            with open(echo_path, "r") as f:
                expiry = float(f.read().strip())
            if now < expiry:
                return True
        except (OSError, ValueError):
            pass

    # Write new marker
    try:
        with open(echo_path, "w") as f:
            f.write(str(now + 30))
    except OSError:
        pass
    return False


def wrap_payload(raw_json: str, config: Dict[str, Any]) -> str:
    """
    Takes a raw JSON-RPC response, applies the optimal context pipe,
    and returns the re-wrapped JSON response.
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return raw_json

    start_t = time.time()

    # 1. Platform Detection
    platform = detect_client_id()
    raw_content, tool_name, agent_label = extract_content(data, platform)

    # 2. Signature Check (Bypass)
    if CPP_SIGNATURE in str(raw_content):
        return raw_json

    # 2.5 Structured Data Exemption
    # Do not pipe valid JSON dictionaries or lists (e.g., Serena outputs)
    try:
        if isinstance(json.loads(str(raw_content)), (dict, list)):
            return raw_json
    except (json.JSONDecodeError, TypeError):
        pass

    # 3. Guard: Echo Detection (Disk-Based)
    if check_echo(str(raw_content)):
        return raw_json

    # 4. Dynamic Routing
    pipe_name = resolve_pipe_from_context(config, str(tool_name), len(str(raw_content)))
    if not pipe_name:
        return raw_json

    pipe = next((p for p in config.get("pipes", []) if p["name"] == pipe_name), None)
    if not pipe:
        return raw_json

    # 5. Execution
    try:
        sifted_content, trace = run_pipe(pipe, str(raw_content), tool_name=tool_name, agent_label=agent_label)
        latency_ms = (time.time() - start_t) * 1000

        # 6. Telemetry (Accounting per node)
        latency_per_node = latency_ms / max(1, len(trace))
        for entry in trace:
            if "error" in entry:
                continue
            log_telemetry(
                pipe_name=pipe_name,
                tool_name=f"{entry.get('node', 'unknown')}:{tool_name}",
                original_size=entry.get("input_size", 0),
                final_size=entry.get("output_size", 0),
                latency_ms=latency_per_node,
                platform=platform,
                agent_label=agent_label,
            )

        # 7. Audit Header
        header = generate_audit_header(pipe_name, trace, latency_ms)

        # 8. Inject & Signature
        final_content = f"{header}{sifted_content}\n\n{CPP_SIGNATURE}"
        data = inject_content(data, final_content, platform)

        return json.dumps(data)
    except Exception:
        return raw_json
