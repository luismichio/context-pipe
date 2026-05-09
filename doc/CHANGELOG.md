# Changelog

All notable changes to the **Context-Pipe** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
