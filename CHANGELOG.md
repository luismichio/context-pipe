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
- **Universal Context Hook**: A platform-aware interceptor (`pipe_hook.py`) that subconsciously applies context pipes to tools in **Cursor, VS Code, Gemini CLI, Claude Desktop, and OpenCode**.

### 📊 Context Accounting & ROI
- **Context Balance Sheet**: Advanced telemetry engine that tracks "Signal Injected" (Augmentation) vs. "Noise Incinerated" (Reduction) across the entire supply chain.
- **Node-Level Tracing**: The orchestrator now records input/output sizes and latency for every individual node in a stream.
- **High-Fidelity Visibility**: Prepend a Markdown Audit Header to every distilled output, providing real-time feedback on reduction percentage, latency, and node-trace.
- **MCP ROI Tools**: Added `get_pipe_stats` tool and a high-fidelity `pipe_dashboard` prompt to make context health visible to AI agents.

### 🛡️ Graceful Resilience & Security
- **Async Timeout Guards**: Implemented node-level execution timeouts (default 10s) to prevent stalled pipes from hanging IDE agents.
- **The Echo Guard**: Integrated a disk-based hash detector to automatically bypass content processed within the last 30 seconds, preventing infinite loops and compute waste.
- **Dependency Awareness**: Implemented a `help_msg` system in `pipes.json`. If a required tool (like `sift-core` or `markitdown`) is missing from the system PATH, Context-Pipe returns a structured, helpful instruction instead of crashing.
- **Subagent Tracking**: Added high-fidelity `agent_label` extraction for **Cursor** ([Explore]/[Bash]) and **Gemini** threads, ensuring accurate ROI attribution.

### 🏗️ Infrastructure & Onboarding
- **Automated Hook Injection**: Added `pipe_onboard` MCP tool to automatically configure `.cursor/hooks.json`, `.github/hooks/`, and `opencode.json` with the absolute path to the Context-Pipe wrapper.
- **High-Fidelity Scaffolding**: Established the Studio of Two project standard, including `AGENTS.md` mandates, `task.md` tactical tracking, and `backlog.md` strategic planning.
- **Apache 2.0 Licensing**: Released under the Apache 2.0 license to facilitate industrial and enterprise adoption.
