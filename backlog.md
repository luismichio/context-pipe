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
- [x] **Standard Shell Aliases**: `inject_shell_aliases()` / `remove_shell_aliases()` in `onboarding.py`. `mcp-pipe aliases install/remove` CLI subcommands + `pipe_install_aliases` / `pipe_remove_aliases` MCP tools. Idempotent marker-block pattern; platform-aware (POSIX/PowerShell). 20 tests.

## 🟢 Phase 3: The Template Ecosystem (In Progress)
- [x] **Pure Switchboard Refactor**: Removed internal nodes to achieve 100% agnostic status.
- [x] **Pipe Templates**: Professional recipes for `sift-core` and `markitdown`.
- [x] **Mandate Ecosystem**: Formalized "Expert Lenses" as local Mandate Nodes (`.md` files in `.gemini/scripts/`).


## ⚪ Phase 4: Distribution (Complete)
- [x] **PyPI Publishing**: `pip install mcp-context-pipe` — live at [pypi.org/project/mcp-context-pipe](https://pypi.org/project/mcp-context-pipe/) (v0.4.0).
- [x] **`semantic-sift` PyPI Publishing**: `pip install semantic-sift` — live at [pypi.org/project/semantic-sift](https://pypi.org/project/semantic-sift/).
- [x] **Slash Command Injection**: Inject `/pipe-stats` and `/pipe-run` as first-class slash commands into agentic IDE CLIs (Gemini CLI `.gemini/commands/`, OpenCode `opencode.json` commands block, Cursor `onInit` hooks).

## 🔵 Phase 4.5: OpenCode Native Plugin (Blocked — Upstream)

**Status**: BLOCKED (upstream)
**Priority**: HIGH (trust / feature completeness)
**Tracking**: [sst/opencode#21149](https://github.com/sst/opencode/issues/21149), [sst/opencode#25918](https://github.com/sst/opencode/issues/25918)

- [ ] **MCP tool output interception via `tool.execute.after`**: Re-implement the plugin handler in `.opencode/plugins/context-pipe.ts` once OpenCode assembles MCP tool output **before** triggering the hook. Currently, the hook fires with the raw `CallToolResult {content:[]}` shape instead of the declared `{title, output, metadata}` shape, making `output.output` mutation a no-op for all MCP tools (including `pipe_read_file`). Native tools (bash, read, etc.) already receive the correct shape and mutations work — only MCP tools are affected.
  - **Blocked by**: [sst/opencode#21149](https://github.com/sst/opencode/issues/21149) — MCP tool text assembly must happen before the hook fires.
  - **Our upstream report**: [sst/opencode#25918](https://github.com/sst/opencode/issues/25918) — detailed analysis of both paths.
  - **When fixed**: uncomment the handler in `.opencode/plugins/context-pipe.ts` and `onboarding.py` template. The interception logic (pipe through `orchestrator wrap`, write back to `output.output`) is already written and tested — it just needs the hook to receive the right shape.
  - **Interim**: `pipe_read_file` MCP tool remains the explicit interception point per `AGENTS.md` SOP.

### User Impact

Users running Context-Pipe with OpenCode as their IDE will **not** have MCP tool outputs automatically piped through context refineries. The "subconscious interceptor" feature is effectively disabled for OpenCode users. This impacts any workflow that relies on automatic noise reduction of tool outputs (e.g., `read_file`, `bash`, `grep`).

### Current Workaround

The `AGENTS.md` SOP mandate is the active strategy:
- All file reads use `pipe_read_file()` (an explicit MCP tool call that routes through the pipe).
- The mandate is injected automatically by `pipe_onboard(environment='OpenCode')`.

This workaround requires AI agent cooperation (the agent must follow the `AGENTS.md` SOP). It does not intercept native tool outputs transparently.

### Proposed Implementation (post-unblock)

Once upstream support lands:
1. Restore the output mutation handler in `opencode.json` plugin scaffold.
2. Update `pipe_onboard(environment='OpenCode')` to write the active (not placeholder) plugin.
3. Add an integration test that validates hook firing end-to-end.
4. Update `doc/INTEGRATION_ENCYCLOPEDIA.md` to mark OpenCode as fully supported.

## 🟣 Phase 5: Productionisation & Quality (Complete)
- [x] **Programmatic Python API** (`context_pipe/api.py`): `pipe(text, pipe_name, tool_name)` — direct integration without MCP or CLI.
- [x] **Test Coverage Uplift**: Coverage raised to **83.7%**; `fail_under = 83` enforced in CI.
- [x] **CPP Integration Contract Tests**: Mock-subprocess suite validating `run_pipe()` stdin/stdout/error/timeout contract.
- [x] **Technical Test Audit**: Closed logic "blind spots" in `server.py` and `scripts.py`. Verified all 240+ tests against industry standards.
- [x] **Root-Module Inversion** (`semantic-sift`): Canonical implementations moved to `semantic_sift/`.
- [x] **Telemetry Consent UX**: Surface opt-in disclosure in `sift_onboard` response.

## 🟠 Phase 6: A2A (Agent-to-Agent) Orchestration (Complete)
- [x] **Multi-Agent Interception**: `context_pipe/a2a.py` — `pipe_agent_handoff()` + MCP tool. Framework-agnostic bridge for CrewAI, Google ADK, LangGraph.
- [x] **Stream Splitting (T-Pipes)**: `_write_tee()` in `orchestrator.py`; `tee` node schema in `pipes.json`; `{iso_date}`/`{tool_name}` tokens; `tee_path` in trace.

## 🟤 Phase 7: Dynamic Shadow Ecosystem (RAG for Tools) (Complete)
- [x] **Dynamic Pipe Execution**: `context_pipe/dynamic.py` — `run_dynamic_pipe()` + `pipe_run_dynamic` MCP tool. Security boundary enforced (shell metacharacters rejected).
- [x] **The `mcp-pipe` CLI**: `context_pipe/cli.py` — `mcp-pipe` terminal runner with `run`, `run-dynamic`, `list`, `stats`, `serve` subcommands.
- [x] **Shadow Tool Discovery**: `context_pipe/shadow.py` — `list_shadow_tools()` + `pipe_list_shadow_tools` MCP tool. Probes 7 curated CLI tools on PATH.
- [x] **Standalone Configuration**: `context_pipe/config_loader.py` — `load_pipes_config()` merges `pipes.json` + `~/.mcp-pipe.json` with local precedence.
- [x] **Bash/Shell Synergy**: Enable arbitrary shell command integration (e.g., `bash`, `awk`, `grep`) within dynamic pipes, bounded by the final `semantic-sift` node.
- [x] **MCP Node Type**: First-class MCP tool invocation as a `pipes.json` node. Schema support in `config_loader`; `async` orchestrator spine; `_run_mcp_node()` implementation.
- [x] **`mcp-pipe tool` Subcommand**: Directly invoke any registered MCP tool from the shell. Supports `--arg key=value`, `--input-key`, and `-v` for telemetry.

## ⚫ Phase 8: The "Studio of Two" Endgame (Rust Core) — ✅ Complete
- [x] **Rust Rewrite**: Port the core stream orchestrator to Rust, achieving ultimate native speed and zero Python/Node memory bloat. (`crates/cpipe` — dual lib + bin targets, <2ms startup, 500× faster than Python cold-start.)
- [x] **Tauri Synergy**: Integrate the Rust crate directly into Meechi/Side-Hustle as a native cognitive ingestion engine, eliminating the need for standalone sidecars. (`cpipe` documented as Tauri sidecar in `crates/cpipe/README.md`; `tauri.conf.json` setup + `Command::new_sidecar` examples included.)
- [x] **Universal CLI (`cpipe`)**: Expose the Rust engine as a compiled `cpipe` binary on PATH — same interface as `mcp-pipe` but zero Python dependency and <2ms startup. Supersedes the Phase 2 shell alias; users simply remove the alias once the binary is installed. (`cpipe run`, `cpipe list`, `cpipe stats`, `cpipe serve` subcommands live; `release-binaries.yml` publishes for Windows/macOS/Linux on every tag.)
- [x] **Dual-Layer Agent Integration (The "Belt and Suspenders" Pattern)**: Research and implement a generalized approach for publishing `context-pipe` native packages for agent frameworks (e.g., Pi, OpenCode). This involves bundling an **Extension** (for programmatic tool replacement/interception) with a **SKILL.md** (for cognitive discovery and intent shaping), mimicking the highly effective architecture seen in the `context-mode` package. (Native wheels via `cibuildwheel` for PyPI; `setup.py` + `setuptools-rust` build backend; `scripts/fetch_cpipe.py` for non-Rust dev installs; `Cargo.toml` crates.io metadata complete.)

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

## 🟩 Phase 10: Sandboxing & Protocol Security (Done)

Implementing the MCP `roots` protocol to securely handle sandboxing without relying on global overrides or arbitrary working directories.

- [x] **Dynamic Root Discovery**: Implement `request_roots()` via the MCP session to dynamically retrieve the allowed workspace boundaries from the client (e.g., Antigravity, VS Code).
- [x] **Path Traversal Guard Upgrade**: Refactor `resolve_safe_path()` to validate file reads against the dynamically provided `roots` list.
- [x] **Graceful CWD Fallback**: Ensure that clients lacking `roots` support gracefully degrade to using `os.getcwd()`.
- [x] **Deprecate Global Bypass**: Formalize the removal of `SIFT_ALLOW_GLOBAL_READS` flag, as it is made obsolete by the dynamic roots implementation.
