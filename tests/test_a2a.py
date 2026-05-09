# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""
A2A Agent Handoff tests — Phase 6.2
"""
from unittest.mock import patch


from context_pipe import a2a


# ---------------------------------------------------------------------------
# 1. Handoff distils output via pipe()
# ---------------------------------------------------------------------------

def test_handoff_distils_output():
    with patch("context_pipe.a2a.pipe", return_value="distilled") as mock_pipe:
        result = a2a.pipe_agent_handoff("raw output", pipe_name="semantic-refinery")

    assert result == "distilled"
    mock_pipe.assert_called_once()


# ---------------------------------------------------------------------------
# 2. from_agent is forwarded as tool_name to pipe()
# ---------------------------------------------------------------------------

def test_handoff_uses_from_agent_as_tool_name():
    with patch("context_pipe.a2a.pipe", return_value="distilled") as mock_pipe:
        a2a.pipe_agent_handoff("data", from_agent="researcher")

    _, kwargs = mock_pipe.call_args
    assert kwargs.get("tool_name") == "researcher"


# ---------------------------------------------------------------------------
# 3. pipe() raising returns original output unchanged
# ---------------------------------------------------------------------------

def test_handoff_fallback_on_pipe_error():
    with patch("context_pipe.a2a.pipe", side_effect=RuntimeError("node crashed")):
        result = a2a.pipe_agent_handoff("original output")

    assert result == "original output"


# ---------------------------------------------------------------------------
# 4. Empty input returns empty string without calling pipe()
# ---------------------------------------------------------------------------

def test_handoff_empty_input_passthrough():
    with patch("context_pipe.a2a.pipe") as mock_pipe:
        result = a2a.pipe_agent_handoff("")

    assert result == ""
    mock_pipe.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Telemetry log_telemetry() is called with correct agent labels
# ---------------------------------------------------------------------------

def test_handoff_logs_telemetry_event():
    with patch("context_pipe.a2a.pipe", return_value="small"), \
         patch("context_pipe.a2a.log_telemetry") as mock_tel:
        a2a.pipe_agent_handoff(
            "raw output data",
            from_agent="researcher",
            to_agent="writer",
        )

    mock_tel.assert_called_once()
    call_kwargs = mock_tel.call_args[1] if mock_tel.call_args[1] else {}
    call_args = mock_tel.call_args[0] if mock_tel.call_args[0] else ()
    # session_id must reference both agent labels
    session_id = call_kwargs.get("session_id") or (call_args[0] if call_args else "")
    assert "researcher" in session_id
    assert "writer" in session_id
