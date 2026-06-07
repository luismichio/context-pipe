import time
import pytest
from unittest.mock import patch
from context_pipe import telemetry as tel

@pytest.fixture(autouse=True)
def isolated_telemetry(tmp_path, monkeypatch):
    """Redirect telemetry writes to a temp file for every test.

    Patches ``_resolve_telemetry_path`` (the lazy resolver) so that
    ``resolve_telemetry_file()`` routes to the temp location.
    """
    temp_file = str(tmp_path / "test_telemetry.jsonl")
    monkeypatch.setattr(tel, "_resolve_telemetry_path", lambda: temp_file)
    monkeypatch.setattr(tel, "PIPE_TELEMETRY_DISABLED", False)
    # Mask semantic_sift to isolate local JSONL checks
    with patch.dict("sys.modules", {"semantic_sift.telemetry": None}):
        yield temp_file

def test_get_recent_telemetry(isolated_telemetry):
    # Log three distinct events
    tel.log_telemetry("session_A", "Sun May 31 10:00:00 2026", "tool1", 100, 50, 10.0)
    tel.log_telemetry("session_B", "Sun May 31 10:05:00 2026", "tool2", 200, 100, 20.0)
    tel.log_telemetry("session_C", "Sun May 31 10:10:00 2026", "tool3", 300, 150, 30.0)

    # Get last 2 events (should be newest first)
    recent = tel.get_recent_telemetry(limit=2)
    assert len(recent) == 2
    assert recent[0]["session_id"] == "session_C"
    assert recent[0]["tool_key"] == "unknown:tool3"
    assert recent[1]["session_id"] == "session_B"
    assert recent[1]["tool_key"] == "unknown:tool2"

def test_get_balance_sheet_session_filter(isolated_telemetry):
    # Log different sessions
    tel.log_telemetry("session_A", "Sun May 31 10:00:00 2026", "tool1", 100, 50, 10.0)
    tel.log_telemetry("session_B", "Sun May 31 10:05:00 2026", "tool2", 200, 80, 20.0)

    # Filter to session_A
    sheet_a = tel.get_balance_sheet(session_id="session_A")
    assert sheet_a["total_events"] == 1
    assert sheet_a["noise_removed"] == 50  # 100 - 50

    # Filter to session_B
    sheet_b = tel.get_balance_sheet(session_id="session_B")
    assert sheet_b["total_events"] == 1
    assert sheet_b["noise_removed"] == 120  # 200 - 80

def test_get_balance_sheet_time_filter(isolated_telemetry):
    # Log one event 5 hours ago, and one event right now
    now_struct = time.localtime(time.time())
    now_str = time.asctime(now_struct)
    
    five_hours_ago_struct = time.localtime(time.time() - 5 * 3600)
    five_hours_ago_str = time.asctime(five_hours_ago_struct)

    tel.log_telemetry("session_old", five_hours_ago_str, "tool_old", 100, 50, 10.0)
    tel.log_telemetry("session_new", now_str, "tool_new", 200, 80, 20.0)

    # Filter to last 2 hours
    sheet_recent = tel.get_balance_sheet(last_hours=2.0)
    assert sheet_recent["total_events"] == 1
    assert sheet_recent["noise_removed"] == 120  # 200 - 80 (new event only)

    # Filter to last 6 hours
    sheet_all = tel.get_balance_sheet(last_hours=6.0)
    assert sheet_all["total_events"] == 2
    assert sheet_all["noise_removed"] == 170  # (100-50) + (200-80)

def test_list_shadow_tools_with_mcp(tmp_path):
    import json
    from context_pipe.shadow import list_shadow_tools
    
    # Create a dummy config with both an MCP node and a registered server
    config = {
        "version": "1.0",
        "pipes": [
            {
                "name": "mcp-test-pipe",
                "description": "Test pipe with MCP node",
                "nodes": [
                    {
                        "server": "dummy-mcp",
                        "tool": "dummy-tool"
                    }
                ]
            }
        ],
        "servers": {
            "dummy-mcp": {
                "command": ["python"],
                "description": "Dummy MCP Server"
            },
            "_example_skipped": {
                "command": ["python"]
            }
        }
    }
    
    cfg_file = str(tmp_path / "pipes.json")
    with open(cfg_file, "w", encoding="utf-8") as fh:
        json.dump(config, fh)
        
    tools = list_shadow_tools(config_path=cfg_file)
    
    # Verify mcp-test-pipe has formatted node
    pipe_tool = next(t for t in tools if t["name"] == "mcp-test-pipe")
    assert pipe_tool["nodes"] == ["mcp:dummy-mcp/dummy-tool"]
    assert pipe_tool["source"] == "pipes.json"

    # Verify dummy-mcp server is discovered
    server_tool = next(t for t in tools if t["name"] == "dummy-mcp")
    assert server_tool["description"] == "Dummy MCP Server"
    assert server_tool["source"] == "pipes.json"
    
    # Verify skipped starting with "_"
    assert not any(t["name"] == "_example_skipped" for t in tools)
