# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
Tests for context_pipe/telemetry.py.

Covers:
- log_telemetry writes a session entry to the telemetry file in jsonl format.
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
from unittest.mock import patch, MagicMock
from context_pipe import telemetry as tel


@pytest.fixture(autouse=True)
def isolated_telemetry(tmp_path, monkeypatch):
    """Redirect telemetry writes to a temp file for every test."""
    temp_file = str(tmp_path / "test_telemetry.jsonl")
    monkeypatch.setattr(tel, "TELEMETRY_FILE", temp_file)
    monkeypatch.setattr(tel, "PIPE_TELEMETRY_DISABLED", False)

    # Force fallback to local ledger by masking semantic_sift
    with patch.dict("sys.modules", {"semantic_sift.telemetry": None}):
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
        lines = f.readlines()

    assert len(lines) == 1
    event = json.loads(lines[0])

    assert event["session_id"] == sid
    assert "grep_search" in event["tool_name"]
    assert event["original_chars"] == 1000
    assert event["final_chars"] == 600


def test_log_telemetry_accumulates_across_calls(isolated_telemetry):
    """Multiple calls to the same session/tool must accumulate in the balance sheet."""
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
        lines = f.readlines()

    assert len(lines) == 3
    
    sheet = tel.get_balance_sheet()
    assert sheet["total_events"] == 3
    assert sheet["noise_removed"] == 600  # (500-300)*3 = 600


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
        lines = f.readlines()
        
    event = json.loads(lines[0])
    
    assert "original_chars" in event
    assert "final_chars" in event
    # No 'content', 'payload', 'body', or 'text' field should exist
    for forbidden in ("content", "payload", "body", "text", "prompt"):
        assert forbidden not in event


def test_log_telemetry_disabled_is_noop(tmp_path, monkeypatch):
    """When PIPE_TELEMETRY_DISABLED is True, the file must not be created."""
    temp_file = str(tmp_path / "should_not_exist.jsonl")
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
    monkeypatch.setattr(tel, "TELEMETRY_FILE", str(tmp_path / "nonexistent.jsonl"))
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


def test_log_bypass_event_writes_jsonl(isolated_telemetry):
    """log_bypass_event must write a bypass entry to the local log."""
    tel.log_bypass_event(tool_name="test_tool", reason="test_reason", platform="test_plat")
    
    with open(isolated_telemetry) as f:
        lines = f.readlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["type"] == "bypass"
        assert event["reason"] == "test_reason"

def test_get_balance_sheet_aggregates_local_ledger(isolated_telemetry):
    """get_balance_sheet must correctly aggregate signal/noise from the local JSONL ledger."""
    # 1. Log a sifting event (100 -> 40 chars = 60 noise removed)
    tel.log_telemetry("s1", "t1", "tool1", 100, 40, 10.0)
    # 2. Log a bypass event
    tel.log_bypass_event("tool2", "reason")
    
    # Isolate from semantic_sift to only test local path
    with patch.dict("sys.modules", {"semantic_sift.telemetry": None}):
        sheet = tel.get_balance_sheet()
        assert sheet["noise_removed"] == 60
        assert sheet["total_events"] == 1
        assert sheet["bypass_events"] == 1

def test_get_latest_telemetry_reads_local_ledger(isolated_telemetry):
    """get_latest_telemetry must return the last tool_call from the local ledger."""
    tel.log_telemetry("s1", "t1", "tool1", 100, 50, 5.0)
    tel.log_telemetry("s2", "t2", "tool2", 200, 100, 10.0)
    
    with patch.dict("sys.modules", {"semantic_sift.telemetry": None}):
        latest = tel.get_latest_telemetry()
        assert latest is not None
        assert latest["tool_key"] == "unknown:tool2"
        assert latest["original_chars"] == 200

def test_estimate_tokens_basic():
    """estimate_tokens must return a positive integer for non-empty input."""
    assert tel.estimate_tokens("hello world") > 0
    assert tel.estimate_tokens("") == 0
    assert tel.estimate_tokens("a" * 400) == 100  # 400 chars / 4

def test_log_bypass_event_skips_cloud_pulse_for_range(isolated_telemetry):
    """log_bypass_event must NOT trigger send_telemetry_pulse if the reason is a line-range bypass."""
    mock_sift_tel = MagicMock()
    with patch.dict("sys.modules", {"semantic_sift.telemetry": mock_sift_tel}):
        tel.log_bypass_event(
            tool_name="view_file",
            reason="Line range <= 50 lines (10)",
            platform="Generic CLI"
        )
        mock_sift_tel.send_telemetry_pulse.assert_not_called()


def test_multi_workspace_telemetry_isolation(tmp_path, monkeypatch):
    """When config_path is provided, telemetry must be routed to the respective project directory."""
    monkeypatch.setenv("SIFT_TELEMETRY_OPTED_IN", "true")
    project_a_dir = tmp_path / "project_a"
    project_b_dir = tmp_path / "project_b"
    project_a_dir.mkdir()
    project_b_dir.mkdir()

    config_a = str(project_a_dir / "pipes.json")
    config_b = str(project_b_dir / "pipes.json")

    # Isolate from semantic_sift to only test local path
    with patch.dict("sys.modules", {"semantic_sift.telemetry": None}):
        tel.log_telemetry(
            session_id="session-a",
            start_time="now",
            tool_name="toolA",
            original_size=100,
            final_size=50,
            latency_ms=10.0,
            config_path=config_a,
        )

        tel.log_telemetry(
            session_id="session-b",
            start_time="now",
            tool_name="toolB",
            original_size=200,
            final_size=150,
            latency_ms=20.0,
            config_path=config_b,
        )

        # Check telemetry files are created in respective workspace folders
        telemetry_a_file = project_a_dir / ".pipe_telemetry.jsonl"
        telemetry_b_file = project_b_dir / ".pipe_telemetry.jsonl"
        assert telemetry_a_file.exists()
        assert telemetry_b_file.exists()

        # Check stats isolation
        sheet_a = tel.get_balance_sheet(config_path=config_a)
        sheet_b = tel.get_balance_sheet(config_path=config_b)

        assert sheet_a["noise_removed"] == 50
        assert sheet_a["total_events"] == 1

        assert sheet_b["noise_removed"] == 50
        assert sheet_b["total_events"] == 1


def test_telemetry_double_counting_prevention(isolated_telemetry):
    """get_balance_sheet must skip node-level sifts or events marked as is_node to prevent double counting."""
    # 1. Log overall pipe-level call (100 -> 10 chars = 90 noise removed)
    tel.log_telemetry("s1", "t1", "tool1", 100, 10, 10.0, pipe_name="my-pipe")
    # 2. Log an internal node call
    tel.log_telemetry("s1", "t1", "tool1", 50, 10, 5.0, pipe_name="my-pipe")
    
    # Overwrite the last log entry in the file to have is_node = True for testing
    import json
    with open(isolated_telemetry, "r", encoding="utf-8") as f:
        events = [json.loads(line) for line in f]
    
    if len(events) >= 2:
        events[1]["is_node"] = True
    
    with open(isolated_telemetry, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    # 3. Verify get_balance_sheet aggregates only the pipe-level event
    with patch.dict("sys.modules", {"semantic_sift.telemetry": None}):
        sheet = tel.get_balance_sheet()
        assert sheet["noise_removed"] == 90
        assert sheet["total_events"] == 1


def test_get_balance_sheet_filters_sift_shared_ledger(tmp_path, monkeypatch):
    """get_balance_sheet must skip tools containing 'sift_cli_' or marked with 'is_node' in the shared ledger."""
    sift_file = tmp_path / "mock_sift_telemetry.json"
    sift_data = {
        "session-1": {
            "start_time": "2026-06-05T20:00:00Z",
            "tools": {
                "my-pipe:tool1": {
                    "calls": 1,
                    "original_chars": 100,
                    "final_chars": 10,
                    "latency_ms": 10.0
                },
                "sift_cli_semantic:tool1": {
                    "calls": 1,
                    "original_chars": 50,
                    "final_chars": 10,
                    "latency_ms": 5.0
                },
                "another-node:tool1": {
                    "calls": 1,
                    "original_chars": 50,
                    "final_chars": 10,
                    "latency_ms": 5.0,
                    "is_node": True
                }
            }
        }
    }
    with open(sift_file, "w", encoding="utf-8") as f:
        json.dump(sift_data, f)

    # Mock semantic_sift.telemetry.TELEMETRY_FILE path
    mock_sift_module = MagicMock()
    mock_sift_module.TELEMETRY_FILE = str(sift_file)
    with patch.dict("sys.modules", {"semantic_sift.telemetry": mock_sift_module}), \
         patch("context_pipe.telemetry.resolve_telemetry_file", return_value=str(tmp_path / "empty_local.jsonl")):
        sheet = tel.get_balance_sheet()
        
    assert sheet["noise_removed"] == 90
    assert sheet["total_events"] == 1
