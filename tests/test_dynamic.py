# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""Tests for context_pipe/dynamic.py — Phase 7.1 + Bash/Shell Synergy."""

import pytest
from unittest.mock import patch, MagicMock

from context_pipe.dynamic import (
    run_dynamic_pipe,
    _validate_nodes,
    SHELL_UTILITY_ALLOWLIST,
    _SIFT_TERMINAL_CMDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _mock_popen(stdout: str = "distilled", returncode: int = 0):
    """Return a mock Popen that yields ``stdout`` and the given returncode."""
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (stdout, "")
    mock_proc.returncode = returncode
    return mock_proc


# ---------------------------------------------------------------------------
# Original tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_dynamic_pipe_runs_single_node():
    """A single-node dynamic pipe returns the node's stdout."""
    nodes = [{"cmd": "semantic-sift-cli", "args": ["logs"]}]
    with patch("subprocess.Popen", return_value=_mock_popen("distilled output")):
        result, trace = await run_dynamic_pipe(nodes, "raw input")
    assert result == "distilled output"
    assert len(trace) == 1
    assert trace[0]["node"] == "semantic-sift-cli"


@pytest.mark.anyio
async def test_dynamic_pipe_runs_multiple_nodes():
    """Two-node chain: second node receives the first node's output."""
    call_count = 0
    outputs = ["intermediate", "final"]

    def fake_popen(cmd, **kwargs):
        nonlocal call_count
        proc = _mock_popen(outputs[call_count])
        call_count += 1
        return proc

    nodes = [{"cmd": "jq", "args": ["."]}, {"cmd": "semantic-sift-cli", "args": ["logs"]}]
    with patch("subprocess.Popen", side_effect=fake_popen):
        result, trace = await run_dynamic_pipe(nodes, "raw input", allow_shell=True)

    assert result == "final"
    assert len(trace) == 2
    # Verify second node received first node's output
    assert trace[1]["input_size"] == len("intermediate")


@pytest.mark.anyio
async def test_dynamic_pipe_rejects_missing_cmd():
    """A node without 'cmd' raises ValueError."""
    nodes = [{"args": ["logs"]}]
    with pytest.raises(ValueError, match="missing required key 'cmd'"):
        await run_dynamic_pipe(nodes, "some input")


@pytest.mark.anyio
async def test_dynamic_pipe_rejects_shell_metacharacter_in_cmd():
    """A cmd containing shell metacharacters raises ValueError."""
    nodes = [{"cmd": "jq | rm -rf /", "args": []}]
    with pytest.raises(ValueError, match="shell metacharacters"):
        await run_dynamic_pipe(nodes, "some input")


@pytest.mark.anyio
async def test_dynamic_pipe_node_crash_returns_error():
    """A non-zero returncode returns an error string and records it in trace."""
    nodes = [{"cmd": "broken-tool"}]
    with patch("subprocess.Popen", return_value=_mock_popen("", returncode=1)):
        # Ensure communicate returns stderr text
        mock_proc = _mock_popen("", returncode=1)
        mock_proc.communicate.return_value = ("", "boom")
        with patch("subprocess.Popen", return_value=mock_proc):
            result, trace = await run_dynamic_pipe(nodes, "raw input")
    assert "Error" in result or "error" in str(trace[0])


@pytest.mark.anyio
async def test_dynamic_pipe_empty_nodes_returns_input():
    """Empty node list returns the original input unchanged."""
    result, trace = await run_dynamic_pipe([], "original text")
    assert result == "original text"
    assert trace == []


@pytest.mark.anyio
async def test_dynamic_pipe_trace_structure():
    """Trace entries have the expected keys."""
    nodes = [{"cmd": "semantic-sift-cli", "args": ["logs"]}]
    with patch("subprocess.Popen", return_value=_mock_popen("out")):
        _, trace = await run_dynamic_pipe(nodes, "in")
    assert len(trace) == 1
    entry = trace[0]
    assert "node" in entry
    assert "input_size" in entry
    assert "output_size" in entry
    assert "delta" in entry


# ---------------------------------------------------------------------------
# Bash/Shell Synergy tests
# ---------------------------------------------------------------------------

def test_shell_utility_allowlist_contains_expected_tools():
    """SHELL_UTILITY_ALLOWLIST must contain the key shell utilities."""
    for tool in ("bash", "sh", "awk", "sed", "grep", "jq", "python3"):
        assert tool in SHELL_UTILITY_ALLOWLIST


def test_sift_terminal_cmds_contains_expected():
    """_SIFT_TERMINAL_CMDS must include semantic-sift-cli and sift."""
    assert "semantic-sift-cli" in _SIFT_TERMINAL_CMDS
    assert "sift" in _SIFT_TERMINAL_CMDS


def test_shell_utility_rejected_by_default():
    """Shell utility nodes raise ValueError when allow_shell is False (default)."""
    nodes = [{"cmd": "awk", "args": ["{print $1}"]}, {"cmd": "semantic-sift-cli"}]
    with pytest.raises(ValueError, match="allow_shell=True"):
        _validate_nodes(nodes, allow_shell=False)


def test_shell_utility_accepted_with_sift_terminal():
    """Shell utility nodes pass validation when allow_shell=True and last node is sift."""
    nodes = [
        {"cmd": "grep", "args": ["-i", "error"]},
        {"cmd": "semantic-sift-cli", "args": ["--rate", "0.5"]},
    ]
    # Should not raise
    _validate_nodes(nodes, allow_shell=True)


def test_shell_utility_rejected_without_sift_terminal():
    """Shell utility pipe without a sift terminal node raises ValueError."""
    nodes = [
        {"cmd": "grep", "args": ["-i", "error"]},
        {"cmd": "some-other-tool"},
    ]
    with pytest.raises(ValueError, match="semantic-sift-cli"):
        _validate_nodes(nodes, allow_shell=True)


def test_shell_utility_single_node_must_be_sift():
    """A lone shell utility node (no sift terminal) is rejected."""
    nodes = [{"cmd": "awk", "args": ["{print $1}"]}]
    with pytest.raises(ValueError, match="semantic-sift-cli"):
        _validate_nodes(nodes, allow_shell=True)


@pytest.mark.anyio
async def test_run_dynamic_pipe_allow_shell_end_to_end():
    """run_dynamic_pipe with allow_shell=True runs the full chain."""
    call_count = 0
    outputs = ["filtered", "distilled"]

    def fake_popen(cmd, **kwargs):
        nonlocal call_count
        proc = _mock_popen(outputs[call_count])
        call_count += 1
        return proc

    nodes = [
        {"cmd": "grep", "args": ["-i", "warn"]},
        {"cmd": "semantic-sift-cli", "args": ["logs"]},
    ]
    with patch("subprocess.Popen", side_effect=fake_popen):
        result, trace = await run_dynamic_pipe(nodes, "some log text", allow_shell=True)

    assert result == "distilled"
    assert len(trace) == 2


@pytest.mark.anyio
async def test_run_dynamic_pipe_allow_shell_false_rejects_shell_cmd():
    """run_dynamic_pipe with allow_shell=False (default) rejects shell utilities."""
    nodes = [
        {"cmd": "grep", "args": ["-i", "warn"]},
        {"cmd": "semantic-sift-cli"},
    ]
    with pytest.raises(ValueError, match="allow_shell=True"):
        await run_dynamic_pipe(nodes, "text")


def test_non_shell_utility_not_affected_by_allow_shell_flag():
    """Non-allowlisted tools like 'semantic-sift-cli' are always accepted regardless of allow_shell."""
    nodes = [{"cmd": "semantic-sift-cli", "args": ["logs"]}]
    # Both False and True should pass for a plain sift-only pipe
    _validate_nodes(nodes, allow_shell=False)
    _validate_nodes(nodes, allow_shell=True)


# ---------------------------------------------------------------------------
# MCP Node Type tests (Phase 7.5-D)
# ---------------------------------------------------------------------------

def test_mcp_node_missing_server_raises():
    """node with type=mcp but no server key raises ValueError."""
    nodes = [{"type": "mcp", "tool": "scrape"}]
    with pytest.raises(ValueError, match="missing required key 'server'"):
        _validate_nodes(nodes)


def test_mcp_node_missing_tool_raises():
    """node with type=mcp but no tool key raises ValueError."""
    nodes = [{"type": "mcp", "server": "firecrawl"}]
    with pytest.raises(ValueError, match="missing required key 'tool'"):
        _validate_nodes(nodes)


def test_mcp_node_metachar_exempt():
    """mcp node with "server" containing "$" does NOT raise (no cmd check)."""
    # Note: Phase 7.5 spec says mcp nodes are exempt from metachar check.
    nodes = [{"type": "mcp", "server": "server-$", "tool": "tool-&"}]
    # Should not raise
    _validate_nodes(nodes)


def test_mcp_node_sift_terminal_guard_exempt():
    """pipe with [mcp_node] (no sift terminal) validates OK when allow_shell=False."""
    nodes = [{"type": "mcp", "server": "firecrawl", "tool": "scrape"}]
    # Should not raise even without sift terminal because no shell utility was used
    _validate_nodes(nodes, allow_shell=False)



