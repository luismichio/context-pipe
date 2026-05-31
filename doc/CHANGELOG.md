# Changelog

All notable changes to the **Context-Pipe** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.6] — 2026-05-31

### Added
- Extended the `get_pipe_stats` tool and backend `get_balance_sheet` logic to support `session_id` and `last_hours` filtering for targeted context ROI reporting.
- Extended the `pipe_audit_last` tool to accept a `limit` parameter to retrieve a chronological range of recent telemetry events.
- Upgraded the `pipe_list_shadow_tools` tool to discover and display configured MCP servers from `pipes.json`, and format MCP nodes as `mcp:server/tool` for clearer agent visibility.
- Added comprehensive unit tests in `tests/test_range_telemetry.py` validating telemetry range filtering, chronological retrieval, and MCP shadow tool/server discovery.

### Fixed
- Changed the native `read` tool interception threshold in the pi.dev extension (`context-pipe.ts`) from 1KB (`1024` bytes) to 50KB (`51200` bytes) to resolve consistency issues with the Python BeforeTool hook and eliminate false-positive blocks on small files (REPORT_042).
- Resolved a `KeyError` bug in `pipe_audit_last` when attempting to read `total_latency_ms` instead of `latency_ms`.
- Improved docstrings for `pipe_run_dynamic` and `pipe_list_shadow_tools` to highlight Context Window Protection benefits and entice agent usage over raw terminal piping.

## [0.5.5] — 2026-05-31

### Fixed
- Added `encoding='utf-8'` and `encoding_error_handler='replace'` to `StdioServerParameters` in the Python engine to prevent `UnicodeDecodeError` crash on Windows when reading non-UTF-8 banner lines (REPORT_040).
- Re-implemented `read_jsonrpc_line` in the Rust engine to read raw bytes line-by-line using `read_until` and decode them lossily via `String::from_utf8_lossy` to prevent invalid UTF-8 bytes from throwing I/O decode errors (REPORT_040).
- Fixed `_run_mcp_node` in the Python engine to correctly append server-level `args` and use `posix=(os.name != "nt")` in `shlex.split` to prevent interactive shell hangs and `FileNotFoundError` on Windows (REPORT_041).

## [0.5.3] — 2026-05-30

### Fixed
- Implemented async context manager (`__aenter__`/`__aexit__`) and async iterator (`__aiter__`/`__anext__`) protocols on `_StdoutToleranceWrapper` to prevent errors in MCP stdio client sessions (REPORT_037).
- Re-implemented `resolve_placeholders` in Python and Rust to fail-fast with a `ValueError` / error result when encountering an unresolved pipe variable placeholder `${VAR}` instead of passing it literally to subprocesses (REPORT_038).
- Fixed orchestrator in Python and Rust to respect the node-level `timeout` override field specified in `pipes.json` (REPORT_039).

## [0.5.2] — 2026-05-30

### Fixed
- Fixed v0.5.1 onboarding `_inject_pi()` template tools execute handlers to return structured `{ content }` objects instead of raw strings to prevent pi session crashes (REPORT_034).
- Replaced `execSync` with `spawnSync` in `callCli` to prevent JSON parsing issues with unquoted shell arguments in `pipe_run_dynamic` (REPORT_035 Defect A).
- Re-implemented `pipe_analyze_file` in the onboarding template to perform a stat-only operation instead of full file read and piping (REPORT_035 Defect B).
- Configured 50 MB `maxBuffer` limit for CLI calls in the template to avoid silent truncation on large outputs (REPORT_035 Defect C).
- Re-implemented `tool_call` interceptor in the template to correctly return block directives for native `read` calls > 1KB (REPORT_035 Defect D / REPORT_036).
- Added `setStatus` indicators in the template auto-sift interceptor (REPORT_035 Defect E).

## [0.5.1] — 2026-05-30

### Fixed
- Fixed v0.5.0 onboarding `_inject_pi()` template fallback pipe name from `"auto"` to `"standard-distill"` for both `pipe_read_file` tool execution and auto-sift interceptor to prevent CLI failures.

## [0.5.0] — 2026-05-30

### ✨ Added
- **Phase 13: MCP Node Banner Tolerance**: Implemented banner tolerance in both Python and Rust engines to gracefully skip up to 50 non-JSON stdout lines emitted by noisy MCP servers during startup or tool execution. Added `verbose` flag to the server config schema to surface skipped lines to `stderr`.
- **Phase 12: Runtime Variable Injection & Run Manifests**: Ported Phase 12 variables and JSON run manifests from Rust to the Python engine (`context_pipe/orchestrator.py`, `server.py`, `cli.py`, `api.py`). Supports defaults, environment variables, invocation overrides, and serialization of run traces/telemetry.
- **Phase 11: Conditional Branching & Validator Nodes**: Upgraded the orchestration engine from a linear array to a full **Directed Acyclic Graph (DAG)** traversal in both Python (`context_pipe/orchestrator.py`) and Rust (`crates/cpipe/src/orchestrator.rs`).
  - **`condition` key** on any node: predicate-based skip logic. Supported predicates: `size:>N`, `size:<N`, `artifact:missing:<path>`, `artifact:exists:<path>`, `contains:<string>`. Unknown predicates fail-open (warn, then run) to avoid blocking pipelines.
  - **`type: "validator"` nodes**: run a subprocess and branch on its exit code. The `branches` map routes `"0"`, `"1"` (or any exit code string) to named node IDs or branch sequences. A `"default"` key provides a fallback; if no branch matches and there is no default, the node fails (respecting `optional`).
  - **`branch_sequences`**: top-level map of named sub-graphs. A validator branch target can be a bare sequence name (e.g. `"on-fail"`) — the engine enters the first node of that sequence automatically.
  - **`id` and `next` fields** on nodes: `id` assigns a stable string identifier for use as a branch target; `next` overrides the natural sequential flow to jump to any named node.
  - **100-step loop guard**: the DAG engine terminates with a structured `--- [Context-Pipe: Loop Guard] ---` error if a pipeline exceeds 100 steps, preventing infinite loops caused by misconfigured `next` cycles.
  - **Full Rust parity** in `crates/cpipe`: `Node` struct updated with `condition`, `branches`, `id`, `next`; `Pipe` struct updated with `branch_sequences`. `evaluate_condition()` and DAG traversal implemented identically to Python. 8 new Rust tests (6 unit + 2 integration) verify all predicates and validator branching.
- **Phase 9: Pipe Transparency Layer**: Implemented real-time pipeline log emission to `stderr` during node execution in both Python and Rust (`cpipe`) orchestrators. Logs are configured per-pipe via a `logging` block in `pipes.json` or fall back to `PIPE_LOG_LEVEL` and `PIPE_LOG_PREFIX` environment variables. Supports `compact` and `verbose` levels and customizable fields (`trigger`, `node`, `tokens`, `timing`).

- **Pre-execution Read Limit Adjustment**: Raised the pre-execution read block threshold to 50KB (51,200 bytes) in `before_tool` and `pipe_read_file` to support file reading workflows in redirection-heavy environments (like Google Antigravity CLI), while removing all line-range blocks and minimum range requirements.
- **Disk-Based Double-Sift Verification**: Implemented disk-based signature checks to verify if a file on disk has already been sifted, preventing double-sifting of chunked reads (e.g. `output.txt` reads).
- **Compact Audit Header**: Defaulted to `SIFT_AUDIT_HEADER="compact"` to omit the full stats table for sifting outputs, reducing the character footprint to just the 30-character signature line while preserving the double-sift guardrail.

### 🐛 Fixed
- **pi.dev extension `execute()` return type** (`context-pipe.ts`): All 6 tool `execute()` methods now return a proper `AgentToolResult` (`{ content: [{type: "text", text}], details: undefined }`) instead of a raw string. Returning a plain string caused `event.content` to be `undefined` in the pi runtime, triggering `Cannot read properties of undefined (reading 'some')`.
- **pi.dev extension — missing `"auto"` pipe**: Replaced non-existent `"auto"` pipe fallback with `"standard-distill"` in `pipe_read_file` and the `tool_result` auto-interceptor.
### 🐛 Fixed (previous)
- **pi.dev extension template (REPORT_031)**: Fixed all 5 defects in `_inject_pi()` generated TypeScript:
  - Tool execute signatures now use correct `(_toolCallId, params)` parameter positions instead of `(input)`
  - Fast path uses resolved `mcp-pipe` absolute path instead of bare `cpipe` (not on PATH)
  - `tool_result` handler reads `event.content?.[0]?.text` instead of undefined `event.result`
  - `tool_result` returns partial patch object instead of mutating event directly
  - Command handler uses `handler` property instead of ignored `execute`
### ✨ Added
- **Missing pi.dev tools**: Registered `list_pipes`, `pipe_analyze_file`, `pipe_run_dynamic` to match the mandate

## [0.4.7] — 2026-05-25
### ✨ Features & Parity
- **Onboarding CLI & Auto-Detect**: Added `onboard` subcommand to `mcp-pipe` CLI and enabled auto-detection in `pipe_onboard` MCP tool.
- **Global Entry Point**: Added `context-pipe-onboard` global console script for direct workspace initialization.
- **Documentation Alignment**: Purged stale `shell: true` references and synchronized use cases with the native execution model.

## [0.4.6] — 2026-05-25
### 🔧 Maintenance
- Internal version bump for documentation alignment release.

## [0.4.5] — 2026-05-24
### ✨ Features & Parity
- **Rust Core Full Parity (Bug REPORT_026)**: Upgraded the Rust `cpipe` orchestrator to achieve full functional parity with the Python implementation.
    - Added `tool` subcommand: Directly invoke MCP tools from the native Rust CLI.
    - Added `aliases` subcommand: Bridge to Python onboarding logic for managing shell aliases (`cpipe aliases install/remove`).
    - Added `snake_case` aliases: All CLI arguments (e.g., `--start-line`, `--input_file`) now support both kebab-case and snake_case for backward compatibility with existing automation scripts.
- **PowerShell `&` Call Operator in Hook Commands (Bug REPORT_027)**: `build_runtime_hook_command()` now prepends `& ` on Windows (`os.name == "nt"`). This ensures PowerShell treats double-quoted executable paths as commands rather than string literals, resolving `Unexpected token '-W'` errors.

### 🛡️ Hook Stability & System Integrity
- **Hook Idempotency & Aggressive Cleanup (Bug REPORT_024)**: Refactored `merge_hook_json` in `onboarding.py` to aggressively filter out all existing context-pipe hooks (including legacy/broken versions) before injecting the modern hook. This breaks the duplication loop and ensures stable configurations across sessions.
- **Vocal Config Resolution in Rust**: Modified `load_pipes_config_with_path` in `crates/cpipe/src/config.rs` to explicitly report errors and exit if a specified `--config` path fails to load, preventing silent and confusing fallbacks to the global configuration.
- **Unicode/Emoji Mitigation for Windows Interceptors**: Stripped all non-ASCII emojis from the source code print statements and batch scripts. This prevents `semantic-sift-cli` (and other stdout interceptors) from crashing with `UnicodeEncodeError: surrogates not allowed` when processing tool output on Windows.
- **Standardized Hook Naming**: Unified all platform-specific hook injections (Cursor, VS Code, GitHub) to include the `{"name": "context-pipe"}` field for more reliable discovery and deduplication.

## [0.4.4] — 2026-05-24
### 🐛 Fixed & Hardened
- **Rust Core Relaxed JSON Parsing (PowerShell)**: Implemented a robust relaxed JSON preprocessor (`normalize_relaxed_json`) for `run-dynamic` in `main.rs`. This handles PowerShell quote-stripping and key/value unquoting by dynamically translating relaxed structures into compliant JSON before deserialization.
- **Onboarding Import & Syntax Fixes**: Resolved a critical syntax error in `onboarding.py` where `def inject_mandates` was commented out due to a missing newline. Fixed `get_env_tool_names` return signature to guarantee `{}` instead of `None` for shielded platforms, restoring full green status (265/265 tests passing) to the unit test gauntlet.
- **Config-File Authorized Roots (`authorized_roots` in `pipes.json`)**: Added a top-level `authorized_roots` array to `pipes.json`. `_resolve_safe_path` in `server.py` now merges these roots with any `PIPE_AUTHORIZED_ROOT` env-var entries on every call. This allows cross-directory file access to survive client-side env-var overrides (e.g. `agy.exe` injecting a narrow workspace root), without requiring shell tricks or profile hacks. Security boundary is unchanged — paths outside all merged roots are still denied.

## [0.4.3] — 2026-05-24
### ✨ Features & Parity
- **Line Range Support in File Reading**: Added optional `start_line` and `end_line` parameters (1-indexed, inclusive) to `pipe_read_file` in both Python (`context_pipe/server.py`) and Rust (`crates/cpipe/src/server.rs`) implementations. This allows surgical reading of specific file segments while bypassing the rest of the file to save tokens.
- **Adaptive Gating Threshold for Range Reads**: Modified the proactive `BeforeTool` hook in `wrapper.py` to allow native file reads (`view_file`/`read_file`) with range arguments when the range is <= 50 lines. Updated `AfterTool` to bypass sifting for these allowed range reads and log bypass events to telemetry (which pushes a bypass pulse to Supabase).

### 🛡️ Hook Reliability & Environment Agnosticism
- **Agnostic Python Runtime Invocation (`[REAL-1]`)**: Replaced shell-specific env variable setting (like `$env:` or `set`) in hook commands with a shell-agnostic Python inline command (`python -c "..."`) that sets `sys.path` and environment variables natively.
- **Universal Proactive Gating (`[REAL-2]`)**: Moved file-size gating from Windsurf-specific shell variables directly into the Python `wrapper.py` layer. It now heuristically detects `BeforeTool` events and gates large native file reads (>1KB) across all platforms.
- **Decision Schema Support for Antigravity (`[REAL-3]`)**: Updated `inject_content()` in `platforms.py` to return the `{"decision": "deny", "reason": content}` schema for both Gemini CLI and Google Antigravity.
- **Extended Agent Label Extraction (`[REAL-4]`)**: Enhanced `extract_content()` in `platforms.py` to fetch subagent labels from generic payload keys (e.g. root `agent_label`/`agent` or metadata dictionary).
- **Broadened Hook Matchers (`[REAL-5]`)**: Broadened the hook matchers for Claude Code, Qwen CLI, and Codex CLI from `"mcp__.*__.*"` to `".*"` to ensure native tool calls are intercepted.
- **Silent Orchestrator Alignment**: Deleted the legacy `generate_audit_header` from `telemetry.py` and updated `cli.py` to direct verbose telemetry to `stderr` rather than `stdout`, completing the silent orchestrator design.
- **Gemini/Antigravity Hook Structure Fix**: Fixed the parser regression in `.gemini/settings.json` and `.agents/settings.json` by wrapping injected command hooks inside a `matcher` block (`{"matcher": ".*", "hooks": [...]}`).

## [0.4.2] — 2026-05-22

### 🛡️ CI/CD & Reliability
- **Linux Wheel Fix**: Skipped `i686` and `musllinux` builds to resolve `libatomic` dependency issues during Rustup installation.
- **macOS Build Fix**: Resolved `delocate-wheel` error by setting `MACOSX_DEPLOYMENT_TARGET` to `10.12`.
- **Binary Path Fix**: Corrected target paths in `release-binaries.yml`.

## [0.4.1] — 2026-05-22

### ⚫ Phase 8: The "Studio of Two" Endgame (Rust Core) — ✅ Complete
- **Rust Rewrite**: Ported the core stream orchestrator to Rust, achieving ultimate native speed and zero Python/Node memory bloat. (`crates/cpipe` — dual lib + bin targets, <2ms startup, 500× faster than Python cold-start.)
- **Tauri Synergy**: Integrated the Rust crate directly into Meechi/Side-Hustle as a native cognitive ingestion engine, eliminating the need for standalone sidecars. (`cpipe` documented as Tauri sidecar in `crates/cpipe/README.md`; `tauri.conf.json` setup + `Command::new_sidecar` examples included.)
- **Universal CLI (`cpipe`)**: Exposed the Rust engine as a compiled `cpipe` binary on PATH — same interface as `mcp-pipe` but zero Python dependency and <2ms startup. Supersedes the Phase 2 shell alias; users simply remove the alias once the binary is installed. (`cpipe run`, `cpipe list`, `cpipe stats`, `cpipe serve` subcommands live; `release-binaries.yml` publishes for Windows/macOS/Linux on every tag.)
- **Dual-Layer Agent Integration (The "Belt and Suspenders" Pattern)**: Researched and implemented a generalized approach for publishing `context-pipe` native packages for agent frameworks (e.g., Pi, OpenCode). This involves bundling an **Extension** (for programmatic tool replacement/interception) with a **SKILL.md** (for cognitive discovery and intent shaping), mimicking the highly effective architecture seen in the `context-mode` package. (Native wheels via `cibuildwheel` for PyPI; `setup.py` + `setuptools-rust` build backend; `scripts/fetch_cpipe.py` for non-Rust dev installs; `Cargo.toml` crates.io metadata complete.)

### 📦 Platform Packaging & Wheel Distribution
- **`crates/cpipe` Documentation**: Added comprehensive Rust library API usage examples, Tauri sidecar integration instructions, performance tiers comparison, and architectural details to the `crates/cpipe/README.md`.
- **Optional Native Build Backend**: Introduced a conditional `setup.py` that utilizes `setuptools-rust` to build the `cpipe` Rust binary when available, falling back gracefully to pure-Python builds for developer clones.
- **Binary Fetching Automation**: Created `scripts/fetch_cpipe.py` to allow developers on non-Rust environments to download pre-built native `cpipe` binaries directly from GitHub Releases.
- **PyPI Native Extra**: Added a `native` optional dependency group in `pyproject.toml` to mirror sister projects and represent native compilation.
- **Cross-Platform Wheel Publishing**: Upgraded `.github/workflows/release.yml` to compile native wheels for macOS, Linux (manylinux_2_28), and Windows using `cibuildwheel` and publish them to PyPI.

### ⚡ Rust Core Orchestrator (`cpipe`)
- **High-Performance Rust Core**: Porting the orchestrator and CLI parser to Rust (`cpipe` CLI and library) to achieve <10ms startup times, zero-dependency packaging, and cross-language wrappers (e.g. Tauri sidecars).
- **Dual-Runtime Coexistence**: Designed the Rust CLI as a high-performance alternative running alongside the primary Python-based FastMCP server.
- **TOML Configuration Support**: Added first-class support for `pipes.toml` alongside the legacy `pipes.json` configuration, introducing native comments, human-friendly syntax, and multi-line strings for pipeline nodes.
- **Crates.io Publication Readiness**: Created a comprehensive `README.md` and updated `Cargo.toml` metadata for `crates/cpipe` to support seamless crates.io publishing.
- **Multi-Platform Release Workflows**: Configured GitHub Actions workflow (`release-binaries.yml`) to compile and package `cpipe` executable assets for Windows, macOS, and Linux on tag releases, and integrated Rust automated testing into the CI pipeline (`ci.yml`).

### 🔄 Architectural Refactor: Blind Spot Resolution
- **Async Orchestration Spine**: Migrated the core execution engine from blocking `subprocess.Popen` to `asyncio.create_subprocess_exec`. This resolves the thread-lock bottleneck where heavy multi-agent concurrency would choke the FastMCP event loop.
- **Concurrent T-Pipes**: Refactored the T-pipe stream splitter (`_write_tee`) to run concurrently with node execution using `asyncio.gather` and `asyncio.to_thread`, eliminating sequential IO overhead.
- **Proactive Volume Alerting**: Implemented real-time payload monitoring in `wrapper.py`. `context-pipe` now proactively alerts the agent/user via `stderr` when unmapped tool calls exceed 10KB, preventing silent token leaks.
- **Unmapped Ledger Visibility**: Added "Unmapped Heavy Calls" to the telemetry ledger and rendered the metric in the `/pipe-stats` ROI Balance Sheet.
- **Subprocess Tax Diagnostics**: Added a performance check in `onboarding.py` that identifies interpreted Python nodes and advises migration to pre-compiled binaries (e.g., Rust `sift-core`) to eliminate the 100ms startup tax.
- **State Isolation Warning**: Addressed the "Lossy Hook-in Trap" by updating global mandates and audit headers. Agents are now strictly warned that distillation mutates line numbers and must rely on search/AST tools for surgical edits.

### 🛡️ Google Antigravity CLI Integration
- **Unified Onboarding**: Added native support for the new Antigravity environment (`agy`). Onboarding now automatically targets the `.agents/` directory structure.
- **Markdown Rules Integration**: Automatically injects slash commands (`/pipe-stats`, `/pipe-run`, etc.) as Markdown files with YAML frontmatter into `.agents/rules/`.
- **Global MCP Security**: Enabled secure global MCP registration in `~/.gemini/antigravity/mcp_config.json`. Introduced `PIPE_AUTHORIZED_ROOT` environment variable to securely sandbox globally-launched servers to local project roots without requiring `SIFT_ALLOW_GLOBAL_READS`.
- **Hook Lifecycle Support**: Verified and implemented support for `AfterTool` and `PreCompress` hooks in Antigravity's `.agents/settings.json`.

## [0.3.4] — 2026-05-18

### 🔄 Architectural Refinement: Sift-Centric Transparency
- **Silent Orchestrator**: Transitioned `context-pipe` into a fully transparent layer. The orchestrator no longer generates audit headers or appends signatures, significantly reducing agent context clutter.
- **Vocal Engine Integration**: Delegation of visible identity and headers to engine nodes (e.g., `semantic-sift`).
- **Unified ROI Ledger**: Refactored `telemetry.py` to utilize the `semantic-sift` local ledger when available, ensuring a single "Context Balance Sheet" for the Studio of Two ecosystem.
- **One Pulse Mandate**: Enforced the "One Pulse" rule where only the engine layer performs cloud telemetry pulses, preventing double-counting.
- **Self-Aware Bypass**: Replaced rigid orchestrator signatures with engine-level self-awareness to prevent double-sifting while allowing transparent multi-node piping.

### 🐛 Fixed (Subconscious Infrastructure)
- **Robust Content Extraction**: Fixed a critical bug in `platforms.py` where Gemini CLI hooks would bypass documentation reads due to stringified JSON envelopes and a dangerous greedy fallback to the system tool list.
- **Project Root Discovery**: Enhanced the orchestrator to automatically discover `pipes.json` by traversing upwards from the CWD until a `.git` boundary is hit, ensuring consistent sifting in subdirectories.
- **Nesting-Aware Telemetry Discovery**: Updated the telemetry opt-in check to recursively search for the `SIFT_TELEMETRY_OPTED_IN` key within `.gemini/settings.json`, resolving a gap where pulses were silenced in Gemini CLI hook subprocesses.

## [0.3.3] — 2026-05-14

### 🛡️ Phase 10: Dynamic Sandboxing via MCP Roots
- **Dynamic Context Bounds**: Integrated the `ServerSession.list_roots()` MCP API to dynamically discover workspace boundaries from connected clients (e.g., VS Code, Antigravity) at runtime, gracefully falling back to the current working directory if roots are unsupported.
- **Global Read Deprecation**: Formally deprecated and removed the static `SIFT_ALLOW_GLOBAL_READS` and `SIFT_WORKSPACE_ROOT` environment variable guards, cementing the client-provided `roots` list as the sole source of truth for authorization in `_resolve_safe_path`.
- **Hardened Onboarding**: Updated the `onboarding.py` mandate injection to use a high-priority `CRITICAL INSTRUCTION` format with consequence framing, specifically designed to combat "System Prompt Dominance" in environments without structural tool hooks (like Antigravity). Mandates are now prepended to the top of instruction files.

### 🛡️ Architecture & Security Audit Resolution
- **Onboarding Monolith Refactoring**: Decomposed the 400-line `inject_hooks` monolith in `context_pipe/onboarding.py` into distinct environment-specific functions (e.g., `_inject_cursor`, `_inject_vscode_github`) to improve maintainability.
- **Telemetry O(1) Migration**: Refactored `context_pipe/telemetry.py` to use an append-only JSON Lines (`.jsonl`) schema. This resolves the `O(n)` read/write contention that previously degraded performance under high-frequency sifting.
- **Python Logging Standardization**: Eliminated raw `sys.stderr.write` and `print` statements in `wrapper.py`, `orchestrator.py`, and `server.py`, replacing them with standard Python `logging` for structured output control.
- **Quality Gates Hardening**: Restored the CI `pytest` coverage gate to `83%` in `.github/workflows/ci.yml` and added `bandit` to the `[project.optional-dependencies] dev` block in `pyproject.toml` to align local and CI execution of `audit.bat`.
- **Documentation Fidelity**: 
  - Aligned `SHELL_UTILITY_ALLOWLIST` in `ARCHITECTURE.md` to precisely reflect the 20 actual tools permitted by `dynamic.py`.
  - Removed outdated references to `shell: true` and `PIPE_WINDOW_PRESSURE`.
  - Updated legacy signatures in `CONTEXT_PIPE_PROTOCOL.md` to use the engine-level audit header.

## [0.3.1] — 2026-05-13

### 🛡️ Orchestration & Fidelity
- **Update Awareness & Self-Heal [Bug REPORT_019]**: Integrated a GitHub-backed version checker into the orchestrator. The `pipe_verify` and `pipe_onboard` tools now proactively alert the user when a newer version is available in the repository, reducing setup fatigue and ensuring environment parity.
- **Stream Integrity & UTF-8 Robustness [Bug REPORT_020]**: Hardened the orchestrator against protocol violations caused by non-UTF8 output. Subprocess streams are now decoded using `errors="replace"`, and internal reading threads have been made null-safe, preventing session crashes when nodes output binary data or garbage bytes.

## [0.3.0] — 2026-05-12

### ✨ Features & Fidelity
- **Recursive Placeholder Resolution [Bug REPORT_013]**: Upgraded the environment variable resolver to be fully recursive. The orchestrator now resolves `${VAR}` tokens anywhere in the `pipes.json` configuration, including node arguments, script parameters, and nested server settings. This enables "Adaptive Window Pressure" by allowing pipes to dynamically adjust behavior based on host environment signals.
- **Trust & Audit System**:
    - **`pipe_audit_last`**: New MCP tool for agents to verify the absolute last recorded sifting event against the on-disk telemetry ledger.
    - **`CPP_DEBUG=true`**: New human-facing debug mode using `stderr` to print real-time sifting decisions (Intercepted vs. Bypassed) directly to the chat interface without polluting JSON payloads.
- **Loop Protection for Admin Tools**: Added `CPP_SIGNATURE` to all administrative MCP tools (`pipe_audit_last`, `get_pipe_stats`, `pipe_verify`, etc.) to prevent recursive sifting loops.
- **Windows Unicode Robustness [Bug REPORT_014]**: Added a `_reconfigure_io()` utility to both the CLI and Orchestrator entry points. This forcefully reconfigures `stdout`/`stderr` to use UTF-8 on Windows, preventing `UnicodeEncodeError` crashes when printing emojis in the Audit Header or Balance Sheet.
- **Resilient Orchestration [Bug REPORT_015]**: Introduced the `optional: true` flag for pipe nodes. If a node is marked as optional, the orchestrator will record any failure (Timeout, FileNotFound, or Exit Code) in the trace but will continue executing the remaining nodes in the pipe instead of aborting.
- **Hook Configuration Fidelity [Bug REPORT_017]**: Fixed an issue where the Gemini CLI hook would ignore critical environment variables. The onboarder now injects `GEMINI_SESSION_ID` and `PYTHONPATH` directly into the `command` string using platform-aware shell syntax, ensuring protocol compliance and module discovery.
- **Subconscious Noise Floor**: Integrated a 500-character floor to automatically silence `Blocked` UI messages for tiny status updates and edits.
- **Reference Updates**: Updated `pipes.json.example` to showcase the new `optional` flags and recursive `${VAR}` resolution patterns.

---

## [0.2.8] — 2026-05-11

### 🛡️ Orchestration & Telemetry
- **Gemini CLI Bypass Schema [Bug REPORT_011]**: Introduced a platform-aware bypass mechanism in the orchestrator wrapper. When a context pipe is bypassed (due to size, structured data, or echo detection), the system now correctly returns the `{"decision": "allow"}` schema required by the Gemini CLI, fixing "Hook failed" errors during transparent passthrough.
- **Robust Exception Fallback [Bug REPORT_012]**: Updated the "Absolute Safety" fallback logic in both `pipe_hook.py` and `context_pipe/orchestrator.py` to be platform-aware. Internal Python exceptions (like import errors or IO failures) now correctly return a `{"decision": "allow"}` response to the Gemini CLI instead of raw JSON, preventing IDE warnings on error paths.

---

## [0.2.7] — 2026-05-11

### 🛡️ Orchestration & Telemetry
- **Audit Header Robustness [Bug REPORT_001]**: Fixed a `KeyError` crash in `generate_audit_header` when generating trace logs for nodes that fail during execution.
- **CLI Registry Leak [Bug REPORT_001]**: Fixed an issue where the `mcp-pipe run` and `run-dynamic` CLI commands failed to pass the server registry to the orchestrator, which previously broke MCP node resolution.
- **MCP Command Parsing [Bug REPORT_001]**: Improved `_run_mcp_node` to safely handle server configurations where the `command` is defined as a string instead of a list (using `shlex.split`).
- **Windows PATH Resolution [Bug REPORT_003]**: Fixed a binary discovery failure on Windows by explicitly passing the venv-aware `PATH` environment variable to `shutil.which()`.
- **Silent Telemetry Gap [Bug REPORT_007]**: Changed the telemetry consent gate from opt-in to opt-out by default. This aligns the codebase with the project's documentation, ensuring that ROI and Context Balance Sheet statistics are automatically recorded unless explicitly disabled.
- **Intelligent Hook Deduplication [Bug REPORT_008]**: Updated `merge_hook_json` to intelligently replace older versions of a hook (such as those missing necessary environment variables) instead of aggressively skipping when the core command is already present. This fixes the Gemini CLI environment detection failure.
- **Python RuntimeWarning Suppression [Bug REPORT_009]**: Injected `-W ignore` into `build_runtime_hook_command()` to prevent native Python warnings from corrupting the JSON output stream expected by the hook pipelines.
- **Gemini CLI Hook Timeout [Bug REPORT_010]**: Added explicit `"timeout": 10000` to the Gemini CLI `AfterTool` and `PreCompress` hook configurations. This prevents the CLI from prematurely terminating the context sifting process due to Python's cold-start latency, especially on Windows or inside fragmented virtual environments.

---

## [0.2.5] — 2026-05-11

### 🛡️ Onboarding & Core
- **Hook Idempotency [Bug REPORT_005]**: Refactored `merge_hook_json` to utilize core-target command normalization. Onboarding now correctly detects duplicate hook registrations even when the Python interpreter path changes (e.g., between global and venv runs).
- **Robust Path Creation**: Fixed a Windows-specific robustness bug in `merge_hook_json` where `os.makedirs` was called on empty directory strings.
- **Gemini CLI Protocol Alignment [Bug REPORT_006]**: Updated the payload injection logic for Gemini CLI to return the specific "Decision" schema (`decision: deny`). This ensures sifting results are correctly recognized by the platform's hook system.

---

## [0.2.4] — 2026-05-11

### 🛡️ Onboarding & Safety
- **Gitignore Automation [Bug REPORT_002]**: The `pipe_onboard` tool now automatically appends internal artifacts (`.pipe_cache/`, `.pipe_identity`, `.pipe_telemetry.json`) to the project's `.gitignore` file, preventing accidental commits of local cache and telemetry data.
- **Robust Hook Injection [Bug REPORT_004]**: Improved the `merge_hook_json` utility to recursively detect and deduplicate commands within nested "matcher" structures. This ensures cleaner hook registration for environments like Gemini CLI and Claude Code.
- **Full Gemini CLI Lifecycle Support**: Enhanced Gemini CLI onboarding to inject both `AfterTool` (for real-time tool sifting) and `PreCompress` (for lifecycle context compaction) hooks into `.gemini/settings.json`.

---

## [0.2.3] — 2026-05-10

### ✨ Zero-Config Onboarding
- **Automated `pipes.json` Creation**: The `pipe_onboard` tool now automatically creates a default `pipes.json` configuration file if one does not exist in the target directory. This removes the manual "copy and rename" step for new projects.
- **Default High-Fidelity Templates**: The auto-generated config includes production-grade definitions for `standard-distill` (logs) and `semantic-refinery` (neural code compression), along with pre-configured routing mappings.
- **Improved Installation Resilience**: Enhanced the auto-linking logic to ensure that even a freshly created `pipes.json` is immediately populated with the correct absolute path to `semantic-sift-cli` if discovered.

---

## [0.2.2] — 2026-05-09

### ✨ Fidelity & Safety Upgrade
- **Test Suite Hardening**: Initiated a technical test audit and closed the logic "blind spots." Added `tests/test_server.py` to verify the MCP server layer.
- **Coverage Ratchet**: Project-wide test coverage raised from **73% to 83.7%**, satisfying the mandatory architectural quality gate.
- **Bug Fix — `server.py`**: Fixed a critical bug in the `pipe_read_file` MCP tool where it was returning a raw coroutine object instead of waiting for the distilled text. The tool is now properly `async` and awaited.
- **Improved Isolation**: Refined sandbox testing patterns using `tmp_path` to ensure zero side effects on the developer's machine during local test runs.

---

## [0.2.1] — 2026-05-09

### Changed
- **Architectural Shift: Skills to Scripts**: Refactored the "Skill Node" concept to clearly distinguish between deterministic local transformations and semantic A2A handoffs.
    - **Local Nodes**: Rebranded as **Script & Mandate Nodes**. Introduced `type: "script"` in `pipes.json` which resolves `.py` (executes) or `.md` (prepends as mandate) from `.gemini/scripts/`.
    - **Multi-Agent Skills**: Scoped the concept of "Skills" exclusively to **A2A Agent Handoffs** (`a2a.py`). Skills are now defined as semantic lenses applied during handoff, with a roadmap toward SLM-backed structural rewriting (Phase 5).
- **Core Modules**:
    - Renamed `context_pipe/skills.py` to `context_pipe/scripts.py`.
    - Updated `orchestrator.py` to provide first-class support for `type: "script"` with automatic path resolution and interpreter matching.
    - Updated `pyproject.toml` to register `context-pipe-script` and deprecate `context-pipe-skill`.
- **Documentation**:
    - **`README.md`**: Updated vision and feature matrix to reflect the Script/Mandate terminology.
    - **`doc/ARCHITECTURE.md`**: Rewrote Section 6 (Script & Mandate Node) and Section 8 (A2A) to formalize the new boundary.
    - **`doc/USE_CASES.md`**: Updated all local examples to use Mandate Nodes.
    - **`doc/OPERATOR_GUIDE.md`**: Updated configuration and CLI reference.
- **Tests**:
    - Renamed `tests/test_skills.py` to `tests/test_scripts.py` and updated logic to cover the new dispatcher.

---

## [0.2.0] — 2026-05-09

### ✨ High-Fidelity Foundation
- **Initial Release**: The official birth of the **Context-Pipe Protocol (CPP)**.
- **Universal Orchestrator**: Python-based engine (`orchestrator.py`) capable of streaming data through multi-node Unix pipelines using standard `stdin`/`stdout`.
- **Bash Node Support**: Added the ability to execute arbitrary shell commands (e.g., `grep`, `sed`, `awk`) directly within a context pipe using the `shell: true` flag.
- **Skill Node Wrapper**: Implemented `context-pipe-skill`, a specialized node type that allows agents to apply "Expert Lenses" (specialized instruction sets) to the context stream.
- **Terminal CLI Mastery**: Established `context-pipe run` as the definitive terminal standard for context engineering, supporting standalone file sifting and complex bash chaining.
- **Agnostic Routing Engine**: Implemented a dynamic `mappings` system in `pipes.json`. The system now automatically routes data to the optimal pipe based on:
    - **Tool Triggers**: Regex-based matching for tool names (e.g., `search|grep|find`).
    - **Size Triggers**: Automatic scaling of distillation based on character count thresholds.
- **Universal Context Hook**: A platform-aware interceptor (`pipe_hook.py`) that subconsciously applies context pipes to tools in **Cursor, VS Code, Gemini CLI, and Claude Desktop**. OpenCode uses a TypeScript plugin scaffold and `AGENTS.md` SOP mandate instead (see [sst/opencode#21149](https://github.com/sst/opencode/issues/21149)).

### 📊 Context Accounting & ROI
- **Context Balance Sheet**: Advanced telemetry engine that tracks "Signal Injected" (Augmentation) vs. "Noise Incinerated" (Reduction) across the entire supply chain.
- **Node-Level Tracing**: The orchestrator now records input/output sizes and latency for every individual node in a stream.
- **High-Fidelity Visibility**: Prepend a Markdown Audit Header to every distilled output, providing real-time feedback on reduction percentage, latency, and node-trace.
- **MCP ROI Tools**: Added `get_pipe_stats` tool and a high-fidelity `pipe_dashboard` prompt to make context health visible to AI agents.

### 🛡️ Graceful Resilience & Security
- **Async Timeout Guards**: Implemented node-level execution timeouts (default 10s) to prevent stalled pipes from hanging IDE agents.
- **The Echo Guard**: Integrated a disk-based hash detector to automatically bypass content processed within the last 30 seconds, preventing infinite loops and compute waste.
- **Dependency Awareness**: Implemented a `help_msg` system in `pipes.json`. If a required tool (like `sift-core` or `markitdown`) is missing from the system PATH, Context-Pipe returns a structured, helpful instruction instead of crashing.
- **Subagent Tracking**: Added high-fidelity `agent_label` extraction for **Cursor** ([Explore]/[Bash]) and **Gemini** threads, ensuring accurate ROI attribution.

### 🏗️ Infrastructure & Onboarding
- **Automated Hook Injection**: Added `pipe_onboard` MCP tool to automatically configure `.cursor/hooks.json`, `.github/hooks/`, and `opencode.json` with the absolute path to the Context-Pipe wrapper.
- **High-Fidelity Scaffolding**: Established the Studio of Two project standard, including `AGENTS.md` mandates, `task.md` tactical tracking, and `backlog.md` strategic planning.
- **Apache 2.0 Licensing**: Released under the Apache 2.0 license to facilitate industrial and enterprise adoption.

### 🧩 Integrated Features (Phased Rollout)

#### Phase 7.6 — mcp-pipe tool subcommand
- **`mcp-pipe tool <server> <tool>` subcommand** [NEW]: Directly invoke any registered MCP tool from the shell. Supports `--arg key=value` for static arguments, `--input-key` to override target field, and `-v` for telemetry. Seamlessly pipes `stdin` to MCP tools and `stdout` to the next shell process.

#### Phase 7.5 — MCP Node Type (Spec)
- **`doc/MCP_NODE_SPEC.md`** [NEW]: Full design specification for the `mcp` node type — first-class MCP tool invocation as a `pipes.json` node. Covers schema (`type`, `server`, `tool`, `input_key`, `servers` registry block), runtime architecture (`_run_mcp_node()` via `mcp.client.stdio` + `ClientSession`), async promotion strategy for `run_pipe()`, Echo Guard node-scope fix, `_validate_nodes()` extension rules, and a 5-phase implementation plan (7.5-A through 7.5-E).
- **`backlog.md`**: Phase 7.5 added with all sub-tasks itemised.

#### Phase 7.5 — Bash/Shell Synergy
- **`context_pipe/dynamic.py`**: `SHELL_UTILITY_ALLOWLIST` — `frozenset` of 21 safe data-processing shell utilities (`bash`, `sh`, `awk`, `sed`, `grep`, `cut`, `sort`, `uniq`, `tr`, `head`, `tail`, `wc`, `cat`, `echo`, `printf`, `xargs`, `python`, `python3`, `jq`, `yq`).
- **`context_pipe/dynamic.py`**: `_SIFT_TERMINAL_CMDS` — terminal-node guard: any pipe containing a shell utility must end with `semantic-sift-cli` or `sift`.
- **`context_pipe/dynamic.py`**: `_validate_nodes()` extended with `allow_shell: bool = False` parameter. Shell utility nodes rejected by default; when `allow_shell=True` the allowlist and terminal-node rule are enforced.
- **`context_pipe/dynamic.py`**: `run_dynamic_pipe()` now accepts `allow_shell: bool = False` and forwards it to `_validate_nodes()`.
- **`context_pipe/server.py`**: `pipe_run_dynamic` MCP tool now accepts `allow_shell: bool = False` parameter; forwarded to `run_dynamic_pipe()`.
- **`tests/test_dynamic.py`**: 9 new tests for allowlist membership, terminal-node enforcement, allow_shell flag toggling, and end-to-end shell utility pipe execution. Total: 16 tests.

#### Phase 7.4 — mcp-pipe CLI
- **`context_pipe/cli.py`** [NEW]: `mcp-pipe` terminal runner — five subcommands: `run`, `run-dynamic`, `list`, `stats`, `serve`. No IDE required.
  - `run <pipe_name>` — executes a named pipe on stdin or `--input-file`; optional `-v` audit header.
  - `run-dynamic '<nodes_json>'` — ad-hoc node array via `run_dynamic_pipe()`; shell metachar guard inherited.
  - `list` — grouped output of configured pipes + PATH tools (delegates to `list_shadow_tools()`).
  - `stats` — prints the Context Balance Sheet.
  - `serve` — starts the MCP server (stdio transport).
- **`pyproject.toml`**: `mcp-pipe` console script entry point registered.
- **`tests/test_cli.py`** [NEW]: 21 tests covering parser, `_read_input`, all five subcommand handlers, error paths, and verbose mode.

#### Phase 7.3 — ~/.mcp-pipe.json Standalone Config
- **`context_pipe/config_loader.py`** [NEW]: `load_pipes_config()` — local + global config merge with silent fallback. Local entries take precedence; duplicates by name resolved in favour of local.
- **`context_pipe/server.py`**: `load_config()` replaced with `config_loader.load_pipes_config()`.
- **`tests/test_config_loader.py`** [NEW]: 6 tests for local-only, global fallback, merge, both-absent, malformed-local, and global path resolution.

#### Phase 7.2 — Shadow Tool Discovery
- **`context_pipe/shadow.py`** [NEW]: `list_shadow_tools()` — combined configured-pipe + PATH tool discovery. Probes curated list of 7 well-known CLI tools (`jq`, `yq`, `markitdown`, `pandoc`, `rg`, `fd`, `bat`).
- **`context_pipe/server.py`**: `pipe_list_shadow_tools` MCP tool registered; renders results as a markdown table.
- **`tests/test_shadow.py`** [NEW]: 5 tests for tool discovery, PATH probing, missing config, and list ordering.

#### Phase 7.1 — Dynamic Pipes
- **`context_pipe/dynamic.py`** [NEW]: `run_dynamic_pipe()` — execute ad-hoc node arrays without a pipes.json entry. Security boundary: shell metacharacters in `cmd` rejected via `ValueError`.
- **`context_pipe/server.py`**: `pipe_run_dynamic` MCP tool registered.
- **`tests/test_dynamic.py`** [NEW]: 7 mock-subprocess tests for dynamic pipe execution, multi-node chaining, and security boundary.

#### Phase 6.2 — A2A Agent Handoff
- **`context_pipe/a2a.py`** [NEW]: `pipe_agent_handoff(output, pipe_name, from_agent, to_agent)` — framework-agnostic distillation bridge for A2A handoffs. Works with CrewAI, Google ADK, LangGraph, or any custom framework via explicit call. Falls back to original output on any error.
- **`context_pipe/server.py`**: `pipe_agent_handoff` MCP tool registered.
- **`tests/test_a2a.py`** [NEW]: 5 tests — distillation, `from_agent` forwarding as `tool_name`, error fallback, empty-input passthrough, telemetry event with agent labels.

#### Phase 6.1 — T-Pipes (Stream Splitting)
- **`context_pipe/orchestrator.py`**: `_write_tee()` private function — synchronous local-file sink. Writes raw node input + separator line before the node subprocess runs. Errors swallowed silently; tee failure never interrupts the chain.
- **`pipes.json` schema**: nodes may declare a `tee` object with fields `sink` (`"file"` only), `path` (supports `{iso_date}` and `{tool_name}` tokens), and `mode` (`"append"` default or `"overwrite"`).
- **`run_pipe()`**: tee fires before `subprocess.Popen` on any node declaring `tee`; trace dict extended with `"tee_path"` key.
- **`tests/test_tee.py`** [NEW]: 6 mock-subprocess contract tests — raw input written, append/overwrite modes, token substitution, silent failure, trace extension.

#### Phase 4 — Package Structure & API Clarity
- **`context_pipe/api.py`** (`pipe()` function): New programmatic Python API. `from context_pipe import pipe` exposes a single `pipe(text, pipe_name, tool_name, config_path)` function for direct integration without MCP or CLI. Always returns input unchanged on error.
- **`context_pipe/__init__.py`**: Exports `pipe` at package level.
- **`context_pipe/orchestrator.py`** (`load_config()`): Extracted inline config loading from `main()` into a standalone function.
- **Removed `shell: true` node support** (`orchestrator.py`): All subprocess invocations now use `shell=False` unconditionally.
- **Runtime path resolution for pipe nodes** (`orchestrator.py`): Added `resolve_node_cmd()` — 4-stage fallback: absolute path, `shutil.which()`, `~/.local/bin`/`PIPX_BIN_DIR`, bare name passthrough.
- **`pipes.json`**: Replaced all hardcoded absolute paths with bare command names. File is now portable.

#### Phase 4 — Slash Command Injection (OpenCode + Cursor)
- **`context_pipe/onboarding.py`**: `inject_hooks()` OpenCode block now injects `/pipe-run` command alongside `/pipe-stats`. Both commands written to `opencode.json` `command` block with description + template.
- **`context_pipe/onboarding.py`**: Cursor injection now creates `.cursor/rules/pipe-stats.mdc` and `.cursor/rules/pipe-run.mdc` — idempotent agent-rule files that expose `/pipe-stats` and `/pipe-run` as first-class Cursor slash commands.
- **`tests/test_onboarding.py`**: 4 new tests covering Cursor rule file creation, idempotency, OpenCode `/pipe-run` injection, and description presence.

#### Phase 3 — Security & Privacy Hardening
- **Opt-In Telemetry**: Flipped gate from opt-out to opt-in. Telemetry is now a no-op unless `CPP_TELEMETRY_OPTED_IN=true` is explicitly set. Legacy `CPP_TELEMETRY_DISABLED=true` kill-switch retained for backward compatibility.

#### Phase 2 — Standard Shell Aliases
- **`context_pipe/onboarding.py`**: `inject_shell_aliases()` — idempotently writes a managed `cpipe` alias block (`alias cpipe='mcp-pipe'` on POSIX, `Set-Alias` on PowerShell) into detected profile files. `remove_shell_aliases()` clears the block for Phase 8 Rust binary adoption. Both functions are platform-aware: POSIX on Linux/macOS, PowerShell on Windows.
- **`context_pipe/cli.py`**: `mcp-pipe aliases install [--shells bash zsh pwsh]` and `mcp-pipe aliases remove` subcommands.
- **`context_pipe/server.py`**: `pipe_install_aliases` and `pipe_remove_aliases` MCP tools registered.
- **`tests/test_aliases.py`** [NEW]: 20 tests covering block detection, upsert/append/update/skip, POSIX/PowerShell injection, platform guard, remove, and CLI subcommand parsing.

#### CPP Contract Test Suite
- **`tests/test_cpp_contract.py`** [NEW]: 6 mock-subprocess contract tests for `run_pipe()` covering happy path, multi-node chaining, non-zero returncode, `FileNotFoundError` + `help_msg` surfacing, timeout kill + trace, and empty-nodes passthrough.
- **`tests/test_api.py`**, **`tests/test_skills.py`**, **`tests/test_platforms.py`**, **`tests/test_onboarding.py`** [NEW]: Coverage uplift tests.

### 📖 Documentation & UX Uplift

#### README Vision, Ecosystem & Shadow MCP Registry
- **`README.md` — Vision section**: Rewritten from one sentence to a full problem statement. Explains the core infrastructure problem (raw tool output flooding context windows), the CPP supply chain model, and enumerates all node types (binary, shell, script, Skill, MCP *(Phase 7.5)*). Added an end-to-end example pipeline with inline token counts and a Context Balance Sheet summary (illustrative: 18,400 → 380 tokens, 97.9% saved).
- **`README.md` — Core Components**: Expanded from 3 stubs to 6 fully described components: CPP Protocol, Orchestration Spine, Universal Switchboard, MCP Surface, Subconscious Interceptors, A2A Bridge.
- **`README.md` — Shadow Tool Discovery → Shadow MCP Registry**: Section renamed and substantially expanded. Now explains the MCP tool bloat problem, the shadow/hidden-until-discovered pattern, the known limitation (tools not directly callable), and terminal access via `mcp-pipe list` + dynamic pipe example.
- **`README.md` — `✨ What Makes This Different` table**: Shadow MCP Registry row updated with full explanation of installed-but-hidden server pattern, bloat prevention, and example shadow tool categories.
- **`README.md` — Tool Synergies & Boundaries** [NEW section]: Comparison table for context-pipe, semantic-sift, context-mode, and Serena covering layer, role, and relationship. "When to use which" decision guide. "Complementary setup" subsection explaining how each tool independently reduces token pressure and how context-pipe compounds the savings automatically. Links to [context-mode](https://github.com/mksglu/context-mode) and [Serena](https://github.com/oraios/serena).
- **`doc/INDEX.md`**: Updated all section entries to reflect current state — added MCP_NODE_SPEC entry, updated OPERATOR_GUIDE topics (T-Pipe, MCP node, shell aliases, Agent SOP), updated ARCHITECTURE topics (§9–§11), updated USE_CASES topics (firecrawl).
- **`doc/OPERATOR_GUIDE.md` — §3 Node Types**: Added §D T-Pipe Nodes and §E MCP Nodes *(Phase 7.5)*; renamed existing §D/§E to §F/§G.
- **`doc/ARCHITECTURE.md` — §11 Slash Command Injection**: Updated slash command table from 2 to 4 commands — added `/pipe-dynamic` and `/pipe-handoff`.
- **`doc/USE_CASES.md` — §3 Web Synthesizer**: Updated from `curl` + raw HTML pattern to Firecrawl MCP node (Shadow MCP pattern). Explains shadow registration, Phase 7.5 dependency, and fallback for current use.
- **`backlog.md` — Phase 9**: Pipe Transparency Layer added — `[PIPE]` real-time stderr logs with customizable level (`summary`/`compact`/`verbose`), fields (`trigger`, `node`, `tokens`, `timing`), prefix, and per-pipe `logging` block in `pipes.json`.

#### Agent SOP & Full-Capability Activation
- **`context_pipe/onboarding.py` — `inject_mandates()`**: Mandate block rewritten from 3 bullet points to a full 5-section SOP injected into `AGENTS.md` and all instruction files. Now covers: (1) File & Large-Output I/O, (2) Named Pipes decision guide, (3) Dynamic Pipes workflow (`pipe_list_shadow_tools` → construct → `pipe_run_dynamic` with rules and example), (4) A2A Handoff trigger conditions, (5) Observability via Balance Sheet.
- **`context_pipe/onboarding.py` — `inject_hooks()`**: Slash command count raised from 2 to 4 across all IDEs. `/pipe-dynamic` and `/pipe-handoff` added with full step-by-step agent workflows. `/pipe-run` and `/pipe-stats` templates upgraded from stubs to actionable decision sequences. Affects: Cursor (`.mdc` rules), Gemini CLI (`.toml` commands), OpenCode (`opencode.json` commands block).
- **`context_pipe/server.py` — tool docstrings**: `pipe_analyze_file`, `pipe_list_shadow_tools`, `pipe_run_dynamic`, and `pipe_agent_handoff` docstrings upgraded with mandatory workflow sequences, decision guides, concrete examples, and explicit "when to call" triggers — making them self-instructing for any LLM reading the tool schema.
- **`doc/OPERATOR_GUIDE.md`**: Added §9 Agent SOP — Full Capability Reference with decision tree, tool reference table, and slash command table.

#### Staleness Fixes
- **`README.md`**: Updated test badge from 105 → 177 passing. Added `✨ What Makes This Different` feature matrix near the top (10 rows: MCP Node Type, Dynamic Pipes, Shadow Tool Discovery, A2A Handoff, T-Pipe, Adaptive Window Pressure, Global Config, Shell Alias Injection, Context Balance Sheet). Added `⚙️ Environment Variables` section. Expanded `pipe_onboard` auto-detect note. Replaced stub Terminal Usage section with full `mcp-pipe` CLI reference. Added MCP node type (§4, Phase 7.5 preview) to Advanced Node Types.
- **`doc/ARCHITECTURE.md`**: Added §9 Dynamic Pipe Engine (`allow_shell`, `SHELL_UTILITY_ALLOWLIST`, `_SIFT_TERMINAL_CMDS`), §10 Global Configuration (`~/.mcp-pipe.json` merge logic), and §11 Slash Command Injection (Phase 4 IDE command injection + Phase 2 shell alias injection).
- **`doc/OPERATOR_GUIDE.md`**: Expanded §7 Auto-Onboarding — added `pipe_onboard` auto-detect note, added step 6 (Slash Command Injection) to "What Onboarding Does". Added §7b Shell Aliases with install/remove instructions for bash/zsh/PowerShell.

---

## [0.1.5] - 2026-05-07

### Fixed
- **`pyproject.toml`**: Added `[tool.pytest.ini_options] testpaths = ["tests"]` to prevent pytest from collecting `test_search.txt` (a binary fixture file at repo root) as a test module.

---

## [0.1.4] - 2026-05-07

### Fixed
- **`doc/INTEGRATION_ENCYCLOPEDIA.md`**: Fixed Claude Desktop config paths for Win/Mac.
- **`doc/INTEGRATION_ENCYCLOPEDIA.md`**: Fixed broken quote in Qwen CLI row (`~/.qwen/settings.json"` → correct backtick).
- **`doc/OPERATOR_GUIDE.md`**: Removed trailing orphan `*` lines at end of file.
- **`README.md`**: Added ℹ️ callout explaining `sift-core` Rust binary is pre-compiled in the PyPI wheel; corrected `semantic-sift` install to include `[neural,multi-modal]` extras; updated venv creation to use `python3.12`; removed trailing `ge.*` lines.

---

## [0.1.2] - 2026-05-06

### ✨ New Features
- **Descriptive Telemetry Attribution**: The orchestrator (`wrapper.py` and `orchestrator.py`) now extracts `tool_name` and `agent_label` from IDE hook payloads and passes them to downstream nodes via `SIFT_TOOL_NAME` and `SIFT_AGENT_LABEL` environment variables.
- **CLI Stats Command**: Added a dedicated `stats` subcommand to the `context-pipe` CLI (with aliases `get_pipe_stats` and `pipe-stats`) to view the ROI Balance Sheet directly from the terminal without invoking the MCP server.

### 🛡️ Graceful Resilience & Security
- **Indestructible Orchestrator**: Wrapped the main orchestrator CLI execution in a global `try/except` block. Any fatal errors (like file corruption or parsing failures) now silently return the original input text instead of crashing the IDE hook.
- **Unified Telemetry Configuration**: Standardized environment variables using the `CPP_PREFIX` (e.g., `CPP_TELEMETRY_FILE`, `CPP_TELEMETRY_DISABLED`) while preserving backward compatibility. Standardized echo detection to use `.pipe_cache`.

### Fixed
- **Persistent Hook Corruption**: Transitioned `pipe_hook.py` and `telemetry.py` to use an "Indestructible Hook" pattern and unified file paths to resolve file-system sync conflicts that were causing interleaved code corruption on some high-latency environments.
- **Reranking Mappings**: Updated default `pipes.json` to map `search|grep|find` tools to the new `rerank-and-sift` pipe utilizing the semantic-sift CLI's `rank` command.

---

## [0.1.1] - 2026-05-05

### Added
- **`discover_sift_executable()`** (`onboarding.py`): Multi-stage discovery algorithm that locates `semantic-sift-cli` across the current venv, system PATH, pipx, sibling venv directories (up to 4 levels deep), and user home venvs. Eliminates the requirement for both packages to share the same virtual environment.
- **`resolve_pipes_config()`** (`onboarding.py`): Rewrites `semantic-sift-cli` nodes in `pipes.json` with the discovered absolute path. Idempotent. Called automatically during `pipe_onboard` for all environments.
- **`verify_installation()`** (`onboarding.py`): Structured health check covering context-pipe importability, `pipes.json` validity, sift CLI discovery and version response, and per-node PATH resolution.
- **`pipe_verify` MCP tool** (`server.py`): Surfaces `verify_installation` results as a formatted markdown report with per-component status icons and actionable fix instructions. Also auto-runs `resolve_pipes_config` before reporting.

### Fixed
- **OpenCode `command` schema** (`onboarding.py`, `opencode.json`): The `pipe_onboard` OpenCode path was writing an invalid `"commands"` key with unsupported `action/server/tool` fields. Corrected to use the `"command"` (singular) key with a `"template"` string per the OpenCode spec.
- **`opencode.json` typo** (`semantic-sift/opencode.json`): `external_directory` permission was set to `context-pie/**` instead of `context-pipe/**`.
- **Documentation accuracy pass** (`INTEGRATION_ENCYCLOPEDIA.md`, `README.md`, `OPERATOR_GUIDE.md`): Corrected OpenCode-specific claims across all docs — config path (`~/.opencode.json` → `<project-root>/opencode.json`), plugin interception capability (active → placeholder pending upstream fix), Section 5 wrapper logic (removed OpenCode from `AfterTool` extraction list), and onboarding description (clarified plugin generates placeholder only). All references now link to [sst/opencode#21149](https://github.com/sst/opencode/issues/21149) and explain the interim `AGENTS.md` SOP strategy.
- **Installation sequence documented** (`README.md`, `OPERATOR_GUIDE.md` Section 0): Added the **Sovereign Dual-Repo Pattern** — the actual setup in use. Documents that `context-pipe/venv` is the master venv holding both packages (via `uv pip install -e ../semantic-sift`), that `semantic-sift/venv312` is the ML-only runtime (Python 3.12, torch/CUDA), that `semantic-sift-cli` lives in `context-pipe/venv/Scripts/`, and that both `pipes.json` files reference that single absolute path. Removed misleading "venv table" and standalone `uv pip install .` instructions that did not reflect the cross-install pattern. The `tool.execute.after` hook is declared in the OpenCode plugin `Hooks` interface but is **never triggered** by the OpenCode runtime (confirmed via full source audit of `session/processor.ts`, `session/llm.ts`, `tool/registry.ts`, `agent.ts`, and all v2 session files). The plugin's output mutation code (`output.output = parsed.result`) was silently a no-op. The plugin is now a documented placeholder with the mutation handler commented out. The real interception point remains the `pipe_read_file` MCP tool per the AGENTS.md SOP. Issue filed upstream: [sst/opencode#25918](https://github.com/sst/opencode/issues/25918).

---

## [0.1.0] - 2026-05-03

### ✨ Initial Release
- The official birth of the **Context-Pipe Protocol (CPP)**.
- First functional orchestrator and basic sifting primitives.
- Initial support for Cursor and Gemini CLI hooks.
