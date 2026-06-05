# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import json
import os


def main():
    raw_input = sys.stdin.read()
    if not raw_input:
        return

    try:
        from context_pipe.wrapper import wrap_payload

        # Load Pipe Configuration
        config_path = os.environ.get("PIPE_CONFIG_PATH", "pipes.json")

        config = {"pipes": [], "mappings": []}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        # Execute Polyfill Wrapper
        result = wrap_payload(raw_input, config, config_path=config_path)
        sys.stdout.write(result)

    except Exception as e:
        # SAFETY FALLBACK: Never crash the hook.
        # Log the failure type for observability in the Balance Sheet.
        try:
            from context_pipe.telemetry import log_fallback_event
            log_fallback_event(tool_name="unknown", reason=type(e).__name__, config_path=config_path)
        except Exception:
            pass

        # Gemini CLI strictly requires a Decision Object schema even on error.
        if os.environ.get("GEMINI_SESSION_ID"):
            sys.stdout.write(json.dumps({
                "decision": "allow",
                "reason": f"Context-Pipe fallback (Error: {type(e).__name__})"
            }))
        else:
            sys.stdout.write(raw_input)


if __name__ == "__main__":
    main()
