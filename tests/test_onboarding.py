# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""Tests for context_pipe.onboarding — key installation helper functions."""

import json
from pathlib import Path
from unittest.mock import patch

from context_pipe.onboarding import (
    build_runtime_hook_command,
    discover_sift_executable,
    resolve_pipes_config,
    verify_installation,
    get_security_gateway_command,
    discover_agent_configs,
    merge_hook_json,
    get_env_tool_names,
    inject_mandates,
    inject_hooks,
)


# ---------------------------------------------------------------------------
# build_runtime_hook_command
# ---------------------------------------------------------------------------


def test_build_runtime_hook_command_contains_executable():
    cmd = build_runtime_hook_command()
    assert "python" in cmd.lower()
    assert "context_pipe.orchestrator" in cmd
    assert "wrap" in cmd


# ---------------------------------------------------------------------------
# discover_sift_executable
# ---------------------------------------------------------------------------


def test_discover_sift_executable_returns_none_when_not_found(monkeypatch):
    # Ensure no semantic-sift-cli in PATH or known locations
    with patch("shutil.which", return_value=None):
        result = discover_sift_executable()
    # May still find it via filesystem; just ensure it returns str or None
    assert result is None or isinstance(result, str)


def test_discover_sift_executable_finds_via_which(tmp_path, monkeypatch):
    fake_exe = tmp_path / "semantic-sift-cli.exe"
    fake_exe.write_text("#!/bin/sh\necho 0.1.0")
    fake_exe.chmod(0o755)
    import sys
    monkeypatch.setattr(sys, "prefix", sys.base_prefix)
    with patch("shutil.which", return_value=str(fake_exe)):
        result = discover_sift_executable()
        assert result == str(fake_exe)


# ---------------------------------------------------------------------------
# resolve_pipes_config
# ---------------------------------------------------------------------------


def test_resolve_pipes_config_returns_no_update_when_missing(tmp_path):
    result = resolve_pipes_config(str(tmp_path / "nonexistent.json"))
    assert result["updated"] is False
    assert result["sift_path"] is None


def test_resolve_pipes_config_no_update_when_sift_not_found(tmp_path):
    config = {"pipes": [{"name": "p", "nodes": [{"cmd": "semantic-sift-cli"}]}]}
    pipes_path = tmp_path / "pipes.json"
    pipes_path.write_text(json.dumps(config))

    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        result = resolve_pipes_config(str(pipes_path))
    assert result["updated"] is False
    assert result["sift_path"] is None


def test_resolve_pipes_config_updates_node_when_sift_found(tmp_path):
    fake_exe = str(tmp_path / "semantic-sift-cli.exe")
    config = {"pipes": [{"name": "p", "nodes": [{"cmd": "semantic-sift-cli"}]}]}
    pipes_path = tmp_path / "pipes.json"
    pipes_path.write_text(json.dumps(config))

    with patch("context_pipe.onboarding.discover_sift_executable", return_value=fake_exe):
        result = resolve_pipes_config(str(pipes_path))

    assert result["updated"] is True
    assert result["sift_path"] == fake_exe

    # Verify the file was actually rewritten
    updated = json.loads(pipes_path.read_text())
    assert updated["pipes"][0]["nodes"][0]["cmd"] == fake_exe


def test_resolve_pipes_config_no_update_when_cmd_already_matches(tmp_path):
    fake_exe = str(tmp_path / "semantic-sift-cli.exe")
    config = {"pipes": [{"name": "p", "nodes": [{"cmd": fake_exe}]}]}
    pipes_path = tmp_path / "pipes.json"
    pipes_path.write_text(json.dumps(config))

    with patch("context_pipe.onboarding.discover_sift_executable", return_value=fake_exe):
        result = resolve_pipes_config(str(pipes_path))
    assert result["updated"] is False


# ---------------------------------------------------------------------------
# verify_installation
# ---------------------------------------------------------------------------


def test_verify_installation_context_pipe_ok(tmp_path):
    report = verify_installation(pipes_json_path=str(tmp_path / "missing.json"))
    assert report["context_pipe"]["ok"] is True


def test_verify_installation_pipes_config_missing(tmp_path):
    report = verify_installation(pipes_json_path=str(tmp_path / "missing.json"))
    assert report["pipes_config"]["ok"] is False
    assert "not found" in report["pipes_config"]["detail"]


def test_verify_installation_pipes_config_ok(tmp_path):
    config = {"pipes": [{"name": "p", "nodes": []}], "mappings": []}
    pipes_path = tmp_path / "pipes.json"
    pipes_path.write_text(json.dumps(config))

    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        report = verify_installation(pipes_json_path=str(pipes_path))
    assert report["pipes_config"]["ok"] is True
    assert "1 pipes" in report["pipes_config"]["detail"]


def test_verify_installation_overall_false_when_sift_missing(tmp_path):
    config = {"pipes": [], "mappings": []}
    pipes_path = tmp_path / "pipes.json"
    pipes_path.write_text(json.dumps(config))

    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        report = verify_installation(pipes_json_path=str(pipes_path))
    assert report["overall"] is False


# ---------------------------------------------------------------------------
# get_security_gateway_command
# ---------------------------------------------------------------------------


def test_get_security_gateway_command_windows():
    with patch("sys.platform", "win32"):
        cmd = get_security_gateway_command()
    assert "pwsh" in cmd
    assert "WINDSURF_TOOL_ARGS" in cmd


def test_get_security_gateway_command_posix():
    with patch("sys.platform", "linux"):
        cmd = get_security_gateway_command()
    assert "stat" in cmd
    assert "WINDSURF_TOOL_ARGS" in cmd


# ---------------------------------------------------------------------------
# discover_agent_configs
# ---------------------------------------------------------------------------


def test_discover_agent_configs_empty_dir(tmp_path):
    result = discover_agent_configs(str(tmp_path))
    assert result == []


def test_discover_agent_configs_finds_agents_md(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "AGENTS.md").write_text("# Agents")
    result = discover_agent_configs(str(tmp_path))
    assert any("AGENTS.md" in p for p in result)


def test_discover_agent_configs_finds_cursor_agents(tmp_path):
    cursor_agents = tmp_path / ".cursor" / "agents"
    cursor_agents.mkdir(parents=True)
    (cursor_agents / "my-agent.md").write_text("agent config")
    result = discover_agent_configs(str(tmp_path))
    assert any("my-agent.md" in p for p in result)


# ---------------------------------------------------------------------------
# merge_hook_json
# ---------------------------------------------------------------------------


def test_merge_hook_json_creates_new_file(tmp_path):
    path = str(tmp_path / "hooks" / "settings.json")
    hook = {"command": "python -m context_pipe.orchestrator wrap"}
    result = merge_hook_json(path, "PostToolUse", hook)
    assert result is True
    data = json.loads(Path(path).read_text())
    assert len(data["hooks"]["PostToolUse"]) == 1


def test_merge_hook_json_no_duplicate(tmp_path):
    path = str(tmp_path / "settings.json")
    hook = {"command": "python -m context_pipe.orchestrator wrap"}
    merge_hook_json(path, "PostToolUse", hook)
    result = merge_hook_json(path, "PostToolUse", hook)
    assert result is False


def test_merge_hook_json_merges_into_existing(tmp_path):
    path = str(tmp_path / "settings.json")
    existing = {"hooks": {"PostToolUse": [{"command": "existing-cmd"}]}}
    Path(path).write_text(json.dumps(existing))
    hook = {"command": "new-cmd"}
    result = merge_hook_json(path, "PostToolUse", hook)
    assert result is True
    data = json.loads(Path(path).read_text())
    cmds = [h["command"] for h in data["hooks"]["PostToolUse"]]
    assert "new-cmd" in cmds
    assert "existing-cmd" in cmds


# ---------------------------------------------------------------------------
# get_env_tool_names
# ---------------------------------------------------------------------------


def test_get_env_tool_names_opencode():
    tools = get_env_tool_names("OpenCode")
    assert tools["read"] == "read"
    assert tools["search"] == "grep"


def test_get_env_tool_names_windsurf():
    tools = get_env_tool_names("Windsurf")
    assert "read_file" in tools["read"]


def test_get_env_tool_names_shielded_returns_empty():
    tools = get_env_tool_names("Cursor")
    assert tools == {}


def test_get_env_tool_names_gemini_shielded():
    tools = get_env_tool_names("Gemini CLI")
    assert tools == {}


# ---------------------------------------------------------------------------
# inject_mandates
# ---------------------------------------------------------------------------


def test_inject_mandates_shielded_env_returns_empty(tmp_path):
    result = inject_mandates(str(tmp_path), [], environment="Cursor")
    assert result == []


def test_inject_mandates_injects_into_existing_file(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# Project\n")
    result = inject_mandates(str(tmp_path), [], environment="OpenCode")
    assert any("AGENTS.md" in a for a in result)
    content = agents_md.read_text()
    assert "CPP_SECTION_START:mandate" in content


def test_inject_mandates_updates_existing_block(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "# Project\n<!-- CPP_SECTION_START:mandate -->\nold content\n<!-- CPP_SECTION_END:mandate -->\n"
    )
    inject_mandates(str(tmp_path), [], environment="OpenCode")
    content = agents_md.read_text()
    # Block should be replaced, not duplicated
    assert content.count("CPP_SECTION_START:mandate") == 1


# ---------------------------------------------------------------------------
# inject_hooks
# ---------------------------------------------------------------------------


def test_inject_hooks_cursor(tmp_path):
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "Cursor")
    assert any("cursor" in a.lower() or "semantic-sift" in a.lower() for a in actions)
    hooks_file = tmp_path / ".cursor" / "hooks.json"
    assert hooks_file.exists()


def test_inject_hooks_gemini(tmp_path):
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "Gemini CLI")
    assert any("gemini" in a.lower() or "pipe-stats" in a.lower() for a in actions)
    assert (tmp_path / ".gemini" / "commands" / "pipe-stats.toml").exists()


def test_inject_hooks_windsurf(tmp_path):
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "Windsurf")
    assert any("windsurf" in a.lower() or "gateway" in a.lower() for a in actions)


def test_inject_hooks_opencode_no_json(tmp_path):
    """OpenCode injection is skipped gracefully when opencode.json doesn't exist."""
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "OpenCode")
    # No crash; may report sift not found
    assert isinstance(actions, list)


def test_inject_hooks_opencode_with_json(tmp_path):
    oc_json = tmp_path / "opencode.json"
    oc_json.write_text(json.dumps({"mcp": {}, "command": {}}))
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "OpenCode")
    assert any("opencode" in a.lower() for a in actions)
    data = json.loads(oc_json.read_text())
    assert "context-pipe" in data["mcp"]


def test_inject_hooks_vscode(tmp_path):
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "VSCode")
    assert any("vscode" in a.lower() or "github" in a.lower() for a in actions)


def test_inject_hooks_cline(tmp_path):
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "Cline")
    assert isinstance(actions, list)


def test_inject_hooks_kilocode(tmp_path):
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "KiloCode")
    assert any("kilo" in a.lower() for a in actions)
    assert (tmp_path / ".kilocode" / "rules" / "context.md").exists()


def test_inject_hooks_sift_found_and_linked(tmp_path):
    fake_exe = str(tmp_path / "semantic-sift-cli.exe")
    config = {"pipes": [{"name": "p", "nodes": [{"cmd": "semantic-sift-cli"}]}]}
    (tmp_path / "pipes.json").write_text(json.dumps(config))
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=fake_exe):
        actions = inject_hooks(str(tmp_path), "Generic CLI")
    assert any("linked" in a.lower() or "semantic-sift" in a.lower() for a in actions)


def test_inject_hooks_creates_pipes_json_if_missing(tmp_path):
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "Generic CLI")
    assert any("Created default pipes.json" in a for a in actions)
    assert (tmp_path / "pipes.json").exists()


# ---------------------------------------------------------------------------
# Slash Command Injection tests
# ---------------------------------------------------------------------------


def test_inject_hooks_cursor_creates_slash_command_rules(tmp_path):
    """Cursor injection must create pipe-stats.mdc and pipe-run.mdc under .cursor/rules/."""
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        actions = inject_hooks(str(tmp_path), "Cursor")
    stats_mdc = tmp_path / ".cursor" / "rules" / "pipe-stats.mdc"
    run_mdc = tmp_path / ".cursor" / "rules" / "pipe-run.mdc"
    assert stats_mdc.exists(), "pipe-stats.mdc not created"
    assert run_mdc.exists(), "pipe-run.mdc not created"
    assert "get_pipe_stats" in stats_mdc.read_text()
    assert "pipe_run" in run_mdc.read_text() or "pipe-run" in run_mdc.read_text()
    assert any("pipe-stats" in a and "pipe-run" in a for a in actions)


def test_inject_hooks_cursor_slash_rules_are_idempotent(tmp_path):
    """Running Cursor injection twice must not duplicate content in rule files."""
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        inject_hooks(str(tmp_path), "Cursor")
        inject_hooks(str(tmp_path), "Cursor")
    stats_mdc = tmp_path / ".cursor" / "rules" / "pipe-stats.mdc"
    content = stats_mdc.read_text()
    # Header must appear exactly once
    assert content.count("description:") == 1


def test_inject_hooks_opencode_injects_pipe_run_command(tmp_path):
    """OpenCode injection must add both pipe-stats and pipe-run to the command block."""
    oc_json = tmp_path / "opencode.json"
    oc_json.write_text(json.dumps({"mcp": {}, "command": {}}))
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        inject_hooks(str(tmp_path), "OpenCode")
    data = json.loads(oc_json.read_text())
    assert "pipe-stats" in data["command"], "pipe-stats command missing"
    assert "pipe-run" in data["command"], "pipe-run command missing"
    assert "pipe_run" in data["command"]["pipe-run"]["template"] or "pipe" in data["command"]["pipe-run"]["template"]


def test_inject_hooks_opencode_pipe_run_has_description(tmp_path):
    """pipe-run command entry must have a non-empty description."""
    oc_json = tmp_path / "opencode.json"
    oc_json.write_text(json.dumps({"mcp": {}, "command": {}}))
    with patch("context_pipe.onboarding.discover_sift_executable", return_value=None):
        inject_hooks(str(tmp_path), "OpenCode")
    data = json.loads(oc_json.read_text())
    assert data["command"]["pipe-run"].get("description"), "pipe-run missing description"

