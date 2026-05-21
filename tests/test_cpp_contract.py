# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""
CPP Contract Tests — Phase 7.1
Mock-subprocess suite validating run_pipe() stdin/stdout/error/timeout contract
without requiring semantic-sift-cli installed on PATH.
"""
import subprocess
import pytest
from unittest.mock import MagicMock, patch


from context_pipe.orchestrator import run_pipe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pipe(nodes):
    """Minimal pipe_config dict for run_pipe()."""
    return {"nodes": nodes}


def _node(cmd="echo-mock", args=None, help_msg=None):
    n = {"cmd": cmd, "args": args or []}
    if help_msg:
        n["help_msg"] = help_msg
    return n


from unittest.mock import AsyncMock
def _mock_proc(stdout="output", stderr="", returncode=0):
    proc = MagicMock()
    # communicate is awaited, so it should be an AsyncMock returning bytes
    proc.communicate = AsyncMock(return_value=(stdout.encode("utf-8"), stderr.encode("utf-8")))
    proc.returncode = returncode
    # create_subprocess_exec returns the proc directly, it's a coroutine so it returns proc
    return proc


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# 1. Happy path — single node passes stdin through to stdout
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_single_node_happy_path():
    proc = _mock_proc(stdout="distilled output")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result, trace = await run_pipe(_pipe([_node()]), "raw input")

    assert result == "distilled output"
    assert len(trace) == 1
    assert trace[0]["node"] == "echo-mock"
    assert trace[0]["input_size"] == len("raw input")
    assert trace[0]["output_size"] == len("distilled output")


# ---------------------------------------------------------------------------
# 2. Multi-node chaining — stdout of node N is stdin of node N+1
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_multi_node_chaining():
    proc_a = _mock_proc(stdout="step-one")
    proc_b = _mock_proc(stdout="step-two")

    with patch("asyncio.create_subprocess_exec", side_effect=[proc_a, proc_b]):
        result, trace = await run_pipe(_pipe([_node("node-a"), _node("node-b")]), "start")

    assert result == "step-two"
    assert len(trace) == 2
    # Verify node-b received node-a's output as its input
    assert trace[1]["input_size"] == len("step-one")


# ---------------------------------------------------------------------------
# 3. Non-zero returncode — returns error string, records error in trace
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_nonzero_returncode_returns_error():
    proc = _mock_proc(stdout="", stderr="something went wrong", returncode=1)
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result, trace = await run_pipe(_pipe([_node("bad-node")]), "data")

    assert "bad-node" in result
    assert "something went wrong" in result
    assert trace[0]["error"] == "something went wrong"


# ---------------------------------------------------------------------------
# 4. FileNotFoundError — returns dependency error string with help_msg
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_file_not_found_returns_help_msg():
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        result, trace = await run_pipe(
            _pipe([_node("missing-cli", help_msg="Install missing-cli via pip install missing-cli")]),
            "data",
        )

    assert "Dependency Error" in result
    assert "Install missing-cli" in result
    assert trace[0]["error"] == "FileNotFound"


# ---------------------------------------------------------------------------
# 5. Timeout — kills process, returns timeout string, records error in trace
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_timeout_kills_process_and_returns_error():
    proc = _mock_proc(stdout="", stderr="")
    import asyncio
    proc.communicate.side_effect = [asyncio.TimeoutError, (b"", b"")]

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result, trace = await run_pipe(_pipe([_node("slow-node")]), "data")

    assert "Timeout" in result
    proc.kill.assert_called_once()
    assert trace[0]["error"] == "Timeout"


# ---------------------------------------------------------------------------
# 6. Empty nodes list — returns input unchanged with empty trace
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_empty_nodes_returns_input_unchanged():
    result, trace = await run_pipe(_pipe([]), "passthrough")

    assert result == "passthrough"
    assert trace == []
