import pytest
import anyio
from mcp.client.session import SessionMessage
from mcp.types import JSONRPCRequest
from context_pipe.orchestrator import _StdoutToleranceWrapper

@pytest.fixture
def anyio_backend():
    return 'asyncio'

class DummyStream:
    def __init__(self, chunks):
        self.chunks = chunks
        self.idx = 0
    async def receive(self):
        if self.idx >= len(self.chunks):
            raise anyio.EndOfStream()
        chunk = self.chunks[self.idx]
        self.idx += 1
        return chunk
    async def aclose(self):
        pass

@pytest.mark.anyio
async def test_tolerance_wrapper_skips_exceptions():
    valid_msg = SessionMessage(JSONRPCRequest(jsonrpc="2.0", id=1, method="test", params={}))
    stream = DummyStream([
        Exception("Banner line 1"),
        Exception("Banner line 2"),
        valid_msg
    ])
    
    wrapper = _StdoutToleranceWrapper(stream, verbose=False)
    
    # Should skip the two exceptions and return the valid message
    res = await wrapper.receive()
    assert res is valid_msg
    assert wrapper.skipped_count == 2

@pytest.mark.anyio
async def test_tolerance_wrapper_fails_after_max_skip():
    chunks = [Exception(f"Line {i}") for i in range(55)]
    stream = DummyStream(chunks)
    
    wrapper = _StdoutToleranceWrapper(stream, verbose=False)
    wrapper.max_skip = 50
    
    res = await wrapper.receive()
    # After max_skip, it should yield the exception
    assert isinstance(res, Exception)
    assert wrapper.skipped_count == 51

@pytest.mark.anyio
async def test_tolerance_wrapper_verbose(capsys):
    valid_msg = SessionMessage(JSONRPCRequest(jsonrpc="2.0", id=1, method="test", params={}))
    stream = DummyStream([
        Exception("Hello MCP"),
        valid_msg
    ])
    
    wrapper = _StdoutToleranceWrapper(stream, verbose=True)
    res = await wrapper.receive()
    assert res is valid_msg
    
    captured = capsys.readouterr()
    assert "[cpipe] MCP server stdout (non-JSON):" in captured.err

