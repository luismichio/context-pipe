# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""Tests for context_pipe.server — closing the 0% coverage gap."""

import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import mcp.types as t
from mcp.server.fastmcp import Context

from context_pipe import server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_context(tmp_path):
    ctx = MagicMock(spec=Context)
    ctx.session = AsyncMock()
    root = t.Root(uri=tmp_path.as_uri(), name="test")
    ctx.session.list_roots.return_value = t.ListRootsResult(roots=[root])
    return ctx


@pytest.fixture
def mock_config(tmp_path):
    config = {
        "pipes": [
            {"name": "standard-distill", "description": "Fast log sifting", "nodes": [{"cmd": "sift"}]}
        ],
        "mappings": []
    }
    config_file = tmp_path / "pipes.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)


# ---------------------------------------------------------------------------
# 1. Basic Tool Listing
# ---------------------------------------------------------------------------

def test_list_pipes_returns_formatted_summary(mock_config):
    with patch("context_pipe.server.CONFIG_PATH", mock_config):
        result = server.list_pipes()
    assert "standard-distill" in result
    assert "Fast log sifting" in result
    


def test_list_pipes_handles_empty_config(tmp_path):
    empty_file = tmp_path / "empty.json"
    empty_file.write_text(json.dumps({"pipes": []}))
    with patch("context_pipe.server.CONFIG_PATH", str(empty_file)):
        result = server.list_pipes()
    assert "No pipes configured" in result
    


# ---------------------------------------------------------------------------
# 2. Pipe Execution
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_pipe_run_executes_orchestrator(mock_config):
    with patch("context_pipe.server.CONFIG_PATH", mock_config):
        with patch("context_pipe.server.run_pipe", return_value=("output", [])) as mock_run:
            result = await server.pipe_run("standard-distill", "input data")
            
    assert "output" in result
    
    mock_run.assert_called_once()


@pytest.mark.anyio
async def test_pipe_run_unknown_pipe_returns_error(mock_config):
    with patch("context_pipe.server.CONFIG_PATH", mock_config):
        result = await server.pipe_run("nonexistent", "data")
    assert "Error: Pipe 'nonexistent' not found" in result
    


@pytest.mark.anyio
async def test_pipe_run_exception_returns_error_string(mock_config):
    with patch("context_pipe.server.CONFIG_PATH", mock_config):
        with patch("context_pipe.server.run_pipe", side_effect=RuntimeError("crash")):
            result = await server.pipe_run("standard-distill", "data")
    assert "Error executing pipe: crash" in result
    


# ---------------------------------------------------------------------------
# 3. File Operations & Security
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_resolve_safe_path_allowed_in_workspace(tmp_path, mock_context):
    safe_file = tmp_path / "safe.txt"
    safe_file.touch()
    
    resolved = await server._resolve_safe_path(str(safe_file), mock_context)
    assert os.path.exists(resolved)


@pytest.mark.anyio
async def test_resolve_safe_path_denies_outside_workspace(tmp_path, mock_context):
    # Use a clearly outside path
    outside_path = "/etc/passwd" if os.name != "nt" else "C:/Windows/System32/drivers/etc/hosts"
    with pytest.raises(PermissionError):
        await server._resolve_safe_path(outside_path, mock_context)


@pytest.mark.anyio
async def test_resolve_safe_path_fallback_cwd(tmp_path):
    # Test that when context is None, it uses cwd
    old_cwd = os.getcwd()
    os.chdir(str(tmp_path))
    try:
        safe_file = tmp_path / "fallback.txt"
        safe_file.touch()
        
        resolved = await server._resolve_safe_path(str(safe_file), None)
        assert os.path.exists(resolved)
    finally:
        os.chdir(old_cwd)

@pytest.mark.anyio
async def test_resolve_safe_path_multi_path_env(tmp_path, mock_context, mock_config):
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    dir2 = tmp_path / "dir2"
    dir2.mkdir()

    file1 = dir1 / "file1.txt"
    file1.touch()
    file2 = dir2 / "file2.txt"
    file2.touch()

    auth_root_val = f"{dir1}{os.pathsep}{dir2}"
    with patch("context_pipe.server.CONFIG_PATH", mock_config):
        with patch.dict(os.environ, {"PIPE_AUTHORIZED_ROOT": auth_root_val}):
            resolved_1 = await server._resolve_safe_path(str(file1), None)
            resolved_2 = await server._resolve_safe_path(str(file2), None)
            assert os.path.exists(resolved_1)
            assert os.path.exists(resolved_2)

            outside = tmp_path / "outside.txt"
            outside.touch()
            with pytest.raises(PermissionError):
                await server._resolve_safe_path(str(outside), None)


@pytest.mark.anyio
async def test_resolve_safe_path_config_file_roots_override_env(tmp_path):
    """Config-file authorized_roots are merged even when PIPE_AUTHORIZED_ROOT
    is set to a narrow/client-injected value that excludes the target path.
    This is the key test for the env-var override bypass."""
    # dir_env: what the client injects — narrow, would normally block access
    dir_env = tmp_path / "env_root"
    dir_env.mkdir()
    # dir_cfg: what we declare in pipes.json — should always be accessible
    dir_cfg = tmp_path / "cfg_root"
    dir_cfg.mkdir()

    file_in_cfg = dir_cfg / "secret.txt"
    file_in_cfg.touch()
    file_in_env = dir_env / "normal.txt"
    file_in_env.touch()

    cfg_with_roots = {
        "pipes": [{"name": "standard-distill", "nodes": [{"cmd": "sift"}]}],
        "authorized_roots": [str(dir_cfg)],
    }
    cfg_file = tmp_path / "pipes_with_roots.json"
    cfg_file.write_text(json.dumps(cfg_with_roots))

    # Simulate client injecting a narrow PIPE_AUTHORIZED_ROOT that excludes dir_cfg
    with patch.dict(os.environ, {"PIPE_AUTHORIZED_ROOT": str(dir_env)}):
        with patch("context_pipe.server.CONFIG_PATH", str(cfg_file)):
            # File in env root — must still work
            resolved_env = await server._resolve_safe_path(str(file_in_env), None)
            assert os.path.exists(resolved_env)

            # File in config root — must work even though client didn't include it
            resolved_cfg = await server._resolve_safe_path(str(file_in_cfg), None)
            assert os.path.exists(resolved_cfg)

            # File completely outside both — must still be denied
            outside = tmp_path / "outside.txt"
            outside.touch()
            with pytest.raises(PermissionError):
                await server._resolve_safe_path(str(outside), None)

@pytest.mark.anyio
async def test_pipe_analyze_file_returns_recommendation(tmp_path, mock_context):
    f = tmp_path / "test.txt"
    f.write_text("a" * 500) # Small file
    
    result = await server.pipe_analyze_file(str(f), mock_context)
    assert "standard-distill" in result
    
    
    f.write_text("a" * 15000) # Large file
    result = await server.pipe_analyze_file(str(f), mock_context)
    assert "semantic-refinery" in result
    


@pytest.mark.anyio
async def test_pipe_analyze_file_error_handling(tmp_path, mock_context):
    result = await server.pipe_analyze_file(str(tmp_path / "nonexistent"), mock_context)
    assert "Error analyzing file" in result
    


@pytest.mark.anyio
async def test_pipe_read_file_success(tmp_path, mock_config, mock_context):
    f = tmp_path / "read.txt"
    f.write_text("file content")
    with patch("context_pipe.server.CONFIG_PATH", mock_config):
        with patch("context_pipe.server.run_pipe", return_value=("distilled", [])):
            result = await server.pipe_read_file(str(f), "standard-distill", ctx=mock_context)
            assert "distilled" in result

@pytest.mark.anyio
async def test_pipe_read_file_error_handling(tmp_path, mock_context):
    result = await server.pipe_read_file(str(tmp_path / "nonexistent"), "standard-distill", ctx=mock_context)
    assert "Error reading file" in result

@pytest.mark.anyio
async def test_pipe_read_file_lines_slicing(tmp_path, mock_config, mock_context):
    f = tmp_path / "read.txt"
    f.write_text("line1\nline2\nline3\nline4\n")
    with patch("context_pipe.server.CONFIG_PATH", mock_config):
        with patch("context_pipe.server.run_pipe", side_effect=lambda pipe, content, **kwargs: (content, [])):
            # Slicing lines 2 to 3 (inclusive, 1-indexed)
            result = await server.pipe_read_file(str(f), "standard-distill", start_line=2, end_line=3, ctx=mock_context)
            assert result == "line2\nline3\n"

@pytest.mark.anyio
async def test_pipe_read_file_lines_clamping(tmp_path, mock_config, mock_context):
    f = tmp_path / "read.txt"
    f.write_text("line1\nline2\n")
    with patch("context_pipe.server.CONFIG_PATH", mock_config):
        with patch("context_pipe.server.run_pipe", side_effect=lambda pipe, content, **kwargs: (content, [])):
            # Slicing lines beyond bounds
            result = await server.pipe_read_file(str(f), "standard-distill", start_line=1, end_line=10, ctx=mock_context)
            assert result == "line1\nline2\n"
            # Out of bounds start_line
            result_empty = await server.pipe_read_file(str(f), "standard-distill", start_line=5, end_line=10, ctx=mock_context)
            assert result_empty == ""


@pytest.mark.anyio
async def test_pipe_read_file_markdown_allows_any_range(tmp_path, mock_config, mock_context):
    f = tmp_path / "readme.md"
    
    f.write_text("line\n" * 200)
    with patch("context_pipe.server.CONFIG_PATH", mock_config):
        # Small range (< 150 lines) should succeed
        with patch("context_pipe.server.run_pipe", return_value=("distilled", [])):
            result_ok = await server.pipe_read_file(str(f), "standard-distill", start_line=1, end_line=10, ctx=mock_context)
            assert result_ok == "distilled"


# ---------------------------------------------------------------------------
# 4. Diagnostics & Onboarding
# ---------------------------------------------------------------------------

def test_get_pipe_stats_returns_balance_sheet():
    fake_sheet = {
        "signal_added": 10,
        "noise_removed": 20,
        "net_change": -10,
        "total_events": 5,
        "avg_latency_ms": 1.0
    }
    with patch("context_pipe.server.get_balance_sheet", return_value=fake_sheet):
        result = server.get_pipe_stats()
    assert "Balance Sheet" in result
    assert "+10" in result
    assert "Saved" in result
    


def test_pipe_verify_returns_report():
    mock_report = {
        "context_pipe": {"ok": True, "detail": "installed"},
        "pipes_config": {"ok": True, "detail": "valid", "path": "p.json"},
        "semantic_sift": {"ok": True, "version": "0.1.0", "path": "/bin/sift"},
        "nodes": [{"cmd": "sift", "ok": True, "resolved": "/bin/sift"}],
        "overall": True
    }
    with patch("context_pipe.server.verify_installation", return_value=mock_report):
        with patch("context_pipe.server.resolve_pipes_config", return_value={"updated": True}):
            result = server.pipe_verify()
    assert "Installation Report" in result
    assert "**context-pipe**" in result
    assert "absolute path" in result
    


def test_pipe_verify_error_report():
    mock_report = {
        "context_pipe": {"ok": False, "detail": "broken"},
        "pipes_config": {"ok": False, "detail": "missing", "path": "p.json"},
        "semantic_sift": {"ok": False, "detail": "not found"},
        "nodes": [],
        "overall": False
    }
    with patch("context_pipe.server.verify_installation", return_value=mock_report):
        with patch("context_pipe.server.resolve_pipes_config", return_value={"updated": False}):
            result = server.pipe_verify()
    assert "âœŒ **context-pipe**" not in result # Should be cross
    assert "Action required" in result
    


def test_pipe_onboard_calls_inject_hooks():
    with patch("context_pipe.server.inject_hooks", return_value=["added cursor rule"]) as mock_inject:
        result = server.pipe_onboard("Cursor")
    assert "Onboarding Successful" in result
    assert "added cursor rule" in result
    
    mock_inject.assert_called_once()


def test_pipe_onboard_no_targets(tmp_path):
    with patch("context_pipe.server.inject_hooks", return_value=[]):
        result = server.pipe_onboard("Cursor", target_dir=str(tmp_path))
    assert "already active" in result
    


# ---------------------------------------------------------------------------
# 5. Dynamic Pipes & Shadow Tools
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_pipe_run_dynamic_executes_logic():
    nodes_json = json.dumps([{"cmd": "sift"}])
    with patch("context_pipe.server.run_dynamic_pipe", return_value=("dyn-out", [])) as mock_dyn:
        result = await server.pipe_run_dynamic(nodes_json, "input")
    assert "dyn-out" in result
    
    mock_dyn.assert_called_once()


@pytest.mark.anyio
async def test_pipe_run_dynamic_invalid_json():
    result = await server.pipe_run_dynamic("NOT JSON", "data")
    assert "Error: nodes_json is not valid JSON" in result
    


@pytest.mark.anyio
async def test_pipe_run_dynamic_value_error():
    with patch("context_pipe.server.run_dynamic_pipe", side_effect=ValueError("bad nodes")):
        result = await server.pipe_run_dynamic("[]", "data")
    assert "Error: bad nodes" in result
    


@pytest.mark.anyio
async def test_pipe_run_dynamic_unexpected_error():
    with patch("context_pipe.server.run_dynamic_pipe", side_effect=Exception("boom")):
        result = await server.pipe_run_dynamic("[]", "data")
    assert "Error executing dynamic pipe: boom" in result
    


def test_pipe_list_shadow_tools_renders_table():
    fake_tools = [
        {"name": "jq", "source": "PATH", "description": "JSON", "nodes": ["jq"]}
    ]
    with patch("context_pipe.server.list_shadow_tools", return_value=fake_tools):
        result = server.pipe_list_shadow_tools()
    assert "| Name | Source |" in result
    assert "jq" in result
    


def test_pipe_list_shadow_tools_empty():
    with patch("context_pipe.server.list_shadow_tools", return_value=[]):
        result = server.pipe_list_shadow_tools()
    assert "No context-processing tools found" in result
    


# ---------------------------------------------------------------------------
# 6. Alias Management
# ---------------------------------------------------------------------------

def test_pipe_install_aliases_calls_helper():
    with patch("context_pipe.server.inject_shell_aliases", return_value=["updated .bashrc"]):
        result = server.pipe_install_aliases("bash")
    assert "cpipe alias installed" in result
    assert ".bashrc" in result
    


def test_pipe_install_aliases_no_changes():
    with patch("context_pipe.server.inject_shell_aliases", return_value=[]):
        result = server.pipe_install_aliases()
    assert "already up-to-date" in result
    


def test_pipe_remove_aliases_calls_helper():
    with patch("context_pipe.server.remove_shell_aliases", return_value=["cleaned .zshrc"]):
        result = server.pipe_remove_aliases()
    assert "cpipe alias removed" in result
    assert ".zshrc" in result
    


def test_pipe_remove_aliases_no_changes():
    with patch("context_pipe.server.remove_shell_aliases", return_value=[]):
        result = server.pipe_remove_aliases()
    assert "nothing removed" in result
    


# ---------------------------------------------------------------------------
# 7. Agent Handoff & Dashboard
# ---------------------------------------------------------------------------

def test_pipe_agent_handoff_delegates():
    with patch("context_pipe.server._pipe_agent_handoff", return_value="distilled") as mock_handoff:
        result = server.pipe_agent_handoff("raw", from_agent="A", to_agent="B")
    assert "distilled" in result
    
    mock_handoff.assert_called_once_with(output="raw", pipe_name=None, from_agent="A", to_agent="B")


def test_pipe_dashboard_returns_text():
    with patch("context_pipe.server.list_pipes", return_value="pipes-list"):
        with patch("context_pipe.server.get_pipe_stats", return_value="stats-list"):
            result = server.pipe_dashboard()
    assert "Context-Pipe Dashboard" in result
    assert "pipes-list" in result
    assert "stats-list" in result
    
