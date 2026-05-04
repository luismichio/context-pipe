# Context-Pipe: Operator's Manual

Welcome to the **Context-Pipe Platform (CPP)**. This manual provides the definitive guide for setting up, configuring, and mastering high-fidelity context engineering.

---

## 1. Core Concepts

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
```json
{ "cmd": "context-pipe-skill", "args": ["security-auditor"] }
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

Replace `'Cursor'` with your active environment (e.g., `'Gemini'`, `'VSCode'`, `'Windsurf'`, `'Claude'`, `'Cline'`).

### What Onboarding Does
1.  **Mandate Injection**: Injects the Context-Pipe SOP into `AGENTS.md`, `.cursorrules`, and other instruction files. This forces the agent to use `pipe_read_file` for all file I/O.
2.  **Hook Injection**: Automatically configures `.cursor/hooks.json` or `.github/hooks/` to use the `context-pipe wrap` polyfill for all other tool calls.
3.  **Security Gateways**: Injects blocking hooks into Windsurf and Cline to proactively prevent large native file reads.
4.  **Subagent Shielding**: Recursively discovers specialized agent configs (e.g., in `.cursor/agents/`) and applies context protection to them.

---
*Building Systems, not Patches.*
