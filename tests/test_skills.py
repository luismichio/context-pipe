# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""Tests for context_pipe.skills — the skill-node wrapper."""

import sys
from io import StringIO
from unittest.mock import patch

from context_pipe import skills


def test_skills_passthrough_when_no_mandate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_text = "my context data"
    with (
        patch.object(sys, "stdin", StringIO(input_text)),
        patch.object(sys, "stdout", StringIO()) as mock_out,
        patch("sys.argv", ["skills", "unknown-skill"]),
    ):
        skills.main()
        mock_out.seek(0)
        assert mock_out.read() == input_text


def test_skills_prepends_mandate_when_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    mandate = skill_dir / "my-skill.md"
    mandate.write_text("# My Skill Instructions")

    input_text = "agent context"
    with (
        patch.object(sys, "stdin", StringIO(input_text)),
        patch.object(sys, "stdout", StringIO()) as mock_out,
        patch("sys.argv", ["skills", "my-skill", "--mandate-dir", str(skill_dir)]),
    ):
        skills.main()
        mock_out.seek(0)
        output = mock_out.read()
    assert "Skill Lens: my-skill" in output
    assert "My Skill Instructions" in output
    assert "agent context" in output


def test_skills_empty_stdin_returns_immediately(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with (
        patch.object(sys, "stdin", StringIO("")),
        patch.object(sys, "stdout", StringIO()) as mock_out,
        patch("sys.argv", ["skills", "some-skill"]),
    ):
        skills.main()
        mock_out.seek(0)
        assert mock_out.read() == ""


def test_skills_env_mandate_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_dir = tmp_path / "env_skills"
    skill_dir.mkdir()
    mandate = skill_dir / "env-skill.md"
    mandate.write_text("env skill body")

    monkeypatch.setenv("PIPE_SKILL_DIR", str(skill_dir))
    input_text = "content"
    with (
        patch.object(sys, "stdin", StringIO(input_text)),
        patch.object(sys, "stdout", StringIO()) as mock_out,
        patch("sys.argv", ["skills", "env-skill"]),
    ):
        skills.main()
        mock_out.seek(0)
        output = mock_out.read()
    assert "env skill body" in output
