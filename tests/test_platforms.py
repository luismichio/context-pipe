# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
"""Tests for context_pipe.platforms — client detection and payload extraction."""

from unittest.mock import patch, MagicMock

from context_pipe.platforms import detect_client_id, extract_content, inject_content


# ---------------------------------------------------------------------------
# detect_client_id
# ---------------------------------------------------------------------------


_ALL_KNOWN_VARS = [
    "ANTIGRAVITY_AGENT", "OPENCODE", "OPENCODE_PID", "CURSOR_TRACE_ID",
    "VSCODE_PID", "WINDSURF_TOOL_ARGS", "__KIRO_MCP", "CONTINUE_SERVER_PORT",
    "JETBRAINS_IDE_URL", "CLINE_TASK_ID", "CLAUDE_TOOL_NAME", "GEMINI_SESSION_ID",
]


def _clear_known_vars(monkeypatch):
    for var in _ALL_KNOWN_VARS:
        monkeypatch.delenv(var, raising=False)


def test_detect_client_id_from_env_opencode(monkeypatch):
    _clear_known_vars(monkeypatch)
    monkeypatch.setenv("OPENCODE", "1")
    assert detect_client_id() == "OpenCode"


def test_detect_client_id_from_env_cursor(monkeypatch):
    _clear_known_vars(monkeypatch)
    monkeypatch.setenv("CURSOR_TRACE_ID", "abc123")
    assert detect_client_id() == "Cursor"


def test_detect_client_id_from_env_windsurf(monkeypatch):
    _clear_known_vars(monkeypatch)
    monkeypatch.setenv("WINDSURF_TOOL_ARGS", "some_args")
    assert detect_client_id() == "Windsurf"


def test_detect_client_id_from_env_vscode(monkeypatch):
    _clear_known_vars(monkeypatch)
    monkeypatch.setenv("VSCODE_PID", "1234")
    assert detect_client_id() == "VSCode"


def test_detect_client_id_from_env_gemini(monkeypatch):
    _clear_known_vars(monkeypatch)
    monkeypatch.setenv("GEMINI_SESSION_ID", "sess-abc")
    assert detect_client_id() == "Gemini CLI"


def test_detect_client_id_generic_fallback(monkeypatch):
    _clear_known_vars(monkeypatch)


    mock_proc = MagicMock()
    mock_proc.name.return_value = "python"
    mock_proc.parents.return_value = []

    with patch("psutil.Process", return_value=mock_proc):
        result = detect_client_id()
    assert result == "Generic CLI"


# ---------------------------------------------------------------------------
# extract_content
# ---------------------------------------------------------------------------


def test_extract_content_from_tool_response():
    data = {"tool_name": "bash", "tool_response": {"llmContent": "output text"}}
    content, tool, agent = extract_content(data, "Generic CLI")
    assert content == "output text"
    assert tool == "bash"
    assert agent is None


def test_extract_content_from_result():
    data = {"tool": "grep", "result": "grep output"}
    content, tool, agent = extract_content(data, "Generic CLI")
    assert content == "grep output"
    assert tool == "grep"


def test_extract_content_cursor_explore_agent():
    data = {"tool_name": "t", "result": "[Explore] some content"}
    content, tool, agent = extract_content(data, "Cursor")
    assert agent == "Explore"


def test_extract_content_cursor_bash_agent():
    data = {"tool_name": "t", "result": "[Bash] some output"}
    content, tool, agent = extract_content(data, "Cursor")
    assert agent == "Bash"


def test_extract_content_gemini_thread_label():
    data = {"tool_name": "t", "result": "text", "hookSpecificOutput": {"threadLabel": "thread-1"}}
    content, tool, agent = extract_content(data, "Gemini CLI")
    assert agent == "thread-1"


def test_extract_content_llm_content_key():
    data = {"tool_name": "t", "llmContent": "direct llmContent"}
    content, tool, agent = extract_content(data, "Generic CLI")
    assert content == "direct llmContent"


def test_extract_content_stringified_envelope():
    # Gemini CLI pattern: tool_response is a stringified JSON
    import json
    inner = {"output": "markdown content"}
    data = {"tool_name": "read_file", "tool_response": json.dumps(inner)}
    content, name, label = extract_content(data, "Gemini CLI")
    assert content == "markdown content"

def test_extract_content_mcp_array():
    # Standard MCP pattern
    data = {
        "tool": "scrape",
        "tool_response": {
            "content": [
                {"type": "text", "text": "part 1"},
                {"type": "text", "text": "part 2"}
            ]
        }
    }
    content, name, label = extract_content(data, "Generic CLI")
    assert content == "part 1\npart 2"
    assert name == "scrape"

def test_extract_content_unknown_tool_defaults():
    data = {}
    content, tool, agent = extract_content(data, "Generic CLI")
    assert tool == "unknown"
    assert content == ""


# ---------------------------------------------------------------------------
# inject_content
# ---------------------------------------------------------------------------


def test_inject_content_tool_response_shape():
    data = {"tool_response": {"llmContent": "old"}}
    result = inject_content(data, "new content", "Generic CLI")
    assert result["tool_response"]["llmContent"] == "new content"


def test_inject_content_result_shape():
    data = {"result": "old"}
    result = inject_content(data, "new", "Cursor")
    assert result["result"] == "new"


def test_inject_content_llm_content_shape():
    data = {"llmContent": "old"}
    result = inject_content(data, "updated", "Generic CLI")
    assert result["llmContent"] == "updated"


def test_inject_content_fallback_shape():
    data = {"other_key": "value"}
    result = inject_content(data, "processed", "Generic CLI")
    assert result["processed_content"] == "processed"
