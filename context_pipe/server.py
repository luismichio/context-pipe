# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import os
import json
import logging
from typing import Any, Optional
from mcp.server.fastmcp import FastMCP
from .orchestrator import run_pipe

# Initialize FastMCP server
mcp = FastMCP("Context-Pipe")

# Configuration
CONFIG_PATH = os.environ.get("PIPE_CONFIG_PATH", "pipes.json")

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"pipes": []}

@mcp.tool()
def list_pipes() -> str:
    """Lists all available context pipes and their descriptions."""
    config = load_config()
    pipes = config.get("pipes", [])
    if not pipes:
        return "No pipes configured."
    
    summary = ["Available Context Pipes:"]
    for p in pipes:
        summary.append(f"- {p['name']}: {p.get('description', 'No description')}")
    
    return "\n".join(summary)

@mcp.tool()
def pipe_run(pipe_name: str, input_text: str) -> str:
    """
    Executes a specific context pipe on the provided input text.
    
    Args:
        pipe_name: The name of the pipe to run (e.g., 'standard-distill', 'semantic-refinery').
        input_text: The raw text to be processed through the pipe.
    """
    config = load_config()
    pipe = next((p for p in config.get("pipes", []) if p["name"] == pipe_name), None)
    
    if not pipe:
        return f"Error: Pipe '{pipe_name}' not found."
    
    try:
        result = run_pipe(pipe, input_text)
        return result
    except Exception as e:
        return f"Error executing pipe: {str(e)}"

@mcp.prompt()
def pipe_dashboard() -> str:
    """Returns a dashboard overview of the current context-pipe configuration."""
    config = load_config()
    return f"""
# ⛓️ Context-Pipe Dashboard

You are currently connected to the Context-Pipe Orchestrator.

## Active Pipes
{list_pipes()}

## Instructions
To protect your context window, always consider sifting large tool outputs using the `pipe_run` tool.
    """

def main():
    mcp.run()

if __name__ == "__main__":
    main()
