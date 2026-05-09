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
- **MCP piping** — MCP tool calls (Phase 7.5) are nodes too. The orchestrator invokes them through the same `stdin`/`stdout` contract, making Figma, GitHub, Firecrawl, and any registered MCP server composable alongside terminal tools.

The result is a unified pipe where a live web fetch, a terminal regex filter, a Rust distiller, and an MCP issue creator can sit in the same chain — each unaware of the others, each doing exactly one thing.

---



The heart of the platform is a high-performance Python-based engine designed to execute multi-node data pipelines at the OS level.

### Standard Stream Execution
The orchestrator utilizes `subprocess.Popen` to create memory-resident pipes between nodes.
- **`stdin` (The Input)**: Each node reads data from its standard input.
- **`stdout` (The Output)**: The node's transformed data is captured and passed to the next node's `stdin`.
- **`stderr` (The Error Stream)**: Redirected to a trace map to ensure node failures are reported without polluting the data stream.

### The Timeout Guard
Every node execution is wrapped in a **Timeout Guard** (default: 30s, configurable via `PIPE_NODE_TIMEOUT_MS`). If a node hangs (e.g., a stalled network fetch or a heavy neural model), the orchestrator kills the process, prevents an IDE freeze, and returns a structured `--- [Context-Pipe: Timeout] ---` response.

---

## 2. Dynamic Routing Engine

Context-Pipe uses a data-driven approach to routing, defined in `pipes.json`.

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
- **Environment Variables**: Fingerprints for 12+ platforms (Antigravity, Cursor, Windsurf, etc.).
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
To satisfy the **Expectation Effect**, the platform prepends a Markdown **Audit Header** to all processed content. This ensures the human architect and the AI partner are always aware of the context's health and ROI.

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


---

## 6. The Skill Node (`skills.py`)

The `context-pipe-skill` CLI entry point exposes a **Skill Lens Node**: a pipe-composable wrapper that prepends a user-defined mandate (instruction set) to the data stream before routing it to a downstream refinery.

### Purpose
Skills let users inject domain-specific expert context — a security auditor persona, a React linting guide, or a specific coding style mandate — into the pipeline *without modifying the orchestrator*. The skill node is just another `stdin → stdout` transformer that adheres to the CPP standard.

### Execution Flow
1. **Read** stdin (the upstream node's output).
2. **Locate** the mandate file: looks for `<skill-name>.md` in `$PIPE_SKILL_DIR` (default: `.gemini/skills/`), then falls back to `cwd`.
3. **Inject** the mandate as a header above the data: `--- [Skill Lens: <name>] ---\n<mandate>\n\n[Content]\n<data>`.
4. **Write** to stdout for the next node.

### Difference from `server.py`
| | `skills.py` (`context-pipe-skill`) | `server.py` (`context-pipe-server`) |
|---|---|---|
| **Transport** | `stdin` / `stdout` (CPP pipe node) | MCP protocol over `stdio` |
| **Purpose** | Instruction injection node | MCP tool host (balance sheet, verification) |
| **Usage** | Embedded in `pipes.json` node chain | Registered as an MCP server in the IDE |

### Current Limitations & Roadmap
- **Prototype-quality**: The current implementation is a proof-of-concept. The mandate is prepended as raw Markdown, relying on the LLM's in-context reasoning to apply the lens. There is no local SLM invocation yet.
- **Phase 5 (Future)**: Skills will be upgraded to drive a local SLM for true structural rewriting (e.g., via `llama.cpp` sidecar), making the lens semantically precise rather than instruction-injected.
- **No Removal Planned**: `context-pipe-skill` is an active, documented entry point and is *not* vestigial. It is retained for future SLM-backed skill execution.

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

The tee fires **before** `subprocess.Popen` — raw node input is persisted even if the node itself crashes. Written content is the raw input plus a separator:

```
--- [Context-Pipe: Tee @ <node_cmd> | <iso_timestamp>] ---
```

### Safety Guarantee

`_write_tee()` wraps all I/O in `try/except Exception`. Any failure (disk full, bad path, permissions error) is silently swallowed. The main chain always continues.

### Trace Extension

When a tee fires, the node's trace entry gains a `"tee_path"` key with the resolved path. Absent when no tee is configured.

---

## 8. A2A Agent Handoff (`context_pipe/a2a.py`)

The A2A module provides a **framework-agnostic bridge** for distilling Agent A's output before it enters Agent B's context window.

### Design Principle

Explicit call — no monkey-patching. Any A2A framework (CrewAI, Google ADK, LangGraph) calls `pipe_agent_handoff()` at the handoff point. Context-Pipe acts as a dumb pipe; zero framework coupling.

### Execution Flow

1. `from_agent` label forwarded as `tool_name` to `api.pipe()` for trigger matching and telemetry attribution.
2. `api.pipe()` resolves the pipe via `pipe_name` (explicit) or `pipes.json` mappings (auto).
3. `run_pipe()` executes the node chain.
4. A telemetry event is logged with input/output sizes and agent labels (no content).
5. On any error, the original output is returned unchanged — the agent chain is never interrupted.

### MCP Surface

`pipe_agent_handoff` is registered as an MCP tool in `server.py`, making it directly invocable by AI assistants without Python code changes.

---

## 9. Dynamic Pipe Engine (`context_pipe/dynamic.py`)

`run_dynamic_pipe()` executes an ad-hoc node list supplied at call-time rather than from `pipes.json`. It is exposed as the `pipe_run_dynamic` MCP tool and the `mcp-pipe run-dynamic` CLI subcommand.

### Security Boundary — `SHELL_UTILITY_ALLOWLIST`

By default, shell nodes are **disabled** in dynamic pipes. Enabling them requires passing `allow_shell=True` explicitly (or setting the `allow_shell` flag in the MCP tool call). Even then, only the 21 tools in `SHELL_UTILITY_ALLOWLIST` are permitted:

```
bash, sh, zsh, fish, python, python3, node, npx, curl, wget,
grep, awk, sed, cut, sort, uniq, wc, head, tail, cat, echo
```

Any node whose command is not in the allowlist AND has `shell: true` raises a `ValueError` and the pipe is rejected before any subprocess is spawned.

### Sift-Terminal Guard (`_SIFT_TERMINAL_CMDS`)

Dynamic pipes that include shell nodes **must** end with a `semantic-sift` terminal command (e.g., `semantic-sift-cli`, `sift`). The guard enforces this constraint to guarantee context safety: raw shell output can never reach the LLM without passing through a sifting node.

---

## 10. Global Configuration (`context_pipe/config_loader.py`)

`load_pipes_config()` merges two sources with **local precedence**:

1. **Local**: `pipes.json` in the project root (or `PIPE_CONFIG_PATH`).
2. **Global**: `~/.mcp-pipe.json` — a user-level config containing shared pipe definitions reusable across all projects.

Keys present in the local file always win over the global file. The global config is silently skipped if it does not exist.

### Schema Compatibility
Both files share the same `pipes.json` schema (`version`, `pipes`, `mappings`). Pipe definitions from both files are merged into a single list; mapping entries from the local file are prepended (higher priority).

---

## 11. Slash Command Injection (`context_pipe/onboarding.py`)

Phase 4 of the CPP roadmap injects four slash commands as first-class commands into IDE runtimes that support them:

| Command | IDE | Mechanism | Path |
|---|---|---|---|
| `/pipe-run` | Cursor, Gemini, OpenCode | `.mdc` rule / `.toml` command / `opencode.json` | Executes a named pipe on selected content |
| `/pipe-stats` | Cursor, Gemini, OpenCode | `.mdc` rule / `.toml` command / `opencode.json` | Prints the Context Balance Sheet |
| `/pipe-dynamic` | Cursor, Gemini, OpenCode | `.mdc` rule / `.toml` command / `opencode.json` | `pipe_list_shadow_tools` → build node graph → `pipe_run_dynamic` |
| `/pipe-handoff` | Cursor, Gemini, OpenCode | `.mdc` rule / `.toml` command / `opencode.json` | `pipe_agent_handoff` at a named A2A boundary |

Injection is idempotent — `inject_hooks()` checks for existing marker blocks before writing. The slash command injection is **distinct** from the Phase 2 Standard Shell Aliases (which targets POSIX/PowerShell profiles) and the Phase 2 `inject_shell_aliases()` function.

### Shell Alias Injection (`inject_shell_aliases` / `remove_shell_aliases`)

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
*High-Fidelity Infrastructure for the Studio of Two.*
