# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import json
import subprocess
import argparse
from typing import List, Dict, Any

def run_pipe(pipe_config: Dict[str, Any], input_data: str) -> str:
    """Executes a chain of nodes via OS-level pipes."""
    current_input = input_data
    
    for node in pipe_config.get("nodes", []):
        cmd = [node["cmd"]] + node.get("args", [])
        
        # High-Fidelity OS Piping
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=current_input)
        
        if process.returncode != 0:
            return f"Error in node {node['cmd']}: {stderr}"
        
        current_input = stdout
        
    return current_input

def main():
    parser = argparse.ArgumentParser(description="Context-Pipe Orchestrator")
    parser.add_argument("pipe_name", help="Name of the pipe to execute from pipes.json")
    parser.add_argument("--config", default="pipes.json", help="Path to pipes.json")
    
    args = parser.parse_args()
    
    try:
        with open(args.config, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file {args.config} not found.")
        sys.exit(1)
        
    # Find the requested pipe
    pipe = next((p for p in config.get("pipes", []) if p["name"] == args.pipe_name), None)
    
    if not pipe:
        print(f"Error: Pipe '{args.pipe_name}' not found in {args.config}")
        sys.exit(1)
        
    # Read from stdin
    input_data = sys.stdin.read()
    
    # Run the pipe
    result = run_pipe(pipe, input_data)
    
    # Output the result
    sys.stdout.write(result)

if __name__ == "__main__":
    main()
