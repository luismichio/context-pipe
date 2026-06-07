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

## 🟢 Phase 3: The Template Ecosystem (Complete)
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

## 🔹 Phase 9: Pipe Transparency Layer (Complete)

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

- [x] **Phase 9-A**: `_emit_pipe_log()` in `orchestrator.py` + `logging` block parsing in `config_loader`. Unit tests for each level + field combination.
- [x] **Phase 9-B**: `PIPE_LOG_LEVEL` / `PIPE_LOG_PREFIX` env var support + global default merge with per-pipe override. Tests for precedence.
- [x] **Phase 9-C — Rust parity** (`crates/cpipe`): Add `PipeLogging` struct to `config.rs` (`enabled`, `level`, `prefix` fields on `Pipe`). Parse `logging` block from both JSON and TOML (`[logging]` table). Add `eprintln!("[PIPE] ...")` emission points in `orchestrator.rs` `run_pipe()` loop matching Python output format. Support `PIPE_LOG_LEVEL` / `PIPE_LOG_PREFIX` env var fallback. The `async` nature of `run_pipe()` means stderr emission is already safe.
- [x] **Phase 9-D**: Docs — `OPERATOR_GUIDE.md` §3 node schema, `ARCHITECTURE.md` §1, `README.md` Environment Variables table, `CHANGELOG.md`.

## 🔶 Phase 11: Conditional Branching & Validator Nodes (Planned)

**Origin:** Figma-to-code workflow — quality gates (validation contract, correction contract, resume-from-artifact contract) require non-linear routing that the current linear `run_pipe()` chain cannot express.

**Production validation:** A design-to-code workflow completed the MCP wrapper refactor (replacing Node.js bridge scripts with native `type: "mcp"` nodes). The refactor exposed two concrete branching failures that imperative script logic had been silently absorbing:

1. **Create run → artifact already exists:** A `create` pipe run detected the output artifact already existed in the registry and failed. The correct behaviour is to branch to the `update` sequence automatically. With a validator node checking for artifact existence, the pipe self-heals — no failure, no manual intervention.

2. **Update run → artifact missing:** An `update` pipe run failed because the source artifact did not exist yet. The correct behaviour is to branch back to the `create` sequence. Same mechanism, opposite direction.

These are not error conditions — they are **state transitions**. The pipeline should navigate them declaratively. A validator node with `condition: "artifact:exists:${OUTPUT_PATH}"` covers both cases and makes the pipeline self-healing rather than brittle.

**Design:** One new node `type`, one new node `key`, one new top-level pipe field. The CPP `stdin`/`stdout` contract is fully preserved — nodes remain unaware of routing; all branching logic lives in the orchestrator.

### Schema additions

**`type: "validator"`** — new node type. Runs a subprocess normally but routes based on **exit code** rather than piping stdout linearly. The node's stdout is passed as input to the first node of the selected branch. Semantically incompatible with `"binary"` (different post-execution contract).

```json
{ "type": "validator", "cmd": "component-validate",
  "branches": { "0": "run", "1": "correct" } }
```

**`"condition"` key** — a new key on *any* node type (`binary`, `script`, `mcp`, `validator`). Evaluated by the orchestrator **before** the node executes. If false, node is skipped entirely. No subprocess involved.

Supported predicates (reuse existing mapping trigger syntax):
- `size:>N` / `size:<N` — byte length of current input
- `artifact:missing:<path>` / `artifact:exists:<path>` — disk presence check
- `contains:<string>` — scan leading 300 bytes of input

```json
{ "cmd": "component-run", "condition": "artifact:missing:.cache/spec.json" }
{ "cmd": "semantic-sift-cli", "args": ["semantic"], "condition": "size:>5000" }
```

**`"branch_sequences"` top-level field** — named node sequences that live outside the linear `"nodes"` array. Validator nodes reference these by name.

```json
{
  "name": "design-to-code",
  "nodes": [
    { "type": "validator", "cmd": "component-preflight",
      "branches": { "0": "extract", "1": "error" } },
    { "id": "extract", "cmd": "component-extract" },
    { "type": "validator", "cmd": "component-validate",
      "branches": { "0": "run", "1": "correct" } },
    { "id": "correct", "cmd": "correction-rules", "next": "run" },
    { "id": "run", "cmd": "component-run",
      "condition": "artifact:missing:.cache/spec.json" },
    { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.4"],
      "condition": "size:>2000" }
  ],
  "branch_sequences": {
    "error": [{ "cmd": "pipe-error-handler" }]
  }
}
```

### Implementation scope

- [ ] **Phase 11-A — `"condition"` key** (`orchestrator.py`, `config_loader.py`): Add `_evaluate_condition(predicate, input_data)` evaluator. Integrate into `run_pipe()` loop before node dispatch. Predicates: `size:>N`, `size:<N`, `artifact:missing:path`, `artifact:exists:path`, `contains:string`. Unit tests for each predicate + interaction with `optional`. Update `ARCHITECTURE.md` §1 node schema table.
- [ ] **Phase 11-B — `type: "validator"` + `"branch_sequences"`** (`orchestrator.py`, `config_loader.py`): Convert `run_pipe()` linear loop to a **DAG traversal** (adjacency map built from `"nodes"` + `"branch_sequences"`). After a validator node executes, read exit code → look up branch name → jump to first node of that sequence. Validator stdout is passed as input to the selected branch. Add `"id"` and `"next"` node keys for explicit sequencing. Schema validation in `config_loader`. Unit + integration tests covering: 0-branch, 1-branch, unknown exit code (fallback to `"default"` branch or fail-fast), nested branches, `condition` + `validator` on same node.
- [ ] **Phase 11-C — Rust parity** (`crates/cpipe`): Add `condition: Option<String>`, `branches: Option<HashMap<String, String>>`, `id: Option<String>`, `next: Option<String>` to `Node` struct in `config.rs`. Add `branch_sequences: Option<HashMap<String, Vec<Node>>>` to `Pipe` struct. Add `_evaluate_condition()` equivalent in `orchestrator.rs`. Convert `run_pipe()` linear `for` loop to DAG traversal — the function is already `async` so no structural change needed. Ensure `pipes.toml` supports all new fields (`[branch_sequences]` table, inline `condition` strings).
- [ ] **Phase 11-D — Docs**: `ARCHITECTURE.md` §1 (node schema table + DAG diagram), `README.md` (new node type + condition key), `CHANGELOG.md`, `pipes.json.example` with a minimal validator example.

## 🔷 Phase 12: Runtime Variable Injection & Run Manifests (Complete)

**Origin:** Figma-to-code experiment — a custom pipe runner was built as a deliberate proof-of-concept to validate CPP's utility for complex multi-step automation. It independently derived two abstractions CPP needs to make the pattern self-sufficient without a custom runner:
1. **Runtime variables** — per-invocation `${VAR}` values passed at call time, not baked into env.
2. **Run manifests** — structured per-run JSON artifacts recording pipe name, per-node status, sift metrics, and final output.

With Phase 9 (trace logging) + Phase 11 (branching) + Phase 12, a single `mcp-pipe run <pipe-name> --var KEY=VALUE` call fully replaces the custom runner.

### 12-A — Runtime Variable Injection

Allow callers to supply a `KEY=VALUE` variable map at invocation time. The orchestrator substitutes `${KEY}` tokens in `cmd` and `args` fields before spawning each node. Variables are scoped to the run — they do not mutate `os.environ`.

**CLI surface:**
```bash
mcp-pipe run my-workflow-pipe \
  --var INPUT_URL="https://..." \
  --var COMPONENT_NAME="MyComponent" \
  --var CATEGORY="atom"
```

**MCP tool surface** (`pipe_run`):
```json
{ "pipe_name": "my-workflow-pipe",
  "vars": { "INPUT_URL": "...", "COMPONENT_NAME": "MyComponent" } }
```

**Python API surface** (`context_pipe.api.pipe`):
```python
pipe(text, "my-workflow-pipe", vars={"INPUT_URL": "..."})
```

**Behaviour rules:**
- `${VAR}` in `cmd` or `args` is substituted before the node runs.
- Missing variable → fail-fast with a clear error: `Missing pipe variable: INPUT_URL`.
- Variable names are `[A-Z0-9_]+` only — no shell metacharacters.
- Invocation vars take precedence over `os.environ`; `os.environ` is the fallback for undeclared vars (preserving existing `${PATH}`-style behaviour).
- `pipes.json` may declare a `"vars"` block with defaults: caller values override defaults.

```json
{
  "name": "my-workflow-pipe",
  "vars": { "CATEGORY": "default" },
  "nodes": [ ... ]
}
```

### 12-B — Run Manifests

After a pipe completes, optionally write a structured JSON artifact recording the full execution trace — equivalent to what the Figma-to-code experiment's custom runner wrote per-run.

**CLI:**
```bash
mcp-pipe run my-workflow-pipe --var KEY=VALUE --manifest artifacts/run.json
```

**Schema:**
```json
{
  "pipe": "my-workflow-pipe",
  "vars": { "INPUT_URL": "...", "COMPONENT_NAME": "MyComponent" },
  "completedAt": "2026-05-27T22:00:00Z",
  "status": "pass",
  "steps": [
    { "index": 1, "cmd": "my-tool ...", "ok": true, "status": 0,
      "stdoutPreview": "...", "siftMetrics": null },
    { "index": 6, "cmd": "semantic-sift-cli semantic --rate 0.35", "ok": true,
      "siftMetrics": { "reductionPct": 35.2, "latencyMs": 75 } }
  ],
  "finalOutput": "..."
}
```

Alternatively, `"manifest": "auto"` in the pipe definition writes to `.pipe_cache/<pipe-name>-<iso>.json` automatically.

### Implementation scope

- [x] **Phase 12-A — Variable substitution** (`orchestrator.py`, `config_loader.py`, `cli.py`, `server.py`, `api.py`): Add `_substitute_vars(text, vars)` in `orchestrator.py`. Extend `run_pipe()` signature with `vars: dict`. Propagate through `cli.py` (`--var KEY=VALUE`, repeatable), `server.py` (`pipe_run` tool `vars` param), `api.py` (`pipe()` `vars` kwarg). Add `"vars"` defaults block to `config_loader` schema. Unit tests: substitution, missing var error, env fallback, defaults override.
- [x] **Phase 12-B — Run manifests** (`orchestrator.py`, `cli.py`, `server.py`): Add `--manifest <path>` to CLI and `manifest_path` param to `run_pipe()`. Write manifest JSON after pipe completes (pass or fail). `"manifest": "auto"` in pipe definition enables automatic path. Tests for schema shape, failure recording, auto-path token expansion.
- [x] **Phase 12-C — Rust parity** (`crates/cpipe`): `resolve_placeholders()` in `config.rs` already accepts a `HashMap<String, String>` with `os::env` fallback — the substitution engine is 80% done. Work needed: add `vars: &HashMap<String, String>` param to `run_pipe()` in `orchestrator.rs` and merge into `process_env` before the node loop; add `--var KEY=VALUE` (repeatable) flag to `main.rs` CLI; add `vars: Option<HashMap<String, String>>` defaults field to `Pipe` struct in `config.rs`; support `[vars]` table in `pipes.toml`. For manifests: add `--manifest <path>` to `main.rs` and a `write_manifest()` function in `orchestrator.rs` that serialises the existing `trace` Vec + metadata to JSON after `run_pipe()` returns.
- [x] **Phase 12-D — Docs**: `ARCHITECTURE.md` §1 (node schema — `vars` block), `README.md` (CLI flags, MCP tool params), `pipes.json.example` with `vars` defaults, `CHANGELOG.md`.

## 🔧 Phase 13: MCP Node Banner Tolerance (Complete)

**Origin:** Some MCP servers (non-conformant but common in the wild) emit a startup banner — version string, connection status, ready message — to `stdout` before any JSON-RPC communication begins. The MCP protocol specifies that `stdout` belongs exclusively to JSON-RPC; a banner is a spec violation by the server. CPP should tolerate it gracefully rather than failing.

**Current failure modes:**
- **Rust** (`run_mcp_node`): raw `read_line()` + immediate `serde_json::from_str()` → `"Malformed json-rpc from MCP server: expected value at line 1 column 1"`. Fails fast, at least traceable.
- **Python** (`_run_mcp_node` via MCP SDK): `stdout_reader()` calls `JSONRPCMessage.model_validate_json(line)`, catches the exception, and **injects it into the message stream** (`read_stream_writer.send(exc)`). The `ClientSession` receives the exception during `initialize()` and raises. More cryptic than Rust. The `# pragma: no cover` on that path confirms Anthropic has never tested it.

**Design: tolerance by default, verbosity opt-in**

Non-JSON stdout lines are silently discarded by default. No config required — works transparently for all banner-emitting servers. The `"verbose": true` flag on the server config opts into surfacing skipped lines to `stderr` for debugging.

```json
"servers": {
    "my-mcp-server": {
        "command": "npx my-server",
        "verbose": true
    }
}
```

With `verbose: true`, skipped lines surface as:
```
[cpipe] MCP server stdout (non-JSON): Figma MCP Server v1.2.3
[cpipe] MCP server stdout (non-JSON): Ready for requests
```

Silent by default, traceable on demand. `verbose` lives on the **server config** (not the node) because the banner is a server property — the same server emits the same banner regardless of which tool is called. Composes naturally with Phase 9 `[PIPE]` logging: when `logging.level: "verbose"` is set on the pipe, MCP server verbose output flows through the same trace channel.

**Safety limit:** scan at most 50 non-JSON lines before returning an error — prevents infinite loops against genuinely broken servers that never emit JSON-RPC.

- [x] **Phase 13-A** (`crates/cpipe/src/orchestrator.rs`): Replace both raw `read_line()` calls in `run_mcp_node()` with a `read_jsonrpc_line(reader, max_skip)` async helper. Scans stdout lines until one parses as valid JSON, logging non-JSON lines to `stderr` (always) or suppressing them (default). Wire `verbose` flag from server config to control stderr emission. Unit tests: clean server (no banner), banner-before-initialize, banner-between-initialize-and-tool-response, >50 non-JSON lines (error path).
- [x] **Phase 13-B** (`context_pipe/orchestrator.py`): The MCP SDK controls stdout reading so injection is not clean. Fix: when `verbose: false` (default), wrap the server's stdout with a pre-filter before `stdio_client` reads it — only forwarding lines that parse as valid JSON (start with `{` after stripping whitespace). When `verbose: true`, forward all lines but log non-JSON ones to `stderr`. Add `verbose` field to server config schema in `config_loader.py`. Tests mirroring Rust test cases.
- [x] **Phase 13-C** (`config_loader.py`, `config.rs`): Add `verbose: bool = false` to the server config schema in both Python and Rust. Document in `pipes.json.example`.
- [x] **Phase 13-D**: Docs: `ARCHITECTURE.md` §1 MCP node section, `README.md` servers block reference, `CHANGELOG.md`.

## 🟩 Phase 10: Sandboxing & Protocol Security (Done)

Implementing the MCP `roots` protocol to securely handle sandboxing without relying on global overrides or arbitrary working directories.

- [x] **Dynamic Root Discovery**: Implement `request_roots()` via the MCP session to dynamically retrieve the allowed workspace boundaries from the client (e.g., Antigravity, VS Code).
- [x] **Path Traversal Guard Upgrade**: Refactor `resolve_safe_path()` to validate file reads against the dynamically provided `roots` list.
- [x] **Graceful CWD Fallback**: Ensure that clients lacking `roots` support gracefully degrade to using `os.getcwd()`.
- [x] **Deprecate Global Bypass**: Formalize the removal of `SIFT_ALLOW_GLOBAL_READS` flag, as it is made obsolete by the dynamic roots implementation.
