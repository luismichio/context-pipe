# Context-Pipe: Operator's Manual

Welcome to the **Context-Pipe Platform (CPP)**. This manual provides the definitive guide for setting up, configuring, and mastering high-fidelity context engineering.

---

## 0. Installation (Sovereign Dual-Repo Pattern)

The recommended setup clones both repos side-by-side and uses a single **master venv** in `context-pipe` that holds both packages. `semantic-sift` gets its own venv only for the heavy ML/neural runtime (torch, transformers).

```
~/Workbench/GitHub/
  context-pipe/       ← orchestration layer
    venv/             ← MASTER venv (Python 3.13+, any OS)
  semantic-sift/      ← neural distillation engine
    venv312/          ← ML runtime venv (Python 3.12, torch/cuda)
```

### Step 1 — Clone both repos

```bash
git clone https://github.com/luismichio/context-pipe.git
git clone https://github.com/luismichio/semantic-sift.git
```

### Step 2 — Create the master venv in context-pipe

```bash
cd context-pipe
python -m venv venv

# Windows:
.\venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate
```

### Step 3 — Install context-pipe (editable)

```bash
uv pip install -e .
```

> The package name in `pyproject.toml` is `mcp-context-pipe` (PyPI) but installs as the `context_pipe` module. The editable install registers `context-pipe`, `context-pipe-server`, and `context-pipe-script` CLI entry points.

### Step 4 — Cross-install semantic-sift into the master venv (editable)

```bash
uv pip install -e ../semantic-sift
```

> **Windows Tip (`uv` environment discovery)**: If `uv` fails to find your environment (error: *"No virtual environment found"*), explicitly point to your interpreter using the `--python` flag:
> `uv pip install -e . --python venv/Scripts/python.exe`

This installs `semantic-sift` from the sibling repo into `context-pipe/venv`. The `semantic-sift-cli` binary now lives at:

| OS | Path |
| :--- | :--- |
| **Windows** | `context-pipe/venv/Scripts/semantic-sift-cli.exe` |
| **macOS/Linux** | `context-pipe/venv/bin/semantic-sift-cli` |

This is the path that `pipes.json` must reference.

### Step 5 — Create the ML runtime venv in semantic-sift

```bash
cd ../semantic-sift
python3.12 -m venv venv312

# Windows:
.\venv312\Scripts\activate
# macOS/Linux:
# source venv312/bin/activate

uv pip install -e .[neural]        # torch, transformers, llmlingua
```

> `semantic-sift/venv312` is the **neural runtime only**. The MCP server (`server.py`) loads the `semantic_sift` package via `sys.path` from the repo root — it does not require `semantic-sift` to be pip-installed in this venv.

### Step 6 — Register both MCP servers in opencode.json

In each project's `opencode.json`, register both servers. The `PIPE_CONFIG_PATH` env var must point to that project's own `pipes.json`.

> **Note**: If you haven't created a `pipes.json` yet, don't worry. Running `pipe_onboard` in the next step will create a default one for you.

**Windows:**
```json
"mcp": {
  "semantic-sift": {
    "type": "local",
    "command": [
      "C:/path/to/semantic-sift/venv312/Scripts/python.exe",
      "C:/path/to/semantic-sift/server.py"
    ]
  },
  "context-pipe": {
    "type": "local",
    "command": [
      "C:/path/to/context-pipe/venv/Scripts/python.exe",
      "-m",
      "context_pipe.server"
    ],
    "environment": {
      "PIPE_CONFIG_PATH": "C:/path/to/<this-project>/pipes.json"
    }
  }
}
```

**macOS/Linux:**
```json
"mcp": {
  "semantic-sift": {
    "type": "local",
    "command": [
      "/path/to/semantic-sift/venv312/bin/python",
      "/path/to/semantic-sift/server.py"
    ]
  },
  "context-pipe": {
    "type": "local",
    "command": [
      "/path/to/context-pipe/venv/bin/python",
      "-m",
      "context_pipe.server"
    ],
    "environment": {
      "PIPE_CONFIG_PATH": "/path/to/<this-project>/pipes.json"
    }
  }
}
```

### Step 7 — Auto-Onboard the Workspace

Once both servers are connected, ask your AI assistant to configure the workspace. This single command automates the entire setup:

> *"Run `pipe_onboard()` to configure this project."*

**What Onboarding Does:**
1. **Creates `pipes.json`**: If the file is missing, it creates a default configuration with production-grade templates for logs (`standard-distill`) and code (`semantic-refinery`).
2. **Auto-Links Sift**: Discovers the absolute path to `semantic-sift-cli` and rewrites every `pipes.json` node to use it (idempotent).
3. **Git Protection**: Automatically appends internal artifacts (`.pipe_cache/`, `.pipe_identity`, `.pipe_telemetry.jsonl`) to the project's `.gitignore` file.
4. **Injects Hooks**: Automatically configures `.cursor/hooks.json`, `.github/hooks/`, and `opencode.json` hooks. For **Gemini CLI**, it registers both `AfterTool` and `PreCompress` hooks in `.gemini/settings.json`.
5. **Injects Rules**: Creates slash commands like `/pipe-run` and `/pipe-stats` in Cursor rules and Gemini CLI commands.
6. **Injects Mandates**: Adds the Agent SOP mandate to `AGENTS.md` and other instruction files.

---


To master Context-Pipe, you must understand its three foundational components:

*   **Nodes**: The individual processing units (tools, scripts, or shell commands).
*   **Pipes**: A named chain of one or more nodes (e.g., `Ingest -> Mask -> Sift`).
*   **Mappings**: Logic that determines *which* pipe to run based on the context (tool name or data size).

---

## 2. Configuration Setup (`pipes.json`)

The `pipes.json` file is the brain of your Switchboard. It must live in your project root or be pointed to via `PIPE_CONFIG_PATH`.

### Basic Structure
```json
{
  "version": "1.0",
  "pipes": [
    {
      "name": "standard-distill",
      "nodes": [
        { "cmd": "semantic-sift-cli", "args": ["logs"] }
      ]
    }
  ],
  "mappings": [
    { "trigger": "default", "pipe": "standard-distill" }
  ]
}
```

---

## 3. Node Types

Context-Pipe supports five distinct node types, plus advanced chaining patterns:

### A. Binary Nodes (Default)
Executes a standalone binary or Python script.
```json
{ "cmd": "sift-core", "args": ["logs"], "optional": true }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `cmd` | string | Yes | The executable or binary name. |
| `args` | array | No | Command-line arguments. |
| `optional` | boolean | No | If `true`, the pipeline continues if the node fails. Default: `false`. |
| `help_msg` | string | No | Custom instruction shown if binary is missing. |

### B. Bash Nodes (Sandboxed)
Executes allowlisted shell commands (e.g., `grep`, `awk`). By design, all commands are executed natively with `shell=False` to prevent injection vulnerabilities.
```json
{ "cmd": "grep", "args": ["ERROR"] }
```

### C. Script Nodes
Executes a project-specific script (Python/Shell) or a local instruction set. Resolved from `.gemini/scripts/` (default).

**Example: React Expert Chain**
This chain uses OS bash to auto-format the code with `eslint`, applies React 19 expert instructions from a Script Node, and then semantically condenses the result. The LLM receives pre-reviewed, compliant code.

```json
{
  "name": "react-expert-chain",
  "nodes": [
    { "cmd": "npx", "args": ["eslint", "--stdin", "--fix-dry-run"] },
    { "type": "script", "cmd": "react-code-fix-linter" },
    { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.6"] }
  ]
}
```

The `type: "script"` node automatically resolves `react-code-fix-linter.py` (executes it) or `react-code-fix-linter.md` (prepends its content) from your local scripts folder.

### D. T-Pipe Nodes (Stream Splitting)
Save a raw copy of the node's input to disk **before** the node processes it — without interrupting the chain. Useful for debugging pipe quality, auditing what was sifted out, and building a research archive.

```json
{
  "cmd": "semantic-sift-cli",
  "args": ["doc"],
  "tee": {
    "sink": "file",
    "path": "logs/{tool_name}_{iso_date}.log",
    "mode": "append"
  }
}
```

`path` supports `{iso_date}` (YYYY-MM-DD) and `{tool_name}` tokens. A tee failure **never** interrupts the main chain.

### E. MCP Nodes
Call any MCP tool (web scrapers, GitHub, context-mode…) as a first-class pipe node. No wrapper scripts — the orchestrator spawns the MCP server, calls the tool, and passes the result downstream.

```json
{
  "type": "mcp",
  "server": "firecrawl",
  "tool": "scrape",
  "input_key": "url",
  "help_msg": "Firecrawl MCP server not reachable. Check FIRECRAWL_API_KEY."
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | No | `"mcp"` — activates MCP client path. Default: `"binary"`. |
| `server` | string | Yes (if mcp) | Server registry key from `servers` block. |
| `tool` | string | Yes (if mcp) | Tool name as registered by the MCP server. |
| `input_key` | string | No | Argument name for stdin content. Default: `"content"`. |
| `args` | object | No | Static key/value args merged with `input_key`. |

Server definitions live in a `servers` block in `pipes.json` or `~/.mcp-pipe.json`. See [`doc/MCP_NODE_SPEC.md`](MCP_NODE_SPEC.md) for the full schema reference.

### F. Bring Your Own Parser (BYOP)
Context-Pipe enables extreme decoupling. If you prefer to use **LlamaIndex** or a standalone **MarkItDown** parser instead of the Hybrid Engine, you can chain your custom parser directly into the native Rust Sidecar (`sift-core`).

**Comparison: Hybrid Engine vs. BYOP Chain**
*   **The Hybrid Path (`semantic-sift-cli auto`)**: The Python MCP handles both ingestion (MarkItDown) and semantic sifting in one step. Best for simplicity.
*   **The BYOP Path (`my_parser | sift-core`)**: You write a tiny Python script to parse the PDF, then pipe its `stdout` directly into the `sift-core` Rust binary. Best for maximum control and zero-VRAM sifting.

```json
{
  "name": "advanced-ingestion-chain",
  "nodes": [
    { "cmd": "python", "args": ["-m", "my_custom_llamaindex_parser"] },
    { "cmd": "sift-core", "args": ["semantic", "--rate", "0.4"] }
  ]
}
```

### G. Extreme Chaining (The God Pipe)
Because Context-Pipe is simply OS-level `stdin`/`stdout`, there is no theoretical limit to how many transformations you can chain. You can combine web fetching, bash filtering, mandate injection, and neural compression into a single stream.

```json
{
  "name": "the-god-pipe",
  "description": "Fetch -> Extract -> Grep -> Mask -> Sift",
  "nodes": [
    { "cmd": "curl", "args": ["-s", "https://raw.githubusercontent.com/kubernetes/kubernetes/master/CHANGELOG/CHANGELOG-1.30.md"] },
    { "cmd": "grep", "args": ["-i", "API"] },
    { "type": "script", "cmd": "pii-masker" },
    { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.2"] }
  ]
}
```

---

## 4. Understanding Triggers (Mappings)

Mappings allow the Switchboard to decide the best distillation strategy automatically.

1.  **Tool Trigger (`tool:regex`)**: Matches the name of the MCP tool being called.
    *   Web Example: `{"trigger": "tool:web_search|web_fetch|google_web_search", "pipe": "semantic-refinery"}`
    *   Code Example: `{"trigger": "tool:search_code|grep_search|glob|find_symbol", "pipe": "semantic-refinery"}`
2.  **Size Trigger (`size:>num`)**: Activates when the payload exceeds a specific character count.
    *   Example: `{"trigger": "size:>20000", "pipe": "heavy-distill"}`
3.  **Default**: The fallback pipe used when no other triggers match.

---

## 5. Terminal Mastery

Context-Pipe is designed to be used as a standalone CLI tool, available both as a Python script (`mcp-pipe`) and a high-performance, zero-dependency compiled Rust binary (`cpipe`).

### Basic Execution
```bash
# Sift data from a file using the Rust binary
cat app.log | cpipe run standard-distill

# Use with standard pipes (Python entry point)
grep "Critical" system.log | mcp-pipe run semantic-refinery
```

### Subcommand & Argument Parity
Both the Python CLI (`mcp-pipe`) and the Rust binary (`cpipe`) support identical interfaces:
- **`run <pipe_name>`**: Executes a named pipe from `pipes.json`. Supports:
  - `--config <path>` (automatically traverses parent directories up to a `.git` boundary to resolve relative paths).
  - `--input-file` / `--input_file <path>` to read from a file instead of stdin.
  - `--start-line` / `--start_line <N>` and `--end-line` / `--end_line <N>` for line-range slicing.
- **`run-dynamic <nodes_json>`**: Executes an ad-hoc JSON node array. Supports:
  - `--allow-shell` / `--allow_shell` to run shell utilities as dynamic pipe nodes.
  - **PowerShell JSON Normalization**: The Rust `cpipe` engine automatically detects and normalizes relaxed JSON structures (such as unquoted keys/values or single quotes, e.g. `[{cmd: grep}]`) passed via PowerShell into compliant RFC-JSON before parsing.
- **`verify`**: Evaluates system installation health (identical to the `pipe_verify` MCP tool).
- **`handoff`**: Distills and processes agent-to-agent output.
- **`list`**: Discovers and lists all configured pipes and shadow tools.
- **`stats`**: Prints the Context Balance Sheet (ROI).

### Direct Module Use
If the CLI executable isn't in your path, you can run the Python module directly:
```bash
cat data.txt | python -m context_pipe.cli run my-pipe
```

---

## 6. Telemetry & ROI

Context-Pipe tracks every character saved. You can view your **Context Balance Sheet** at any time.

*   **Terminal**: Run `context-pipe-server get_pipe_stats` (if the server is active).
*   **IDE**: Use the `/pipe-stats` slash command (if onboarded).

### Audit Headers
In the Sift-Centric model, the orchestrator is **silent**. Audit headers are generated and prepended by the engine nodes (e.g., `semantic-sift`) rather than the orchestrator itself.

```markdown
--- [Semantic-Sift Audit] ---
📊 Reduction: 65.4% (120.4KB -> 41.5KB)
🛡️ Guard: Trace-Verified (No Echo)
⚡ Latency: 145.2ms
-----------------------------
```

---

## 7. Auto-Onboarding

Context-Pipe includes an automated engine to configure your project workspace with one command.

### How to Onboard
Once you have connected the MCP server to your IDE, ask your AI assistant:
> *"Run `pipe_onboard(environment='Cursor')` to configure this project."*

Replace `'Cursor'` with your active environment (e.g., `'Gemini'`, `'VSCode'`, `'Windsurf'`, `'Claude'`, `'Cline'`, `'OpenCode'`). If `environment` is omitted, `pipe_onboard` **auto-detects** your IDE by inspecting environment variables and parent-process names across 12+ platforms.

### What Onboarding Does
1.  **Agent SOP Injection**: Injects the Context-Pipe SOP into `AGENTS.md`, `.cursorrules`, and other instruction files. This forces the agent to use `pipe_read_file` for all file I/O.
2.  **Hook Injection**: Automatically configures `.cursor/hooks.json` or `.github/hooks/` to use the `context-pipe wrap` polyfill for all other tool calls. For OpenCode, generates a TypeScript plugin at `.opencode/plugins/context-pipe.ts`. **Note**: the OpenCode plugin is currently a documented placeholder — `tool.execute.after` does not fire correctly for MCP tools as of v1.14.39 ([sst/opencode#21149](https://github.com/sst/opencode/issues/21149)). The `AGENTS.md` SOP mandate is the active interception strategy in OpenCode workspaces.
3.  **Security Gateways**: Injects blocking hooks into Windsurf and Cline to proactively prevent large native file reads.
4.  **Subagent Shielding**: Recursively discovers specialized agent configs (e.g., in `.cursor/agents/`) and applies context protection to them.
5.  **Refinery Auto-Link**: Discovers `semantic-sift-cli` across all known locations (current venv, system PATH, pipx, sibling venv directories) and writes its **absolute path** into `pipes.json`. This means context-pipe and semantic-sift can live in completely separate virtual environments — no manual linking required.
6.  **Performance Diagnostics**: Scans nodes for interpreted Python tax and warns if compiled binaries should be used.
7.  **Slash Command Injection** *(Phase 4)*: Injects `/pipe-stats` and `/pipe-run` as first-class slash commands into IDEs that support them:
    - **Gemini CLI**: writes `.gemini/commands/pipe-stats.md` and `pipe-run.md`.
    - **OpenCode**: adds entries to the `commands` block in `opencode.json`.
    - **Cursor**: adds an `onInit` hook in `.cursor/mcp.json`.
    All injections are idempotent (marker-block pattern) and safe to re-run.

---

## 7b. Shell Aliases (Optional — Phase 2)

For terminal-first workflows, Context-Pipe can install convenient shell aliases so `mcp-pipe` and `cpipe` work from any directory without activating the venv.

### Install
```
Ask your AI: "Run pipe_install_aliases()"
# or via CLI:
mcp-pipe aliases install
```

This writes a marker block into your shell profile:

| Shell | Profile |
|---|---|
| **bash** | `~/.bashrc` |
| **zsh** | `~/.zshrc` |
| **PowerShell** | `$PROFILE` |

### Remove
```
Ask your AI: "Run pipe_remove_aliases()"
# or via CLI:
mcp-pipe aliases remove
```

The remove operation is idempotent and leaves no residue in your profile.

---

## 8. Verifying the Installation

After onboarding, always verify the full stack is operational:
> *"Run `pipe_verify()` to confirm the installation."*

`pipe_verify` performs a health check across every component and returns a structured report:

```
## Context-Pipe Installation Report

✅ context-pipe: Installed at /path/to/context_pipe/orchestrator.py
✅ pipes.json (/path/to/pipes.json): 4 pipes defined
✅ semantic-sift-cli: semantic-sift 0.2.2 — /path/to/venv312/Scripts/semantic-sift-cli.exe
   > pipes.json nodes updated to use absolute path.

### Pipe Node Resolution
✅ /abs/path/to/semantic-sift-cli → `/abs/path/to/semantic-sift-cli`

Overall: ✅ All systems operational.
```

If semantic-sift is not found, the report will include actionable install instructions.

### Version Awareness & Self-Heal

Context-Pipe proactively checks for updates during `pipe_verify` and `pipe_onboard`. If a newer version is available on GitHub, the report will include a warning:

```
âš ï¸  Update Available: A newer version (v0.3.1) is available. Run `pip install --upgrade mcp-context-pipe` to apply.
```

This ensures you are always testing against the latest stable primitives without needing to manually monitor the repository.

### Supported Install Patterns

| Pattern | Works? |
| :--- | :--- |
| `uv pip install mcp-context-pipe` + `uv pip install semantic-sift` (same venv) | ✅ |
| `uv pip install mcp-context-pipe` + `uv pip install semantic-sift` (separate venvs) | ✅ Auto-linked by `pipe_onboard` / `pipe_verify` |
| `pipx install semantic-sift` | ✅ Discovered via pipx path |
| Clone both repos with dedicated venvs | ✅ Sibling venv discovery |
| `uv pip install mcp-context-pipe` only (no sift) | ✅ Graceful — pipes return helpful error |

---

## 9. Agent SOP — Full Capability Reference

After onboarding, the agent has access to the following tools and knows when to use each one. This section documents the complete decision tree injected into `AGENTS.md` and all slash command templates.

### Decision Tree

```
Incoming content or task
        │
        ├── Reading a file?
        │     ├── Unsure of size/type → pipe_analyze_file(path)
        │     └── Know the pipe → pipe_read_file(path, pipe_name, start_line, end_line)
        │
        ├── Large tool output (logs, API response, search results > 100 lines)?
        │     └── pipe_run("standard-distill", raw_output)
        │
        ├── Named pipe exists for this content type?
        │     └── list_pipes() → pipe_run(pipe_name, input_text)
        │
        ├── No named pipe fits — need a one-off graph?
        │     └── pipe_list_shadow_tools()
        │           → construct nodes_json (must end with semantic-sift-cli)
        │           → pipe_run_dynamic(nodes_json, input_text, allow_shell=<bool>)
        │
        ├── Passing output to another agent?
        │     └── pipe_agent_handoff(output, from_agent="X", to_agent="Y")
        │
        └── Want to see ROI?
              └── get_pipe_stats()
```

### Tool Reference for Agents

| Tool | When to call | Key rule |
|---|---|---|
| `pipe_analyze_file(path)` | Before `pipe_read_file` when unsure of pipe | Returns recommended `pipe_name` |
| `pipe_read_file(path, pipe_name, start_line, end_line)` | Instead of any native file read > 1KB | Default pipe: `standard-distill`; optional 1-indexed range boundaries |
| `list_pipes()` | Before `pipe_run` to see available named pipes | — |
| `pipe_run(pipe_name, input_text)` | When a named pipe matches the content type | Produces audit header |
| `pipe_list_shadow_tools()` | Always before `pipe_run_dynamic` | Discover available nodes |
| `pipe_run_dynamic(nodes_json, input_text)` | One-off graphs with no named pipe | Must end with `semantic-sift-cli` |
| `pipe_agent_handoff(output, ...)` | At every A2A boundary | Pass `pipe_name` if content type known |
| `get_pipe_stats()` | Anytime; proactively after heavy sessions | Reports cumulative ROI and Unmapped Heavy Calls (silent token leaks) |

### Slash Commands (injected by `pipe_onboard`)

| Command | IDE | What the agent does |
|---|---|---|
| `/pipe-stats` | Cursor, Gemini, Antigravity, OpenCode | Calls `get_pipe_stats`, displays Balance Sheet |
| `/pipe-run` | Cursor, Gemini, Antigravity, OpenCode | `list_pipes` → user picks → `pipe_run` |
| `/pipe-dynamic` | Cursor, Gemini, Antigravity, OpenCode | `pipe_list_shadow_tools` → build graph → confirm → `pipe_run_dynamic` |
| `/pipe-handoff` | Cursor, Gemini, Antigravity, OpenCode | `pipe_agent_handoff` at named A2A boundary |

---

## 10. Troubleshooting & Platform Notes

### Gemini CLI: "Tool result blocked"
When using the Gemini CLI, you will frequently see a message saying **`Tool result blocked:`** followed by the sifted text.

**This is not an error.** It is the intended behavior of the Gemini hook protocol:
- To replace raw tool output with sifted text, Context-Pipe must return a `decision: deny` command to the CLI.
- The Gemini CLI interprets this "Denial" as a security block and displays the warning label in the UI.
- In reality, the sifting was successful and the agent received the reduced context as intended.

---
*Building Systems, not Patches.*
