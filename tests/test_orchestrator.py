from context_pipe.orchestrator import resolve_pipe_from_context

def test_resolve_pipe_tool_trigger():
    config = {
        "mappings": [
            {"trigger": "tool:grep", "pipe": "semantic-refinery"},
            {"trigger": "default", "pipe": "standard-distill"}
        ]
    }
    assert resolve_pipe_from_context(config, "grep_search", 100) == "semantic-refinery"
    assert resolve_pipe_from_context(config, "read_file", 100) == "standard-distill"

def test_resolve_pipe_size_trigger():
    config = {
        "mappings": [
            {"trigger": "size:>5000", "pipe": "heavy-pipe"},
            {"trigger": "default", "pipe": "standard-distill"}
        ]
    }
    assert resolve_pipe_from_context(config, "read_file", 6000) == "heavy-pipe"
    assert resolve_pipe_from_context(config, "read_file", 1000) == "standard-distill"
