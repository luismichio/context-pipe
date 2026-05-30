# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""Tests for context_pipe/config_loader.py — Phase 7.3."""

import json
import os
from unittest.mock import patch, mock_open

import context_pipe.config_loader as config_loader
from context_pipe.config_loader import load_pipes_config, GLOBAL_CONFIG_PATH


_LOCAL_CONFIG = json.dumps({"pipes": [{"name": "local-pipe", "description": "local"}]})
_GLOBAL_CONFIG = json.dumps({"pipes": [{"name": "global-pipe", "description": "global"}]})
_LOCAL_AND_GLOBAL_LOCAL = json.dumps({"pipes": [{"name": "shared-pipe", "description": "local version"}]})
_LOCAL_AND_GLOBAL_GLOBAL = json.dumps({"pipes": [{"name": "shared-pipe", "description": "global version"}, {"name": "extra-pipe", "description": "extra"}]})


def _open_factory(files: dict):
    """Returns a side_effect for builtins.open that serves content per path."""
    def _open(path, *args, **kwargs):
        path_str = str(path)
        for key, data in files.items():
            if key in path_str:
                return mock_open(read_data=data)()
        raise FileNotFoundError(f"File not found: {path}")
    return _open


def test_load_local_only():
    """Local pipes.json present and loaded correctly."""
    with patch("builtins.open", _open_factory({"pipes.json": _LOCAL_CONFIG, "~": ""})):
        with patch.object(config_loader, "GLOBAL_CONFIG_PATH", "/nonexistent/global.json"):
            result = load_pipes_config("pipes.json")
    assert any(p["name"] == "local-pipe" for p in result["pipes"])


def test_load_global_fallback():
    """Local absent — ~/.mcp-pipe.json loaded."""
    def fake_open(path, *args, **kwargs):
        if "pipes.json" in str(path) and "mcp-pipe" not in str(path):
            raise FileNotFoundError
        return mock_open(read_data=_GLOBAL_CONFIG)()

    with patch("builtins.open", side_effect=fake_open):
        with patch.object(config_loader, "GLOBAL_CONFIG_PATH", "~/.mcp-pipe.json"):
            result = load_pipes_config("pipes.json")
    assert any(p["name"] == "global-pipe" for p in result["pipes"])


def test_load_merge_local_and_global():
    """Both present: local entries first; duplicate name uses local version."""
    def fake_open(path, *args, **kwargs):
        path_str = str(path)
        if "mcp-pipe" in path_str:
            return mock_open(read_data=_LOCAL_AND_GLOBAL_GLOBAL)()
        return mock_open(read_data=_LOCAL_AND_GLOBAL_LOCAL)()

    with patch("builtins.open", side_effect=fake_open):
        with patch.object(config_loader, "GLOBAL_CONFIG_PATH", "~/.mcp-pipe.json"):
            result = load_pipes_config("pipes.json")

    pipes = result["pipes"]
    # shared-pipe should appear only once and use the local version
    shared = [p for p in pipes if p["name"] == "shared-pipe"]
    assert len(shared) == 1
    assert shared[0]["description"] == "local version"
    # extra-pipe from global should be included
    assert any(p["name"] == "extra-pipe" for p in pipes)
    # local entry comes first
    assert pipes[0]["name"] == "shared-pipe"


def test_load_both_absent_returns_empty():
    """Both local and global absent — scaffold returned."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = load_pipes_config("pipes.json")
    assert result == {"pipes": [], "servers": {}, "mappings": []}


def test_servers_local_overrides_global():
    """Local key wins when both define same server key."""
    local_cfg = json.dumps({"servers": {"test-server": {"command": ["local"]}}})
    global_cfg = json.dumps({"servers": {"test-server": {"command": ["global"]}}})

    def fake_open(path, *args, **kwargs):
        if "mcp-pipe" in str(path):
            return mock_open(read_data=global_cfg)()
        return mock_open(read_data=local_cfg)()

    with patch("builtins.open", side_effect=fake_open):
        with patch.object(config_loader, "GLOBAL_CONFIG_PATH", "~/.mcp-pipe.json"):
            result = load_pipes_config("pipes.json")

    assert result["servers"]["test-server"]["command"] == ["local"]


def test_servers_global_fills_missing():
    """Global key appears when local does not define it."""
    local_cfg = json.dumps({"servers": {"local-server": {"command": ["local"]}}})
    global_cfg = json.dumps({"servers": {"global-server": {"command": ["global"]}}})

    def fake_open(path, *args, **kwargs):
        if "mcp-pipe" in str(path):
            return mock_open(read_data=global_cfg)()
        return mock_open(read_data=local_cfg)()

    with patch("builtins.open", side_effect=fake_open):
        with patch.object(config_loader, "GLOBAL_CONFIG_PATH", "~/.mcp-pipe.json"):
            result = load_pipes_config("pipes.json")

    assert "local-server" in result["servers"]
    assert "global-server" in result["servers"]


def test_servers_empty_when_neither_defines():
    """Returns {} servers if no file has servers block."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = load_pipes_config("pipes.json")
    assert result["servers"] == {}


def test_load_merge_mappings():
    """Mappings from both sources are combined, local first."""
    local_cfg = json.dumps({"mappings": [{"trigger": "local", "pipe": "p1"}]})
    global_cfg = json.dumps({"mappings": [{"trigger": "global", "pipe": "p2"}]})

    def fake_open(path, *args, **kwargs):
        if "mcp-pipe" in str(path):
            return mock_open(read_data=global_cfg)()
        return mock_open(read_data=local_cfg)()

    with patch("builtins.open", side_effect=fake_open):
        with patch.object(config_loader, "GLOBAL_CONFIG_PATH", "~/.mcp-pipe.json"):
            result = load_pipes_config("pipes.json")

    assert len(result["mappings"]) == 2
    assert result["mappings"][0]["trigger"] == "local"
    assert result["mappings"][1]["trigger"] == "global"


def test_env_placeholder_resolved():
    """${MY_VAR} substituted from os.environ."""
    env = {"MY_VAR": "secret-value"}
    with patch.dict(os.environ, env):
        env_dict = {"API_KEY": "${MY_VAR}"}
        resolved = config_loader.resolve_placeholders(env_dict)
        assert resolved["API_KEY"] == "secret-value"


def test_env_placeholder_unknown_raises_value_error():
    """${UNKNOWN_VAR} raises ValueError."""
    import pytest
    with patch.dict(os.environ, {}, clear=True):
        env_dict = {"API_KEY": "${UNKNOWN_VAR}"}
        with pytest.raises(ValueError, match="Missing pipe variable: UNKNOWN_VAR"):
            config_loader.resolve_placeholders(env_dict)


def test_env_placeholder_empty_dict():
    """Empty env dict returns empty dict."""
    assert config_loader.resolve_placeholders({}) == {}


def test_load_local_malformed_falls_back_to_global():
    """Local is invalid JSON — global config is used."""
    def fake_open(path, *args, **kwargs):
        path_str = str(path)
        if "mcp-pipe" in path_str:
            return mock_open(read_data=_GLOBAL_CONFIG)()
        return mock_open(read_data="NOT JSON {{{{")()

    with patch("builtins.open", side_effect=fake_open):
        with patch.object(config_loader, "GLOBAL_CONFIG_PATH", "~/.mcp-pipe.json"):
            result = load_pipes_config("pipes.json")
    assert any(p["name"] == "global-pipe" for p in result["pipes"])


def test_load_global_path_is_user_home():
    """GLOBAL_CONFIG_PATH resolves to ~/.mcp-pipe.json."""
    expected = os.path.expanduser("~/.mcp-pipe.json")
    assert GLOBAL_CONFIG_PATH == expected
