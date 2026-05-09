# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import os
import argparse
import subprocess


def main():
    parser = argparse.ArgumentParser(description="Context-Pipe Script & Mandate Node Wrapper")
    parser.add_argument("script_name", help="Name of the script or mandate to apply")
    parser.add_argument("--script-dir", default=None, help="Directory to look for scripts/mandates")
    # Use parse_known_args to handle extra arguments for the script
    args, script_args = parser.parse_known_args()

    # 1. Load Input Data
    input_data = sys.stdin.read()
    if not input_data:
        return

    # 2. Resolve Path
    script_dir = args.script_dir or os.environ.get("PIPE_SCRIPT_DIR", ".gemini/scripts")
    
    py_script = os.path.join(script_dir, f"{args.script_name}.py")
    md_mandate = os.path.join(script_dir, f"{args.script_name}.md")

    # 3. Execution Logic
    if os.path.exists(py_script):
        # Execute Python script
        cmd = [sys.executable, py_script] + script_args
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=input_data)
        if process.returncode != 0:
            sys.stderr.write(stderr)
            sys.stdout.write(input_data) # Pass through on error
        else:
            sys.stdout.write(stdout)
            
    elif os.path.exists(md_mandate):
        # Mandate Prepend Logic
        with open(md_mandate, "r", encoding="utf-8") as f:
            mandate_text = f.read()
        output = f"--- [Context-Pipe: Mandate ({args.script_name})] ---\n{mandate_text}\n\n[Content]\n{input_data}"
        sys.stdout.write(output)
        
    else:
        # Fallback / Warning
        sys.stderr.write(f"[Context-Pipe] Warning: Script or mandate '{args.script_name}' not found in {script_dir}.\n")
        sys.stdout.write(input_data)


if __name__ == "__main__":
    main()
