# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
Tests for mcp-pipe tool subcommand (Phase 7.6-A/B/C).

Coverage:
  Phase 7.6-A: CLI scaffold — subcommand registration, argument validation
  Phase 7.6-B: Execution — tool call, input_key, static args, list-tools, timeout, _parse_tool_args
  Phase 7.6-C: Telemetry accounting
"""

import json
import sys
import io
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from context_pipe.cli import _build_parser, _parse_tool_args, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pipes_json(tmp_path, servers: dict) -> str:
    """Write a pipes.json with the given servers block and return its path."""
    config = {"servers": servers}
    p = tmp_path / "pipes.json"
    p.write_text(json.dumps(config))
    return str(p)


def _make_mock_session(result_text: str = "mcp output"):
    """Build a mock MCP ClientSession that returns result_text from call_tool."""
    from mcp.types import CallToolResult, TextContent

    mock_result = CallToolResult(content=[TextContent(type="text", text=result_text)])
    session = MagicMock()
    session.initialize = AsyncMock()
    session.call_tool = AsyncMock(return_value=mock_result)
    session.list_tools = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    return session


def _make_list_tools_session(tool_names: list[str]):
    """Build a mock session whose list_tools returns the given tool names."""
    from mcp.types import ListToolsResult, Tool

    tools = [Tool(name=n, description=f"desc of {n}", inputSchema={}) for n in tool_names]
    result = ListToolsResult(tools=tools)
    session = MagicMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(return_value=result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    return session


def _run_tool(*argv, stdin_text: str = "") -> tuple[str, str, int]:
    """
    Invoke main() with the given argv, capturing stdout/stderr and exit code.
    Returns (stdout, stderr, exit_code).
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exit_code = 0
    with patch.object(sys, "argv", ["mcp-pipe"] + list(argv)):
        with patch("sys.stdout", stdout_buf):
            with patch("sys.stderr", stderr_buf):
                with patch("sys.stdin", io.StringIO(stdin_text)):
                    with patch.object(sys.stdin, "isatty", return_value=bool(not stdin_text)):
                        try:
                            main()
                        except SystemExit as exc:
                            exit_code = exc.code if isinstance(exc.code, int) else 0
    return stdout_buf.getvalue(), stderr_buf.getvalue(), exit_code


# ---------------------------------------------------------------------------
# Phase 7.6-A — CLI scaffold (3 tests)
# ---------------------------------------------------------------------------

def test_tool_subcommand_registered():
    """mcp-pipe tool --help exits 0 and shows server_key in usage."""
    parser = _build_parser()
    # Parser can parse the subcommand without error
    args = parser.parse_args(["tool", "myserver", "mytool"])
    assert args.command == "tool"
    assert args.server == "myserver"
    assert args.tool_name == "mytool"
    assert args.list_tools is False
    assert args.input_key == "content"


def test_tool_unknown_server_exits_1(tmp_path, capsys):
    """mcp-pipe tool nonexistent-server exits 1 with helpful message."""
    config_path = _make_pipes_json(tmp_path, {})
    out, err, code = _run_tool("tool", "nonexistent-server", "some-tool", "--config", config_path)
    assert code == 1
    assert "nonexistent-server" in err


def test_tool_no_tool_name_exits_1(tmp_path):
    """mcp-pipe tool myserver (no tool_name, no --list-tools) exits 1."""
    config_path = _make_pipes_json(tmp_path, {"myserver": {"command": ["cmd"]}})
    out, err, code = _run_tool("tool", "myserver", "--config", config_path)
    assert code == 1
    assert "tool_name" in err or "required" in err.lower() or "list-tools" in err


# ---------------------------------------------------------------------------
# Phase 7.6-B — Execution (8 tests)
# ---------------------------------------------------------------------------

def test_tool_call_basic(tmp_path, capsys):
    """stdin routed to tool, result written to stdout."""
    config_path = _make_pipes_json(tmp_path, {"myserver": {"command": ["cmd"]}})
    session = _make_mock_session("hello from mcp")

    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio, \
         patch("context_pipe.orchestrator.ClientSession", return_value=session):
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        out, err, code = _run_tool(
            "tool", "myserver", "my-tool", "--config", config_path,
            stdin_text="some input",
        )

    assert code == 0
    assert "hello from mcp" in out
    session.call_tool.assert_called_once_with("my-tool", {"content": "some input"})


def test_tool_call_input_key_override(tmp_path):
    """--input-key url routes stdin under the 'url' key."""
    config_path = _make_pipes_json(tmp_path, {"fc": {"command": ["cmd"]}})
    session = _make_mock_session("scraped")

    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio, \
         patch("context_pipe.orchestrator.ClientSession", return_value=session):
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        _run_tool(
            "tool", "fc", "scrape", "--input-key", "url",
            "--config", config_path, stdin_text="https://example.com",
        )

    session.call_tool.assert_called_once_with("scrape", {"url": "https://example.com"})


def test_tool_call_static_arg_merged(tmp_path):
    """--arg depth=2 is merged with the input_key arg."""
    config_path = _make_pipes_json(tmp_path, {"s": {"command": ["cmd"]}})
    session = _make_mock_session()

    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio, \
         patch("context_pipe.orchestrator.ClientSession", return_value=session):
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        _run_tool(
            "tool", "s", "t", "--arg", "depth=2", "--arg", "mode=fast",
            "--config", config_path, stdin_text="data",
        )

    call_args = session.call_tool.call_args[0][1]
    assert call_args["content"] == "data"
    assert call_args["depth"] == "2"
    assert call_args["mode"] == "fast"


def test_tool_list_tools(tmp_path, capsys):
    """--list-tools prints tool names and descriptions."""
    config_path = _make_pipes_json(tmp_path, {"myserver": {"command": ["cmd"]}})
    session = _make_list_tools_session(["alpha", "beta", "gamma"])

    with patch("context_pipe.cli.stdio_client") as mock_stdio, \
         patch("context_pipe.cli.ClientSession", return_value=session):
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        out, err, code = _run_tool(
            "tool", "myserver", "--list-tools", "--config", config_path,
        )

    assert code == 0
    assert "alpha" in out
    assert "beta" in out
    assert "gamma" in out


def test_tool_list_tools_empty(tmp_path):
    """Server with no tools prints a message and exits 0."""
    config_path = _make_pipes_json(tmp_path, {"myserver": {"command": ["cmd"]}})
    session = _make_list_tools_session([])

    with patch("context_pipe.cli.stdio_client") as mock_stdio, \
         patch("context_pipe.cli.ClientSession", return_value=session):
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        out, err, code = _run_tool(
            "tool", "myserver", "--list-tools", "--config", config_path,
        )

    assert code == 0
    assert "No tools found" in out


def test_tool_timeout_exits_1(tmp_path):
    """asyncio.TimeoutError from _run_mcp_node causes exit 1 with timeout message."""
    config_path = _make_pipes_json(tmp_path, {"s": {"command": ["cmd"]}})

    with patch("context_pipe.cli._run_mcp_node", new=AsyncMock(side_effect=asyncio.TimeoutError)), \
         patch.dict("os.environ", {"PIPE_NODE_TIMEOUT_MS": "5000"}):
        out, err, code = _run_tool(
            "tool", "s", "slow-tool", "--config", config_path, stdin_text="x",
        )

    assert code == 1
    assert "timed out" in err.lower() or "timeout" in err.lower()


def test_tool_parse_tool_args_valid():
    """_parse_tool_args(['key=val']) returns {'key': 'val'}."""
    result = _parse_tool_args(["key=val"])
    assert result == {"key": "val"}


def test_tool_parse_tool_args_equals_in_val():
    """_parse_tool_args(['k=a=b']) returns {'k': 'a=b'} (splits on first '=' only)."""
    result = _parse_tool_args(["k=a=b"])
    assert result == {"k": "a=b"}


# ---------------------------------------------------------------------------
# Phase 7.6-C — Telemetry accounting (2 tests)
# ---------------------------------------------------------------------------

def test_tool_telemetry_logged_on_success(tmp_path):
    """Successful call writes a telemetry entry via log_telemetry."""
    config_path = _make_pipes_json(tmp_path, {"s": {"command": ["cmd"]}})
    session = _make_mock_session("ok")

    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio, \
         patch("context_pipe.orchestrator.ClientSession", return_value=session), \
         patch("context_pipe.cli.log_telemetry") as mock_tel:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        out, err, code = _run_tool(
            "tool", "s", "my-tool", "--config", config_path, stdin_text="hello",
        )

    assert code == 0
    mock_tel.assert_called_once()
    kwargs = mock_tel.call_args
    # tool_name should encode the server/tool path
    assert "s/my-tool" in str(kwargs)


def test_tool_telemetry_not_logged_on_error(tmp_path):
    """Failed call (server not found) does not call log_telemetry."""
    config_path = _make_pipes_json(tmp_path, {})  # empty — server missing

    with patch("context_pipe.cli.log_telemetry") as mock_tel:
        out, err, code = _run_tool(
            "tool", "missing", "my-tool", "--config", config_path,
        )

    assert code == 1
    mock_tel.assert_not_called()
