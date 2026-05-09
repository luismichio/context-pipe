# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""Tests for shell alias injection — Phase 2 Standard Shell Aliases."""

import os
import io
from unittest.mock import patch

from context_pipe.onboarding import (
    inject_shell_aliases,
    remove_shell_aliases,
    _alias_block_present,
    _upsert_alias_block,
    _ALIAS_MARKER_START,
    _ALIAS_MARKER_END,
    _POSIX_ALIAS_BLOCK,
)
from context_pipe.cli import _build_parser


# ---------------------------------------------------------------------------
# _alias_block_present
# ---------------------------------------------------------------------------

def test_alias_block_present_true():
    content = f"some stuff\n{_ALIAS_MARKER_START}\nalias cpipe='mcp-pipe'\n{_ALIAS_MARKER_END}\nmore stuff"
    assert _alias_block_present(content) is True


def test_alias_block_present_false():
    assert _alias_block_present("# just a normal profile\nexport PATH=$PATH\n") is False


# ---------------------------------------------------------------------------
# _upsert_alias_block — append path
# ---------------------------------------------------------------------------

def test_upsert_adds_block_to_empty_file(tmp_path):
    profile = tmp_path / ".bashrc"
    profile.write_text("")
    result = _upsert_alias_block(str(profile), _POSIX_ALIAS_BLOCK)
    assert result == "added"
    assert _ALIAS_MARKER_START in profile.read_text()


def test_upsert_appends_to_existing_content(tmp_path):
    profile = tmp_path / ".bashrc"
    profile.write_text("export PATH=$HOME/bin:$PATH\n")
    _upsert_alias_block(str(profile), _POSIX_ALIAS_BLOCK)
    content = profile.read_text()
    assert "export PATH" in content
    assert "alias cpipe" in content


def test_upsert_creates_file_if_absent(tmp_path):
    profile = tmp_path / ".bashrc"
    assert not profile.exists()
    result = _upsert_alias_block(str(profile), _POSIX_ALIAS_BLOCK)
    assert result == "added"
    assert profile.exists()


# ---------------------------------------------------------------------------
# _upsert_alias_block — update path (idempotent)
# ---------------------------------------------------------------------------

def test_upsert_updates_existing_block(tmp_path):
    profile = tmp_path / ".bashrc"
    old_block = f"{_ALIAS_MARKER_START}\nalias cpipe='OLD'\n{_ALIAS_MARKER_END}"
    profile.write_text(f"# header\n{old_block}\n# footer\n")
    result = _upsert_alias_block(str(profile), _POSIX_ALIAS_BLOCK)
    assert result == "updated"
    content = profile.read_text()
    assert "OLD" not in content
    assert "mcp-pipe" in content
    assert "# header" in content
    assert "# footer" in content


def test_upsert_skipped_when_block_unchanged(tmp_path):
    profile = tmp_path / ".bashrc"
    # Write the exact block that would be written
    block = _POSIX_ALIAS_BLOCK.rstrip("\n")
    profile.write_text(f"{block}\n")
    result = _upsert_alias_block(str(profile), _POSIX_ALIAS_BLOCK)
    assert result == "skipped"


# ---------------------------------------------------------------------------
# inject_shell_aliases — POSIX
# ---------------------------------------------------------------------------

def test_inject_posix_adds_to_bashrc(tmp_path):
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("")
    profiles = [str(bashrc)]
    with patch("context_pipe.onboarding._POSIX_PROFILES", profiles):
        with patch("sys.platform", "linux"):
            actions = inject_shell_aliases()
    assert any("bashrc" in a or ".bashrc" in a for a in actions)


def test_inject_posix_skips_nonexistent_profiles(tmp_path):
    """Only ~/.bashrc is created if absent; other profiles are skipped when missing."""
    nonexistent = str(tmp_path / ".zshrc")
    bashrc = str(tmp_path / ".bashrc")
    profiles = [bashrc, nonexistent]
    with patch("context_pipe.onboarding._POSIX_PROFILES", profiles):
        with patch("sys.platform", "linux"):
            inject_shell_aliases()
    # .zshrc should not have been created
    assert not os.path.exists(nonexistent)


def test_inject_posix_idempotent(tmp_path):
    """Calling inject twice produces 'updated' on second call, not duplicate blocks."""
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("")
    profiles = [str(bashrc)]
    with patch("context_pipe.onboarding._POSIX_PROFILES", profiles):
        with patch("sys.platform", "linux"):
            inject_shell_aliases()
            inject_shell_aliases()
    content = bashrc.read_text()
    assert content.count(_ALIAS_MARKER_START) == 1


# ---------------------------------------------------------------------------
# inject_shell_aliases — PowerShell
# ---------------------------------------------------------------------------

def test_inject_pwsh_adds_set_alias(tmp_path):
    profile = tmp_path / "Microsoft.PowerShell_profile.ps1"
    profile.write_text("")
    pwsh_profiles = [str(profile)]
    with patch("context_pipe.onboarding._PWSH_PROFILES", pwsh_profiles):
        with patch("sys.platform", "win32"):
            actions = inject_shell_aliases()
    assert any("cpipe" in a.lower() or "alias" in a.lower() for a in actions)
    assert "Set-Alias" in profile.read_text()


def test_inject_posix_not_run_on_win32(tmp_path):
    """On win32, POSIX profiles must not be touched."""
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("")
    pwsh_profile = tmp_path / "profile.ps1"
    pwsh_profile.write_text("")
    with patch("context_pipe.onboarding._POSIX_PROFILES", [str(bashrc)]):
        with patch("context_pipe.onboarding._PWSH_PROFILES", [str(pwsh_profile)]):
            with patch("sys.platform", "win32"):
                inject_shell_aliases()
    # bashrc must be untouched
    assert bashrc.read_text() == ""


# ---------------------------------------------------------------------------
# remove_shell_aliases
# ---------------------------------------------------------------------------

def test_remove_clears_managed_block(tmp_path):
    profile = tmp_path / ".bashrc"
    profile.write_text(
        f"# header\n{_ALIAS_MARKER_START}\nalias cpipe='mcp-pipe'\n{_ALIAS_MARKER_END}\n# footer\n"
    )
    with patch("context_pipe.onboarding._POSIX_PROFILES", [str(profile)]):
        with patch("context_pipe.onboarding._PWSH_PROFILES", []):
            actions = remove_shell_aliases()
    assert actions
    content = profile.read_text()
    assert _ALIAS_MARKER_START not in content
    assert "# header" in content
    assert "# footer" in content


def test_remove_no_op_when_absent(tmp_path):
    profile = tmp_path / ".bashrc"
    profile.write_text("# clean profile\n")
    with patch("context_pipe.onboarding._POSIX_PROFILES", [str(profile)]):
        with patch("context_pipe.onboarding._PWSH_PROFILES", []):
            actions = remove_shell_aliases()
    assert actions == []


def test_remove_skips_nonexistent_profiles():
    with patch("context_pipe.onboarding._POSIX_PROFILES", ["/nonexistent/.bashrc"]):
        with patch("context_pipe.onboarding._PWSH_PROFILES", []):
            actions = remove_shell_aliases()
    assert actions == []


# ---------------------------------------------------------------------------
# CLI — mcp-pipe aliases subcommand
# ---------------------------------------------------------------------------

def test_cli_aliases_install_subcommand_parses():
    parser = _build_parser()
    args = parser.parse_args(["aliases", "install"])
    assert args.command == "aliases"
    assert args.alias_action == "install"


def test_cli_aliases_remove_subcommand_parses():
    parser = _build_parser()
    args = parser.parse_args(["aliases", "remove"])
    assert args.command == "aliases"
    assert args.alias_action == "remove"


def test_cli_aliases_install_with_shells():
    parser = _build_parser()
    args = parser.parse_args(["aliases", "install", "--shells", "bash", "zsh"])
    assert args.shells == ["bash", "zsh"]


def test_cli_aliases_install_calls_inject(tmp_path):
    """mcp-pipe aliases install calls inject_shell_aliases and prints results."""
    from context_pipe.cli import main
    stdout_buf = io.StringIO()
    with patch("sys.argv", ["mcp-pipe", "aliases", "install"]):
        with patch("sys.stdout", stdout_buf):
            with patch("context_pipe.cli.inject_shell_aliases", return_value=["Added cpipe alias to ~/.bashrc."]) as mock_inj:
                try:
                    main()
                except SystemExit:
                    pass
    mock_inj.assert_called_once()
    assert "cpipe" in stdout_buf.getvalue() or "alias" in stdout_buf.getvalue().lower()


def test_cli_aliases_remove_calls_remove(tmp_path):
    """mcp-pipe aliases remove calls remove_shell_aliases."""
    from context_pipe.cli import main
    with patch("sys.argv", ["mcp-pipe", "aliases", "remove"]):
        with patch("context_pipe.cli.remove_shell_aliases", return_value=["Removed cpipe alias from ~/.bashrc."]) as mock_rem:
            try:
                main()
            except SystemExit:
                pass
    mock_rem.assert_called_once()
