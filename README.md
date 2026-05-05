# ⛓️ Context-Pipe

**The Universal Standard for Context Engineering.**

[![CI](https://github.com/luismichio/context-pipe/actions/workflows/ci.yml/badge.svg)](https://github.com/luismichio/context-pipe/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-2%20Passing-brightgreen)](tests/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-context-pipe)](https://pypi.org/project/mcp-context-pipe/)
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
Universal hooks that automatically apply your context pipes to *any* MCP tool call in IDEs like Cursor, VS Code, and Windsurf. For OpenCode, the `AGENTS.md` SOP mandate (`pipe_read_file` for all file reads) is the active strategy until transparent plugin interception is supported upstream.

---

## 🏗️ Getting Started

### 1. Installation

**Option A: Quick Install (PyPI)**
```bash
pip install mcp-context-pipe
pip install semantic-sift
```

**Option B: Sovereign Pattern (Recommended for Studio of Two)**
Clone both repos side-by-side. The `context-pipe` venv acts as the master environment holding both packages. See **[Section 0 of the Operator's Guide](doc/OPERATOR_GUIDE.md#0-installation-sovereign-dual-repo-pattern)** for the full sequence.

```bash
# 1. Clone both repos
git clone https://github.com/luismichio/context-pipe.git
git clone https://github.com/luismichio/semantic-sift.git

# 2. Master venv in context-pipe — holds both packages
cd context-pipe
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate
pip install -e .
pip install -e ../semantic-sift  # semantic-sift-cli lands in context-pipe/venv/Scripts/ (Win) or venv/bin/ (Mac/Linux)

# 3. ML runtime venv in semantic-sift (Python 3.12 for torch/CUDA compatibility)
cd ../semantic-sift
python3.12 -m venv venv312
# Windows:
.\venv312\Scripts\activate
# macOS/Linux:
# source venv312/bin/activate
pip install mcp
pip install -e .[neural]         # torch, transformers, llmlingua
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

---

## 📚 Documentation

Detailed documentation is available in the [`doc/`](./doc) directory.

*   **[doc/INDEX.md](doc/INDEX.md)**: The navigational roadmap for the documentation ecosystem.
*   **[doc/USE_CASES.md](doc/USE_CASES.md)**: Real-world, high-impact scenarios demonstrating how to chain Bash, Skills, and Semantic-Sift.
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

## 🔗 The Ecosystem (Studio of Two)

Context-Pipe is a foundational member of the **Studio of Two** infrastructure. It is designed to work in high-fidelity harmony with:

*   **[Semantic-Sift](https://github.com/luismichio/semantic-sift)**: The intelligent refinery for agentic context. Sift is the flagship distillation engine for Context-Pipe, providing the mathematical and neural sifting nodes used in our standard templates.

---

## ⚖️ Licensing
`context-pipe` is licensed under the **Apache License 2.0**. It is an "Open Source, Closed Contribution" project maintained by the Studio of Two to ensure architectural integrity.

---
*Building High-Fidelity Infrastructure for the Intelligence Age.*
