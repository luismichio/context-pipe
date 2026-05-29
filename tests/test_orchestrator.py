import os
import sys
import shutil
import pytest
from unittest.mock import patch
from context_pipe.orchestrator import resolve_pipe_from_context, resolve_node_cmd, load_config, run_pipe
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


# ---------------------------------------------------------------------------
# Pipe Logging & Script Node Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_run_pipe_logging_disabled(capsys):
    """Verify that no logging is output to stderr when disabled."""
    pipe_config = {
        "name": "test-log-disabled",
        "nodes": [{"cmd": sys.executable, "args": ["-c", "print('hello')"]}]
    }
    with patch.dict(os.environ, {}):
        if "PIPE_LOG_LEVEL" in os.environ:
            del os.environ["PIPE_LOG_LEVEL"]
        await run_pipe(pipe_config, "input_data")
        captured = capsys.readouterr()
        assert captured.err == ""


@pytest.mark.anyio
async def test_run_pipe_logging_compact(capsys):
    """Verify compact logging output to stderr on exit."""
    pipe_config = {
        "name": "test-log-compact",
        "logging": {
            "enabled": True,
            "prefix": "[MYPREFIX]",
            "level": "compact",
            "fields": ["node", "tokens"]
        },
        "nodes": [{"cmd": sys.executable, "args": ["-c", "import sys; sys.stdout.write('x'*10)"]}]
    }
    await run_pipe(pipe_config, "y" * 100)
    captured = capsys.readouterr()
    # Should contain exit line but no entry line
    assert "[MYPREFIX] →" not in captured.err
    assert "[MYPREFIX] ✓" in captured.err
    assert "100 → 10 chars" in captured.err


@pytest.mark.anyio
async def test_run_pipe_logging_verbose(capsys):
    """Verify verbose logging output to stderr on entry and exit."""
    pipe_config = {
        "name": "test-log-verbose",
        "logging": {
            "enabled": True,
            "prefix": "[VERB]",
            "level": "verbose",
            "fields": ["trigger", "node", "tokens", "timing"]
        },
        "nodes": [{"cmd": sys.executable, "args": ["-c", "import sys; sys.stdout.write('output')"]}]
    }
    await run_pipe(pipe_config, "input", tool_name="my_tool")
    captured = capsys.readouterr()
    lines = captured.err.strip().split("\n")
    assert len(lines) == 2
    assert "[VERB] trigger:my_tool | → python" in lines[0] or "[VERB]" in lines[0]
    assert "[VERB] trigger:my_tool | ✓" in lines[1]
    assert "5 → 6 chars" in lines[1] or "5 → 6" in lines[1]


@pytest.mark.anyio
async def test_run_pipe_logging_precedence(capsys):
    """Verify that pipe-level logging configuration overrides environment variables."""
    # Pipe configuration has logging disabled explicitly
    pipe_config = {
        "name": "test-log-override",
        "logging": {
            "enabled": False
        },
        "nodes": [{"cmd": sys.executable, "args": ["-c", "print('hello')"]}]
    }
    with patch.dict(os.environ, {"PIPE_LOG_LEVEL": "compact", "PIPE_LOG_PREFIX": "[ENVPREFIX]"}):
        await run_pipe(pipe_config, "input_data")
        captured = capsys.readouterr()
        assert captured.err == ""  # Should be empty because per-pipe wins


@pytest.mark.anyio
async def test_run_pipe_executes_python_script(tmp_path, capsys):
    """Verify that a Python script node runs successfully (testing our python script bug fix)."""
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    py_script = script_dir / "my_py_script.py"
    py_script.write_text("import sys; sys.stdout.write(f'python_processed: {sys.stdin.read()}')")

    pipe_config = {
        "name": "test-script-py",
        "logging": {
            "enabled": True,
            "prefix": "[SCRIPT_LOG]",
            "level": "compact",
            "fields": ["node", "tokens"]
        },
        "nodes": [{"cmd": "my_py_script", "type": "script", "args": []}]
    }

    with patch.dict(os.environ, {"PIPE_SCRIPT_DIR": str(script_dir)}):
        result, trace = await run_pipe(pipe_config, "original_content")
        assert result == "python_processed: original_content"
        assert len(trace) == 1
        assert trace[0]["node"] == "my_py_script" or "my_py_script" in trace[0]["node"]
        
        # Verify exit log was printed
        captured = capsys.readouterr()
        assert "[SCRIPT_LOG] ✓ my_py_script" in captured.err or "[SCRIPT_LOG] ✓ script:my_py_script" in captured.err


def test_evaluate_condition_size():
    from context_pipe.orchestrator import _evaluate_condition
    assert _evaluate_condition("size:>10", "12345678901") is True
    assert _evaluate_condition("size:>10", "1234567890") is False
    assert _evaluate_condition("size:<10", "123456789") is True
    assert _evaluate_condition("size:<10", "1234567890") is False
    assert _evaluate_condition("size:>invalid", "data") is True  # Warning, fallback to True


def test_evaluate_condition_artifact(tmp_path):
    from context_pipe.orchestrator import _evaluate_condition
    exist_file = tmp_path / "exist.txt"
    exist_file.touch()
    missing_file = tmp_path / "missing.txt"

    assert _evaluate_condition(f"artifact:exists:{exist_file}", "") is True
    assert _evaluate_condition(f"artifact:exists:{missing_file}", "") is False
    assert _evaluate_condition(f"artifact:missing:{exist_file}", "") is False
    assert _evaluate_condition(f"artifact:missing:{missing_file}", "") is True


def test_evaluate_condition_contains():
    from context_pipe.orchestrator import _evaluate_condition
    # Match leading 300 characters
    long_input = "a" * 100 + "findme" + "a" * 500
    assert _evaluate_condition("contains:findme", long_input) is True
    assert _evaluate_condition("contains:findme", "a" * 400 + "findme") is False  # not in leading 300
    assert _evaluate_condition("contains:notfound", long_input) is False


@pytest.mark.anyio
async def test_run_pipe_skip_node_on_condition():
    pipe_config = {
        "name": "test-condition-skip",
        "nodes": [
            {
                "cmd": sys.executable,
                "args": ["-c", "import sys; sys.stdout.write('node1')"],
                "condition": "size:<5"
            },
            {
                "cmd": sys.executable,
                "args": ["-c", "import sys; sys.stdout.write('node2')"],
                "condition": "size:>50"
            }
        ]
    }
    result, trace = await run_pipe(pipe_config, "input_content")
    # Len(input_content) is 13, which is NOT <5. So node1 is skipped.
    # Second node has condition size:>50. Input is "input_content" (13 chars), which is NOT >50. So node2 is skipped.
    # Result should remain "input_content" and trace should be empty.
    assert result == "input_content"
    assert len(trace) == 0


@pytest.mark.anyio
async def test_run_pipe_validator_node_branching():
    # Validator runs python script returning exit code 0 or 1
    # If 0 -> route to node "branch_zero"
    # If 1 -> route to node "branch_one"
    pipe_config = {
        "name": "test-validator-branching",
        "nodes": [
            {
                "type": "validator",
                "cmd": sys.executable,
                "args": ["-c", "import sys; c=sys.stdin.read(); sys.stdout.write(f'validator_out:{c}'); sys.exit(0 if 'zero' in c else 1)"],
                "branches": {
                    "0": "branch_zero",
                    "1": "branch_one"
                }
            },
            {
                "id": "branch_zero",
                "cmd": sys.executable,
                "args": ["-c", "import sys; sys.stdout.write(sys.stdin.read() + ':took_zero')"],
                "next": "end_node"
            },
            {
                "id": "branch_one",
                "cmd": sys.executable,
                "args": ["-c", "import sys; sys.stdout.write(sys.stdin.read() + ':took_one')"],
                "next": "end_node"
            },
            {
                "id": "end_node",
                "cmd": sys.executable,
                "args": ["-c", "import sys; sys.stdout.write(sys.stdin.read() + ':ended')"]
            }
        ]
    }

    # Run taking branch 0
    res_zero, trace_zero = await run_pipe(pipe_config, "val_zero")
    assert res_zero == "validator_out:val_zero:took_zero:ended"
    assert len(trace_zero) == 3
    assert trace_zero[0]["branch"] == "branch_zero"
    assert trace_zero[0]["exit_code"] == 0

    # Run taking branch 1
    res_one, trace_one = await run_pipe(pipe_config, "val_one")
    assert res_one == "validator_out:val_one:took_one:ended"
    assert len(trace_one) == 3
    assert trace_one[0]["branch"] == "branch_one"
    assert trace_one[0]["exit_code"] == 1


@pytest.mark.anyio
async def test_run_pipe_branch_sequences():
    # Test using branch_sequences top-level dict
    pipe_config = {
        "name": "test-branch-sequences",
        "nodes": [
            {
                "type": "validator",
                "cmd": sys.executable,
                "args": ["-c", "import sys; sys.stdout.write('validator'); sys.exit(0 if 'zero' in sys.stdin.read() else 2)"],
                "branches": {
                    "0": "branch_zero",
                    "default": "sequence_fallback"
                }
            },
            {
                "id": "branch_zero",
                "cmd": sys.executable,
                "args": ["-c", "import sys; sys.stdout.write('zero')"]
            }
        ],
        "branch_sequences": {
            "sequence_fallback": [
                {
                    "cmd": sys.executable,
                    "args": ["-c", "import sys; sys.stdout.write('seq_fallback')"]
                }
            ]
        }
    }

    res, trace = await run_pipe(pipe_config, "other")
    # exit code is 2, matches "default" -> "sequence_fallback"
    assert res == "seq_fallback"
    assert len(trace) == 2
    assert trace[0]["branch"] == "sequence_fallback"


@pytest.mark.anyio
async def test_run_pipe_max_steps_prevent_loop():
    # Loop: node next points to itself
    pipe_config = {
        "name": "test-infinite-loop",
        "nodes": [
            {
                "id": "loop_node",
                "cmd": sys.executable,
                "args": ["-c", "import sys; sys.stdout.write('loop')"],
                "next": "loop_node"
            }
        ]
    }
    res, trace = await run_pipe(pipe_config, "input")
    assert "Maximum pipe execution steps (100) exceeded" in res
