# MCP Node Type — Design Specification

**Status**: Approved for implementation
**Phase**: 7.5 (extension of the Dynamic Shadow Ecosystem)
**Author**: Studio of Two

---

## 1. Problem Statement

The current `pipes.json` node model supports only subprocess-based executables
(`binary`, `shell`, `script`). Every node must be a program that reads `stdin`
and writes `stdout`.

This excludes a whole class of context-processing tools that are only reachable
via the **MCP protocol** — web scrapers, GitHub, context-mode, database connectors,
proprietary enterprise APIs. Calling these today requires authoring a thin
wrapper script per tool, which is exactly the boilerplate CPP was designed to
eliminate.

The `mcp` node type makes MCP tools **first-class citizens** in a
`pipes.json` pipeline, with the same timeout guard, trace accounting, and tee
support as any binary node.

### Motivating example (the web research pipeline)

```
[stdin: URL]
        │
  firecrawl/scrape       ← MCP node, fetches and cleans live web page
        │
  markitdown             ← binary node, converts to structured Markdown
        │
  context-mode/index     ← MCP node, indexes content for RAG
        │
  semantic-sift-cli      ← binary node, distils indexed context
        │
[stdout: distilled context]
```

Without the `mcp` node type this requires four external wrapper scripts.
With it, the entire flow is declared in `pipes.json` and managed by the
orchestrator.

---

## 2. Schema

### New node fields

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | No | `"mcp"` activates the MCP client path. Omit or set to `"binary"` for the current subprocess path. |
| `server` | `string` | Yes (if `type=mcp`) | Server registry key — matches a key in the `servers` block of `pipes.json` or `~/.mcp-pipe.json`. |
| `tool` | `string` | Yes (if `type=mcp`) | Fully-qualified tool name as registered by the MCP server (e.g., `get_file`, `index`). |
| `input_key` | `string` | No | Argument key used to pass `stdin` content to the tool. Default: `"content"`. |
| `args` | `object` | No | Additional static key/value arguments merged with `input_key`. |

All existing fields (`tee`, `help_msg`) remain valid on `mcp` nodes.

### New top-level block: `servers`

```json
{
  "version": "1.0",
  "servers": {
    "firecrawl": {
      "command": ["python", "-m", "firecrawl_mcp.server"],
      "env": { "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}" }
    },
    "context-mode": {
      "command": ["python", "-m", "context_mode.server"]
    }
  },
  "pipes": [ ... ],
  "mappings": [ ... ]
}
```

| Field | Type | Description |
|---|---|---|
| `command` | `string[]` | argv to spawn the MCP server process (stdio transport). |
| `env` | `object` | Extra environment variables. Values prefixed with `${VAR}` are resolved from the host environment at runtime. |

The `servers` block follows the same local-precedence merge as `pipes` and
`mappings`: entries in the project `pipes.json` override `~/.mcp-pipe.json`.

### Full example: web research pipeline

```json
{
  "version": "1.0",
  "servers": {
    "firecrawl": {
      "command": ["python", "-m", "firecrawl_mcp.server"],
      "env": { "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}" }
    },
    "context-mode": {
      "command": [
        "C:/path/to/venv/Scripts/python.exe",
        "-m", "context_mode.server"
      ]
    }
  },
  "pipes": [
    {
      "name": "web-research-pipe",
      "nodes": [
        {
          "type": "mcp",
          "server": "firecrawl",
          "tool": "scrape",
          "input_key": "url",
          "help_msg": "Firecrawl MCP server not reachable. Check FIRECRAWL_API_KEY and server config."
        },
        {
          "cmd": "markitdown"
        },
        {
          "type": "mcp",
          "server": "context-mode",
          "tool": "index",
          "input_key": "content"
        },
        {
          "cmd": "semantic-sift-cli",
          "args": ["semantic", "--rate", "0.4"]
        }
      ]
    }
  ],
  "mappings": [
    { "trigger": "tool:web_fetch|tool:web_search", "pipe": "web-research-pipe" }
  ]
}
```

---

## 3. Runtime Architecture

### 3.1 Execution path in `orchestrator.py`

`run_pipe()` gains a single branch at the top of the node loop:

```python
for node in pipe_config.get("nodes", []):
    if node.get("type") == "mcp":
        stdout = await _run_mcp_node(node, current_input, server_registry, process_env)
    else:
        # existing subprocess.Popen path — unchanged
        ...
```

Because `mcp.client.stdio` uses `anyio` internally, `_run_mcp_node` is an
`async` function. `run_pipe()` will be promoted to `async` and callers updated
accordingly (see §3.4).

### 3.2 `_run_mcp_node()` — MCP client call

```python
async def _run_mcp_node(
    node: dict,
    stdin_data: str,
    server_registry: dict,
    env: dict,
) -> str:
    server_key = node["server"]
    tool_name  = node["tool"]
    input_key  = node.get("input_key", "content")
    static_args = {k: v for k, v in node.get("args", {}).items()}

    server_cfg = server_registry.get(server_key)
    if not server_cfg:
        raise ValueError(f"MCP server '{server_key}' not found in servers registry.")

    # Resolve ${VAR} env placeholders
    resolved_env = _resolve_env_placeholders(server_cfg.get("env", {}))
    child_env = {**env, **resolved_env}

    cmd = server_cfg["command"]
    server_params = StdioServerParameters(command=cmd[0], args=cmd[1:], env=child_env)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            arguments = {input_key: stdin_data, **static_args}
            result = await session.call_tool(tool_name, arguments)

    # Extract text from the CallToolResult content list
    return _extract_text(result)
```

`_extract_text()` iterates `result.content`, concatenates all `TextContent`
items, and falls back to `str(result)` if none are found.

### 3.3 Server registry resolution

`config_loader.load_pipes_config()` is extended to merge the `servers` block
from both `pipes.json` and `~/.mcp-pipe.json` (local precedence), and return
it alongside the existing `pipes` and `mappings`.

`run_pipe()` receives the merged `server_registry` dict as a new parameter
(default `{}`), keeping the function signature backward-compatible for all
existing callers.

### 3.4 Async promotion strategy

`run_pipe()` becomes `async`. Call-site impact:

| Caller | Change |
|---|---|
| `orchestrator.py main()` | `asyncio.run(run_pipe(...))` |
| `api.pipe()` | `asyncio.run(run_pipe(...))` |
| `dynamic.run_dynamic_pipe()` | becomes `async` |
| `server.py` MCP tools | already in async context — `await run_pipe(...)` |
| `cli.py` subcommands | `asyncio.run(...)` wrapper |
| All existing tests | wrap calls in `asyncio.run()` or use `pytest-anyio` |

Pipes with **no `mcp` nodes** execute identically to today — the `asyncio.run`
overhead for a pure-subprocess pipe is negligible (<1ms).

---

## 4. Echo Guard — Node-Scope Fix

### Current behaviour (pipe-scope)

The Echo Guard hash is computed on the full pipe input and stored with a 30s
TTL. If the same content passes through any pipe twice within 30s, the second
pass is suppressed.

### Problem with multi-sift pipes

A pipe like:

```
[context-mode/index] → [semantic-sift-cli] → [context-mode/search] → [semantic-sift-cli]
```

Would have the second `semantic-sift-cli` node suppress itself because the
hash of its input (the output of `context-mode/search`) happens to collide with
a prior hash — or because the guard is keyed on the original pipe input, not
per-node input.

### Fix: node-scoped hash key

Change the hash key from:

```python
hash_key = sha256(input_data.encode()).hexdigest()
```

to:

```python
hash_key = sha256(f"{pipe_name}:{node_index}:{input_data}".encode()).hexdigest()
```

This scopes each guard entry to a specific `(pipe, node_position, content)`
tuple, making it impossible for two different nodes in the same pipe to collide,
while still preventing genuine double-sift loops across separate pipe
invocations.

---

## 5. Validation Rules (`dynamic.py`)

`_validate_nodes()` is extended with two rules for `mcp` nodes:

1. `type == "mcp"` nodes **must** have both `server` and `tool` keys.
2. `type == "mcp"` nodes are **exempt** from the shell-metacharacter check
   (they have no `cmd` to validate).
3. `type == "mcp"` nodes **do not count** as shell utility nodes for the
   sift-terminal guard — only `binary`/`shell` nodes with allowlisted commands
   trigger that constraint.

---

## 6. Implementation Plan

### Phase 7.5-A — Schema & Config (no behaviour change)
- [ ] Add `servers` block parsing to `config_loader.load_pipes_config()`.
- [ ] Add `_resolve_env_placeholders()` utility.
- [ ] Update `pipes.json.example` with a commented-out `servers` block.
- [ ] Add 6 unit tests: merge precedence, env placeholder resolution, missing
      server key error.

### Phase 7.5-B — `_run_mcp_node()` + async promotion
- [ ] Implement `_run_mcp_node()` in `orchestrator.py`.
- [ ] Promote `run_pipe()` to `async`; update all call sites.
- [ ] Update `dynamic.run_dynamic_pipe()` to `async`.
- [ ] Update `api.pipe()` with `asyncio.run()`.
- [ ] Update `cli.py` subcommands with `asyncio.run()`.
- [ ] Update `server.py` MCP tools with `await`.
- [ ] Add `pytest-anyio` to `[test]` extras; mark async tests.
- [ ] Add 8 integration tests using a mock MCP server (in-process `FastMCP`
      instance) to validate: tool call, `input_key` routing, static args merge,
      env placeholder injection, timeout, server-not-found error, text
      extraction fallback, tee on mcp node.

### Phase 7.5-C — Echo Guard node-scope fix
- [ ] Change hash key in `wrapper.py` to `pipe_name:node_index:content`.
- [ ] Add 3 regression tests: same content two nodes same pipe, genuine
      double-sift cross-pipe, node index boundary.

### Phase 7.5-D — `_validate_nodes()` extension
- [ ] Extend `_validate_nodes()` with `mcp` node rules.
- [ ] Add 4 unit tests: missing `server`, missing `tool`, metachar exempt,
      sift-terminal guard exempt.

### Phase 7.5-E — Docs & Release
- [ ] Update `doc/ARCHITECTURE.md` §9 with `mcp` node execution path.
- [ ] Update `doc/OPERATOR_GUIDE.md` §3 Node Types with new `mcp` entry.
- [ ] Update `README.md` Advanced Node Types section.
- [ ] Add `## [Unreleased] — Phase 7.5` block to `doc/CHANGELOG.md`.
- [ ] Raise `fail_under` after coverage is measured.

---

## 7. Out of Scope

- **HTTP/SSE transport**: only `stdio` MCP servers are supported in this phase.
  HTTP transport requires a different connection model and session lifecycle.
  Tracked as a future item.
- **Server pooling / keep-alive**: each `mcp` node spawns and tears down its
  own server process. Connection reuse across pipe runs is a Phase 8 concern.
- **Auth beyond env vars**: OAuth flows, keychain integration, etc. are out of
  scope. `${VAR}` env placeholder resolution covers the common case.

---

*Building Systems, not Patches — Studio of Two.*
