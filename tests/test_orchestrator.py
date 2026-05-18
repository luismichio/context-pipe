import os
import sys
import shutil
from context_pipe.orchestrator import resolve_pipe_from_context, resolve_node_cmd, load_config
import json

def test_load_config_traversal(tmp_path):
    # Create sub/sub/sub structure
    sub = tmp_path / "a" / "b" / "c"
    sub.mkdir(parents=True)

    # Create pipes.json at root
    config = {"pipes": [{"name": "root-pipe"}]}
    (tmp_path / "pipes.json").write_text(json.dumps(config))

    # Run load_config from deep sub
    old_cwd = os.getcwd()
    os.chdir(str(sub))
    try:
        loaded = load_config("pipes.json")
        assert loaded["pipes"][0]["name"] == "root-pipe"
    finally:
        os.chdir(old_cwd)

def test_load_config_absolute_path(tmp_path):
    config_file = tmp_path / "abs_pipes.json"
    config = {"pipes": [{"name": "abs-pipe"}]}
    config_file.write_text(json.dumps(config))
    loaded = load_config(str(config_file))
    assert loaded["pipes"][0]["name"] == "abs-pipe"

def test_load_config_invalid_json(tmp_path):
    config_file = tmp_path / "broken.json"
    config_file.write_text("{ broken }")
    loaded = load_config(str(config_file))
    assert loaded == {"pipes": [], "mappings": []}

def test_load_config_nonexistent():
    loaded = load_config("this_file_does_not_exist_at_all.json")
    assert loaded == {"pipes": [], "mappings": []}

def test_resolve_pipe_tool_trigger():
    config = {
        "mappings": [
            {"trigger": "tool:grep", "pipe": "semantic-refinery"},
            {"trigger": "default", "pipe": "standard-distill"},
        ]
    }
    assert resolve_pipe_from_context(config, "grep_search", 100) == "semantic-refinery"
    assert resolve_pipe_from_context(config, "read_file", 100) == "standard-distill"


def test_resolve_pipe_size_trigger():
    config = {
        "mappings": [
            {"trigger": "size:>5000", "pipe": "heavy-pipe"},
            {"trigger": "default", "pipe": "standard-distill"},
        ]
    }
    assert resolve_pipe_from_context(config, "read_file", 6000) == "heavy-pipe"
    assert resolve_pipe_from_context(config, "read_file", 1000) == "standard-distill"


def test_resolve_node_cmd_absolute_path_exists(tmp_path):
    """An absolute path that exists on disk must be returned unchanged."""
    # Create a temporary fake executable
    fake_exe = tmp_path / ("fake_cmd.exe" if os.name == "nt" else "fake_cmd")
    fake_exe.write_text("#!/bin/sh\necho ok")
    fake_exe.chmod(0o755)

    result = resolve_node_cmd(str(fake_exe))
    assert result == str(fake_exe)


def test_resolve_node_cmd_absolute_path_missing():
    """An absolute path that does NOT exist must fall through to the bare-name return."""
    missing = r"C:\nonexistent\path\to\fake.exe" if os.name == "nt" else "/nonexistent/path/fake"
    result = resolve_node_cmd(missing)
    # Falls through to step 4 — returns the original cmd unchanged
    assert result == missing


def test_resolve_node_cmd_from_path():
    """A command available in PATH must be resolved to its full absolute path."""
    # Use Python's own executable name as a reliable cross-platform target
    python_name = os.path.basename(sys.executable)
    result = resolve_node_cmd(python_name)
    # Must resolve to something real and executable
    assert result is not None
    assert os.path.isfile(result) or shutil.which(python_name) is not None


def test_resolve_node_cmd_unknown_returns_bare():
    """An unknown command that is not in PATH must be returned as-is (not raise)."""
    result = resolve_node_cmd("this-command-definitely-does-not-exist-xyz123")
    assert result == "this-command-definitely-does-not-exist-xyz123"
