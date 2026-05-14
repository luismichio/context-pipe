# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import time
import uuid
import asyncio
import logging
from typing import Dict, Any
from .platforms import detect_client_id, extract_content, inject_content
from .orchestrator import run_pipe, resolve_pipe_from_context, CPP_SIGNATURE, check_echo
from .telemetry import log_telemetry, generate_audit_header

logger = logging.getLogger(__name__)

# Global session for the wrapper (hook context)
WRAPPER_SESSION_ID = f"hook-{uuid.uuid4().hex[:8]}"
WRAPPER_START_TIME = time.ctime()


def _generate_bypass_payload(raw_json: str, platform: str) -> str:
    """Returns the platform-correct payload to silently bypass sifting."""
    if platform == "Gemini CLI":
        return json.dumps({"decision": "allow"})
    return raw_json


def wrap_payload(raw_json: str, config: Dict[str, Any]) -> str:
    """
    Parses an incoming tool response, applies the optimal context pipe,
    and returns the re-wrapped JSON response.
    """
    debug = os.environ.get("CPP_DEBUG", "").lower() == "true"
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        if debug:
            logger.debug("[CPP DEBUG] Error: Invalid JSON input to wrapper.")
        return raw_json

    start_t = time.time()

    # 1. Platform Detection
    platform = detect_client_id()
    raw_content, tool_name, agent_label = extract_content(data, platform)

    if debug:
        content_peek = str(raw_content)[:100].replace("\n", " ")
        logger.debug(f"[CPP DEBUG] Platform: {platform}, Tool: {tool_name}, Content: {content_peek}...")

    # 2. Signature Check (Bypass)
    if CPP_SIGNATURE in str(raw_content):
        if debug:
            logger.debug(f"[CPP DEBUG] Bypassing '{tool_name}': Signature detected.")
        return _generate_bypass_payload(raw_json, platform)

    # 2.5 Structured Data Exemption
    # Do not pipe valid JSON dictionaries or lists (e.g., Serena outputs)
    try:
        parsed = json.loads(str(raw_content))
        if isinstance(parsed, (dict, list)):
            if debug:
                logger.debug(f"[CPP DEBUG] Bypassing '{tool_name}': Structured JSON detected.")
            return _generate_bypass_payload(raw_json, platform)
    except (json.JSONDecodeError, TypeError):
        pass

    # 4. Dynamic Routing
    pipe_name = resolve_pipe_from_context(config, str(tool_name), len(str(raw_content)))
    if not pipe_name:
        if debug:
            logger.debug(f"[CPP DEBUG] Bypassing '{tool_name}': No routing match found.")
        return _generate_bypass_payload(raw_json, platform)

    # 3. Guard: Echo Detection (Disk-Based)
    # Scoped to pipe_name to prevent false suppression cross-pipe
    if check_echo(str(raw_content), pipe_name=pipe_name):
        if debug:
            logger.debug(f"[CPP DEBUG] Bypassing '{tool_name}': Echo Guard hit (recently processed).")
        return _generate_bypass_payload(raw_json, platform)

    pipe = next((p for p in config.get("pipes", []) if p["name"] == pipe_name), None)
    if not pipe:
        if debug:
            logger.debug(f"[CPP DEBUG] Error: Pipe '{pipe_name}' matched but not found in config.")
        return _generate_bypass_payload(raw_json, platform)

    # 5. Execution
    try:
        sifted_content, trace = asyncio.run(run_pipe(pipe, str(raw_content), tool_name=tool_name, agent_label=agent_label))
        latency_ms = (time.time() - start_t) * 1000

        if debug:
            logger.debug(f"[CPP DEBUG] Intercepted '{tool_name}': Applied '{pipe_name}' ({len(str(raw_content))} -> {len(sifted_content)}) in {latency_ms:.1f}ms")

        # 6. Telemetry (Accounting per node)
        latency_per_node = latency_ms / max(1, len(trace))
        for entry in trace:
            if "error" in entry:
                continue

            # Note: We use the node-level data for high-fidelity attribution,
            # but log_telemetry is designed to handle this session-keyed schema.
            log_telemetry(
                session_id=WRAPPER_SESSION_ID,
                start_time=WRAPPER_START_TIME,
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
