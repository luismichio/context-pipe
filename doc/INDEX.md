# Context-Pipe: Documentation Index

Welcome to the central hub for the **Context-Pipe Platform (CPP)**. This directory contains the technical specifications, integration guides, and operator manuals for the universal context switchboard.

---

### 1. [`doc/OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md)
*   **Intent**: The primary "How-To" guide for human operators.
*   **Topics**:
    *   Installation & Basic Setup.
    *   Configuration logic for `pipes.json`.
    *   Understanding Node Types (Binary, Bash, Skill).
    *   Terminal CLI Mastery.
    *   Telemetry and ROI reporting.

### 2. [`doc/USE_CASES.md`](USE_CASES.md)
*   **Intent**: Real-world examples of chaining Bash, Skills, and Sift.
*   **Topics**:
    *   PR Reviewer (ESLint + Skill + Sift).
    *   K8s Responder (Grep + Skill + Sift).
    *   Web Synthesizer (Curl + MarkItDown + Skill + Sift).
    *   Codebase Auditor (Bandit + Skill + Sift).

### 3. [`doc/ARCHITECTURE.md`](ARCHITECTURE.md)
*   **Intent**: Technical specification of the system internals.
*   **Topics**:
    *   The Orchestration Spine (`orchestrator.py`).
    *   Dynamic Routing Engine logic.
    *   Subconscious Interceptor Hook (`pipe_hook.py`).
    *   Context Accounting (`telemetry.py`).

### 4. [`doc/CONTEXT_PIPE_PROTOCOL.md`](CONTEXT_PIPE_PROTOCOL.md)
*   **Intent**: The language-agnostic standard for context engineering.
*   **Topics**:
    *   Standard I/O requirements.
    *   The Native Execution Signature (Double-Sifting Protection).
    *   Dynamic Discovery standards.

### 5. [`doc/INTEGRATION_ENCYCLOPEDIA.md`](INTEGRATION_ENCYCLOPEDIA.md)
*   **Intent**: Compatibility matrix, payload specifications, and Master Configuration blocks for IDEs.
*   **Topics**:
    *   Support for Cursor, Windsurf, VS Code, Claude Code, and more.
    *   Hook injection logic and payload shapes.
    *   Security Gateways and Inhibitors.
    *   Standard, Unified, and Extended Configuration schemas.

### 6. [`doc/IDE_MCP_INTEGRATION_WIKI.md`](IDE_MCP_INTEGRATION_WIKI.md)
*   **Intent**: Exhaustive legacy reference for deep IDE integration patterns.

### 7. [`doc/CHANGELOG.md`](CHANGELOG.md)
*   **Intent**: Historical record of features, fixes, and architectural shifts.

---
*Building High-Fidelity Infrastructure for the Studio of Two.*
