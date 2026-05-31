# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""
context_pipe/shadow.py  Shadow tool discovery.
Lists all available context-processing capabilities: configured pipes from
pipes.json and well-known CLI tools found on PATH.
"""
import os
import json
import logging
import shutil
from typing import Any

logger = logging.getLogger(__name__)

# Curated CLI tools to probe on PATH.
_KNOWN_PATH_TOOLS: dict[str, str] = {
    "jq": "Command-line JSON processor",
    "yq": "Command-line YAML/JSON/XML processor",
    "markitdown": "Converts Office/PDF/HTML documents to Markdown",
    "pandoc": "Universal document format converter",
    "rg": "Fast line-oriented search (ripgrep)",
    "fd": "Fast file finder (fd-find)",
    "bat": "Syntax-highlighted cat replacement",
}


def list_shadow_tools(config_path: str = "pipes.json") -> list[dict[str, Any]]:
    """
    Returns a combined list of available context-processing tools.
    Entries from ``pipes.json`` come first (source ``"pipes.json"``), followed
    by discovered CLI tools on PATH (source ``"PATH"``).
    Never raises  all errors are logged to stderr and an empty/partial list
    is returned.
    Args:
        config_path: Path to the project-level pipes.json file.
    Returns:
        List of tool descriptor dicts with keys:
        ``name``, ``source``, ``description``, ``nodes``.
    """
    tools: list[dict[str, Any]] = []

    # --- 1. Configured pipes from pipes.json ---
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            config = json.load(fh)
        for pipe in config.get("pipes", []):
            nodes_desc = []
            for n in pipe.get("nodes", []):
                if n.get("cmd"):
                    nodes_desc.append(n["cmd"])
                elif n.get("server") and n.get("tool"):
                    nodes_desc.append(f"mcp:{n['server']}/{n['tool']}")
                else:
                    nodes_desc.append(str(n))
            tools.append(
                {
                    "name": pipe.get("name", ""),
                    "source": "pipes.json",
                    "description": pipe.get("description", ""),
                    "nodes": nodes_desc,
                }
            )
    except FileNotFoundError:
        logger.debug("pipes.json not found at '%s'; skipping configured pipes.", config_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read pipes.json: %s", exc)

    # --- 2. Registered MCP Servers from pipes.json ---
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as fh:
                config = json.load(fh)
            servers = config.get("servers", {})
            for name, srv_config in servers.items():
                if name.startswith("_"):  # Skip comments/examples
                    continue
                tools.append(
                    {
                        "name": name,
                        "source": "pipes.json",
                        "description": srv_config.get("description", "Registered MCP server. Can be run in custom pipes."),
                        "nodes": [],
                    }
                )
    except Exception as exc:
        logger.debug("Could not read MCP servers from config: %s", exc)

    # --- 3. Curated CLI tools on PATH ---
    for cmd, description in _KNOWN_PATH_TOOLS.items():
        if shutil.which(cmd) is not None:
            tools.append(
                {
                    "name": cmd,
                    "source": "PATH",
                    "description": description,
                    "nodes": [cmd],
                }
            )
    return tools
