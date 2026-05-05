# Context-Pipe: Architecture Specification

This document provides the technical specification of the Context-Pipe system's core orchestration, routing, and telemetry layers. It is strictly aligned with the implemented codebase.

---

## 1. The Orchestration Spine (`orchestrator.py`)

The heart of the platform is a high-performance Python-based engine designed to execute multi-node data pipelines at the OS level.

### Standard Stream Execution
The orchestrator utilizes `subprocess.Popen` to create memory-resident pipes between nodes.
- **`stdin` (The Input)**: Each node reads data from its standard input.
- **`stdout` (The Output)**: The node's transformed data is captured and passed to the next node's `stdin`.
- **`stderr` (The Error Stream)**: Redirected to a trace map to ensure node failures are reported without polluting the data stream.

### The Timeout Guard
Every node execution is wrapped in a **Timeout Guard** (default: 10s). If a node hangs (e.g., a stalled network fetch or a heavy neural model), the orchestrator kills the process, prevents an IDE freeze, and returns a structured `--- [Context-Pipe: Timeout] ---` response.

---

## 2. Dynamic Routing Engine

Context-Pipe uses a data-driven approach to routing, defined in `pipes.json`.

### Agnostic Trigger Logic
The system resolves the optimal pipe name based on three prioritized triggers:
1.  **Tool Trigger (`tool:<regex>`)**: Matches the calling tool name (e.g., `tool:search|grep`).
2.  **Size Trigger (`size:><num>`)**: Activates aggressive pipes for massive payloads (e.g., `size:>10000`).
3.  **Default Fallback**: Ensures a safety-net pipe is always applied.

### Pipe Templates
Instead of bundling code, Context-Pipe provides **Recipes**. Templates demonstrate how to chain external refineries:
- **`standard-distill`**: Routes to `semantic-sift-cli logs`.
- **`semantic-refinery`**: Routes to `semantic-sift-cli semantic`.
- **`full-refinery`**: Routes to `context-pipe-ingest | semantic-sift-cli`.

---

## 3. The Universal Switchboard (`pipe_hook.py`)

The platform includes a "Subconscious Interceptor" that acts as a universal polyfill for AI agents.

### Platform detection
Using `platforms.py`, the hook identifies the host environment via:
- **Environment Variables**: Fingerprints for 12+ platforms (Antigravity, Cursor, Windsurf, etc.).
- **Parent Process Inspection**: High-fidelity detection via `psutil`.

### The Polyfill Wrapper (`wrapper.py`)
The Switchboard logic is decoupled into a reusable wrapper that performs:
1.  **JSON-to-Raw Extraction**: Extracts signal from `tool_response`, `result`, or `content` keys.
2.  **Structured Data Exemption**: Automatically bypasses valid JSON dictionaries to prevent syntax corruption.
3.  **The Echo Guard**: Uses a disk-persistent hash detector (30s TTL) to prevent "Double-Sifting" loops in nested environments.

---

## 4. Context Accounting (`telemetry.py`)

Telemetry in Context-Pipe is designed as a **Context Balance Sheet**.

### Supply Chain Traceability
The system records a `Trace Map` for every execution:
- **Input/Output Sizes**: Tracks the exact growth or reduction of every node.
- **Node Latency**: Identifies bottlenecks in the "Supply Chain."
- **Agent Attribution**: Tracks specific subagent labels (e.g., `[Explore]`, `[Bash]`) for granular ROI reporting.

### High-Fidelity Visibility
To satisfy the **Expectation Effect**, the platform prepends a Markdown **Audit Header** to all processed content. This ensures the human architect and the AI partner are always aware of the context's health and ROI.

---

## 5. Onboarding & Refinery Discovery (`onboarding.py`)

The onboarding module is responsible for bootstrapping Context-Pipe into any IDE or CLI environment and for establishing a reliable link to external refineries like `semantic-sift`.

### Refinery Discovery (`discover_sift_executable`)

Because `semantic-sift` may be installed in a completely separate virtual environment, Context-Pipe uses a multi-stage discovery algorithm to locate its CLI binary at onboard time:

1. **Current venv** (`sys.prefix/Scripts|bin`)
2. **System PATH** (`shutil.which`)
3. **pipx** (`~/.local/pipx/venvs/semantic-sift/`)
4. **Sibling venv directories** — walks up to 4 levels to find a `../semantic-sift/venv*/` pattern
5. **User home venvs** (`~/.venv`, `~/venv`)

### Refinery Linking (`resolve_pipes_config`)

Once the binary is discovered, `resolve_pipes_config` rewrites every `semantic-sift-cli` node in `pipes.json` with the resolved **absolute path**. This operation is idempotent and safe to call repeatedly. The orchestrator then uses this absolute path directly, bypassing any PATH ambiguity between isolated environments.

### Installation Verification (`verify_installation`)

`verify_installation` performs a structured health check:
- Is `context_pipe.orchestrator` importable?
- Does `pipes.json` exist and parse as valid JSON?
- Is `semantic-sift-cli` discoverable and responsive (`--version`)?
- Is every node command in `pipes.json` resolvable on disk or PATH?

The results are surfaced via the `pipe_verify` MCP tool, which also auto-runs `resolve_pipes_config` to link sift before reporting.

---
*High-Fidelity Infrastructure for the Studio of Two.*
