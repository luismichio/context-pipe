# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
Tests for pipe_hook.py — the root-level IDE hook entrypoint.

Covers:
- Pass-through when stdin is empty.
- Pass-through when pipes.json is absent.
- Successful pipe transform when config is present and wrap_payload succeeds.
- Safety fallback: any exception in wrap_payload returns raw input unchanged.
"""

import importlib
import io
import json
from unittest.mock import patch


def _run_hook_with_stdin(monkeypatch, stdin_data: str, *, mock_wrap=None, mock_config_exists=False):
    """Helper: runs pipe_hook.main() with controlled stdin and captures stdout."""
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_data))
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    # Control os.path.exists for the config path
    with patch("os.path.exists", return_value=mock_config_exists):
        if mock_wrap is not None:
            with patch("context_pipe.wrapper.wrap_payload", mock_wrap):
                # Re-import to execute __main__ block under fresh stdin
                import pipe_hook
                importlib.reload(pipe_hook)
                pipe_hook.main()
        else:
            import pipe_hook
            importlib.reload(pipe_hook)
            pipe_hook.main()

    return captured.getvalue()


def test_empty_stdin_produces_no_output(monkeypatch):
    """Empty stdin must result in no output and no crash."""
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    with patch("os.path.exists", return_value=False):
        import pipe_hook
        importlib.reload(pipe_hook)
        pipe_hook.main()

    assert captured.getvalue() == ""


def test_passthrough_when_no_config(monkeypatch):
    """When pipes.json does not exist, raw input must pass through unchanged."""
    raw = '{"tool_response": {"content": "hello world"}}'
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    with patch("os.path.exists", return_value=False):
        # wrap_payload with an empty config returns raw_json unchanged
        import pipe_hook
        importlib.reload(pipe_hook)
        pipe_hook.main()

    # Output should still be the raw input (wrap_payload with empty config passes through)
    assert captured.getvalue() == raw


def test_wrap_payload_called_with_config(monkeypatch, tmp_path):
    """When a valid pipes.json exists, wrap_payload must be called and its result written."""
    raw = '{"tool_response": {"content": "2026-01-01T00:00:00Z INFO: hello"}}'
    expected_output = '{"tool_response": {"content": "sifted"}}'
    config_file = tmp_path / "pipes.json"
    config_file.write_text(json.dumps({"pipes": [], "mappings": []}))

    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)
    monkeypatch.setenv("PIPE_CONFIG_PATH", str(config_file))

    with patch("context_pipe.wrapper.wrap_payload", return_value=expected_output):
        import pipe_hook
        importlib.reload(pipe_hook)
        pipe_hook.main()

    assert captured.getvalue() == expected_output


def test_safety_fallback_on_exception(monkeypatch, tmp_path):
    """If wrap_payload raises any exception, the hook must output raw input and not crash."""
    raw = '{"tool_response": {"content": "data"}}'
    config_file = tmp_path / "pipes.json"
    config_file.write_text(json.dumps({"pipes": [], "mappings": []}))

    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)
    monkeypatch.setenv("PIPE_CONFIG_PATH", str(config_file))

    with patch("context_pipe.wrapper.wrap_payload", side_effect=RuntimeError("boom")):
        import pipe_hook
        importlib.reload(pipe_hook)
        pipe_hook.main()

    assert captured.getvalue() == raw
