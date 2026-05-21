# Phase 8 Implementation Plan: Context-Pipe Rust Core (`cpipe`)

This plan outlines the design and steps required to port the Python-based `context-pipe` orchestrator and CLI to Rust. The goals are to achieve near-instantaneous startup times (~5ms), eliminate Python runtime dependencies, reduce memory overhead to zero in agent runtimes, and enable direct, high-performance integration with Tauri apps (like Meechi/Side-Hustle) and cross-language wrappers.

## User Review Required

> [!IMPORTANT]
> **Coexistence of Rust and Python Versions**
> The Rust core will be built as an **addition, not a replacement**. Rust and Python will coexist in the repository. The Python implementation remains the primary and default MCP server, while the Rust core (`cpipe` CLI and crate) is added as a high-performance alternative (providing ~5ms startup times and zero-dependency execution).

> [!IMPORTANT]
> **Workspace Location for the Crate**
> The Rust crate will be created in a new directory named `crates/cpipe` within the existing `context-pipe` repository.

> [!IMPORTANT]
> **Binary Name and Command Line Aliases**
> `cpipe` will be the primary name of the compiled Rust binary. We will support compatibility aliases so that the Rust binary can be invoked in place of `context-pipe` or `mcp-pipe`.

## Open Questions & Decisions

> [!NOTE]
> **TOML Configuration Support**
> We will support both `pipes.json` (for backwards compatibility and cross-parity with the Python engine) and `pipes.toml`.
>
> **Advantages of TOML over JSON for configurations:**
> 1. **Native Comments**: TOML supports standard comments (`# comment`), eliminating the need for hacky JSON string fields like `"_comment"`.
> 2. **Multi-line Strings**: TOML supports raw multi-line strings (`"""`), which is incredibly useful for writing complex node arguments, command descriptions, or inline sifting patterns without escaping quotes and newlines with `\n`.
> 3. **Human Friendliness**: TOML is designed for humans to write configurations and does not fail on trailing commas or strict quote formatting.

---

## Proposed Changes

We will introduce a Cargo workspace in the project root or create a standalone crate under `crates/cpipe`.

### [Rust Core Orchestrator]

#### [NEW] [Cargo.toml](file:///C:/Users/luism/Workbench/GitHub/context-pipe/crates/cpipe/Cargo.toml)
Defines the crate dependencies (e.g., `serde`, `serde_json`, `tokio` with `process` and `rt` features, `clap` for CLI parsing, and `log`/`env_logger` for telemetry).

#### [NEW] [lib.rs](file:///C:/Users/luism/Workbench/GitHub/context-pipe/crates/cpipe/src/lib.rs)
The library entry point exposing core orchestration, parsing, and execution APIs so it can be integrated directly into other Rust applications (like Tauri backend projects).

#### [NEW] [config.rs](file:///C:/Users/luism/Workbench/GitHub/context-pipe/crates/cpipe/src/config.rs)
Handles loading, merging, and parsing local `pipes.json` and global `~/.mcp-pipe.json` configurations.
* Resolves `${VAR}` placeholders inside environment settings.
* Performs schema validation on pipes, mappings, and server configurations.

#### [NEW] [orchestrator.rs](file:///C:/Users/luism/Workbench/GitHub/context-pipe/crates/cpipe/src/orchestrator.rs)
Port of `orchestrator.py` and `dynamic.py` stream-routing algorithms:
* Manages standard I/O redirection between sequential pipe nodes.
* Employs timeout guards using `tokio::time::timeout`.
* Implements the **Self-Aware Node Bypass** rule (checking for `--- [Semantic-Sift Audit] ---`).

#### [NEW] [shadow.rs](file:///C:/Users/luism/Workbench/GitHub/context-pipe/crates/cpipe/src/shadow.rs)
Probes the system `PATH` for curated CLI tools (`jq`, `rg`, `markitdown`, `pandoc`, etc.) and parses their availability to return a live capability manifest.

#### [NEW] [telemetry.rs](file:///C:/Users/luism/Workbench/GitHub/context-pipe/crates/cpipe/src/telemetry.rs)
Calculates and updates the Context Balance Sheet (local JSON ledger) and formats the standard Markdown audit headers.

#### [NEW] [server.rs](file:///C:/Users/luism/Workbench/GitHub/context-pipe/crates/cpipe/src/server.rs)
Standard input/output JSON-RPC handler that registers and runs the MCP tools: `pipe_run`, `pipe_run_dynamic`, `pipe_read_file`, `pipe_analyze_file`, `pipe_list_shadow_tools`, and `get_pipe_stats`.

#### [NEW] [main.rs](file:///C:/Users/luism/Workbench/GitHub/context-pipe/crates/cpipe/src/main.rs)
The executable entry point parsing command-line parameters (`run`, `run-dynamic`, `list`, `stats`, `serve`) using `clap`.

---

## Verification Plan

### Automated Tests
* **Unit Tests**:
  * Config loading and schema merge validation.
  * Timeout guard correctness.
  * Node bypass validation (header detection).
  * Path probing robustness.
* **Integration Tests**:
  * Execute standard pipeline runs (e.g., feeding test streams to `cpipe run standard-distill`) and verifying character reduction.
  * Verify MCP JSON-RPC protocol compliance by feeding mock MCP stdio messages to `cpipe serve`.

### Manual Verification
* Compare binary startup latency against the Python package (`context-pipe`) using PowerShell's `Measure-Command`. Target startup latency is **<10ms**.
* Verify integration as a global MCP server in a test Antigravity session.
