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


def get_env_with_venv_path() -> Dict[str, str]:
    """Ensures the current venv's bin/Scripts directory is in the PATH for child processes."""
    env = os.environ.copy()

    # Detect if we are running in a virtual environment
    if sys.prefix != sys.base_prefix:
        venv_bin = os.path.join(sys.prefix, "Scripts" if os.name == "nt" else "bin")
        if os.path.exists(venv_bin):
            path_sep = ";" if os.name == "nt" else ":"
            current_path = env.get("PATH", "")
            if venv_bin not in current_path:
                env["PATH"] = f"{venv_bin}{path_sep}{current_path}"

    return env


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


def run_pipe(
    pipe_config: Dict[str, Any], input_data: str, tool_name: Optional[str] = None, agent_label: Optional[str] = None
) -> tuple[str, List[Dict[str, Any]]]:
    """Executes a chain of nodes and tracks context deltas with a timeout guard."""
    current_input = input_data
    trace = []

    # 1. Prepare Environment (Self-Aware Venv Path + Metadata)
    process_env = get_env_with_venv_path()
    if tool_name:
        process_env["SIFT_TOOL_NAME"] = tool_name
    if agent_label:
        process_env["SIFT_AGENT_LABEL"] = agent_label

    # Global timeout for the entire pipe execution (default 30s to allow model warmup)
    raw_timeout = os.environ.get("PIPE_NODE_TIMEOUT_MS", "30000")
    node_timeout = int(raw_timeout) / 1000.0

    for node in pipe_config.get("nodes", []):
        use_shell = node.get("shell", False)

        cmd: str | List[str]
        if use_shell:
            # Join cmd and args for shell execution
            cmd = " ".join([node["cmd"]] + [str(a) for a in node.get("args", [])])
        else:
            cmd = [node["cmd"]] + [str(a) for a in node.get("args", [])]

        start_size = len(current_input)

        try:
            # High-Fidelity OS Piping
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=use_shell,  # nosec B602
                env=process_env,
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
                trace.append({"node": node["cmd"], "error": stderr.strip()})
                return f"Error in node {node['cmd']}: {stderr}", trace

        except FileNotFoundError:
            help_msg = node.get("help_msg", f"Command '{node['cmd']}' not found in system PATH.")
            error_text = f"--- [Context-Pipe: Dependency Error] ---\n{help_msg}"
            trace.append({"node": node["cmd"], "error": "FileNotFound"})
            return error_text, trace

        end_size = len(stdout)
        trace.append(
            {"node": node["cmd"], "input_size": start_size, "output_size": end_size, "delta": end_size - start_size}
        )

        current_input = stdout

    return current_input, trace


def main():
    # 1. Capture raw input immediately for safety fallback
    raw_input = None
    if not sys.stdin.isatty():
        try:
            raw_input = sys.stdin.read()
        except EOFError:
            pass

    try:
        parser = argparse.ArgumentParser(description="Context-Pipe Orchestrator")
        subparsers = parser.add_subparsers(dest="command", help="Subcommands")

        # 1. 'run' command (default)
        run_parser = subparsers.add_parser("run", help="Run a specific pipe")
        run_parser.add_argument("pipe_name", help="Name of the pipe to execute from pipes.json")
        run_parser.add_argument("--config", default="pipes.json", help="Path to pipes.json")

        # 2. 'wrap' command (JSON polyfill)
        wrap_parser = subparsers.add_parser("wrap", help="Wrap a JSON-RPC payload")
        wrap_parser.add_argument("--config", default="pipes.json", help="Path to pipes.json")

        # 3. 'stats' command (Balance Sheet)
        subparsers.add_parser("stats", help="Display Context-Pipe ROI Balance Sheet")

        # Compatibility with old behavior (no subcommand)
        if len(sys.argv) > 1 and sys.argv[1] not in ["run", "wrap", "stats"]:
            # Handle common aliases for stats
            if sys.argv[1] in ["get_pipe_stats", "pipe-stats"]:
                sys.argv[1] = "stats"
            else:
                sys.argv.insert(1, "run")

        args = parser.parse_args()

        # Load Config with relative/absolute fallback
        config = {"pipes": [], "mappings": []}
        config_path = getattr(args, "config", "pipes.json")

        # Try finding config in current dir, then in the orchestrator's parent dir
        search_paths = [config_path]
        if not os.path.isabs(config_path):
            search_paths.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config_path))

        for path in search_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    break
                except (json.JSONDecodeError, OSError):
                    continue

        if args.command == "run":
            if not raw_input:
                sys.exit(0)
            # Find the requested pipe
            pipe = next((p for p in config.get("pipes", []) if p["name"] == args.pipe_name), None)

            if not pipe:
                sys.stdout.write(raw_input)
                sys.exit(0)

            # Run the pipe
            result, trace = run_pipe(pipe, raw_input)
            sys.stdout.write(result)

        elif args.command == "wrap":
            if not raw_input:
                sys.exit(0)
            from .wrapper import wrap_payload

            result = wrap_payload(raw_input, config)
            sys.stdout.write(result)

        elif args.command == "stats":
            from .telemetry import get_balance_sheet

            sheet = get_balance_sheet()
            net_label = "Saved" if sheet["net_change"] < 0 else "Added"

            print("\n--- [Context-Pipe: ROI Balance Sheet] ---")
            print(f"Signal Injected:  +{sheet['signal_added']:,} chars")
            print(f"Noise Incinerated: -{sheet['noise_removed']:,} chars")
            print(f"Net Context {net_label}: {abs(sheet['net_change']):,} chars")
            print(f"Platform Events:   {sheet['total_events']}")
            print(f"Avg Node Latency:  {sheet['avg_latency_ms']:.2f}ms")
            print("-----------------------------------------\n")

    except Exception:
        # ABSOLUTE SAFETY: Never crash the hook.
        if raw_input:
            sys.stdout.write(raw_input)
        sys.exit(0)


if __name__ == "__main__":
    main()
