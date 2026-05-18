# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
Tests for context_pipe/wrapper.py — the polyfill wrapper.

Covers:
- wrap_payload routes to the correct pipe based on tool name trigger.
- wrap_payload routes to the correct pipe based on content size trigger.
- wrap_payload returns raw input unchanged when no pipe resolves.
- wrap_payload bypasses structured JSON (dict/list) content.
- wrap_payload bypasses content already containing the CPP signature.
- wrap_payload handles invalid JSON input gracefully (passthrough).
"""

import json
from unittest.mock import patch, AsyncMock


from context_pipe.wrapper import wrap_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(pipe_name: str, trigger: str = "default") -> dict:
    """Minimal pipes.json config that routes everything to a named pipe."""
    return {
        "pipes": [
            {
                "name": pipe_name,
                "nodes": [{"cmd": "semantic-sift-cli", "args": ["logs"]}],
            }
        ],
        "mappings": [{"trigger": trigger, "pipe": pipe_name}],
    }


def _make_payload(content: str, tool: str = "read_file") -> str:
    """Wraps content in a minimal Cursor-style tool response JSON."""
    return json.dumps(
        {
            "hook_event_name": "AfterTool",
            "tool_name": tool,
            "tool_response": {"llmContent": content},
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_invalid_json_returns_raw():
    """Non-JSON input must be returned unchanged."""
    raw = "this is not json at all"
    config = _make_config("standard-distill")
    result = wrap_payload(raw, config)
    assert result == raw


def test_no_matching_pipe_returns_raw():
    """When no mapping matches, raw JSON must be returned unchanged."""
    payload = _make_payload("hello world")
    config = {"pipes": [], "mappings": []}  # empty — nothing matches
    result = wrap_payload(payload, config)
    assert result == payload


def test_engine_signature_bypass():
    """Content already containing the engine signature must be bypassed (no double-sift)."""
    signature = "--- [Semantic-Sift Audit] ---"
    content = f"already processed content\n{signature}"
    payload = _make_payload(content)
    config = _make_config("standard-distill")

    result = wrap_payload(payload, config)
    # Must return the original payload unchanged
    assert result == payload


def test_structured_json_bypass():
    """Valid JSON dict/list content must be exempted from piping."""
    payload = _make_payload('{"key": "value", "nested": [1, 2, 3]}')
    config = _make_config("standard-distill")

    result = wrap_payload(payload, config)
    assert result == payload


def test_large_structured_json_is_sifted():
    """Structured JSON larger than 10KB must NOT be bypassed (sifted for ROI)."""
    large_json = json.dumps({"data": "x" * 12000})
    payload = _make_payload(large_json)
    config = _make_config("standard-distill")

    sifted = "compressed-json"
    mock_trace = [{"node": "sift", "input_size": len(large_json), "output_size": len(sifted)}]

    with patch("context_pipe.wrapper.run_pipe", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (sifted, mock_trace)
        result = wrap_payload(payload, config)

    # Should have called run_pipe instead of bypassing
    mock_run.assert_called_once()
    assert sifted in result

def test_tool_trigger_routes_to_correct_pipe():
    """A tool name matching the trigger regex must select the correct pipe."""
    noisy_log = "2026-01-01T00:00:00Z INFO: something happened [100/200]\n" * 5
    payload = _make_payload(noisy_log, tool="grep_search")
    config = _make_config("semantic-refinery", trigger="tool:grep|search")

    sifted = "cleaned output"
    mock_trace = [{"node": "semantic-sift-cli", "input_size": len(noisy_log), "output_size": len(sifted)}]

    with patch("context_pipe.wrapper.run_pipe", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (sifted, mock_trace)
        result = wrap_payload(payload, config)

    mock_run.assert_called_once()
    result_data = json.loads(result)
    assert sifted in str(result_data)


def test_size_trigger_routes_to_heavy_pipe():
    """Content exceeding the size threshold must route to the heavy pipe."""
    from context_pipe.orchestrator import resolve_pipe_from_context

    config = {
        "pipes": [
            {"name": "semantic-refinery", "nodes": [{"cmd": "semantic-sift-cli", "args": ["semantic"]}]},
            {"name": "standard-distill", "nodes": [{"cmd": "semantic-sift-cli", "args": ["logs"]}]},
        ],
        "mappings": [
            {"trigger": "size:>10000", "pipe": "semantic-refinery"},
            {"trigger": "default", "pipe": "standard-distill"},
        ],
    }

    # Directly test the routing logic (size trigger at the orchestration layer)
    pipe_name = resolve_pipe_from_context(config, "view_file", 15_000)
    assert pipe_name == "semantic-refinery"

    # And verify default kicks in below the threshold
    pipe_name_small = resolve_pipe_from_context(config, "view_file", 500)
    assert pipe_name_small == "standard-distill"


def test_stringified_tool_response_is_handled():
    """Gemini CLI often passes stringified JSON in tool_response; wrap_payload must handle this."""
    inner_response = {"output": "noisy log content with lots of text" * 50}
    payload = json.dumps({
        "tool_name": "read_file",
        "tool_response": json.dumps(inner_response)
    })
    config = _make_config("standard-distill")

    sifted = "compressed"
    mock_trace = [{"node": "sift", "input_size": 1000, "output_size": 100}]

    with patch("context_pipe.wrapper.run_pipe", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (sifted, mock_trace)
        result = wrap_payload(payload, config)

    mock_run.assert_called_once()
    assert sifted in result

def test_run_pipe_exception_falls_back_to_raw():
    """If run_pipe raises, wrap_payload must return the original raw JSON."""
    noisy = "2026-01-01T00:00:00Z INFO: hello" * 10
    payload = _make_payload(noisy)
    config = _make_config("standard-distill")

    with patch("context_pipe.wrapper.run_pipe", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = OSError("pipe broken")
        result = wrap_payload(payload, config)

    assert result == payload
