# Changelog

All notable changes to the **Context-Pipe** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-03

### ✨ High-Fidelity Foundation
- **Initial Release**: The official birth of the **Context-Pipe Protocol (CPP)**.
- **Universal Orchestrator**: Python-based engine (`orchestrator.py`) capable of streaming data through multi-node Unix pipelines using standard `stdin`/`stdout`.
- **Agnostic Routing Engine**: Implemented a dynamic `mappings` system in `pipes.json`. The system now automatically routes data to the optimal pipe based on:
    - **Tool Triggers**: Regex-based matching for tool names (e.g., `search|grep|find`).
    - **Size Triggers**: Automatic scaling of distillation based on character count thresholds.
- **Universal Context Hook**: A platform-aware interceptor (`pipe_hook.py`) that subconsciousy applies context pipes to tools in **Cursor, VS Code, Gemini CLI, Claude Desktop, and OpenCode**.

### 📊 Context Accounting & ROI
- **Context Balance Sheet**: Advanced telemetry engine that tracks "Signal Injected" (Augmentation) vs. "Noise Incinerated" (Reduction) across the entire supply chain.
- **Node-Level Tracing**: The orchestrator now records input/output sizes and latency for every individual node in a stream.
- **MCP ROI Tools**: Added `get_pipe_stats` tool and a high-fidelity `pipe_dashboard` prompt to make context health visible to AI agents.

### 🛡️ Graceful Resilience
- **Dependency Awareness**: Implemented a `help_msg` system in `pipes.json`. If a required tool (like `sift-core` or `markitdown`) is missing from the system PATH, Context-Pipe returns a structured, helpful instruction instead of crashing.
- **Execution Signatures**: Established the `--- [Context-Pipe: Native Execution] ---` signature to prevent "Double-Sifting" loops in nested agent environments.

### 🏗️ Infrastructure
- **High-Fidelity Scaffolding**: Established the Studio of Two project standard, including `AGENTS.md` mandates, `task.md` tactical tracking, and `backlog.md` strategic planning.
- **Apache 2.0 Licensing**: Released under the Apache 2.0 license to facilitate industrial and enterprise adoption.
