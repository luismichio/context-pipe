# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""Tests for context_pipe/shadow.py — Phase 7.2."""

import json
from unittest.mock import patch, mock_open

from context_pipe.shadow import list_shadow_tools


_SAMPLE_CONFIG = json.dumps({
    "pipes": [
        {"name": "standard-distill", "description": "Fast distillation", "nodes": [{"cmd": "semantic-sift-cli"}]},
        {"name": "semantic-refinery", "description": "Deep refinery", "nodes": [{"cmd": "semantic-sift-cli"}]},
    ]
})


def test_list_shadow_tools_returns_pipes_from_config():
    """Config with 2 pipes: both returned with source 'pipes.json'."""
    with patch("builtins.open", mock_open(read_data=_SAMPLE_CONFIG)):
        with patch("shutil.which", return_value=None):
            tools = list_shadow_tools("pipes.json")

    pipe_tools = [t for t in tools if t["source"] == "pipes.json"]
    assert len(pipe_tools) == 2
    names = {t["name"] for t in pipe_tools}
    assert "standard-distill" in names
    assert "semantic-refinery" in names


def test_list_shadow_tools_discovers_path_tools():
    """jq found on PATH: one PATH entry returned."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/jq" if cmd == "jq" else None):
            tools = list_shadow_tools("pipes.json")

    path_tools = [t for t in tools if t["source"] == "PATH"]
    assert any(t["name"] == "jq" for t in path_tools)


def test_list_shadow_tools_skips_missing_path_tools():
    """Tools not on PATH are not included in the result."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        with patch("shutil.which", return_value=None):
            tools = list_shadow_tools("pipes.json")

    path_tools = [t for t in tools if t["source"] == "PATH"]
    assert path_tools == []


def test_list_shadow_tools_handles_missing_config():
    """Missing pipes.json returns empty list without raising."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        with patch("shutil.which", return_value=None):
            tools = list_shadow_tools("pipes.json")
    assert tools == []


def test_list_shadow_tools_config_first_then_path():
    """Config entries appear before PATH entries in the combined list."""
    with patch("builtins.open", mock_open(read_data=_SAMPLE_CONFIG)):
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/jq" if cmd == "jq" else None):
            tools = list_shadow_tools("pipes.json")

    sources = [t["source"] for t in tools]
    # All pipes.json entries come before any PATH entry
    last_config_idx = max((i for i, s in enumerate(sources) if s == "pipes.json"), default=-1)
    first_path_idx = next((i for i, s in enumerate(sources) if s == "PATH"), len(sources))
    assert last_config_idx < first_path_idx
