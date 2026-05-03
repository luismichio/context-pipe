# ⛓️ Context-Pipe

**The Universal Standard for Context Engineering.**

[![CI](https://github.com/luismichio/context-pipe/actions/workflows/ci.yml/badge.svg)](https://github.com/luismichio/context-pipe/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-2%20Passing-brightgreen)](tests/)
[![Python](https://img.shields.io/pypi/pyversions/context-pipe)](https://pypi.org/project/context-pipe/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue)](LICENSE.md)
[![OSI](https://img.shields.io/badge/OSI-Approved-brightgreen)](https://opensource.org/licenses/Apache-2.0)

`context-pipe` is a high-performance orchestration layer designed to bring the **Unix Philosophy** to the AI context window. It allows you to connect AI tools (Spokes) into a series of **Streams**, ensuring that data is refined, distilled, and noise-free before it ever reaches the LLM.

---

## 🚀 The Vision
In the "Studio of Two" philosophy, we build **Systems, not Patches**. `context-pipe` is the system that manages the flow of context, allowing you to chain specialized tools (Refineries) like `semantic-sift` into your agentic workflows with zero token overhead and millisecond latency.

---

## 🛠️ Core Components

### 1. The Context-Pipe Protocol (CPP)
A language-agnostic standard based on `stdin` and `stdout`. If a tool can read text and emit text, it can be a node in the pipe.

### 2. The Universal Switchboard
A lightweight orchestrator that manages multi-node data streams (e.g., `[Ingest] -> [Mask] -> [Rerank] -> [Distill]`).

### 3. Subconscious Interceptors
Universal hooks that automatically apply your context pipes to *any* MCP tool call in IDEs like Cursor, VS Code, and Windsurf.

---

## 🏗️ Getting Started

1. **Install the Orchestrator:**
   `pip install context-pipe` (or `pip install context-pipe[multi-modal]` for PDF support)

2. **Connect a Refinery:**
   `pip install semantic-sift` (Hybrid Engine) or `cargo install semantic-sift-core` (Native Sidecar)

3. **Configure your first Pipe:**
   Edit `pipes.json` to define your high-fidelity context streams.

---

## 📚 Documentation

Detailed documentation is available in the [`doc/`](./doc) directory.

*   **[doc/INDEX.md](doc/INDEX.md)**: The navigational roadmap for the documentation ecosystem.
*   **[doc/OPERATOR_GUIDE.md](doc/OPERATOR_GUIDE.md)**: Definitive guide for setup, terminal mastery, and `pipes.json` configuration.
*   **[doc/ARCHITECTURE.md](doc/ARCHITECTURE.md)**: Technical specifications of the orchestration spine and switchboard.
*   **[doc/CONTEXT_PIPE_PROTOCOL.md](doc/CONTEXT_PIPE_PROTOCOL.md)**: The language-agnostic standard for tool interoperability.
*   **[doc/INTEGRATION_ENCYCLOPEDIA.md](doc/INTEGRATION_ENCYCLOPEDIA.md)**: Master Compatibility Matrix for Cursor, VS Code, Gemini, and Claude.

---

## 💻 Terminal Usage

Context-Pipe follows the **Unix Philosophy**. You can use it as a standalone utility or inside existing bash chains.

```bash
# Sift a log file through the 'standard-distill' pipe
cat app.log | context-pipe run standard-distill

# Process a document through a multi-node refinery
cat spec.pdf | context-pipe run full-refinery > distilled_spec.md

# Pre-distill code for manual copy-pasting
cat server.py | context-pipe run semantic-refinery | clip
```

---

## 🔗 Advanced Node Types

Context-Pipe supports more than just simple binaries. You can chain standard OS tools and expert mandates.

### 1. Bash Nodes (`shell: true`)
Execute arbitrary shell commands as part of your pipe.
```json
{ "cmd": "grep 'ERROR'", "shell": true }
```

### 2. Skill Nodes
Apply an "Expert Lens" to the context by injecting specialized skill mandates.
```json
{ "cmd": "context-pipe-skill", "args": ["security-auditor"] }
```

---

## ⚖️ Licensing
`context-pipe` is licensed under the **Apache License 2.0**. It is an "Open Source, Closed Contribution" project maintained by the Studio of Two to ensure architectural integrity.

---
*Building High-Fidelity Infrastructure for the Intelligence Age.*
