# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
import sys
import json
import subprocess
import argparse
import re
import os
from typing import List, Dict, Any, Optional

# Metadata Signatures
CPP_SIGNATURE = "--- [Context-Pipe: Native Execution] ---"

def resolve_pipe_from_context(config: Dict[str, Any], tool_name: str, content_len: int) -> Optional[str]:
    """Resolves a pipe name based on mapping triggers."""
    mappings = config.get("mappings", [])
    
    for m in mappings:
        trigger = m.get("trigger", "")
        
        # 1. Tool Trigger (tool:regex)
        if trigger.startswith("tool:"):
            pattern = trigger.replace("tool:", "")
            if re.search(pattern, tool_name, re.IGNORECASE):
                return m["pipe"]
                
        # 2. Size Trigger (size:>num)
        if trigger.startswith("size:>"):
            try:
                threshold = int(trigger.replace("size:>", ""))
                if content_len > threshold:
                    return m["pipe"]
            except ValueError:
                continue
                
        # 3. Default Trigger
        if trigger == "default":
            return m["pipe"]
            
    return None

def run_pipe(pipe_config: Dict[str, Any], input_data: str) -> tuple[str, List[Dict[str, Any]]]:
    """Executes a chain of nodes and tracks context deltas with a timeout guard."""
    current_input = input_data
    trace = []
    
    # Global timeout for the entire pipe execution (default 10s)
    raw_timeout = os.environ.get("PIPE_NODE_TIMEOUT_MS", "10000")
    node_timeout = int(raw_timeout) / 1000.0

    for node in pipe_config.get("nodes", []):
        cmd = [node["cmd"]] + node.get("args", [])
        start_size = len(current_input)
        
        try:
            # High-Fidelity OS Piping
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(input=current_input, timeout=node_timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                error_text = f"--- [Context-Pipe: Timeout] ---\nNode {node['cmd']} exceeded {node_timeout}s."
                trace.append({"node": node["cmd"], "error": "Timeout"})
                return error_text, trace
            
            if process.returncode != 0:
                # Record error in trace
                trace.append({
                    "node": node["cmd"],
                    "error": stderr.strip()
                })
                return f"Error in node {node['cmd']}: {stderr}", trace
                
        except FileNotFoundError:
            help_msg = node.get("help_msg", f"Command '{node['cmd']}' not found in system PATH.")
            error_text = f"--- [Context-Pipe: Dependency Error] ---\n{help_msg}"
            trace.append({
                "node": node["cmd"],
                "error": "FileNotFound"
            })
            return error_text, trace
        
        end_size = len(stdout)
        trace.append({
            "node": node["cmd"],
            "input_size": start_size,
            "output_size": end_size,
            "delta": end_size - start_size
        })
        
        current_input = stdout
        
    return current_input, trace

def main():
    parser = argparse.ArgumentParser(description="Context-Pipe Orchestrator")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    
    # 1. 'run' command (default)
    run_parser = subparsers.add_parser("run", help="Run a specific pipe")
    run_parser.add_argument("pipe_name", help="Name of the pipe to execute from pipes.json")
    run_parser.add_argument("--config", default="pipes.json", help="Path to pipes.json")
    
    # 2. 'wrap' command (JSON polyfill)
    wrap_parser = subparsers.add_parser("wrap", help="Wrap a JSON-RPC payload")
    wrap_parser.add_argument("--config", default="pipes.json", help="Path to pipes.json")
    
    # Compatibility with old behavior (no subcommand)
    if len(sys.argv) > 1 and sys.argv[1] not in ["run", "wrap"]:
        sys.argv.insert(1, "run")
        
    args = parser.parse_args()
    
    try:
        with open(args.config, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file {args.config} not found.")
        sys.exit(1)
        
    if args.command == "run":
        # Find the requested pipe
        pipe = next((p for p in config.get("pipes", []) if p["name"] == args.pipe_name), None)
        
        if not pipe:
            print(f"Error: Pipe '{args.pipe_name}' not found in {args.config}")
            sys.exit(1)
            
        # Read from stdin
        input_data = sys.stdin.read()
        
        # Run the pipe
        result, trace = run_pipe(pipe, input_data)
        
        # Output the result
        sys.stdout.write(result)
        
    elif args.command == "wrap":
        from .wrapper import wrap_payload
        raw_input = sys.stdin.read()
        result = wrap_payload(raw_input, config)
        sys.stdout.write(result)

if __name__ == "__main__":
    main()
