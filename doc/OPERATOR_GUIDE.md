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
pip install -e .
```

> The package name in `pyproject.toml` is `mcp-context-pipe` (PyPI) but installs as the `context_pipe` module. The editable install registers `context-pipe`, `context-pipe-server`, and `context-pipe-skill` CLI entry points.

### Step 4 — Cross-install semantic-sift into the master venv (editable)

```bash
pip install -e ../semantic-sift
```

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

pip install mcp
pip install -e .[neural]        # torch, transformers, llmlingua
```

> `semantic-sift/venv312` is the **neural runtime only**. The MCP server (`server.py`) loads the `semantic_sift` package via `sys.path` from the repo root — it does not require `semantic-sift` to be pip-installed in this venv.

### Step 6 — Register both MCP servers in opencode.json

In each project's `opencode.json`, register both servers. The `PIPE_CONFIG_PATH` env var must point to that project's own `pipes.json`.

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

### Step 7 — Verify `pipes.json` points to the correct sift-cli

Open `pipes.json` in your project root and confirm every node `cmd` is the **absolute path** to `context-pipe/venv/Scripts/semantic-sift-cli.exe`. If it isn't, ask your AI assistant:
> *"Run `pipe_verify()` to confirm the installation."*

`pipe_verify` will auto-link sift if the path is wrong or missing.

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

Context-Pipe supports three distinct ways to execute logic:

### A. Binary Nodes (Default)
Executes a standalone binary or Python script.
```json
{ "cmd": "sift-core", "args": ["logs"] }
```

### B. Bash Nodes (`shell: true`)
Executes arbitrary shell commands. Ideal for using standard Unix utilities.
```json
{ "cmd": "grep 'ERROR' | head -n 50", "shell": true }
```

### C. Skill Nodes
Applies an "Expert Lens" by injecting specialized mandates.

**Example: React Expert Chain**
This chain uses OS bash to auto-format the code with `eslint`, injects React 19 expert instructions from the MCP Market via a Skill Node, and then semantically condenses the result. The LLM receives pre-reviewed, compliant code.

```json
{
  "name": "react-expert-chain",
  "nodes": [
    { "cmd": "npx", "args": ["eslint", "--stdin", "--fix-dry-run"], "shell": true },
    { "cmd": "context-pipe-skill", "args": ["react-code-fix-linter"] },
    { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.6"] }
  ]
}
```

### D. Bring Your Own Parser (BYOP)
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

### E. Extreme Chaining (The God Pipe)
Because Context-Pipe is simply OS-level `stdin`/`stdout`, there is no theoretical limit to how many transformations you can chain. You can combine web fetching, bash filtering, skill masking, and neural compression into a single stream.

```json
{
  "name": "the-god-pipe",
  "description": "Fetch -> Extract -> Grep -> Mask -> Sift",
  "nodes": [
    { "cmd": "curl", "args": ["-s", "https://raw.githubusercontent.com/kubernetes/kubernetes/master/CHANGELOG/CHANGELOG-1.30.md"], "shell": true },
    { "cmd": "grep", "args": ["-i", "API"], "shell": true },
    { "cmd": "context-pipe-skill", "args": ["pii-masker"] },
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

Context-Pipe is designed to be used as a standalone CLI tool.

### Basic Execution
```bash
# Sift data from a file
cat app.log | context-pipe run standard-distill

# Use with standard pipes
grep "Critical" system.log | context-pipe run semantic-refinery
```

### Direct Module Use
If the CLI isn't in your path, use Python:
```bash
cat data.txt | python -m context_pipe.orchestrator run my-pipe
```

---

## 6. Telemetry & ROI

Context-Pipe tracks every character saved. You can view your **Context Balance Sheet** at any time.

*   **Terminal**: Run `context-pipe-server get_pipe_stats` (if the server is active).
*   **IDE**: Use the `/pipe-stats` slash command (if onboarded).

### Audit Headers
Every piped output includes a Markdown header:
```markdown
--- [Context-Pipe: standard-distill] ---
📊 Context: 65.4% Reduction (120.4KB -> 41.5KB)
⚡ Latency: 145.2ms
Nodes: context-pipe-ingest → semantic-sift-cli
-----------------------------
```

---

## 7. Auto-Onboarding

Context-Pipe includes an automated engine to configure your project workspace with one command.

### How to Onboard
Once you have connected the MCP server to your IDE, ask your AI assistant:
> *"Run `pipe_onboard(environment='Cursor')`"*

Replace `'Cursor'` with your active environment (e.g., `'Gemini'`, `'VSCode'`, `'Windsurf'`, `'Claude'`, `'Cline'`, `'OpenCode'`).

### What Onboarding Does
1.  **Mandate Injection**: Injects the Context-Pipe SOP into `AGENTS.md`, `.cursorrules`, and other instruction files. This forces the agent to use `pipe_read_file` for all file I/O.
2.  **Hook Injection**: Automatically configures `.cursor/hooks.json` or `.github/hooks/` to use the `context-pipe wrap` polyfill for all other tool calls. For OpenCode, generates a TypeScript plugin at `.opencode/plugins/context-pipe.ts`. **Note**: the OpenCode plugin is currently a documented placeholder — `tool.execute.after` does not fire correctly for MCP tools as of v1.14.39 ([sst/opencode#21149](https://github.com/sst/opencode/issues/21149)). The `AGENTS.md` SOP mandate is the active interception strategy in OpenCode workspaces.
3.  **Security Gateways**: Injects blocking hooks into Windsurf and Cline to proactively prevent large native file reads.
4.  **Subagent Shielding**: Recursively discovers specialized agent configs (e.g., in `.cursor/agents/`) and applies context protection to them.
5.  **Refinery Auto-Link**: Discovers `semantic-sift-cli` across all known locations (current venv, system PATH, pipx, sibling venv directories) and writes its **absolute path** into `pipes.json`. This means context-pipe and semantic-sift can live in completely separate virtual environments — no manual linking required.

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

### Supported Install Patterns

| Pattern | Works? |
| :--- | :--- |
| `pip install mcp-context-pipe` + `pip install semantic-sift` (same venv) | ✅ |
| `pip install mcp-context-pipe` + `pip install semantic-sift` (separate venvs) | ✅ Auto-linked by `pipe_onboard` / `pipe_verify` |
| `pipx install semantic-sift` | ✅ Discovered via pipx path |
| Clone both repos with dedicated venvs | ✅ Sibling venv discovery |
| `pip install mcp-context-pipe` only (no sift) | ✅ Graceful — pipes return helpful error |

---
*Building Systems, not Patches.*
