# Changelog

All notable changes to the **Context-Pipe** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5] - 2026-05-07

### Fixed
- **`pyproject.toml`**: Added `[tool.pytest.ini_options] testpaths = ["tests"]` to prevent pytest from collecting `test_search.txt` (a binary fixture file at repo root) as a test module — this was causing the Release CI to fail with `UnicodeDecodeError` on every tag since v0.1.3.

## [0.1.4] - 2026-05-07

### Fixed
- **`doc/INTEGRATION_ENCYCLOPEDIA.md`**: Fixed Claude Desktop config path — was Windows-only tilde syntax; now shows both Win (`%APPDATA%\Claude\...`) and Mac (`~/Library/Application Support/Claude/...`).
- **`doc/INTEGRATION_ENCYCLOPEDIA.md`**: Fixed broken quote in Qwen CLI row (`~/.qwen/settings.json"` → correct backtick).
- **`doc/OPERATOR_GUIDE.md`**: Removed trailing orphan `*` lines at end of file.
- **`README.md`**: Added ℹ️ callout explaining `sift-core` Rust binary is pre-compiled in the PyPI wheel; corrected `semantic-sift` install to include `[neural,multi-modal]` extras; updated venv creation to use `python3.12`; removed trailing `ge.*` lines.

## [0.1.2] - 2026-05-06

### ✨ New Features
- **Descriptive Telemetry Attribution**: The orchestrator (`wrapper.py` and `orchestrator.py`) now extracts `tool_name` and `agent_label` from IDE hook payloads and passes them to downstream nodes via `SIFT_TOOL_NAME` and `SIFT_AGENT_LABEL` environment variables.
- **CLI Stats Command**: Added a dedicated `stats` subcommand to the `context-pipe` CLI (with aliases `get_pipe_stats` and `pipe-stats`) to view the ROI Balance Sheet directly from the terminal without invoking the MCP server.

### 🛡️ Graceful Resilience & Security
- **Indestructible Orchestrator**: Wrapped the main orchestrator CLI execution in a global `try/except` block. Any fatal errors (like file corruption or parsing failures) now silently return the original input text instead of crashing the IDE hook.
- **Unified Telemetry Configuration**: Standardized environment variables using the `CPP_` prefix (e.g., `CPP_TELEMETRY_FILE`, `CPP_TELEMETRY_DISABLED`) while preserving backward compatibility. Standardized echo detection to use `.pipe_cache`.

### Fixed
- **Persistent Hook Corruption**: Transitioned `pipe_hook.py` and `telemetry.py` to use an "Indestructible Hook" pattern and unified file paths to resolve file-system sync conflicts that were causing interleaved code corruption on some high-latency environments.
- **Reranking Mappings**: Updated default `pipes.json` to map `search|grep|find` tools to the new `rerank-and-sift` pipe utilizing the semantic-sift CLI's `rank` command.

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

### Changed
- **`inject_hooks()`** (`onboarding.py`): Step 0b now runs `resolve_pipes_config` for all environments so `pipe_onboard` always attempts to auto-link sift regardless of IDE target.
- **`README.md`**: Removed `uv pip install mcp-context-pipe[multi-modal]` instruction (markitdown is a semantic-sift concern, not context-pipe). Added `pipe_verify` step to Getting Started. Updated refinery install instructions.
- **`OPERATOR_GUIDE.md`**: Expanded section 7 (Auto-Onboarding) with refinery auto-link detail. Added new section 8 (Verifying the Installation) with `pipe_verify` output example and supported install pattern matrix.
- **`ARCHITECTURE.md`**: Added section 5 documenting the onboarding/discovery/verification subsystem.

## [0.1.0] - 2026-05-03

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
