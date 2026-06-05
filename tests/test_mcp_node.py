# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock
from context_pipe.orchestrator import run_pipe

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _make_mock_session(result_text="mcp output"):
    from mcp.types import CallToolResult, TextContent
    mock_result = CallToolResult(content=[TextContent(type="text", text=result_text)])
    
    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    return mock_session

@pytest.mark.anyio
async def test_mcp_node_basic_call():
    """Basic MCP node call: stdin routed to tool, result returned as text."""
    mock_session = _make_mock_session("mcp output")
    
    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        with patch("context_pipe.orchestrator.ClientSession", return_value=mock_session):
            pipe_config = {
                "nodes": [
                    {
                        "type": "mcp",
                        "server": "test-server",
                        "tool": "test-tool",
                    }
                ]
            }
            server_registry = {
                "test-server": {
                    "command": ["python", "-m", "mock_server"]
                }
            }
            
            result, trace = await run_pipe(
                pipe_config, 
                "input text", 
                server_registry=server_registry
            )
            
            assert result == "mcp output"
            assert trace[0]["node"] == "mcp:test-server/test-tool"
            mock_session.call_tool.assert_called_once_with(
                "test-tool", {"content": "input text"}
            )

@pytest.mark.anyio
async def test_mcp_node_input_key_override():
    """MCP node uses custom input_key instead of 'content'."""
    mock_session = _make_mock_session()
    
    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        with patch("context_pipe.orchestrator.ClientSession", return_value=mock_session):
            pipe_config = {
                "nodes": [
                    {
                        "type": "mcp",
                        "server": "test-server",
                        "tool": "scrape",
                        "input_key": "url"
                    }
                ]
            }
            server_registry = {"test-server": {"command": ["mock"]}}
            
            await run_pipe(pipe_config, "https://example.com", server_registry=server_registry)
            
            mock_session.call_tool.assert_called_once_with(
                "scrape", {"url": "https://example.com"}
            )

@pytest.mark.anyio
async def test_mcp_node_static_args_merged():
    """Static args from node['args'] are merged with stdin input."""
    mock_session = _make_mock_session()
    
    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        with patch("context_pipe.orchestrator.ClientSession", return_value=mock_session):
            pipe_config = {
                "nodes": [
                    {
                        "type": "mcp",
                        "server": "test-server",
                        "tool": "test-tool",
                        "args": {"extra": "value", "count": 1}
                    }
                ]
            }
            server_registry = {"test-server": {"command": ["mock"]}}
            
            await run_pipe(pipe_config, "main data", server_registry=server_registry)
            
            mock_session.call_tool.assert_called_once_with(
                "test-tool", {"content": "main data", "extra": "value", "count": 1}
            )

@pytest.mark.anyio
async def test_mcp_node_env_placeholder_injected():
    """${VAR} in server env is resolved at call time."""
    mock_session = _make_mock_session()
    
    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        with patch("context_pipe.orchestrator.ClientSession", return_value=mock_session):
            with patch.dict(os.environ, {"SECRET_KEY": "top-secret"}):
                pipe_config = {"nodes": [{"type": "mcp", "server": "secure", "tool": "auth"}]}
                server_registry = {
                    "secure": {
                        "command": ["mock"],
                        "env": {"API_KEY": "${SECRET_KEY}", "DEBUG": "1"}
                    }
                }
                
                await run_pipe(pipe_config, "data", server_registry=server_registry)
                
                # Check that stdio_client was called with resolved env
                args, kwargs = mock_stdio.call_args
                params = args[0]
                assert params.env["API_KEY"] == "top-secret"
                assert params.env["DEBUG"] == "1"

@pytest.mark.anyio
async def test_mcp_node_timeout_returns_error():
    """PIPE_NODE_TIMEOUT_MS triggers TimeoutError path."""
    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        with patch("context_pipe.orchestrator.ClientSession") as mock_session_cls:
            mock_session = mock_session_cls.return_value.__aenter__.return_value
            mock_session.initialize = AsyncMock()
            # Simulate timeout
            mock_session.call_tool = AsyncMock(side_effect=asyncio.TimeoutError())
            
            pipe_config = {"nodes": [{"type": "mcp", "server": "slow", "tool": "wait"}]}
            server_registry = {"slow": {"command": ["mock"]}}
            
            result, trace = await run_pipe(pipe_config, "input", server_registry=server_registry)
            
            assert "Timeout" in result
            assert trace[0]["error"] == "Timeout"

@pytest.mark.anyio
async def test_mcp_node_timeout_override():
    """Node-level timeout override is used in wait_for."""
    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        with patch("context_pipe.orchestrator.ClientSession") as mock_session_cls:
            mock_session = mock_session_cls.return_value.__aenter__.return_value
            mock_session.initialize = AsyncMock()
            
            pipe_config = {
                "nodes": [
                    {"type": "mcp", "server": "slow", "tool": "wait", "timeout": 2.5}
                ]
            }
            server_registry = {"slow": {"command": ["mock"]}}
            
            with patch("asyncio.wait_for") as mock_wait_for:
                mock_wait_for.side_effect = asyncio.TimeoutError()
                result, trace = await run_pipe(pipe_config, "input", server_registry=server_registry)
                
                # Verify wait_for was called with timeout=2.5 instead of default 30.0
                mock_wait_for.assert_called_once()
                assert mock_wait_for.call_args[1]["timeout"] == 2.5

@pytest.mark.anyio
async def test_mcp_node_server_not_found_error():
    """Missing server key returns error trace entry."""
    pipe_config = {"nodes": [{"type": "mcp", "server": "missing", "tool": "tool"}]}
    server_registry = {} # empty
    
    result, trace = await run_pipe(pipe_config, "input", server_registry=server_registry)
    
    assert "MCP Error" in result
    assert "not found in servers registry" in trace[0]["error"]

@pytest.mark.anyio
async def test_mcp_node_text_extraction_fallback():
    """non-TextContent result falls back to str(result)."""
    from mcp.types import CallToolResult
    # Result with no content at all or unknown content type
    mock_result = CallToolResult(content=[])
    
    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        with patch("context_pipe.orchestrator.ClientSession", return_value=mock_session):
            pipe_config = {"nodes": [{"type": "mcp", "server": "test", "tool": "tool"}]}
            server_registry = {"test": {"command": ["mock"]}}
            
            result, trace = await run_pipe(pipe_config, "input", server_registry=server_registry)
            
            assert result == str(mock_result)

@pytest.mark.anyio
async def test_mcp_node_tee_on_mcp_node(tmp_path):
    """tee config on mcp node writes input to file."""
    sink = str(tmp_path / "mcp_raw.log")
    mock_session = _make_mock_session()
    
    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        with patch("context_pipe.orchestrator.ClientSession", return_value=mock_session):
            pipe_config = {
                "nodes": [
                    {
                        "type": "mcp",
                        "server": "test",
                        "tool": "tool",
                        "tee": {"sink": "file", "path": sink}
                    }
                ]
            }
            server_registry = {"test": {"command": ["mock"]}}
            
            await run_pipe(pipe_config, "raw data for tee", server_registry=server_registry)
            
            assert os.path.exists(sink)
            content = open(sink).read()
            assert "raw data for tee" in content


@pytest.mark.anyio
async def test_mcp_node_http_sse_call():
    """MCP node with type 'sse' connects via sse_client."""
    mock_session = _make_mock_session("supabase result")
    
    # Mock sse_client
    mock_sse = MagicMock()
    mock_sse.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    mock_sse.__aexit__ = AsyncMock()
    
    with patch("mcp.client.sse.sse_client", return_value=mock_sse) as mock_sse_func, \
         patch("context_pipe.orchestrator.ClientSession", return_value=mock_session):
         
        pipe_config = {
            "nodes": [
                {
                    "type": "mcp",
                    "server": "supabase-mcp",
                    "tool": "query_db",
                }
            ]
        }
        server_registry = {
            "supabase-mcp": {
                "type": "sse",
                "url": "https://mcp.supabase.com/mcp?project_ref=${PROJECT_REF}",
                "headers": {
                    "Authorization": "Bearer ${AUTH_TOKEN}"
                }
            }
        }
        
        # Inject env vars
        os.environ["PROJECT_REF"] = "abc123"
        os.environ["AUTH_TOKEN"] = "token123"
        
        result, trace = await run_pipe(
            pipe_config,
            "SELECT * FROM users",
            server_registry=server_registry
        )
        
        assert result == "supabase result"
        mock_sse_func.assert_called_once_with(
            "https://mcp.supabase.com/mcp?project_ref=abc123",
            headers={"Authorization": "Bearer token123"}
        )


@pytest.mark.anyio
async def test_run_pipe_loads_registry_automatically():
    """Verify that run_pipe dynamically loads the server registry if it is None."""
    mock_session = _make_mock_session("auto loaded registry output")
    pipe_config = {
        "nodes": [
            {
                "type": "mcp",
                "server": "test-auto-server",
                "tool": "test-tool",
            }
        ]
    }
    
    mock_config = {
        "servers": {
            "test-auto-server": {
                "command": ["mock-cmd"]
            }
        }
    }
    
    with patch("context_pipe.orchestrator.stdio_client") as mock_stdio, \
         patch("context_pipe.orchestrator.ClientSession", return_value=mock_session), \
         patch("context_pipe.config_loader.load_pipes_config", return_value=mock_config):
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        
        result, trace = await run_pipe(
            pipe_config,
            "input text",
            server_registry=None
        )
        assert result == "auto loaded registry output"


@pytest.mark.anyio
async def test_mcp_node_streamable_http_call():
    """Verify that type: http executes via streamable_http_client."""
    mock_session = _make_mock_session("streamable http output")
    mock_streamable = MagicMock()
    mock_streamable.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    mock_streamable.__aexit__ = AsyncMock()

    pipe_config = {
        "nodes": [
            {
                "type": "mcp",
                "server": "supabase-http",
                "tool": "query_db",
            }
        ]
    }
    server_registry = {
        "supabase-http": {
            "type": "http",
            "url": "https://mcp.supabase.com/mcp?project_ref=ref123",
            "headers": {
                "Authorization": "Bearer tok123"
            }
        }
    }

    with patch("mcp.client.streamable_http.streamable_http_client", return_value=mock_streamable) as mock_client_func, \
         patch("context_pipe.orchestrator.ClientSession", return_value=mock_session), \
         patch("httpx.AsyncClient"):
        
        result, trace = await run_pipe(
            pipe_config,
            "query data",
            server_registry=server_registry
        )
        assert result == "streamable http output"
        mock_client_func.assert_called_once()
        # Ensure it passed the configured url
        assert mock_client_func.call_args[0][0] == "https://mcp.supabase.com/mcp?project_ref=ref123"
