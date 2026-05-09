# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
context_pipe/dynamic.py — Ad-hoc (dynamic) pipe execution.

Allows AI agents to construct and execute a pipe from a node list at runtime,
without requiring a pre-declared entry in pipes.json.
"""

import re
import logging
from typing import Any

from .orchestrator import run_pipe

logger = logging.getLogger(__name__)

# Characters that would allow shell injection via cmd values.
_SHELL_METACHAR_RE = re.compile(r"[|;&$`>]")

# Curated list of well-known context-processing CLI tools probed on PATH.
KNOWN_SHADOW_TOOLS: list[str] = ["jq", "yq", "markitdown", "pandoc", "rg", "fd", "bat"]

# Shell utilities permitted as dynamic pipe nodes when allow_shell=True.
# These are data-processing utilities only — no network, no exec, no privilege escalation.
# The final node in any pipe that includes a shell utility MUST be semantic-sift-cli
# to guarantee context safety.
SHELL_UTILITY_ALLOWLIST: frozenset[str] = frozenset(
    [
        "bash",
        "sh",
        "awk",
        "sed",
        "grep",
        "cut",
        "sort",
        "uniq",
        "tr",
        "head",
        "tail",
        "wc",
        "cat",
        "echo",
        "printf",
        "xargs",
        "python",
        "python3",
        "jq",
        "yq",
    ]
)

# The executable names that are considered context-safety terminal nodes.
_SIFT_TERMINAL_CMDS: frozenset[str] = frozenset(["semantic-sift-cli", "sift"])


def _validate_nodes(nodes: list[dict], allow_shell: bool = False) -> None:
    """
    Validates a dynamic node list.

    Args:
        nodes:       Node list to validate.
        allow_shell: When True, commands in ``SHELL_UTILITY_ALLOWLIST`` are permitted
                     even though they are not in the default allowlist.  The final node
                     in the pipe MUST be a semantic-sift-cli terminal node.

    Raises:
        ValueError: if a node is missing ``cmd``, contains shell metacharacters,
                    uses a non-allowlisted shell utility, or (when allow_shell=True)
                    the pipe does not end with a sift terminal node.
    """
    has_shell_utility = False
    for i, node in enumerate(nodes):
        if "cmd" not in node:
            raise ValueError(f"Node at index {i} is missing required key 'cmd'.")
        cmd: str = str(node["cmd"])
        if _SHELL_METACHAR_RE.search(cmd):
            raise ValueError(
                f"Node cmd '{cmd}' contains shell metacharacters. "
                "Use args[] for arguments — cmd must be a bare executable name."
            )
        # Bare executable name (first token) for allowlist check.
        exe = cmd.strip().split()[0] if cmd.strip() else cmd
        if exe in SHELL_UTILITY_ALLOWLIST:
            if not allow_shell:
                raise ValueError(
                    f"Node cmd '{exe}' is a shell utility. "
                    "Set allow_shell=True to enable shell utility nodes. "
                    "The final node must be semantic-sift-cli to guarantee context safety."
                )
            has_shell_utility = True

    if has_shell_utility:
        last_exe = str(nodes[-1].get("cmd", "")).strip().split()[0]
        if last_exe not in _SIFT_TERMINAL_CMDS:
            raise ValueError(
                f"Pipes containing shell utilities must end with a semantic-sift-cli node "
                f"to guarantee context safety. Last node cmd was '{last_exe}'. "
                "Add a terminal node: {\"cmd\": \"semantic-sift-cli\", \"args\": [\"--rate\", \"0.5\"]}."
            )


def run_dynamic_pipe(
    nodes: list[dict[str, Any]],
    input_text: str,
    tool_name: str = "dynamic",
    allow_shell: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Executes an ad-hoc pipe defined by a caller-supplied node list.

    Args:
        nodes:       List of node dicts following the pipes.json node schema.
                     Each must have a ``cmd`` key.
        input_text:  Raw text to feed into the pipe.
        tool_name:   Label forwarded to nodes via ``SIFT_TOOL_NAME`` env var.
        allow_shell: When True, commands in ``SHELL_UTILITY_ALLOWLIST`` (bash, awk,
                     grep, sed, jq, etc.) are permitted as intermediate nodes.
                     The final node MUST be semantic-sift-cli to guarantee context
                     safety.  Default False.

    Returns:
        ``(result, trace)`` — same contract as ``run_pipe()``.

    Raises:
        ValueError: on malformed node definitions, shell metacharacters in cmd,
                    non-allowlisted shell utilities (when allow_shell=False), or
                    missing terminal sift node (when allow_shell=True).
    """
    if not nodes:
        return input_text, []

    _validate_nodes(nodes, allow_shell=allow_shell)

    pipe_config: dict[str, Any] = {"name": "dynamic", "nodes": nodes}
    return run_pipe(pipe_config, input_text, tool_name=tool_name)
