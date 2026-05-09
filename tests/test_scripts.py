# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""Tests for context_pipe.scripts — the script/mandate-node wrapper."""

import sys
from io import StringIO
from unittest.mock import patch

from context_pipe import scripts


def test_scripts_passthrough_when_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_text = "my context data"
    with (
        patch.object(sys, "stdin", StringIO(input_text)),
        patch.object(sys, "stdout", StringIO()) as mock_out,
        patch("sys.argv", ["scripts", "unknown-script"]),
    ):
        scripts.main()
        mock_out.seek(0)
        assert mock_out.read() == input_text


def test_scripts_prepends_mandate_when_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    mandate = script_dir / "my-mandate.md"
    mandate.write_text("# My Mandate Instructions")

    input_text = "agent context"
    with (
        patch.object(sys, "stdin", StringIO(input_text)),
        patch.object(sys, "stdout", StringIO()) as mock_out,
        patch("sys.argv", ["scripts", "my-mandate", "--script-dir", str(script_dir)]),
    ):
        scripts.main()
        mock_out.seek(0)
        output = mock_out.read()
    assert "Mandate (my-mandate)" in output
    assert "My Mandate Instructions" in output
    assert "agent context" in output


def test_scripts_executes_python_script(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    py_script = script_dir / "my-script.py"
    py_script.write_text("import sys; print(f'PROCESSED: {sys.stdin.read()}')")

    input_text = "raw data"
    with (
        patch.object(sys, "stdin", StringIO(input_text)),
        patch.object(sys, "stdout", StringIO()) as mock_out,
        patch("sys.argv", ["scripts", "my-script", "--script-dir", str(script_dir)]),
    ):
        scripts.main()
        mock_out.seek(0)
        output = mock_out.read()
    assert "PROCESSED: raw data" in output


def test_scripts_empty_stdin_returns_immediately(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with (
        patch.object(sys, "stdin", StringIO("")),
        patch.object(sys, "stdout", StringIO()) as mock_out,
        patch("sys.argv", ["scripts", "some-script"]),
    ):
        scripts.main()
        mock_out.seek(0)
        assert mock_out.read() == ""


def test_scripts_env_script_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script_dir = tmp_path / "env_scripts"
    script_dir.mkdir()
    mandate = script_dir / "env-script.md"
    mandate.write_text("env script body")

    monkeypatch.setenv("PIPE_SCRIPT_DIR", str(script_dir))
    input_text = "content"
    with (
        patch.object(sys, "stdin", StringIO(input_text)),
        patch.object(sys, "stdout", StringIO()) as mock_out,
        patch("sys.argv", ["scripts", "env-script"]),
    ):
        scripts.main()
        mock_out.seek(0)
        output = mock_out.read()
    assert "env script body" in output
