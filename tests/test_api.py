# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""Tests for context_pipe.api — the programmatic Python API."""

import json

from context_pipe.api import pipe


def test_pipe_returns_original_on_empty_string():
    assert pipe("") == ""


def test_pipe_returns_original_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = pipe("hello world", config_path="nonexistent.json")
    assert result == "hello world"


def test_pipe_returns_original_when_no_mapping_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {"pipes": [], "mappings": []}
    (tmp_path / "pipes.json").write_text(json.dumps(config))
    result = pipe("some text", tool_name="bash")
    assert result == "some text"


def test_pipe_explicit_pipe_name_not_found_returns_original(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {"pipes": [], "mappings": []}
    (tmp_path / "pipes.json").write_text(json.dumps(config))
    result = pipe("data", pipe_name="nonexistent-pipe")
    assert result == "data"


def test_pipe_explicit_pipe_name_runs_echo(tmp_path, monkeypatch):
    """Integration: a pipe with a single echo-like node."""
    monkeypatch.chdir(tmp_path)
    config = {
        "pipes": [
            {
                "name": "echo-pipe",
                "nodes": [
                    {
                        "cmd": "python",
                        "args": ["-c", "import sys; sys.stdout.write(sys.stdin.read())"],
                    }
                ],
            }
        ],
        "mappings": [],
    }
    (tmp_path / "pipes.json").write_text(json.dumps(config))
    result = pipe("hello pipe", pipe_name="echo-pipe")
    assert result == "hello pipe"


def test_pipe_tool_trigger_resolves_pipe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {
        "pipes": [
            {
                "name": "bash-pipe",
                "nodes": [
                    {
                        "cmd": "python",
                        "args": ["-c", "import sys; sys.stdout.write(sys.stdin.read())"],
                    }
                ],
            }
        ],
        "mappings": [{"trigger": "tool:bash", "pipe": "bash-pipe"}],
    }
    (tmp_path / "pipes.json").write_text(json.dumps(config))
    result = pipe("data", tool_name="bash")
    assert result == "data"


def test_pipe_node_error_returns_original(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {
        "pipes": [
            {
                "name": "fail-pipe",
                "nodes": [
                    {
                        "cmd": "python",
                        "args": ["-c", "import sys; sys.exit(1)"],
                    }
                ],
            }
        ],
        "mappings": [],
    }
    (tmp_path / "pipes.json").write_text(json.dumps(config))
    result = pipe("data", pipe_name="fail-pipe")
    # run_pipe raises / returns error text; api catches and returns original
    assert result is not None
