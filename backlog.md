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
- [ ] **Standard CLI Aliases**: Add `/pipe` commands to common shells.

## 🟢 Phase 3: The Template Ecosystem (In Progress)
- [x] **Pure Switchboard Refactor**: Removed internal nodes to achieve 100% agnostic status.
- [x] **Pipe Templates**: Professional recipes for `sift-core` and `markitdown`.
- [ ] **Adaptive Thresholding**: Dynamically adjust rates based on window pressure.

## ⚪ Phase 4: Distribution
- [ ] **PyPI Publishing**: `pip install context-pipe`.
- [ ] **Slash Command Injection**: Universal `/pipe` commands for agentic CLIs.

## 🔵 Phase 4.5: OpenCode Native Plugin (Blocked — Upstream)
- [ ] **MCP tool output interception via `tool.execute.after`**: Re-implement the plugin handler in `.opencode/plugins/context-pipe.ts` once OpenCode assembles MCP tool output **before** triggering the hook. Currently, the hook fires with the raw `CallToolResult {content:[]}` shape instead of the declared `{title, output, metadata}` shape, making `output.output` mutation a no-op for all MCP tools (including `pipe_read_file`). Native tools (bash, read, etc.) already receive the correct shape and mutations work — only MCP tools are affected.
  - **Blocked by**: [sst/opencode#21149](https://github.com/sst/opencode/issues/21149) — MCP tool text assembly must happen before the hook fires.
  - **Our upstream report**: [sst/opencode#25918](https://github.com/sst/opencode/issues/25918) — detailed analysis of both paths.
  - **When fixed**: uncomment the handler in `.opencode/plugins/context-pipe.ts` and `onboarding.py` template. The interception logic (pipe through `orchestrator wrap`, write back to `output.output`) is already written and tested — it just needs the hook to receive the right shape.
  - **Interim**: `pipe_read_file` MCP tool remains the explicit interception point per `AGENTS.md` SOP.

## 🟣 Phase 5: A2A (Agent-to-Agent) Orchestration
- [ ] **Multi-Agent Interception**: Position Context-Pipe as the definitive "Data Bus" for A2A frameworks (e.g., CrewAI, Google ADK). Allow Agent A's output to be piped through a distillation refinery before reaching Agent B's context window.
- [ ] **Stream Splitting (T-Pipes)**: Allow a single upstream tool to output to multiple downstream nodes (e.g., logging a raw stream to disk while piping the distilled stream to the LLM).
