# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import json
import time
from typing import Dict, Any, Optional
from .platforms import detect_client_id, extract_content, inject_content
from .orchestrator import run_pipe, resolve_pipe_from_context, CPP_SIGNATURE
from .telemetry import log_telemetry

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
    raw_content, tool_name = extract_content(data, platform)

    # 2. Signature Check (Bypass)
    if CPP_SIGNATURE in str(raw_content):
        return raw_json

    # 3. Dynamic Routing
    pipe_name = resolve_pipe_from_context(config, str(tool_name), len(str(raw_content)))
    if not pipe_name:
        return raw_json

    pipe = next((p for p in config.get("pipes", []) if p["name"] == pipe_name), None)
    if not pipe:
        return raw_json

    # 4. Execution
    try:
        sifted_content, trace = run_pipe(pipe, str(raw_content))
        
        # 5. Telemetry
        latency_per_node = (time.time() - start_t) * 1000 / max(1, len(trace))
        for entry in trace:
            if "error" in entry: continue
            log_telemetry(
                pipe_name=pipe_name,
                tool_name=f"{entry['node']}:{tool_name}",
                original_size=entry['input_size'],
                final_size=entry['output_size'],
                latency_ms=latency_per_node,
                platform=platform
            )
            
        # 6. Injection & Signature
        final_content = f"{sifted_content}\n\n{CPP_SIGNATURE}"
        data = inject_content(data, final_content, platform)
        
        return json.dumps(data)
    except Exception:
        return raw_json
