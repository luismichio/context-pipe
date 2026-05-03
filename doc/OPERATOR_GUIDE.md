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

---

## 4. Understanding Triggers (Mappings)

Mappings allow the Switchboard to decide the best distillation strategy automatically.

1.  **Tool Trigger (`tool:regex`)**: Matches the name of the MCP tool being called.
    *   Example: `{"trigger": "tool:grep|search", "pipe": "semantic-refinery"}`
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
*Building Systems, not Patches.*
