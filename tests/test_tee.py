# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""
T-Pipe (Stream Splitting) contract tests — Phase 6.1

All tests use mock subprocesses; no real nodes are required.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


from context_pipe.orchestrator import run_pipe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pipe(nodes):
    return {"nodes": nodes}


def _node(cmd="echo-mock", args=None, tee=None):
    n = {"cmd": cmd, "args": args or []}
    if tee is not None:
        n["tee"] = tee
    return n


def _mock_proc(stdout="output", stderr="", returncode=0):
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout.encode("utf-8"), stderr.encode("utf-8")))
    proc.returncode = returncode
    return proc


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# 1. Tee writes raw input to file before node processes it
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tee_writes_raw_input_to_file(tmp_path):
    sink = str(tmp_path / "raw.log")
    tee = {"sink": "file", "path": sink}

    proc = _mock_proc(stdout="distilled")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result, trace = await run_pipe(_pipe([_node(tee=tee)]), "raw input")

    assert result == "distilled"
    content = (tmp_path / "raw.log").read_text(encoding="utf-8")
    assert "raw input" in content
    assert "Context-Pipe: Tee @" in content


# ---------------------------------------------------------------------------
# 2. Append mode — second call appends; file has two tee entries
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tee_append_mode(tmp_path):
    sink = str(tmp_path / "raw.log")
    tee = {"sink": "file", "path": sink, "mode": "append"}

    proc = _mock_proc(stdout="out")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        await run_pipe(_pipe([_node(tee=tee)]), "first call")
        await run_pipe(_pipe([_node(tee=tee)]), "second call")

    content = (tmp_path / "raw.log").read_text(encoding="utf-8")
    assert "first call" in content
    assert "second call" in content
    assert content.count("Context-Pipe: Tee @") == 2


# ---------------------------------------------------------------------------
# 3. Overwrite mode — second call replaces; file has only latest entry
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tee_overwrite_mode(tmp_path):
    sink = str(tmp_path / "raw.log")
    tee = {"sink": "file", "path": sink, "mode": "overwrite"}

    proc = _mock_proc(stdout="out")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        await run_pipe(_pipe([_node(tee=tee)]), "first call")
        await run_pipe(_pipe([_node(tee=tee)]), "second call")

    content = (tmp_path / "raw.log").read_text(encoding="utf-8")
    assert "first call" not in content
    assert "second call" in content
    assert content.count("Context-Pipe: Tee @") == 1


# ---------------------------------------------------------------------------
# 4. Path token substitution — {tool_name} and {iso_date} resolved
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tee_path_token_substitution(tmp_path):
    template = str(tmp_path / "{tool_name}_{iso_date}.log")
    tee = {"sink": "file", "path": template}

    proc = _mock_proc(stdout="out")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        await run_pipe(_pipe([_node(tee=tee)]), "data", tool_name="bash")

    # _write_tee is called inside run_pipe; verify a resolved file exists
    files = list(tmp_path.glob("bash_*.log"))
    assert len(files) == 1
    assert "bash_" in files[0].name
    # iso_date pattern: YYYY-MM-DD
    import re
    assert re.search(r"\d{4}-\d{2}-\d{2}", files[0].name)


# ---------------------------------------------------------------------------
# 5. Tee failure does not interrupt the chain
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tee_failure_does_not_interrupt_chain(tmp_path):
    tee = {"sink": "file", "path": str(tmp_path / "raw.log")}

    proc = _mock_proc(stdout="distilled")
    with patch("asyncio.create_subprocess_exec", return_value=proc), \
         patch("builtins.open", side_effect=OSError("disk full")):
        result, trace = await run_pipe(_pipe([_node(tee=tee)]), "raw input")

    # Chain must complete successfully despite tee failure
    assert result == "distilled"
    assert len(trace) == 1
    assert "error" not in trace[0]


# ---------------------------------------------------------------------------
# 6. Trace includes tee_path when tee fires; absent when no tee configured
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tee_trace_includes_tee_path(tmp_path):
    sink = str(tmp_path / "raw.log")
    tee = {"sink": "file", "path": sink}

    proc = _mock_proc(stdout="out")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        _, trace_with_tee = await run_pipe(_pipe([_node(tee=tee)]), "data")
        _, trace_without_tee = await run_pipe(_pipe([_node()]), "data")

    assert "tee_path" in trace_with_tee[0]
    assert trace_with_tee[0]["tee_path"] == sink
    assert "tee_path" not in trace_without_tee[0]
