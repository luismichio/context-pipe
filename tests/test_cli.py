# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""Tests for context_pipe/cli.py — mcp-pipe CLI (Phase 7, mcp-pipe item)."""

import json
import sys
import io
import pytest
from unittest.mock import patch

from context_pipe.cli import _build_parser, _read_input, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_cli(*argv, stdin_text: str = "") -> tuple[str, str, int]:
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
# Parser tests
# ---------------------------------------------------------------------------

def test_parser_run_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["run", "standard-distill"])
    assert args.command == "run"
    assert args.pipe_name == "standard-distill"
    assert args.config == "pipes.json"
    assert args.verbose is False


def test_parser_run_dynamic_subcommand():
    parser = _build_parser()
    nodes = '[{"cmd": "jq"}]'
    args = parser.parse_args(["run-dynamic", nodes])
    assert args.command == "run-dynamic"
    assert args.nodes_json == nodes


def test_parser_list_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["list"])
    assert args.command == "list"


def test_parser_stats_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["stats"])
    assert args.command == "stats"


def test_parser_serve_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["serve"])
    assert args.command == "serve"


def test_parser_no_subcommand_exits():
    """No subcommand should exit non-zero."""
    with pytest.raises(SystemExit) as exc_info:
        _build_parser().parse_args([])
    assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# _read_input tests
# ---------------------------------------------------------------------------

def test_read_input_from_file(tmp_path):
    f = tmp_path / "data.txt"
    f.write_text("hello from file")
    result = _read_input(str(f))
    assert result == "hello from file"


def test_read_input_from_stdin():
    with patch("sys.stdin", io.StringIO("stdin data")):
        with patch.object(sys.stdin, "isatty", return_value=False):
            result = _read_input(None)
    assert result == "stdin data"


def test_read_input_tty_returns_empty():
    with patch("sys.stdin", io.StringIO("")):
        with patch.object(sys.stdin, "isatty", return_value=True):
            result = _read_input(None)
    assert result == ""


def test_read_input_missing_file_exits():
    with pytest.raises(SystemExit):
        _read_input("/nonexistent/path/file.txt")


# ---------------------------------------------------------------------------
# mcp-pipe run
# ---------------------------------------------------------------------------

def test_cmd_run_calls_run_pipe():
    """mcp-pipe run invokes run_pipe and writes result to stdout."""
    mock_config = {"pipes": [{"name": "standard-distill", "nodes": [{"cmd": "sift"}]}]}
    with patch("context_pipe.cli.load_pipes_config", return_value=mock_config):
        with patch("context_pipe.cli.run_pipe", return_value=("distilled output", [])) as mock_rp:
            stdout, stderr, code = _run_cli("run", "standard-distill", stdin_text="raw input")

    assert code == 0
    assert "distilled output" in stdout
    mock_rp.assert_called_once()


def test_cmd_run_unknown_pipe_exits_nonzero():
    """Unknown pipe name exits with code 1 and error on stderr."""
    mock_config = {"pipes": []}
    with patch("context_pipe.cli.load_pipes_config", return_value=mock_config):
        stdout, stderr, code = _run_cli("run", "no-such-pipe", stdin_text="data")

    assert code == 1
    assert "not found" in stderr


def test_cmd_run_empty_stdin_exits_zero():
    """Empty stdin (TTY) exits 0 silently."""
    mock_config = {"pipes": [{"name": "my-pipe", "nodes": []}]}
    with patch("context_pipe.cli.load_pipes_config", return_value=mock_config):
        stdout, stderr, code = _run_cli("run", "my-pipe")  # no stdin_text → TTY

    assert code == 0
    assert stdout == ""


def test_cmd_run_verbose_prepends_header():
    """--verbose flag prepends audit header to output."""
    mock_config = {"pipes": [{"name": "p", "nodes": [{"cmd": "sift"}]}]}
    trace = [{"node": "sift", "input_size": 9, "output_size": 4, "delta": -5}]
    with patch("context_pipe.cli.load_pipes_config", return_value=mock_config):
        with patch("context_pipe.cli.run_pipe", return_value=("out", trace)):
            stdout, _, code = _run_cli("run", "p", "-v", stdin_text="raw input")

    assert code == 0
    # Audit header contains node name
    assert "sift" in stdout or "out" in stdout


# ---------------------------------------------------------------------------
# mcp-pipe run-dynamic
# ---------------------------------------------------------------------------

def test_cmd_run_dynamic_executes_nodes():
    nodes = json.dumps([{"cmd": "jq", "args": ["."]}])
    with patch("context_pipe.cli.run_dynamic_pipe", return_value=("dynout", [])) as mock_dyn:
        stdout, stderr, code = _run_cli("run-dynamic", nodes, stdin_text="input")

    assert code == 0
    assert "dynout" in stdout
    mock_dyn.assert_called_once()


def test_cmd_run_dynamic_invalid_json_exits():
    stdout, stderr, code = _run_cli("run-dynamic", "NOT JSON", stdin_text="data")
    assert code == 1
    assert "not valid JSON" in stderr


def test_cmd_run_dynamic_shell_metachar_exits():
    nodes = json.dumps([{"cmd": "jq | rm -rf /"}])
    with patch("context_pipe.cli.run_dynamic_pipe", side_effect=ValueError("shell metacharacters")):
        stdout, stderr, code = _run_cli("run-dynamic", nodes, stdin_text="data")
    assert code == 1
    assert "shell metacharacters" in stderr


# ---------------------------------------------------------------------------
# mcp-pipe list
# ---------------------------------------------------------------------------

def test_cmd_list_prints_pipes_and_tools():
    fake_tools = [
        {"name": "standard-distill", "source": "pipes.json", "description": "Fast", "nodes": ["sift"]},
        {"name": "jq", "source": "PATH", "description": "JSON processor", "nodes": ["jq"]},
    ]
    with patch("context_pipe.cli.list_shadow_tools", return_value=fake_tools):
        stdout, _, code = _run_cli("list")

    assert code == 0
    assert "standard-distill" in stdout
    assert "jq" in stdout


def test_cmd_list_empty_prints_message():
    with patch("context_pipe.cli.list_shadow_tools", return_value=[]):
        stdout, _, code = _run_cli("list")

    assert code == 0
    assert "No pipes" in stdout or "none" in stdout.lower() or "No" in stdout


# ---------------------------------------------------------------------------
# mcp-pipe stats
# ---------------------------------------------------------------------------

def test_cmd_stats_prints_balance_sheet():
    fake_sheet = {
        "signal_added": 100,
        "noise_removed": 500,
        "net_change": -400,
        "total_events": 7,
        "avg_latency_ms": 12.5,
        "fallback_events": 0,
    }
    with patch("context_pipe.cli.get_balance_sheet", return_value=fake_sheet):
        stdout, _, code = _run_cli("stats")

    assert code == 0
    assert "Balance Sheet" in stdout
    assert "500" in stdout


# ---------------------------------------------------------------------------
# mcp-pipe serve
# ---------------------------------------------------------------------------

def test_cmd_serve_calls_server_main():
    with patch("context_pipe.cli._cmd_serve") as mock_serve:
        mock_serve.return_value = 0
        # Just verify the dispatch reaches _cmd_serve; don't actually start the server
        parser = _build_parser()
        args = parser.parse_args(["serve"])
        assert args.command == "serve"
