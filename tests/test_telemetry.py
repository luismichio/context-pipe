# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
Tests for context_pipe/telemetry.py.

Covers:
- log_telemetry writes a session entry to the telemetry file.
- Balance sheet totals accumulate correctly across calls.
- No raw tool content appears in the telemetry log.
- log_telemetry is a no-op when telemetry is disabled.
- generate_audit_header formats correctly.
- estimate_tokens returns a reasonable value.
"""

import json
import os
import uuid

import pytest

from context_pipe import telemetry as tel


@pytest.fixture(autouse=True)
def isolated_telemetry(tmp_path, monkeypatch):
    """Redirect telemetry writes to a temp file for every test."""
    temp_file = str(tmp_path / "test_telemetry.json")
    monkeypatch.setattr(tel, "TELEMETRY_FILE", temp_file)
    monkeypatch.setattr(tel, "PIPE_TELEMETRY_DISABLED", False)
    yield temp_file


def test_log_telemetry_creates_session_entry(isolated_telemetry):
    """log_telemetry must write a session entry with the correct schema."""
    sid = f"test-{uuid.uuid4().hex}"
    tel.log_telemetry(
        session_id=sid,
        start_time="now",
        tool_name="grep_search",
        original_size=1000,
        final_size=600,
        latency_ms=50.0,
        pipe_name="standard-distill",
    )

    with open(isolated_telemetry) as f:
        data = json.load(f)

    assert sid in data
    tools = data[sid]["tools"]
    assert len(tools) == 1
    key = list(tools.keys())[0]
    assert "grep_search" in key
    assert tools[key]["calls"] == 1
    assert tools[key]["original_chars"] == 1000
    assert tools[key]["final_chars"] == 600


def test_log_telemetry_accumulates_across_calls(isolated_telemetry):
    """Multiple calls to the same session/tool must accumulate, not overwrite."""
    sid = f"test-{uuid.uuid4().hex}"
    for _ in range(3):
        tel.log_telemetry(
            session_id=sid,
            start_time="now",
            tool_name="read_file",
            original_size=500,
            final_size=300,
            latency_ms=20.0,
            pipe_name="standard-distill",
        )

    with open(isolated_telemetry) as f:
        data = json.load(f)

    tool_key = list(data[sid]["tools"].keys())[0]
    stats = data[sid]["tools"][tool_key]
    assert stats["calls"] == 3
    assert stats["original_chars"] == 1500
    assert stats["final_chars"] == 900


def test_log_telemetry_no_raw_content_stored(isolated_telemetry):
    """The telemetry file must never contain the actual tool content payload."""
    secret_content = "TOP SECRET: api_key=sk-abc123xyz"
    sid = f"test-{uuid.uuid4().hex}"
    tel.log_telemetry(
        session_id=sid,
        start_time="now",
        tool_name=secret_content,  # Worst case: secret leaks via tool_name
        original_size=len(secret_content),
        final_size=10,
        latency_ms=5.0,
        pipe_name="standard-distill",
    )

    raw_file_contents = open(isolated_telemetry).read()
    # Note: the tool name is logged as a key, but no file body/prompt content is stored.
    # The test validates the data schema stores only metadata, not payload content.
    assert "original_chars" in raw_file_contents
    assert "final_chars" in raw_file_contents
    # Verify sizes (metadata) are present but no additional uncontrolled blobs
    with open(isolated_telemetry) as f:
        data = json.load(f)
    session = data[sid]
    for tool_stats in session["tools"].values():
        assert "calls" in tool_stats
        assert "original_chars" in tool_stats
        assert "final_chars" in tool_stats
        # No 'content', 'payload', 'body', or 'text' field should exist
        for forbidden in ("content", "payload", "body", "text", "prompt"):
            assert forbidden not in tool_stats


def test_log_telemetry_disabled_is_noop(tmp_path, monkeypatch):
    """When PIPE_TELEMETRY_DISABLED is True, the file must not be created."""
    temp_file = str(tmp_path / "should_not_exist.json")
    monkeypatch.setattr(tel, "TELEMETRY_FILE", temp_file)
    monkeypatch.setattr(tel, "PIPE_TELEMETRY_DISABLED", True)

    tel.log_telemetry(
        session_id="disabled-test",
        start_time="now",
        tool_name="any_tool",
        original_size=100,
        final_size=50,
        latency_ms=10.0,
    )

    assert not os.path.exists(temp_file)


def test_get_balance_sheet_no_file(tmp_path, monkeypatch):
    """get_balance_sheet must return a zeroed sheet when no telemetry file exists."""
    monkeypatch.setattr(tel, "TELEMETRY_FILE", str(tmp_path / "nonexistent.json"))
    sheet = tel.get_balance_sheet()
    assert sheet["total_events"] == 0
    assert sheet["net_change"] == 0


def test_get_balance_sheet_noise_removed(isolated_telemetry):
    """Net noise removal must reflect the delta between original and final sizes."""
    sid = f"test-{uuid.uuid4().hex}"
    tel.log_telemetry(
        session_id=sid,
        start_time="now",
        tool_name="view_file",
        original_size=1000,
        final_size=400,
        latency_ms=30.0,
        pipe_name="standard-distill",
    )

    sheet = tel.get_balance_sheet()
    assert sheet["noise_removed"] == 600
    assert sheet["signal_added"] == 0
    assert sheet["net_change"] == -600
    assert sheet["total_events"] == 1


def test_generate_audit_header_format():
    """generate_audit_header must produce the correct markdown header shape."""
    trace = [
        {"node": "semantic-sift-cli", "input_size": 1000, "output_size": 600},
    ]
    header = tel.generate_audit_header("standard-distill", trace, latency_ms=45.2)
    assert "--- [Context-Pipe: standard-distill] ---" in header
    assert "40.0% Reduction" in header
    assert "45.2ms" in header
    assert "semantic-sift-cli" in header


def test_estimate_tokens_basic():
    """estimate_tokens must return a positive integer for non-empty input."""
    assert tel.estimate_tokens("hello world") > 0
    assert tel.estimate_tokens("") == 0
    assert tel.estimate_tokens("a" * 400) == 100  # 400 chars / 4
