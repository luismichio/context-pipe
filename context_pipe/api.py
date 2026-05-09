# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""
Programmatic Python API for Context-Pipe.

Provides a single `pipe()` function for direct integration into Python scripts,
notebooks, test suites, and agent frameworks (LangChain, CrewAI, etc.)
without going through the MCP server or CLI.

Example::

    from context_pipe import pipe

    clean = pipe(raw_logs, tool_name="bash")
    structured = pipe(document_text, pipe_name="semantic-refinery")
"""

from typing import Optional

from .orchestrator import load_config, resolve_pipe_from_context, run_pipe


def pipe(
    text: str,
    pipe_name: Optional[str] = None,
    tool_name: str = "",
    config_path: str = "pipes.json",
) -> str:
    """
    Run text through a context pipe and return the distilled result.

    Resolution order for ``pipe_name``:
    1. If ``pipe_name`` is provided explicitly, that pipe is used directly.
    2. Otherwise the mapping rules in ``pipes.json`` are evaluated against
       ``tool_name`` and ``len(text)`` to select the best pipe automatically.
    3. If no pipe resolves, the original ``text`` is returned unchanged.

    Args:
        text:        The raw content to distill.
        pipe_name:   Optional explicit pipe name (e.g. ``"standard-distill"``).
                     When omitted, routing is determined by ``pipes.json`` mappings.
        tool_name:   The originating tool name used for trigger matching and
                     telemetry attribution (e.g. ``"bash"``, ``"grep_search"``).
        config_path: Path to ``pipes.json``. Defaults to ``"pipes.json"`` in the
                     current working directory; the orchestrator also searches the
                     package root as a fallback.

    Returns:
        Distilled text, or the original ``text`` if no pipe resolved or an
        error occurred.
    """
    if not text:
        return text

    try:
        config = load_config(config_path)
    except Exception:
        return text

    resolved_name = pipe_name or resolve_pipe_from_context(config, tool_name, len(text))
    if not resolved_name:
        return text

    pipe_config = next((p for p in config.get("pipes", []) if p["name"] == resolved_name), None)
    if not pipe_config:
        return text

    try:
        result, _ = run_pipe(pipe_config, text, tool_name=tool_name or None)
        return result
    except Exception:
        return text
