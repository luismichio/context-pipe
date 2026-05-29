# Context-Pipe: Architecture Specification

This document provides the technical specification of the Context-Pipe system's core orchestration, routing, and telemetry layers. It is strictly aligned with the implemented codebase.

---

## 0. Design Lineage — Terminal Piping as the Foundation

Context-Pipe is directly and deliberately inspired by Unix terminal piping. The same primitive that made `cmd1 | cmd2 | cmd3` the most durable composition pattern in computing underlies every architectural decision here.

The mapping is exact:

| Terminal Piping | Context-Pipe |
|---|---|
| OS process | Pipe node (binary, script, MCP tool) |
| `stdout` → `stdin` byte stream | Context stream between nodes |
| Shell pipe operator (`\|`) | `pipes.json` node sequence |
| `/dev/stderr` for diagnostics | Per-node `stderr` trace map |
| Process timeout / `SIGKILL` | Timeout Guard (`PIPE_NODE_TIMEOUT_MS`) |
| `tee` for stream splitting | T-Pipe (save raw copy mid-chain) |

This lineage is not cosmetic. It is the reason for every constraint in the Context-Pipe Protocol (CPP):

- **`stdin`/`stdout` first** — any tool that honours this is a node, no SDK required.
- **`shell=False` enforced** — same injection-safety principle as secure shell scripting.
- **Single-responsibility nodes** — each node does one transformation; composition is the orchestrator's job.
- **Language-agnostic boundary** — a Rust binary, a Python script, and an MCP tool call are interchangeable at the pipe level.

### Dual Transport Support

Context-Pipe extends the terminal model to two transport modes, which compose freely in a single pipe definition:

- **Terminal piping** — any binary or shell command on `PATH` is a valid node. `rg`, `jq`, `prettier`, `semantic-sift-cli`, custom scripts — all first-class citizens.
- **MCP piping** — MCP tool calls are nodes too. The orchestrator invokes them through the same `stdin`/`stdout` contract, making Figma, GitHub, Firecrawl, and any registered MCP server composable alongside terminal tools.

The result is a unified pipe where a live web fetch, a terminal regex filter, a Rust distiller, and an MCP issue creator can sit in the same chain — each unaware of the others, each doing exactly one thing.

### Extending the Terminal with `mcp-pipe`

Traditional terminal piping is bounded by what is installed on `PATH`. `mcp-pipe` removes that ceiling. By exposing the full MCP ecosystem as pipe-addressable nodes, any terminal user can pipe data through richly capable MCP servers — web scrapers, code search engines, design tools, knowledge bases — without writing a single line of integration code.

```bash
echo "https://example.com" | mcp-pipe run web-research-pipe
cat error.log | mcp-pipe run triage-pipe
```

This means the decades of compounding value locked inside the MCP ecosystem becomes directly accessible from the shell, composable with every existing terminal tool.

---

## 1. Core Orchestration Engine

The heart of the platform is a high-performance Python-based engine designed to execute multi-node data pipelines at the OS level.

### Standard Stream Execution
The orchestrator utilizes `asyncio.create_subprocess_exec` to create memory-resident pipes between nodes.
- **`stdin` (The Input)**: Each node reads data from its standard input.
- **`stdout` (The Output)**: The node's transformed data is captured and passed to the next node's `stdin`.
- **`stderr` (The Error Stream)**: Redirected to a trace map to ensure node failures are reported without polluting the data stream.

#### Node Schema
Each node is a dictionary following this schema:

| Key | Type | Default | Description |
|---|---|---|---|
| `cmd` | string | (required) | Binary name, script path, or shell command. |
| `args` | array | `[]` | List of arguments passed to the command. |
| `type` | string | `"binary"` | `"binary"`, `"script"`, `"mcp"`, or `"validator"`. |
| `optional` | boolean | `false` | If `true`, orchestration continues even if the node fails. |
| `help_msg` | string | `""` | User-friendly instruction shown on node failure. |
| `tee` | object | `null` | Optional T-Pipe configuration for stream splitting. |
| `id` | string | auto | Stable node identifier used as a branch target (`__node_N__` if omitted). |
| `next` | string | auto | Override the natural sequential flow — jump to the node with this `id`. |
| `condition` | string | `null` | Skip this node if the predicate evaluates to `false`. See §1.5. |
| `branches` | object | `null` | Exit-code → node-id routing for `validator` nodes. See §1.5. |

### The Timeout Guard
Every node execution is wrapped in a **Timeout Guard** (default: 30s, configurable via `PIPE_NODE_TIMEOUT_MS`). If a node hangs (e.g., a stalled network fetch or a heavy neural model), the orchestrator kills the process, prevents an IDE freeze, and returns a structured `--- [Context-Pipe: Timeout] ---` response.

### Stream Integrity & Robustness
Context-Pipe is hardened against protocol violations caused by malformed or non-UTF8 output from pipe nodes.
- **Decoding Safety**: All subprocess streams (`stdout`, `stderr`) are decoded using `errors="replace"`. This ensures that binary data or invalid byte sequences do not trigger `UnicodeDecodeError` crashes in the orchestration engine.
- **Null-Safety**: Internal reading threads include robust `None` checks for process streams, preventing `TypeError` during high-pressure or timed-out execution paths.

### MCP Node Execution Path
In addition to standard binary nodes, Context-Pipe supports first-class MCP nodes (`type: "mcp"`). Instead of spawning a subprocess for every call, it uses the MCP `stdio` transport to communicate with registered servers.

```
run_pipe()
  │
  ├─── binary branch: asyncio.create_subprocess_exec(cmd) ────┐
  │                                             │
  └─── MCP branch: _run_mcp_node() ─────────────┤
          │                                     │
          ├── stdio_client(server_params)       │
          ├── ClientSession.call_tool(tool)     │
          └── _extract_text(result)             │
                                                │
          next node input <─────────────────────┘
```

#### MCP Node Banner Tolerance (Phase 13)
To handle non-conformant MCP servers that emit startup banners or debug messages to `stdout` before or between JSON-RPC frames, both the Python and Rust engines implement a tolerance filter:
- **Behavior**: Non-JSON lines are silently discarded up to a limit of 50 lines.
- **Verbosity**: Setting `verbose: true` in the server configuration surfaces skipped lines to `stderr`.

The orchestrator manages the full lifecycle of the MCP server connection for each node, ensuring clean teardown and timeout enforcement.

### 1.5 DAG Traversal Engine (Phase 11)

As of Phase 11, `run_pipe()` executes pipelines as **Directed Acyclic Graphs** rather than simple arrays. The linear array definition in `pipes.json` remains the common case; DAG semantics are additive and backward-compatible.

#### How Traversal Works

1. **ID Assignment** — every node is assigned a stable string ID at pipe-load time. If the node has an explicit `"id"` field, that is used. Otherwise an auto-generated ID is assigned (`__node_0__`, `__node_1__`, … for main-sequence nodes; `__branch_{name}_{i}__` for `branch_sequences` sub-graphs).
2. **Start** — traversal begins at the first main-sequence node.
3. **Condition Check** — if a node has a `"condition"` predicate, it is evaluated against the current input data. A `false` result skips the node and advances to the natural next node.
4. **Execution** — the node runs normally (binary, script, MCP, or validator).
5. **Next-Node Resolution** — priority order:
   1. For `validator` nodes: the exit code is stringified and looked up in `"branches"`. If found, the matching target ID is the next node. If not found, the `"default"` key is used. If neither exists, the node fails (respecting `optional`).
   2. If the node has a `"next"` field, that ID is the next node.
   3. Otherwise the natural sequential successor is used.
6. **Branch Sequence Entry** — if the next-node ID matches a `branch_sequences` key (not a node ID), the engine enters that sequence at its first node.
7. **Loop Guard** — if the step counter exceeds **100**, the engine halts with `--- [Context-Pipe: Loop Guard] ---` and returns an error. This prevents cycles from locking the orchestrator.

#### Condition Predicates (`"condition"`)

| Predicate | Example | Description |
|---|---|---|
| `size:>N` | `size:>10000` | Node runs only if input exceeds N bytes. |
| `size:<N` | `size:<500` | Node runs only if input is smaller than N bytes. |
| `artifact:exists:<path>` | `artifact:exists:output/report.md` | Node runs if the file at `<path>` already exists on disk. |
| `artifact:missing:<path>` | `artifact:missing:dist/bundle.js` | Node runs if the file at `<path>` does NOT exist on disk. |
| `contains:<string>` | `contains:ERROR` | Node runs if the leading 300 chars of input contain `<string>`. |

Unknown predicates **fail-open** — they log a warning and return `true` (run the node) to avoid silently blocking pipelines.

#### Validator Nodes (`"type": "validator"`)

A validator runs like a binary node but its exit code — rather than `stdout` — drives routing:

```json
{
  "cmd": "check-schema",
  "type": "validator",
  "id": "schema-check",
  "branches": {
    "0": "publish-step",
    "1": "fix-step",
    "default": "fix-step"
  }
}
```

- If the validator exits `0`, the engine transitions to node `publish-step`.
- If it exits `1`, it transitions to `fix-step`.
- `"default"` catches any other exit code.
- If no branch matches and `"default"` is absent, the node fails (unless `"optional": true`).
- The validator's `stdout` is passed as input to the branch target.

#### `branch_sequences`

Branch sequences are named sub-graphs of nodes that live outside the main pipe array. They are only entered when a validator (or a `"next"` pointer) references them by name:

```json
"branch_sequences": {
  "fix-step": [
    { "cmd": "auto-fixer", "args": ["--in-place"] },
    { "cmd": "semantic-sift-cli", "args": ["semantic"] }
  ]
}
```

Sequence nodes also support `condition`, `next`, `id`, and `branches` — the same traversal rules apply recursively.

### Pipe Transparency Layer (Logging)
To provide real-time visibility into the pipeline's execution (latency, node status, token/character deltas), the orchestrator includes a native logging layer:
*   **Emission Path**: Logs are printed directly to `stderr` during execution, allowing them to flow in real time through the terminal (e.g. `mcp-pipe run`) or be captured by IDE terminals.
*   **Log Levels**:
    *   `compact`: Emits a single exit line when a node completes: `[PIPE] ✓ node_name | input → output chars (delta | reduction%) | timing`.
    *   `verbose`: Emits both entry and exit lines: `[PIPE] → node_name` then `[PIPE] ✓ node_name ...`.
*   **Customization**: The log prefix, level, and visible fields are customizable per pipe or globally via environment variables. Data is sourced from the trace map, introducing zero overhead or new instrumentation.

### Resilient Orchestration (Failure-Bypass)
By default, the orchestrator follows a **Fail-Fast** strategy: any node failure (FileNotFound, Timeout, or Non-zero Exit Code) aborts the entire pipe.

To support complex "Mental Supply Chains," nodes may be marked as **Optional** (`"optional": true`) in `pipes.json`.
- **Optional nodes** that fail will record the error in the trace but will **not** abort the execution.
- The pipeline will continue using the `stdin` from the failed optional node as the input for the next node in the chain.

---

## 2. Dynamic Routing Engine

Context-Pipe uses a data-driven approach to routing, defined in `pipes.json`.

### Config Discovery (`load_config`)
The orchestrator employs a robust traversal discovery algorithm to find the project-level `pipes.json` file. This ensures that hooks and CLI commands work correctly even when the agent is operating in deep subdirectories.

**Resolution Order:**
1.  **Explicit Path**: Uses the `--config` argument or `PIPE_CONFIG_PATH` env var.
2.  **Upward Traversal**: Searches parent directories starting from the CWD until `pipes.json` or a `.git` boundary is discovered.
3.  **Package Fallback**: Reverts to the package root directory (where the core library is installed).

### Agnostic Trigger Logic
The system resolves the optimal pipe name based on three prioritized triggers:
1.  **Tool Trigger (`tool:<regex>`)**: Matches the calling tool name (e.g., `tool:search|grep`).
2.  **Size Trigger (`size:><num>`)**: Activates aggressive pipes for massive payloads (e.g., `size:>10000`).
3.  **Default Fallback**: Ensures a safety-net pipe is always applied.

### Pipe Templates
Instead of bundling code, Context-Pipe provides **Recipes**. Templates demonstrate how to chain external refineries:
- **`standard-distill`**: Routes to `semantic-sift-cli logs`.
- **`semantic-refinery`**: Routes to `semantic-sift-cli semantic`.
- **`full-refinery`**: Routes to `context-pipe-ingest | semantic-sift-cli`.

---

## 3. The Universal Switchboard (`context_pipe/wrapper.py` + `pipe_hook.py`)

The platform includes a "Subconscious Interceptor" that acts as a universal polyfill for AI agents.

### Platform detection
Using `platforms.py`, the hook identifies the host environment via:
- **Environment Variables**: Fingerprints for 13+ platforms (Antigravity, Cursor, Windsurf, pi.dev, etc.).
- **Parent Process Inspection**: High-fidelity detection via `psutil`.

### The Polyfill Wrapper (`wrapper.py`)
The Switchboard logic is decoupled into a reusable wrapper that performs:
1.  **JSON-to-Raw Extraction**: Extracts signal from `tool_response`, `result`, or `content` keys.
2.  **Structured Data Exemption**: Automatically bypasses valid JSON dictionaries to prevent syntax corruption.
3.  **The Echo Guard**: Uses a disk-persistent hash detector (30s TTL) to prevent "Double-Sifting" loops in nested environments.

---

## 4. Context Accounting (`telemetry.py`)

Telemetry in Context-Pipe is designed as a **Context Balance Sheet**.

### Supply Chain Traceability
The system records a `Trace Map` for every execution:
- **Input/Output Sizes**: Tracks the exact growth or reduction of every node.
- **Node Latency**: Identifies bottlenecks in the "Supply Chain."
- **Agent Attribution**: Tracks specific subagent labels (e.g., `[Explore]`, `[Bash]`) for granular ROI reporting.

### High-Fidelity Visibility
In the Sift-Centric model, the orchestrator is **silent**. Context distillation is reported via audit headers generated by the engine nodes (e.g., `semantic-sift-cli`) rather than the orchestrator itself. This ensures the human architect and the AI partner are aware of the context's health without redundant metadata from the orchestration layer.

---

## 5. Onboarding & Refinery Discovery (`onboarding.py`)

The onboarding module is responsible for bootstrapping Context-Pipe into any IDE or CLI environment and for establishing a reliable link to external refineries like `semantic-sift`.

### Refinery Discovery (`discover_sift_executable`)

Because `semantic-sift` may be installed in a completely separate virtual environment, Context-Pipe uses a multi-stage discovery algorithm to locate its CLI binary at onboard time:

1. **Current venv** (`sys.prefix/Scripts|bin`)
2. **System PATH** (`shutil.which`)
3. **pipx** (`~/.local/pipx/venvs/semantic-sift/`)
4. **Sibling venv directories** — walks up to 4 levels to find a `../semantic-sift/venv*/` pattern
5. **User home venvs** (`~/.venv`, `~/venv`)

### Refinery Linking (`resolve_pipes_config`)

Once the binary is discovered, `resolve_pipes_config` rewrites every `semantic-sift-cli` node in `pipes.json` with the resolved **absolute path**. This operation is idempotent and safe to call repeatedly. The orchestrator then uses this absolute path directly, bypassing any PATH ambiguity between isolated environments.

### Installation Verification (`verify_installation`)

`verify_installation` performs a structured health check:
- Is `context_pipe.orchestrator` importable?
- Does `pipes.json` exist and parse as valid JSON?
- Is `semantic-sift-cli` discoverable and responsive (`--version`)?
- Is every node command in `pipes.json` resolvable on disk or PATH?

The results are surfaced via the `pipe_verify` MCP tool, which also auto-runs `resolve_pipes_config` to link sift before reporting.

### Version Awareness & Self-Heal (`check_for_updates`)

To ensure environment parity and reduce "Setup Fatigue," Context-Pipe includes a proactive version checker:
- **GitHub-Backed**: The system queries the GitHub Releases API to identify the latest stable tag (`vX.Y.Z`).
- **Seamless Integration**: Update checks are automatically performed during `pipe_onboard` and `pipe_verify`. 
- **Actionable Alerts**: If a newer version is available, the system returns a formatted warning with the exact `pip install --upgrade` command required to self-heal the environment.

---

## 6. The Script Node (`scripts.py`)

The `type: "script"` node in `pipes.json` allows for deterministic local transformations and project-specific instructions without the overhead of absolute binary paths. It serves as the primary extension point for local automation.

### Purpose
Scripts provide a safe, standardized way to run local logic (Python scripts) or apply local instruction sets to the data stream. Unlike binary nodes, they are resolved from a dedicated `.gemini/scripts/` directory, keeping the project's transformation logic isolated and portable.

### Execution Flow
1. **Resolve**: The orchestrator looks for `<cmd>.py` or `<cmd>.md` in `$PIPE_SCRIPT_DIR` (default: `.gemini/scripts/`).
2. **Execute (Python)**: If a `.py` file is found, it is executed via the current Python interpreter (`sys.executable`).
3. **Prepend (Script)**: If a `.md` file is found, its content is prepended as a structured header: `--- [Context-Pipe: Script (<name>)] ---\n<text>\n\n[Content]\n<data>`.
4. **Fallback**: If neither is found, it falls back to a standard binary search on the system `PATH`.

### Difference from Skills
| | **Script Node** | **Skill (A2A)** |
|---|---|---|
| **Scope** | Local / Single-Agent | Distributed / Multi-Agent |
| **Logic** | Deterministic (Python/Regex) | Semantic (SLM-backed) |
| **Transport** | Terminal `stdin` / `stdout` | A2A handoff boundary |
| **Goal** | Structural filtering / Context tagging | Persona shift / Structural rewriting |

---

## 7. T-Pipes — Stream Splitting (`orchestrator.py`)

T-Pipes allow a single stream to be **saved to disk at any node boundary** without interrupting the main chain. This is the Unix `tee` pattern applied to the context pipeline.

### Schema

A node in `pipes.json` may declare an optional `tee` object:

```json
{
  "cmd": "semantic-sift-cli",
  "args": ["logs"],
  "tee": {
    "sink": "file",
    "path": "logs/{tool_name}_{iso_date}.log",
    "mode": "append"
  }
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `sink` | string | — | `"file"` (only supported sink in v0.3.0) |
| `path` | string | — | Destination path. Supports `{iso_date}` and `{tool_name}` tokens. |
| `mode` | string | `"append"` | `"append"` or `"overwrite"` |

### Execution Order

The tee fires **before** `asyncio.create_subprocess_exec` — raw node input is persisted even if the node itself crashes. Written content is the raw input plus a separator:

```
--- [Context-Pipe: Tee @ <node_cmd> | <iso_timestamp>] ---
```

### Safety Guarantee

`_write_tee()` wraps all I/O in `try/except Exception`. Any failure (disk full, bad path, permissions error) is silently swallowed. The main chain always continues.

### Trace Extension

When a tee fires, the node's trace entry gains a `"tee_path"` key with the resolved path. Absent when no tee is configured.

---

## 8. A2A Agent Handoff & Skill Engine (`context_pipe/a2a.py`)

The A2A module provides the boundary where **Active Skills** are applied.

### Design Principle
Explicit call — no monkey-patching. Any A2A framework (CrewAI, Google ADK, LangGraph) calls `pipe_agent_handoff()` at the handoff point. Context-Pipe acts as a semantic bridge, distilling Agent A's output into the optimal persona-driven context for Agent B.

### The Skill Engine (Phase 5 Roadmap)
While local nodes focus on deterministic sifting, the A2A handoff is the exclusive home for the **Skill Engine**. When Agent A hands data to Agent B, the orchestrator invokes a local SLM (e.g., Llama 3 via `llama.cpp`) to semantically rewrite the content based on the "Skill" lens.

By scoping Skills to the A2A boundary, Context-Pipe ensures that high-latency AI transformations only happen when a semantic shift (persona change) is explicitly required, keeping local CLI and IDE operations blazingly fast.

---

## 9. Dynamic Pipe Engine (`context_pipe/dynamic.py`)

`run_dynamic_pipe()` executes an ad-hoc node list supplied at call-time rather than from `pipes.json`. It is exposed as the `pipe_run_dynamic` MCP tool and the `mcp-pipe run-dynamic` CLI subcommand.

### Security Boundary — `SHELL_UTILITY_ALLOWLIST`

By default, shell nodes are **disabled** in dynamic pipes. Enabling them requires passing `allow_shell=True` explicitly (or setting the `allow_shell` flag in the MCP tool call). Even then, only the 21 tools in `SHELL_UTILITY_ALLOWLIST` are permitted:

```
bash, sh, awk, sed, grep, cut, sort, uniq, tr, head, tail,
wc, cat, echo, printf, xargs, python, python3, jq, yq
```

Any node whose command is not in the allowlist in a dynamic pipe where shell utilities are enabled (via `allow_shell=True`) raises a `ValueError` and the pipe is rejected before any subprocess is spawned.

### Sift-Terminal Guard (`_SIFT_TERMINAL_CMDS`)

Dynamic pipes that include shell nodes **must** end with a `semantic-sift` terminal command (e.g., `semantic-sift-cli`, `sift`). The guard enforces this constraint to guarantee context safety: raw shell output can never reach the LLM without passing through a sifting node.

---

## 10. Secure Global Configuration
To support secure global MCP registration (e.g., in Antigravity), the orchestrator utilizes `PIPE_AUTHORIZED_ROOT`. This variable can contain a single directory path or a list of directory paths separated by the platform's path separator (`;` on Windows, `:` on macOS/Linux), allowing context-pipe to safely read files across multiple authorized workspace boundaries.

## 10b. Global Configuration (`context_pipe/config_loader.py`)

`load_pipes_config()` merges two sources with **local precedence**:

1. **Local**: `pipes.json` in the project root (or `PIPE_CONFIG_PATH`).
2. **Global**: `~/.mcp-pipe.json` — a user-level config containing shared pipe definitions reusable across all projects.

Keys present in the local file always win over the global file. The global config is silently skipped if it does not exist.

### Schema Compatibility
Both files share the same `pipes.json` schema (`version`, `pipes`, `mappings`). Pipe definitions from both files are merged into a single list; mapping entries from the local file are prepended (higher priority).

---

## 11. Slash Command & Hook Injection (`context_pipe/onboarding.py`)

Phase 4 of the CPP roadmap injects four slash commands as first-class commands into IDE runtimes that support them:

| Command | IDE | Mechanism | Path |
|---|---|---|---|
| `/pipe-run` | Cursor, Gemini, OpenCode | `.mdc` rule / `.toml` command / `opencode.json` | Executes a named pipe on selected content |
| `/pipe-stats` | Cursor, Gemini, OpenCode | `.mdc` rule / `.toml` command / `opencode.json` | Prints the Context Balance Sheet |
| `/pipe-dynamic` | Cursor, Gemini, OpenCode | `.mdc` rule / `.toml` command / `opencode.json` | `pipe_list_shadow_tools` → build node graph → `pipe_run_dynamic` |
| `/pipe-handoff` | Cursor, Gemini, OpenCode | `.mdc` rule / `.toml` command / `opencode.json` | `pipe_agent_handoff` at a named A2A boundary |

### Robust Hook Deduplication (`merge_hook_json`)
Hook injection for Cursor, VS Code, Gemini CLI, and Claude Code utilizes a high-fidelity recursive deduplication algorithm. `merge_hook_json` scans existing JSON hook structures for matching core command strings even when nested within complex "matcher" arrays. To ensure seamless updates across versions, it employs an **Intelligent Replacement** strategy: if an older version of the hook is detected (e.g., missing new environment variables like `GEMINI_SESSION_ID`), it is safely filtered out and replaced with the upgraded payload without causing duplication.

### Payload Stream Protection
When invoking the orchestrator via IDE hooks, the Python executable is strictly invoked with the `-W ignore` flag (e.g., `python -W ignore -m context_pipe.orchestrator wrap`). This ensures that native `RuntimeWarning` or other standard error logs do not bleed into `stdout`, which would corrupt the JSON output stream expected by platforms like Gemini CLI and OpenCode.

### 11.2. Git Protection (`update_gitignore`)
To maintain repository hygiene and prevent machine-specific paths or local cache data from being committed, `pipe_onboard` automatically updates the project's `.gitignore` file. It appends the following artifacts under a managed `# Project Specific (Context-Pipe)` section:
- `.pipe_cache/` (Echo Guard storage)
- `.pipe_identity` (Telemetry identifiers)
- `.pipe_telemetry.jsonl` (Local accounting data)

The operation is idempotent and only appends missing entries.

### 11.3. Shell Alias Injection (`inject_shell_aliases` / `remove_shell_aliases`)

`inject_shell_aliases()` writes platform-aware marker blocks into `~/.bashrc`, `~/.zshrc`, or the PowerShell profile:

```bash
# POSIX
alias mcp-pipe='python -m context_pipe.cli'
alias cpipe='python -m context_pipe.cli'
```

```powershell
# PowerShell
Set-Alias -Name mcp-pipe -Value python -m context_pipe.cli
Set-Alias -Name cpipe -Value python -m context_pipe.cli
```

`remove_shell_aliases()` removes the marker block idempotently. Both operations are exposed as `pipe_install_aliases` / `pipe_remove_aliases` MCP tools and `mcp-pipe aliases install/remove` CLI subcommands.

---

## 12. Terminal ↔ MCP Bridge — `mcp-pipe tool`

### Motivation

The `mcp-pipe run` command executes named pipes defined in `pipes.json`. All nodes inside those pipes are currently terminal binaries. The `mcp-pipe tool` subcommand extends `mcp-pipe` into a direct terminal-to-MCP bridge, removing the boundary between the shell and the MCP ecosystem entirely.

### Interface

```bash
mcp-pipe tool <server-key> <tool-name> [--arg key=value ...] [--list-tools]
```

| Mode | Behaviour |
|---|---|
| `cat file \| mcp-pipe tool ctx ctx_execute` | Reads stdin, calls `ctx_execute` on the `ctx` server, writes stdout |
| `mcp-pipe tool github create_issue --arg title="Bug"` | Static args merged with stdin as `content` |
| `mcp-pipe tool firecrawl scrape --list-tools` | Introspects server, prints all available tools |

### Execution Model

1. Resolve `<server-key>` from `pipes.json` `servers` block (shared schema with Phase 7.5-A).
2. Spawn the MCP server process via `stdio` transport — load on demand, no idle cost.
3. Read `stdin` → call tool with `{"content": <stdin>, **static_args}` → capture result.
4. Write tool result to `stdout`. Timeout guard active (`PIPE_NODE_TIMEOUT_MS`).
5. Log telemetry event (input/output sizes, latency, server/tool labels).

This means any MCP server — local (context-mode, serena) or remote (GitHub, Firecrawl, any registered server) — is composable with any terminal tool through standard shell piping:

```bash
# terminal → MCP → terminal
cat error.log | mcp-pipe tool semantic-sift sift_logs | rg "CRITICAL"

# full chain: terminal + MCP + named pipe
curl -s https://example.com | mcp-pipe tool firecrawl scrape | mcp-pipe run semantic-refinery
```

### Relationship to MCP Nodes

MCP tool calls can also be defined *inside* `pipes.json` pipe definitions — the orchestrator calls them mid-chain transparently. `mcp-pipe tool` is the complementary surface: it exposes that same MCP call capability as a direct shell subcommand, one tool at a time, composable with any terminal pipeline. Both share the `servers` registry schema in `pipes.json`.

---

## 13. The Native Rust Core (`crates/cpipe`)

### Motivation

The Python-based FastMCP server carries a mandatory cold-start tax (~1000ms) due to interpreter startup. For real-time IDE hooks, Tauri sidecars, and shell-first workflows this latency is unacceptable. `cpipe` is the Rust port of the orchestration engine that eliminates this tax entirely.

### Coexistence Design

`cpipe` is explicitly *not* a replacement for the Python server. The two runtimes are complementary:

| Surface | Runtime | Role |
| :--- | :--- | :--- |
| MCP Tools (`pipe_run`, `pipe_read_file`, …) | Python (FastMCP) | AI assistant integration, complex logic |
| Standalone CLI (`cpipe run`, `cpipe list`, …) | Rust (`cpipe`) | Terminal workflows, shell hooks, low-latency |
| Tauri Sidecar | Rust (`cpipe`) | Desktop apps — zero Python dependency |
| Cargo Library | Rust (`cpipe`) | Direct embedding in Rust/Tauri applications |

### Ported Engine Rules

`cpipe` faithfully implements the full **Context-Pipe Protocol (CPP)**:

1. **Config Merging & Relative Traversal**: Loads and merges `pipes.json` (or `pipes.toml`) with global `~/.mcp-pipe.json`. Local config takes precedence. It supports relative path upward traversal to `.git` boundaries when resolving relative config files.
2. **Placeholder Resolution**: Recursively resolves `${VAR}` tokens against process environment variables.
3. **Stream Routing & CLI Parity**: Chains `stdin`/`stdout` between nodes via `tokio::process::Command` with `PIPE_NODE_TIMEOUT_MS` timeout guards. Implements 100% subcommand parity (`verify` and `handoff`) and full parameter aliases support (snake_case/kebab-case parity).
4. **PowerShell JSON Normalization**: Dynamically pre-processes unquoted or single-quoted JSON strings (e.g. `[{cmd: grep}]`) passed via PowerShell arguments using a robust character-by-character scanner, normalising them to valid RFC-JSON before parsing.
5. **Self-Aware Bypass**: Detects the sifting signature (`--- [Semantic-Sift Audit] ---`) and skips redundant re-processing, preventing infinite sifting loops.
6. **Path Security**: `resolve_safe_path()` validates file paths against `PIPE_AUTHORIZED_ROOT` (split by the platform-specific path separator to support multiple directories) and the client-reported workspace roots (`CLIENT_ROOTS`) before any I/O, mirroring the Python server's safety contract.
7. **DAG Traversal Engine (Phase 11)**: Full parity with the Python DAG engine. `Node` struct carries `condition`, `branches`, `id`, `next`. `Pipe` struct carries `branch_sequences`. `evaluate_condition()` implements all 5 predicates. The DAG `while` loop supports validator branching, `branch_sequences` entry, `next` overrides, condition-based node skipping, and the 100-step loop guard.

### TOML Configuration Support

`cpipe` adds first-class support for `pipes.toml` alongside the legacy `pipes.json`. TOML advantages: inline comments, multi-line strings for complex node arguments, and human-friendly syntax. Both formats are loaded and merged transparently — no migration required.

### Distribution

- **GitHub Releases**: Pre-built binaries for `x86_64-pc-windows-msvc`, `x86_64-apple-darwin`, `aarch64-apple-darwin`, `x86_64-unknown-linux-gnu`.
- **PyPI Wheels**: `cibuildwheel` compiles and bundles the `cpipe` binary inside the platform wheel — no Rust toolchain needed by end users.
- **Cargo**: `crates/cpipe` is publishable to crates.io with full library + binary dual targets.
- **Developer Fetch**: `python scripts/fetch_cpipe.py` downloads the matching release binary for the current platform.

### Release Workflow

Two parallel GitHub Actions workflows fire on `v*` tags:

- **`release.yml`**: Builds Python wheels (via `cibuildwheel`) for Windows/macOS/Linux and publishes to PyPI. The `CIBW_BEFORE_BUILD: pip install setuptools-rust` step compiles and embeds `cpipe` inside the wheel automatically.
- **`release-binaries.yml`**: Compiles standalone `cpipe` executables for all four target triples and uploads them as GitHub Release assets.

---
*High-Fidelity Infrastructure for the Studio of Two.*
