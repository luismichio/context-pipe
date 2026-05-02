# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import json
import os
from context_pipe.wrapper import wrap_payload

def main():
    raw_input = sys.stdin.read()
    if not raw_input:
        return

    # Load Pipe Configuration
    config_path = os.environ.get("PIPE_CONFIG_PATH", "pipes.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        sys.stdout.write(raw_input)
        return

    # Execute Polyfill Wrapper
    result = wrap_payload(raw_input, config)
    sys.stdout.write(result)

if __name__ == "__main__":
    main()
