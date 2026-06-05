# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""
A2A (Agent-to-Agent) handoff module  Phase 6.2

Provides a framework-agnostic bridge for distilling Agent A's output before
it enters Agent B's context window. Works with any A2A framework (CrewAI,
Google ADK, LangGraph) via an explicit function call  no monkey-patching.

Example::

    from context_pipe.a2a import pipe_agent_handoff

    agent_b_input = pipe_agent_handoff(
        agent_a_output,
        pipe_name="semantic-refinery",
        from_agent="researcher",
        to_agent="writer",
    )
"""

import logging
from typing import Optional

from .api import pipe
from .telemetry import log_telemetry

logger = logging.getLogger(__name__)


def pipe_agent_handoff(
    output: str,
    pipe_name: Optional[str] = None,
    from_agent: Optional[str] = None,
    to_agent: Optional[str] = None,
    config_path: str = "pipes.json",
) -> str:
    """
    Distil Agent A's output before passing it to Agent B's context window.

    Args:
        output:      The raw output from Agent A to distil.
        pipe_name:   Optional explicit pipe name. When omitted, routing is
                     determined by ``pipes.json`` mappings using ``from_agent``
                     as the tool name trigger.
        from_agent:  Label for the producing agent (used for telemetry and
                     trigger matching).
        to_agent:    Label for the consuming agent (telemetry only).
        config_path: Path to ``pipes.json``. Defaults to CWD lookup with
                     package-root fallback.

    Returns:
        Distilled text, or the original ``output`` if no pipe resolved or
        any error occurred  the chain must never be interrupted.
    """
    if not output:
        return output

    tool_name = from_agent or "a2a"
    input_size = len(output)

    try:
        result = pipe(output, pipe_name=pipe_name, tool_name=tool_name, config_path=config_path)
    except Exception:
        logger.debug("pipe_agent_handoff: pipe() raised  returning original output unchanged.")
        return output

    output_size = len(result)

    # Telemetry: log the handoff event (no content  sizes only)
    try:
        import time
        log_telemetry(
            session_id=f"a2a-{from_agent or 'unknown'}-{to_agent or 'unknown'}",
            start_time=str(time.time()),
            tool_name=tool_name,
            original_size=input_size,
            final_size=output_size,
            latency_ms=0.0,
            config_path=config_path,
        )
    except Exception:
        pass  # Telemetry failure must never block the handoff

    return result
