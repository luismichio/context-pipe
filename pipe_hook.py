# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import json
import os
import time
from context_pipe.platforms import detect_client_id, extract_content, inject_content
from context_pipe.orchestrator import run_pipe, resolve_pipe_from_context
from context_pipe.telemetry import log_telemetry

# Metadata Signatures
CPP_SIGNATURE = "--- [Context-Pipe: Native Execution] ---"

def main():
    raw_input = sys.stdin.read()
    if not raw_input:
        return

    try:
        data = json.loads(raw_input)
    except json.JSONDecodeError:
        # If not JSON, we can't hook it properly, just pass it through
        sys.stdout.write(raw_input)
        return

    start_t = time.time()

    # 1. Detect Platform & Extract Content
    platform = detect_client_id()
    raw_content, tool_name = extract_content(data, platform)

    # 2. Safety Bypass: Already processed?
    if CPP_SIGNATURE in str(raw_content):
        sys.stdout.write(raw_input)
        return

    # 3. Load Pipe Configuration
    config_path = os.environ.get("PIPE_CONFIG_PATH", "pipes.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        sys.stdout.write(raw_input)
        return

    # 4. Resolve Pipe Name (Agnostic Mapping)
    pipe_name = resolve_pipe_from_context(config, str(tool_name), len(str(raw_content)))

    if not pipe_name:
        sys.stdout.write(raw_input)
        return

    pipe = next((p for p in config.get("pipes", []) if p["name"] == pipe_name), None)

    if not pipe:
        sys.stdout.write(raw_input)
        return

    # 5. Execute Pipe
    try:
        sifted_content, trace = run_pipe(pipe, str(raw_content))
        
        # 6. Telemetry (Accounting per node)
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
        
        # 7. Inject & Signature
        final_content = f"{sifted_content}\n\n{CPP_SIGNATURE}"
        data = inject_content(data, final_content, platform)
        
        sys.stdout.write(json.dumps(data))
    except Exception:
        # On failure, fail safe by returning original
        sys.stdout.write(raw_input)

if __name__ == "__main__":
    main()
