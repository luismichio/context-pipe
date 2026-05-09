# Context-Pipe: Documentation Index

Welcome to the central hub for the **Context-Pipe Platform (CPP)**. This directory contains the technical specifications, integration guides, and operator manuals for the universal context switchboard.

---

### 1. [`doc/OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md)
*   **Intent**: The primary "How-To" guide for human operators and agents.
*   **Topics**:
    *   Installation & Sovereign Dual-Repo Pattern.
    *   Configuration logic for `pipes.json` and `~/.mcp-pipe.json`.
    *   Node Types: Binary, Bash, Skill, T-Pipe, MCP *(Phase 7.5)*.
    *   Terminal CLI Mastery (`mcp-pipe` + `cpipe` alias).
    *   Telemetry and ROI reporting (Context Balance Sheet).
    *   Shell Alias Injection (`inject_shell_aliases`).
    *   Agent SOP — Full Capability Reference (decision tree, tool table, slash commands).

### 2. [`doc/USE_CASES.md`](USE_CASES.md)
*   **Intent**: Real-world examples of chaining Bash, Skills, Shadow MCP tools, and Semantic-Sift.
*   **Topics**:
    *   PR Reviewer (ESLint + Skill + Sift).
    *   K8s Responder (Grep + Skill + Sift).
    *   Web Research Synthesizer (Firecrawl MCP + MarkItDown + Skill + Sift).
    *   Codebase Auditor (Bandit + Skill + Sift).
    *   Multi-Stage Refinery (double-sifting).
    *   Visual QA Bot (Playwright SPA Crawler).

### 3. [`doc/ARCHITECTURE.md`](ARCHITECTURE.md)
*   **Intent**: Technical specification of the system internals.
*   **Topics**:
    *   The Orchestration Spine (`orchestrator.py`).
    *   Dynamic Routing Engine logic.
    *   Subconscious Interceptor Hook (`wrapper.py`).
    *   Context Accounting (`telemetry.py`).
    *   The Skill Node (`skills.py`).
    *   Onboarding & Refinery Discovery (`onboarding.py`).
    *   **T-Pipes — Stream Splitting** (`orchestrator.py` §7): `tee` node schema, token substitution, silent-failure guarantee.
    *   **A2A Agent Handoff** (`a2a.py` §8): framework-agnostic distillation bridge for multi-agent pipelines.
    *   **Dynamic Pipe Engine** (`dynamic.py` §9): `SHELL_UTILITY_ALLOWLIST`, sift-terminal guard, `allow_shell` flag.
    *   **Global Configuration** (`config_loader.py` §10): `~/.mcp-pipe.json` merge logic and local precedence.
    *   **Slash Command Injection** (`onboarding.py` §11): `/pipe-run`, `/pipe-stats`, `/pipe-dynamic`, `/pipe-handoff` across Cursor, Gemini CLI, and OpenCode; shell alias injection.

### 4. [`doc/MCP_NODE_SPEC.md`](MCP_NODE_SPEC.md)
*   **Intent**: Full design specification for the `mcp` node type *(Phase 7.5 — approved for implementation)*.
*   **Topics**:
    *   Problem statement and motivating example (web research pipeline).
    *   Schema: `type`, `server`, `tool`, `input_key`, `servers` registry block.
    *   Runtime architecture: `_run_mcp_node()`, async promotion strategy.
    *   Echo Guard node-scope fix.
    *   `_validate_nodes()` extension rules.
    *   5-phase implementation plan (7.5-A through 7.5-E).

### 5. [`doc/CONTEXT_PIPE_PROTOCOL.md`](CONTEXT_PIPE_PROTOCOL.md)
*   **Intent**: The language-agnostic standard for context engineering.
*   **Topics**:
    *   Standard I/O requirements.
    *   The Native Execution Signature (Double-Sifting Protection).
    *   Dynamic Discovery standards.

### 6. [`doc/INTEGRATION_ENCYCLOPEDIA.md`](INTEGRATION_ENCYCLOPEDIA.md)
*   **Intent**: Compatibility matrix, payload specifications, and Master Configuration blocks for IDEs.
*   **Topics**:
    *   Support for Cursor, Windsurf, VS Code, Claude Code, OpenCode, and more.
    *   Hook injection logic and payload shapes.
    *   Security Gateways and Inhibitors.
    *   Standard, Unified, and Extended Configuration schemas.

### 7. [`doc/IDE_MCP_INTEGRATION_WIKI.md`](IDE_MCP_INTEGRATION_WIKI.md)
*   **Intent**: Exhaustive legacy reference for deep IDE integration patterns.

### 8. [`doc/CHANGELOG.md`](CHANGELOG.md)
*   **Intent**: Historical record of features, fixes, and architectural shifts.

---
*Building High-Fidelity Infrastructure for the Studio of Two.*
