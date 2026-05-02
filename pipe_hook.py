# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import json
import os
from context_pipe.platforms import detect_client_id, extract_content, inject_content
from context_pipe.orchestrator import run_pipe

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

    # 1. Detect Platform & Extract Content
    platform = detect_client_id()
    raw_content, tool_name = extract_content(data, platform)

    # 2. Safety Bypass: Already processed?
    if CPP_SIGNATURE in str(raw_content):
        sys.stdout.write(raw_input)
        return

    # 3. Decision Logic: Should we pipe?
    # For now, we only pipe if it's large (> 1000 chars)
    if len(str(raw_content)) < 1000:
        sys.stdout.write(raw_input)
        return

    # 4. Load Pipe Configuration
    # We use 'standard-distill' as the default pipe for the hook
    config_path = os.environ.get("PIPE_CONFIG_PATH", "pipes.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        # No config, no pipe
        sys.stdout.write(raw_input)
        return

    # Default Hook Pipe
    pipe_name = os.environ.get("PIPE_HOOK_DEFAULT", "standard-distill")
    pipe = next((p for p in config.get("pipes", []) if p["name"] == pipe_name), None)

    if not pipe:
        sys.stdout.write(raw_input)
        return

    # 5. Execute Pipe
    try:
        sifted_content = run_pipe(pipe, raw_content)
        
        # 6. Inject & Signature
        final_content = f"{sifted_content}\n\n{CPP_SIGNATURE}"
        data = inject_content(data, final_content, platform)
        
        sys.stdout.write(json.dumps(data))
    except Exception:
        # On failure, fail safe by returning original
        sys.stdout.write(raw_input)

if __name__ == "__main__":
    main()
