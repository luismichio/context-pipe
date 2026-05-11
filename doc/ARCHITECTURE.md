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
The orchestrator utilizes `subprocess.Popen` to create memory-resident pipes between nodes.
- **`stdin` (The Input)**: Each node reads data from its standard input.
- **`stdout` (The Output)**: The node's transformed data is captured and passed to the next node's `stdin`.
- **`stderr` (The Error Stream)**: Redirected to a trace map to ensure node failures are reported without polluting the data stream.

### The Timeout Guard
Every node execution is wrapped in a **Timeout Guard** (default: 30s, configurable via `PIPE_NODE_TIMEOUT_MS`). If a node hangs (e.g., a stalled network fetch or a heavy neural model), the orchestrator kills the process, prevents an IDE freeze, and returns a structured `--- [Context-Pipe: Timeout] ---` response.

### MCP Node Execution Path
In addition to standard binary nodes, Context-Pipe supports first-class MCP nodes (`type: "mcp"`). Instead of spawning a subprocess for every call, it uses the MCP `stdio` transport to communicate with registered servers.

```
run_pipe()
  │
  ├─── binary branch: subprocess.Popen(cmd) ────┐
  │                                             │
  └─── MCP branch: _run_mcp_node() ─────────────┤
          │                                     │
          ├── stdio_client(server_params)       │
          ├── ClientSession.call_tool(tool)     │
          └── _extract_text(result)             │
                                                │
          next node input <─────────────────────┘
```

The orchestrator manages the full lifecycle of the MCP server connection for each node, ensuring clean teardown and timeout enforcement.

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

The tee fires **before** `subprocess.Popen` — raw node input is persisted even if the node itself crashes. Written content is the raw input plus a separator:

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
- `.pipe_telemetry.json` (Local accounting data)

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
*High-Fidelity Infrastructure for the Studio of Two.*
