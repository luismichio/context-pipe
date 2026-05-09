# ⛓️ Context-Pipe

**The Universal Standard for Context Engineering.**

[![CI](https://github.com/luismichio/context-pipe/actions/workflows/ci.yml/badge.svg)](https://github.com/luismichio/context-pipe/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-177%20Passing-brightgreen)](tests/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-context-pipe)](https://pypi.org/project/mcp-context-pipe/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue)](LICENSE.md)
[![OSI](https://img.shields.io/badge/OSI-Approved-brightgreen)](https://opensource.org/licenses/Apache-2.0)

`context-pipe` is a high-performance orchestration layer directly inspired by Unix terminal piping — the same philosophy that made `cmd1 | cmd2 | cmd3` the most durable composition primitive in computing. Just as the terminal chains processes through `stdin`/`stdout` byte streams, Context-Pipe chains AI tool calls through context streams: each node does one thing, passes its output to the next, and the LLM only sees the final, refined signal.

This is not a metaphor — it is a literal extension. Context-Pipe supports both **MCP piping** (chaining MCP tool calls through the orchestrator) and **terminal piping** (any binary, shell command, or script that reads `stdin` and writes `stdout` is a valid node). The two modes compose freely in a single pipe definition. And through the `mcp-pipe` CLI, it extends the terminal itself: the `mcp-pipe tool` subcommand (Phase 7.6) makes any MCP server — context-mode, serena, GitHub, Firecrawl, or any server registered in `pipes.json` — directly pipeable from the shell, loading on demand, with no wrapper scripts and no IDE required:

```bash
cat error.log | mcp-pipe tool semantic-sift sift_logs | rg "CRITICAL"
curl -s https://example.com | mcp-pipe tool firecrawl scrape | mcp-pipe run semantic-refinery
```

Today, `mcp-pipe run <pipe>` already gives the terminal first-class access to any named pipe defined in `pipes.json`, composing terminal binaries through the same orchestrator used by the IDE.

---

## 🚀 The Vision

The AI agent has a fundamental infrastructure problem: every tool call returns raw, unfiltered output directly into the context window. Logs arrive with timestamps. Search results arrive with boilerplate. Agent A's 40KB analysis gets passed verbatim to Agent B. The context window fills. Signal drowns in noise. The LLM degrades.

`context-pipe` solves this at the infrastructure layer — before the LLM sees anything.

In the **Studio of Two** philosophy, we build **Systems, not Patches**. A patch would be a custom filter per tool. A system is a universal protocol: any tool that reads `stdin` and writes `stdout` becomes a node. Any sequence of nodes becomes a pipe. Any pipe is named, versioned, audited, and reusable across every project and every agent framework.

The result is a **context supply chain**: data enters raw, passes through a sequence of refineries (normalize → filter → compress → distil), and arrives at the LLM as dense, high-signal content. Every byte saved is accounted for in the Context Balance Sheet. Every pipe run is traceable. Every A2A handoff is protected.

This is not a wrapper around `semantic-sift`. It is the orchestration layer that makes any refinery composable, observable, and production-grade. A node can be a binary, a shell command, a Python script, a **Mandate** (an expert-lens instruction set injected into the stream), or — coming in Phase 7.5 — a **full MCP tool** (Figma, GitHub, context-mode, or any server registered in `pipes.json`). If it reads `stdin` and writes `stdout`, it belongs in the pipe.


**Example — crawl the web, research it, save it, and ship it:**
```
trigger: tool:web_search | tool:web_fetch
```
```
[URL]
    → firecrawl/scrape             # MCP node ✦: fetch live page as clean text     ~18,400 tokens
    → markitdown                   # binary node: convert to structured Markdown     ~16,200 tokens
    → rg 'security|vulnerability'  # shell node: surface only relevant sections      ~3,100 tokens
    → prettier --parser markdown   # shell node: normalize formatting                ~3,050 tokens
    → semantic-sift-cli doc        # binary node: distil to high-signal summary        ~420 tokens
          ↳ tee → research.md      # T-pipe: save raw distilled copy to disk
    → security-auditor mandate     # script node: inject expert security lens          ~380 tokens
    → github/create_issue          # MCP node ✦: open a tracked issue with findings
```
*✦ Phase 7.5 — coming soon*

```
Context Balance Sheet (illustrative)
  in:  18,400 tokens  →  out: 380 tokens  —  97.9% saved  ·  1.2s total
```

Every node is a real subprocess. The T-pipe saves a raw copy at any point without interrupting the chain. The LLM receives only what matters — and every byte in, byte out, and millisecond of latency is recorded in the Context Balance Sheet automatically.

---

## 🛠️ Core Components

### 1. The Context-Pipe Protocol (CPP)
A language-agnostic standard with one rule: a node reads `stdin`, transforms content, and writes to `stdout`. Any binary, shell command, Python script, or MCP tool that honours this contract is a valid node. The protocol is defined in [`doc/CONTEXT_PIPE_PROTOCOL.md`](doc/CONTEXT_PIPE_PROTOCOL.md) and is deliberately simple — no SDKs, no registration, no framework coupling.

### 2. The Orchestration Spine (`orchestrator.py`)
The execution engine that chains nodes into pipes. Runs each node as a real OS subprocess with `shell=False` enforced (no injection surface). Features: per-node timeout guard (`PIPE_NODE_TIMEOUT_MS`), T-Pipe stream splitting (save raw input to disk before a node processes it), full trace accounting (input/output size + latency per node), and Adaptive Window Pressure (`PIPE_WINDOW_PRESSURE` env var passed to every node).

### 3. The Universal Switchboard (`pipes.json` + mappings)
Data-driven routing that resolves the optimal pipe automatically based on three trigger types: **tool name** (`tool:regex`), **payload size** (`size:>N`), and **default fallback**. Pipe definitions live in `pipes.json` (project-level) and optionally `~/.mcp-pipe.json` (global, merged with local precedence). No code changes required to add, modify, or re-route pipes.

### 4. The MCP Surface (`server.py` + `mcp-pipe` CLI)
Eight MCP tools expose every capability to AI assistants directly: `pipe_run`, `pipe_run_dynamic`, `pipe_read_file`, `pipe_analyze_file`, `pipe_list_shadow_tools`, `pipe_agent_handoff`, `get_pipe_stats`, and `pipe_onboard`. The `mcp-pipe` CLI mirrors the same surface for terminal-first workflows — no IDE required. Shadow Tool Discovery (`pipe_list_shadow_tools`) gives the agent a live capability manifest combining configured pipes and curated PATH tools (`jq`, `rg`, `markitdown`, `pandoc`…).

### 5. Subconscious Interceptors (`pipe_hook.py` + `onboarding.py`)
IDE hooks that apply pipes transparently after every tool call — without the agent needing to invoke `pipe_run` explicitly. Supported: Cursor (`postToolUse`), VS Code/GitHub (hooks), Claude Code/Qwen/Codex (`PostToolUse`), Windsurf and Cline (pre-read security gateway), OpenClaw (native plugin). For OpenCode, the `AGENTS.md` SOP mandate is the active strategy (see [Known Limitations](#️-known-limitations)). `pipe_onboard` injects all hooks, slash commands (`/pipe-run`, `/pipe-dynamic`, `/pipe-handoff`, `/pipe-stats`), and the full agent SOP in one command.

### 6. The A2A Bridge (`a2a.py`)
`pipe_agent_handoff()` distils Agent A's output before it enters Agent B's context window. Framework-agnostic — no monkey-patching. Works in CrewAI task callbacks, Google ADK transfer hooks, LangGraph edge functions, or any custom handoff point. Available as both a Python function and an MCP tool. Returns the original output unchanged on any error, so the agent chain is never interrupted.

---

## ✨ What Makes This Different

| Feature | What it does | Where |
|---|---|---|
| **Unix pipe model for AI** | Chain any `stdin→stdout` tool into a named pipe. Binary, shell, mandate, or MCP tool — same contract. | [Advanced Node Types](#-advanced-node-types) |
| **MCP Node Type** *(Phase 7.5)* | Call any MCP tool (Figma, GitHub, context-mode…) as a first-class pipe node — no wrapper scripts. | [doc/MCP_NODE_SPEC.md](doc/MCP_NODE_SPEC.md) |
| **Dynamic Pipes** | AI agents construct and execute ad-hoc node lists at runtime via `pipe_run_dynamic` — no `pipes.json` entry required. | [Dynamic Pipes](#dynamic-pipes) |
| **Shadow MCP Registry** | MCP servers can be installed locally or called remotely without being registered in your IDE — keeping them invisible to the agent's tool list, preventing MCP tool list bloat. `pipe_list_shadow_tools` boots and queries them on demand, routing calls through `pipe_run` or `pipe_run_dynamic`. Ideal for high-noise utility servers you never want polluting the agent's decision space: format converters (`markitdown`, `pandoc`), search tools (`rg`, `fd`), data processors (`jq`, `yq`), web scrapers (`firecrawl`), and document ingestors (`unstructured`, `tika`). One MCP tool in the IDE. Everything else stays shadow. | [Shadow MCP Registry](#shadow-mcp-registry) |
| **A2A Agent Handoff** | Distil Agent A's output before it enters Agent B's context window — framework-agnostic, no monkey-patching. | [A2A Handoff](#-a2a-agent-to-agent-handoff) |
| **T-Pipe Stream Splitting** | Save a raw copy of any node's input to disk before it is distilled — for audit, debugging, and quality measurement — without interrupting the chain. | [T-Pipe Nodes](#3-t-pipe-nodes-stream-splitting) |
| **Adaptive Window Pressure** | `PIPE_WINDOW_PRESSURE` (0.0–1.0) signals remaining context headroom to every node; `semantic-sift` auto-adjusts `--rate` accordingly. | [Environment Variables](#️-environment-variables) |
| **Global Config (`~/.mcp-pipe.json`)** | Share pipe definitions and MCP server registries across all projects — local `pipes.json` always wins. | [doc/ARCHITECTURE.md §10](doc/ARCHITECTURE.md) |
| **Shell Alias Injection** | `pipe_install_aliases` writes `mcp-pipe` / `cpipe` into your shell profile — terminal-ready without venv activation. | [Terminal Usage](#-terminal-usage-mcp-pipe-cli) |
| **Context Balance Sheet** | Every pipe run is accounted: chars in, chars out, latency per node, agent attribution, net ROI. | [Telemetry & ROI](doc/OPERATOR_GUIDE.md#6-telemetry--roi) |

---

## ⚡ Quickstart (60 seconds)

```bash
# 1. Install
pip install mcp-context-pipe "semantic-sift[neural]"

# 2. Onboard (writes pipes.json + hooks for your IDE)
context-pipe-onboard   # or: ask your AI "Run pipe_onboard()"

# 3. Verify the full stack
echo "noisy log [14:22:05.123] DEBUG: heartbeat ok" | context-pipe run standard-distill
# → distilled, noise-free output with audit header
```

> **Full setup guide** (Sovereign Dual-Repo Pattern, venv layout, IDE config): [doc/OPERATOR_GUIDE.md](doc/OPERATOR_GUIDE.md)

---

## 🏗️ Getting Started

### 1. Installation

**Option A: Quick Install (PyPI)**

Because MCP servers require an explicit Python executable path in your IDE config, you must create a virtual environment first:

> **ℹ️ What you get:** This installs the Context-Pipe orchestration layer and Semantic-Sift's core Python server. The `sift-core` Rust binary (for near-instant heuristic sifting) is included in the PyPI wheel — no Rust toolchain required. The `[neural]` extra adds PyTorch (~1.5 GB) for large-payload semantic compression.

```bash
uv venv
# Windows: .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
uv pip install mcp-context-pipe "semantic-sift[neural,multi-modal]"
```

**Option B: Sovereign Pattern (Recommended for Studio of Two)**
Clone both repos side-by-side. The `context-pipe` venv acts as the master environment holding both packages. See **[Section 0 of the Operator's Guide](doc/OPERATOR_GUIDE.md#0-installation-sovereign-dual-repo-pattern)** for the full sequence.

```bash
# 1. Clone both repos
git clone https://github.com/luismichio/context-pipe.git
git clone https://github.com/luismichio/semantic-sift.git

# 2. Master venv in context-pipe - holds both packages
cd context-pipe
python3.12 -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate
uv pip install -e .
uv pip install -e ../semantic-sift  # semantic-sift-cli lands in context-pipe/venv/Scripts/ (Win) or venv/bin/ (Mac/Linux)

# 3. ML runtime venv in semantic-sift (Python 3.12 for torch/CUDA compatibility)
cd ../semantic-sift
python3.12 -m venv venv312
# Windows:
.\venv312\Scripts\activate
# macOS/Linux:
# source venv312/bin/activate
uv pip install -e .[neural]         # torch, transformers, llmlingua
```

> **Note:** The package name on PyPI is `mcp-context-pipe` but the installed module is `context_pipe`. The `semantic-sift-cli` binary is registered only in the venv where `semantic-sift` is pip-installed (step 2 above). Both `pipes.json` files must reference that absolute path.

### 2. Connect the MCP

> **CRITICAL**: For exact configuration paths for Cursor, Gemini, OpenCode, VS Code, and Claude, reference the **[Master Configuration Matrix](doc/INTEGRATION_ENCYCLOPEDIA.md#2-master-configuration-matrix-installation)**.

### 3. Connect a Refinery
Context-Pipe is the "Switchboard," but it needs a "Refinery" to distill data. **[Semantic-Sift](https://github.com/luismichio/semantic-sift)** is the flagship intelligence engine for this ecosystem. It uses heuristic sieves and neural models (BERT/ONNX) to incinerate noise (timestamps, boilerplate) while preserving 95% of the signal.

> **Note:** In the Sovereign Pattern, `semantic-sift` is cross-installed into `context-pipe/venv` (step 2 above). Context-Pipe will also auto-discover a separately installed `semantic-sift-cli` across all known locations (system PATH, pipx, sibling venv directories) via `pipe_onboard` or `pipe_verify`.

### 4. Verify the Installation
After installing both packages, ask your AI assistant to verify the full stack:
> *"Run `pipe_verify()` to confirm the installation."*

This will report the health of every component and automatically link `semantic-sift-cli` into `pipes.json` if it was found in a separate environment.

### 5. Configure your first Pipe
Edit `pipes.json` (see `pipes.json.example`) to define your high-fidelity context streams.

### 6. Auto-Onboard
Once connected, ask your AI Assistant to configure your workspace:
> *"Run `pipe_onboard(environment='Cursor')` to configure this project."*

`pipe_onboard` **auto-detects your IDE** if `environment` is omitted — it inspects environment variables and parent-process names to fingerprint 12+ platforms (Cursor, Gemini, OpenCode, VS Code, Windsurf, Claude, Cline, etc.). Pass `environment` explicitly only when auto-detection is ambiguous.

---

## 📚 Documentation

Detailed documentation is available in the [`doc/`](./doc) directory.

*   **[doc/INDEX.md](doc/INDEX.md)**: The navigational roadmap for the documentation ecosystem.
*   **[doc/USE_CASES.md](doc/USE_CASES.md)**: Real-world, high-impact scenarios demonstrating how to chain Bash, Mandates, and Semantic-Sift.
*   **[doc/OPERATOR_GUIDE.md](doc/OPERATOR_GUIDE.md)**: Definitive guide for setup, terminal mastery, and `pipes.json` configuration.
*   **[doc/ARCHITECTURE.md](doc/ARCHITECTURE.md)**: Technical specifications of the orchestration spine and switchboard.
*   **[doc/CONTEXT_PIPE_PROTOCOL.md](doc/CONTEXT_PIPE_PROTOCOL.md)**: The language-agnostic standard for tool interoperability.
*   **[doc/INTEGRATION_ENCYCLOPEDIA.md](doc/INTEGRATION_ENCYCLOPEDIA.md)**: Master Compatibility Matrix for Cursor, VS Code, Gemini, and Claude.

---

## 🐍 Programmatic Usage

Context-Pipe exposes a single `pipe()` function for direct integration into Python scripts, notebooks, and agent frameworks (LangChain, CrewAI, etc.) — no MCP server or CLI required.

```python
from context_pipe import pipe

# Auto-route based on pipes.json mappings
clean = pipe(raw_logs, tool_name="bash")

# Specify a pipe explicitly
distilled = pipe(document_text, pipe_name="semantic-refinery")

# Minimal usage — returns input unchanged if no pipe resolves
result = pipe(text)
```

**Function signature:**
```python
def pipe(
    text: str,
    pipe_name: str | None = None,   # explicit pipe name; auto-routes if omitted
    tool_name: str = "",            # used for trigger matching and telemetry
    config_path: str = "pipes.json",
) -> str: ...
```

The function always returns the original `text` unchanged on any error (subprocess failure, missing config, etc.), so it is safe to use as a drop-in filter.

---

## 🤝 A2A (Agent-to-Agent) Handoff

When chaining agents, use `pipe_agent_handoff` to distil Agent A's output before it enters Agent B's context window. Works with any framework — no monkey-patching required.

```python
from context_pipe.a2a import pipe_agent_handoff

# In a CrewAI task callback, ADK transfer hook, or any custom handoff point:
agent_b_input = pipe_agent_handoff(
    agent_a_output,
    pipe_name="semantic-refinery",   # optional; auto-routes if omitted
    from_agent="researcher",
    to_agent="writer",
)
```

Also available as an MCP tool — ask your AI assistant: *"Run `pipe_agent_handoff()` to distil this agent output before passing it on."*

**Function signature:**
```python
def pipe_agent_handoff(
    output: str,
    pipe_name: str | None = None,   # explicit pipe; auto-routes if omitted
    from_agent: str | None = None,  # producing agent label (telemetry + routing)
    to_agent: str | None = None,    # consuming agent label (telemetry only)
    config_path: str = "pipes.json",
) -> str: ...
```

Always returns the original `output` unchanged on any error — the agent chain is never interrupted.

---

## 💻 Terminal Usage (`mcp-pipe` CLI)

Context-Pipe ships a first-class terminal runner — `mcp-pipe` — so you can use every capability without an IDE or MCP server.

```bash
# Run a named pipe on stdin
cat app.log | mcp-pipe run standard-distill

# Run a named pipe on a file directly
mcp-pipe run semantic-refinery --file spec.md

# Run an ad-hoc node array (shell synergy requires --allow-shell)
echo "noisy output" | mcp-pipe run-dynamic '[{"cmd":"semantic-sift-cli","args":["logs"]}]'

# List all configured pipes + curated PATH tools (Shadow MCP discovery)
mcp-pipe list

# Print the Context Balance Sheet (ROI across all sessions)
mcp-pipe stats

# Start the MCP server manually (stdio transport)
mcp-pipe serve

# Install/remove the cpipe shell alias
mcp-pipe aliases install
mcp-pipe aliases remove
```

> The `mcp-pipe` entry point is registered automatically when you `pip install mcp-context-pipe`. Use `cpipe` as a shorthand after running `mcp-pipe aliases install`.

### Shadow MCP Registry

Every MCP server you add to an IDE registers its tools globally — they all appear in the agent's tool list whether the agent needs them or not. At scale this causes **MCP tool bloat**: hundreds of tools in the prompt, wasted tokens on every inference call, and a higher chance the agent picks the wrong one.

`context-pipe` takes a different approach. Instead of registering every context-processing tool as a first-class MCP tool, it exposes a **single discovery tool** — `pipe_list_shadow_tools` — that returns a live capability manifest on demand. The tools stay hidden ("shadow") until the agent asks for them. One MCP tool does the work of many.

**What the manifest includes:**
1. **`pipes.json` pipes** — every named pipe configured in your project.
2. **Curated PATH tools** — probes 7 well-known CLI tools (`jq`, `yq`, `markitdown`, `pandoc`, `rg`, `fd`, `bat`) and surfaces any found on PATH.

**Known limitation:** shadow tools are not callable as independent MCP tools — the agent must route them through `pipe_run` or `pipe_run_dynamic`. This is by design (it keeps the MCP surface minimal), but it means the agent cannot call `jq` or `markitdown` directly without constructing a dynamic pipe node.

**Terminal access via `mcp-pipe`:** the same manifest is available without an IDE or MCP server — `mcp-pipe list` prints every pipe and curated PATH tool to stdout. Pipe any content through a shadow tool directly from the terminal:

```bash
# Discover what's available
mcp-pipe list

# Run a shadow tool via a dynamic pipe — no pipes.json entry needed
echo "# My Doc" | mcp-pipe run-dynamic '[{"cmd":"markitdown"},{"cmd":"semantic-sift-cli","args":["doc"]}]'
```

---

## 🔗 Advanced Node Types

Context-Pipe supports more than just simple binaries. You can chain standard OS tools and expert mandates.

### 1. Bash Nodes (`shell: true`)
Execute arbitrary shell commands as part of your pipe.
```json
{ "cmd": "grep 'ERROR'", "shell": true }
```

### 2. Script & Mandate Nodes
Executes a project-specific script or applies an "Expert Mandate" (instruction set) to the context. Resolved from `.gemini/scripts/` (default).
```json
{ "type": "script", "cmd": "security-auditor" }
```

### 3. T-Pipe Nodes (Stream Splitting)
Save a raw copy of the stream to disk before a node distils it — without interrupting the chain. Useful for debugging pipe quality and auditing what was sifted out.
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
`path` supports `{iso_date}` (YYYY-MM-DD) and `{tool_name}` tokens. A tee failure never interrupts the main chain.

### 4. MCP Nodes *(Phase 7.5 — coming soon)*
Call any MCP tool as a pipe node. No wrapper scripts — the orchestrator spawns the MCP server, calls the tool, and passes the result downstream via `stdout`.
```json
{
  "type": "mcp",
  "server": "figma",
  "tool": "get_file",
  "input_key": "file_id"
}
```
Server definitions live in a `servers` block in `pipes.json` or `~/.mcp-pipe.json`. See [doc/MCP_NODE_SPEC.md](doc/MCP_NODE_SPEC.md) for the full spec.

---

## 🔗 The Ecosystem (Studio of Two)

Context-Pipe is a foundational member of the **Studio of Two** infrastructure. It is designed to work in high-fidelity harmony with:

*   **[Semantic-Sift](https://github.com/luismichio/semantic-sift)**: The intelligent refinery for agentic context. Sift is the flagship distillation engine for Context-Pipe, providing the mathematical and neural sifting nodes used in our standard templates.

---

## 🧩 Tool Synergies & Boundaries

Four tools often appear together in a Studio of Two stack. They are complementary, not overlapping — each owns a distinct layer.

| Tool | Layer | Primary Role | Relationship |
|---|---|---|---|
| **context-pipe** | Orchestration | Routes content through named pipes; manages node execution, timeouts, T-pipe, telemetry, and A2A handoff. | The switchboard. Calls all other tools as nodes when wired together. |
| **semantic-sift** | Distillation | Heuristic + neural compression of text. Removes noise (timestamps, boilerplate, repeated tokens) while preserving signal. | Fully standalone CLI and MCP server. The flagship refinery node inside context-pipe pipes. |
| **[context-mode](https://github.com/mksglu/context-mode)** | In-session indexing | BM25 full-text search over content indexed during the current agent session. Fast retrieval without a vector database. | Fully standalone MCP server. Optionally wired as an `mcp` node (Phase 7.5) to index or search within a pipe. |
| **[Serena](https://github.com/oraios/serena)** | Code intelligence | LSP-backed symbol search, refactoring, and code navigation. Understands the AST — not just text. | Fully standalone MCP server. Optionally wired as an `mcp` node to feed precise code symbols into a pipe instead of raw file reads. |

### When to use which

**Use `context-pipe` when** you need to orchestrate: chain tools, apply pipes automatically on tool call, route by trigger, save T-pipe snapshots, account for ROI, or bridge agent handoffs.

**Use `semantic-sift` when** you need to compress: a large document, a log file, a search result, or any payload where noise-to-signal ratio is high. Runs standalone via CLI or MCP — and as a node inside context-pipe pipes.

**Use `context-mode` when** you need to retrieve: you have already ingested content this session and want fast BM25 search over it. Works standalone as an MCP server in any IDE. Pair it with `semantic-sift` on both sides — upstream to compress content before indexing (smaller index, faster search), and downstream to distil retrieved chunks before they hit the context window.

**Use `Serena` when** you need to navigate code: find a symbol, trace references, inspect types, or perform a refactor. Works standalone as an MCP server. Its structured, precise output is far better than a raw file read as input to any downstream tool — including a sifting pipe.

### Complementary setup — reducing token usage

Each tool independently reduces token pressure. Together, the savings compound:

- **Serena** returns only the symbol you asked for — not the entire file.
- **semantic-sift** compresses content before it enters context-mode (smaller index, faster search) and after retrieval (noise-free chunks into the context window).
- **context-mode** returns only the relevant indexed chunks — not the entire ingested corpus.
- **context-pipe** ensures this sequence fires automatically and is accounted for — no manual wiring per task.

The result: the agent works with a fraction of the raw token volume, every session, without changing how it thinks or what tools it calls.

### Synergy example

```
[user query]
    → serena/find_symbol           # MCP node: precise code symbol — not a raw file dump
    → context-mode/search          # MCP node: retrieve related session context
    → semantic-sift-cli semantic   # binary node: compress both into a dense summary
    → security-auditor mandate     # script node: expert lens over the result
```

All four tools in one pipe. Each doing exactly one job.

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PIPE_CONFIG_PATH` | `pipes.json` | Absolute path to the project's `pipes.json` config file. |
| `PIPE_NODE_TIMEOUT_MS` | `30000` | Per-node execution timeout in milliseconds. |
| `PIPE_WINDOW_PRESSURE` | _(unset)_ | Float `0.0–1.0` passed to each node as an env var. `semantic-sift-cli` reads this and overrides `--rate` accordingly. Set by context-pipe routing when payload pressure is high (cross-project dependency with `semantic-sift`). |
| `allow_shell` | `false` | Enable arbitrary shell command nodes in dynamic pipes (`pipe_run_dynamic` MCP tool / `run_dynamic_pipe()` API). Requires the final node to be a `semantic-sift` terminal command to guarantee context safety. |

---

## ⚠️ Known Limitations

### OpenCode — MCP Tool Output Interception

The "subconscious interceptor" feature (`pipe_hook.py`) works transparently for **Cursor, VS Code, Gemini CLI, and Claude Desktop** by injecting hook handlers that fire after every tool call.

**OpenCode is the exception.** The `tool.execute.after` hook is declared in the OpenCode plugin `Hooks` interface but is **never triggered** by the OpenCode runtime (confirmed via source audit of `session/processor.ts`, `session/llm.ts`, `tool/registry.ts`, `agent.ts`). The plugin's output mutation code is silently a no-op.

**Current workaround**: The `AGENTS.md` SOP mandate (`pipe_read_file` for all file reads) is the active interception strategy for OpenCode until transparent hook injection is supported upstream.

- Upstream issue: [sst/opencode#21149](https://github.com/sst/opencode/issues/21149)
- Plugin issue: [sst/opencode#25918](https://github.com/sst/opencode/issues/25918)
- Tracked in our backlog: Phase 4.5 — see [`doc/backlog.md`](doc/backlog.md)

---

## ⚖️ Licensing
`context-pipe` is licensed under the **Apache License 2.0**. It is an "Open Source, Closed Contribution" project maintained by the Studio of Two to ensure architectural integrity.

---
*Building High-Fidelity Infrastructure for the Intelligence Age.*
