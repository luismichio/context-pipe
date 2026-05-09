# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import pytest
import os
import shutil
from unittest.mock import patch, MagicMock
from context_pipe.orchestrator import run_pipe, check_echo

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure .pipe_cache is empty before each test."""
    cache_dir = os.path.join(os.getcwd(), ".pipe_cache")
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)
    yield
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

def test_echo_guard_node_index_boundary():
    """node 0 and node 1 with identical input produce different hash keys."""
    content = "A" * 600
    pipe_name = "test-pipe"
    
    # First call for node 0
    assert check_echo(content, pipe_name, node_index=0) is False
    # Second call for node 0 IS an echo
    assert check_echo(content, pipe_name, node_index=0) is True
    
    # But node 1 with SAME content is NOT an echo (scoped by index)
    assert check_echo(content, pipe_name, node_index=1) is False

@pytest.mark.anyio
async def test_echo_guard_same_content_two_nodes_no_suppression():
    """same content at node 0 and node 1 in the same pipe is NOT suppressed."""
    content = "B" * 600
    # Two nodes that just echo
    pipe_config = {
        "name": "multi-node",
        "nodes": [
            {"cmd": "python", "args": ["-c", "import sys; sys.stdout.write(sys.stdin.read())"]},
            {"cmd": "python", "args": ["-c", "import sys; sys.stdout.write(sys.stdin.read())"]}
        ]
    }
    
    # Integration through run_pipe
    # We need to mock Popen to avoid real subprocess overhead, but we want to check trace
    from unittest.mock import MagicMock
    def _mock_proc(stdout):
        m = MagicMock()
        m.communicate.return_value = (stdout, "")
        m.returncode = 0
        return m

    with patch("subprocess.Popen", side_effect=[_mock_proc(content), _mock_proc(content)]):
        result, trace = await run_pipe(pipe_config, content)
        
    # Both nodes should have run (not suppressed)
    assert len(trace) == 2
    assert "node" in trace[0]
    assert "node" in trace[1]

@pytest.mark.anyio
async def test_echo_guard_genuine_double_sift_cross_pipe():
    """same content through the same pipe twice within TTL IS suppressed."""
    content = "C" * 600
    pipe_config = {
        "name": "single-node",
        "nodes": [{"cmd": "python", "args": ["-c", "import sys; sys.stdout.write(sys.stdin.read())"]}]
    }
    
    def _mock_proc(stdout):
        m = MagicMock()
        m.communicate.return_value = (stdout, "")
        m.returncode = 0
        return m

    # First run
    with patch("subprocess.Popen", return_value=_mock_proc(content)):
        result1, trace1 = await run_pipe(pipe_config, content)
    assert len(trace1) == 1
    
    # Second run with same content and same pipe
    with patch("subprocess.Popen", return_value=_mock_proc(content)) as mock_popen:
        result2, trace2 = await run_pipe(pipe_config, content)
    
    # Should be suppressed (trace empty or node skipped)
    # In my implementation, I used 'continue', so trace entry for that node is missing.
    assert len(trace2) == 0
    assert result2 == content
    mock_popen.assert_not_called()
