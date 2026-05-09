# 📋 Context-Pipe Backlog

## 🔴 Phase 1: High-Fidelity Foundation (Complete)
- [x] Repository scaffolding (`AGENTS.md`, `README`, `LICENSE`).
- [x] Initial Context-Pipe Protocol (CPP) specification.
- [x] **Python Orchestrator Boilerplate**: Initialize the core `context-pipe` package.
- [x] **Pipes Logic**: Implementation of the `pipes.json` parser and execution engine.
- [x] **MCP Server**: Formal tool and prompt interface.
- [x] **Universal Hook**: Subconscious interceptor.
- [x] **Telemetry Engine**: Context Balance Sheet (ROI tracking).

## 🟡 Phase 2: Interoperability (Complete)
- [x] **CPP Polyfill Wrapper**: Standalone utility (`context-pipe wrap`) for JSON-RPC tools.
- [x] **Dynamic Environment Detection**: Multi-platform support (Zed, Continue, Windsurf, Cursor).
- [x] **Agnostic Routing**: Dynamic pipe resolution based on tool and size triggers.
- [x] **Standard Shell Aliases**: `inject_shell_aliases()` / `remove_shell_aliases()` in `onboarding.py`. `mcp-pipe aliases install/remove` CLI subcommands + `pipe_install_aliases` / `pipe_remove_aliases` MCP tools. Idempotent marker-block pattern; platform-aware (POSIX/PowerShell). 20 tests. `fail_under` raised 68 → 69. (unreleased).

## 🟢 Phase 3: The Template Ecosystem (In Progress)
- [x] **Pure Switchboard Refactor**: Removed internal nodes to achieve 100% agnostic status.
- [x] **Pipe Templates**: Professional recipes for `sift-core` and `markitdown`.
- [ ] **Adaptive Thresholding** *(delegated to `semantic-sift`)*: Dynamically adjust `--rate` based on estimated remaining context window headroom. The triggering signal (payload size, tool name) originates in `context-pipe` routing, but the rate adjustment logic belongs in `semantic-sift`'s kernel. Implementation path: `context-pipe` passes a `PIPE_WINDOW_PRESSURE` env var (0.0–1.0) to each node; `semantic-sift-cli` reads it and overrides `--rate` if set. Tracked in `semantic-sift` backlog; listed here as a cross-project dependency.

## ⚪ Phase 4: Distribution (Partially Complete)
- [x] **PyPI Publishing**: `pip install mcp-context-pipe` — live at [pypi.org/project/mcp-context-pipe](https://pypi.org/project/mcp-context-pipe/) (v0.1.5). Next publish: v0.2.0 (Phase 7.3 of `REFACTOR_PLAN_EXT2.md`).
- [x] **`semantic-sift` PyPI Publishing**: `pip install semantic-sift` — live at [pypi.org/project/semantic-sift](https://pypi.org/project/semantic-sift/) (v0.2.7). Next publish: v0.3.0 (Phase 7.3 of `REFACTOR_PLAN_EXT2.md`).
- [x] **Slash Command Injection**: Inject `/pipe-stats` and `/pipe-run` as first-class slash commands into agentic IDE CLIs (Gemini CLI `.gemini/commands/`, OpenCode `opencode.json` commands block, Cursor `onInit` hooks). *(Distinct from Phase 2 Standard Shell Aliases, which targets POSIX/PowerShell profiles, not IDE runtimes. The Gemini CLI injection is already implemented in `inject_hooks()`; OpenCode and Cursor complete as of (unreleased).)*

## 🔵 Phase 4.5: OpenCode Native Plugin (Blocked — Upstream)
- [ ] **MCP tool output interception via `tool.execute.after`**: Re-implement the plugin handler in `.opencode/plugins/context-pipe.ts` once OpenCode assembles MCP tool output **before** triggering the hook. Currently, the hook fires with the raw `CallToolResult {content:[]}` shape instead of the declared `{title, output, metadata}` shape, making `output.output` mutation a no-op for all MCP tools (including `pipe_read_file`). Native tools (bash, read, etc.) already receive the correct shape and mutations work — only MCP tools are affected.
  - **Blocked by**: [sst/opencode#21149](https://github.com/sst/opencode/issues/21149) — MCP tool text assembly must happen before the hook fires.
  - **Our upstream report**: [sst/opencode#25918](https://github.com/sst/opencode/issues/25918) — detailed analysis of both paths.
  - **When fixed**: uncomment the handler in `.opencode/plugins/context-pipe.ts` and `onboarding.py` template. The interception logic (pipe through `orchestrator wrap`, write back to `output.output`) is already written and tested — it just needs the hook to receive the right shape.
  - **Interim**: `pipe_read_file` MCP tool remains the explicit interception point per `AGENTS.md` SOP.

## 🟣 Phase 5: Productionisation & Quality (In Progress)
- [x] **Programmatic Python API** (`context_pipe/api.py`): `pipe(text, pipe_name, tool_name)` — direct integration without MCP or CLI.
- [x] **Test Coverage Uplift**: Coverage raised from ~3% → 63%; `fail_under = 60` enforced in CI.
- [x] **CPP Integration Contract Tests**: Mock-subprocess suite validating `run_pipe()` stdin/stdout/error/timeout contract without requiring `semantic-sift-cli` installed.
- [x] **Root-Module Inversion** (`semantic-sift`): Canonical implementations moved to `semantic_sift/`; root files are DeprecationWarning stubs pending v0.3.0 deletion.
- [x] **Telemetry Fallback URL** (`semantic-sift`): `SIFT_TELEMETRY_FALLBACK_URL` env var; silent retry on primary endpoint failure.
- [ ] **Telemetry Consent UX**: Surface opt-in disclosure in `sift_onboard` response (Phase 7.2 of `REFACTOR_PLAN_EXT2.md`).
- [ ] **v0.3.0 / v0.2.0 Release**: Stub deletion (`semantic-sift`) + version bumps + PyPI publish (Phase 7.3 of `REFACTOR_PLAN_EXT2.md`).

## 🟠 Phase 6: A2A (Agent-to-Agent) Orchestration (Complete)
- [x] **Multi-Agent Interception**: `context_pipe/a2a.py` — `pipe_agent_handoff()` + MCP tool. Framework-agnostic bridge for CrewAI, Google ADK, LangGraph.
- [x] **Stream Splitting (T-Pipes)**: `_write_tee()` in `orchestrator.py`; `tee` node schema in `pipes.json`; `{iso_date}`/`{tool_name}` tokens; `tee_path` in trace.

## 🟤 Phase 7: Dynamic Shadow Ecosystem (RAG for Tools) (In Progress)
- [x] **Dynamic Pipe Execution**: `context_pipe/dynamic.py` — `run_dynamic_pipe()` + `pipe_run_dynamic` MCP tool. Security boundary enforced (shell metacharacters rejected). (unreleased).
- [x] **The `mcp-pipe` CLI**: `context_pipe/cli.py` — `mcp-pipe` terminal runner with `run`, `run-dynamic`, `list`, `stats`, `serve` subcommands. 21 tests. `fail_under` raised 65 → 68. (unreleased).
- [x] **Shadow Tool Discovery**: `context_pipe/shadow.py` — `list_shadow_tools()` + `pipe_list_shadow_tools` MCP tool. Probes 7 curated CLI tools on PATH. (unreleased).
- [x] **Standalone Configuration**: `context_pipe/config_loader.py` — `load_pipes_config()` merges `pipes.json` + `~/.mcp-pipe.json` with local precedence. (unreleased).
- [x] **Bash/Shell Synergy**: Enable arbitrary shell command integration (e.g., `bash`, `awk`, `grep`) within dynamic pipes, bounded by the final `semantic-sift` node to guarantee context safety. `SHELL_UTILITY_ALLOWLIST` (21 tools) + `_SIFT_TERMINAL_CMDS` guard + `allow_shell` flag on `run_dynamic_pipe()` and `pipe_run_dynamic` MCP tool. 9 new tests. (unreleased).

## 🔷 Phase 7.5: MCP Node Type (Planned — see `doc/MCP_NODE_SPEC.md`)

First-class MCP tool invocation as a `pipes.json` node. Eliminates the need for per-tool wrapper scripts when chaining MCP-only capabilities (Figma, GitHub, context-mode, etc.) into deterministic context pipelines.

- [ ] **Phase 7.5-A — Schema & Config**: `servers` block in `pipes.json` / `~/.mcp-pipe.json`; `${VAR}` env placeholder resolution; `config_loader` merge; `pipes.json.example` update. 6 unit tests.
- [ ] **Phase 7.5-B — `_run_mcp_node()` + async promotion**: `mcp.client.stdio` + `ClientSession` MCP client; `run_pipe()` promoted to `async`; all call sites updated (`api.py`, `cli.py`, `server.py`, `dynamic.py`); `pytest-anyio` added; 8 integration tests with mock `FastMCP` server.
- [ ] **Phase 7.5-C — Echo Guard node-scope fix**: Hash key changed from pipe-input to `pipe_name:node_index:content` to prevent false suppression in multi-sift pipes. 3 regression tests.
- [ ] **Phase 7.5-D — `_validate_nodes()` extension**: `mcp` nodes require `server` + `tool` keys; exempt from shell-metachar check and sift-terminal guard. 4 unit tests.
- [ ] **Phase 7.5-E — Docs & Release**: `ARCHITECTURE.md` §9, `OPERATOR_GUIDE.md` §3, `README.md` Advanced Node Types, `CHANGELOG.md` entry; `fail_under` raised.

**Cross-project dependency**: `mcp>=1.0` already declared in `pyproject.toml`. No new dependencies required for stdio transport.

## ⚫ Phase 8: The "Studio of Two" Endgame (Rust Core)
- [ ] **Rust Rewrite**: Port the core stream orchestrator to Rust, achieving ultimate native speed and zero Python/Node memory bloat.
- [ ] **Tauri Synergy**: Integrate the Rust crate directly into Meechi/Side-Hustle as a native cognitive ingestion engine, eliminating the need for standalone sidecars.
- [ ] **Universal CLI (`cpipe`)**: Expose the Rust engine as a compiled `cpipe` binary on PATH — same interface as `mcp-pipe` but zero Python dependency and ~5ms startup. Supersedes the Phase 2 shell alias; users simply remove the alias once the binary is installed.

## 🔹 Phase 9: Pipe Transparency Layer (Planned)

Real-time `[PIPE]` log lines emitted to `stderr` as a native behaviour of the pipe execution itself — not a CLI flag, not an IDE hook. The logs fire whenever `logging.enabled: true` is set in the pipe definition, regardless of whether the pipe was triggered via the MCP tool, the Python API, or the `mcp-pipe` CLI.

**Primary consumption pattern:** the agent shells out to `mcp-pipe run <pipe>` so the logs flow through the terminal in real time, visible to the user before the result is handed back. This sidesteps IDE stderr capture reliability entirely — the terminal is the display surface, not the IDE hook layer.

**Secondary patterns** (logs fire, visibility depends on runtime):
- `pipe_run` MCP tool — stderr visible in IDE terminals that capture it
- `pipe()` Python API — stderr visible when running in a terminal process

**Design:**
- `_emit_pipe_log()` private function in `orchestrator.py` — writes to `stderr` only; ~40 lines, no new dependencies
- Activated by a `logging` block in the pipe definition in `pipes.json` — pipe-native, not a flag
- Data sourced from the existing trace dict (input/output sizes, per-node latency) — no new instrumentation required
- Global default via env vars (`PIPE_LOG_LEVEL`, `PIPE_LOG_PREFIX`); per-pipe `logging` block always wins

**Log levels:**
- `summary` — one final line: `[PIPE] ✓ web-researcher | 18,400 → 380 tokens | 3.0s | -97.9%`
- `compact` — one exit line per node: `[PIPE] ✓ markitdown | 74,200 → 16,100 chars | 0.3s`
- `verbose` — entry + exit per node: `[PIPE] → markitdown` then `[PIPE] ✓ markitdown | 74,200 → 16,100 chars | 0.3s`

**Customizable fields per line:** `trigger`, `node`, `tokens` (char counts + delta + %), `timing`

**`pipes.json` schema:**
```json
{
  "name": "web-researcher",
  "logging": {
    "enabled": true,
    "prefix": "[PIPE]",
    "level": "verbose",
    "fields": ["trigger", "node", "tokens", "timing"]
  },
  "nodes": [ ... ]
}
```

**Env var fallback:** `PIPE_LOG_LEVEL=compact` | `PIPE_LOG_PREFIX=[PIPE]` — per-pipe `logging` block always wins.

- [ ] **Phase 9-A**: `_emit_pipe_log()` in `orchestrator.py` + `logging` block parsing in `config_loader`. Unit tests for each level + field combination.
- [ ] **Phase 9-B**: `PIPE_LOG_LEVEL` / `PIPE_LOG_PREFIX` env var support + global default merge with per-pipe override. Tests for precedence.
- [ ] **Phase 9-C**: Docs — `OPERATOR_GUIDE.md` §3 node schema, `ARCHITECTURE.md` §1, `README.md` Environment Variables table, `CHANGELOG.md`.
