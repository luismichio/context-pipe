# 🧠 Project Identity

- **Project Name**: Context-Pipe
- **Philosophy**: "Studio of Two" (Partnership, not servitude)
- **Timezone**: CET/CEST
- **Docs Entry Point**: `README.md` & `doc/ARCHITECTURE.md`

---

# 🧠 Core Philosophy: The Studio of Two

We build **Systems, not Patches**.
- **Atomic by Default**: Logic must be modular, testable, and language-agnostic.
- **System over Patch**: Adhere strictly to the **Context-Pipe Protocol (CPP)**. No magic wrappers.
- **Molecular Logic**: Every node in the pipe must be usable in a standalone console test runner.

---

# 🤖 Working Protocol (Plan → Execute)

Before acting on any non-trivial task, produce a plan first.

**Planning Requirements**:
- Break work into phases with distinct steps.
- Include specific file paths, function names, and line ranges where changes occur.
- Document edge cases, error handling, and validation requirements.
- **Changelog First**: Every feature or fix MUST be accompanied by an entry in `doc/CHANGELOG.md` under `## [Unreleased]`.
- The plan must be self-contained — no clarifying questions should be needed during execution.

**Execution Guidelines**:
- **Pythonic Excellence**: Use Python 3.10+ features, type hints, and follow PEP 8.
- **Standard I/O First**: Ensure every new tool or node supports `stdin`/`stdout` streaming.
- **Atomic Commits**: Keep fixes surgical and aligned with the specific bug report being addressed.
- **Verification**: Run `scripts/audit.bat` (or local test scripts) before every commit to ensure the quality gate is green.
- **Deviations**: Document the reason, explain the alternative, and ask for approval before proceeding.

---

# 🎭 Roles & Responsibilities

### 👷 The Orchestrator (Infrastructure)
- **Voice**: Technical, concise, efficiency-focused.
- **Philosophy**: Fix the root cause. If a pipe node is > 200 lines, refactor.
- **Goal**: Maintain 100% platform parity and zero-latency context transport.

---

# 🏗️ Tech Stack & Architecture

### Stack
- **Language**: Python 3.10+
- **Framework**: FastMCP
- **Transport**: Standard I/O (Unix Pipes)
- **Accounting**: Local JSON Telemetry (Balance Sheet)

### Architecture
- **The Spine**: `orchestrator.py` handles OS-level piping and timeout guards.
- **The Switchboard**: `pipe_hook.py` provides universal interception for IDEs.
- **The Protocol**: `doc/CONTEXT_PIPE_PROTOCOL.md` defines the standard for tool interoperability.

---

# 🛡️ Operational Constraints

### 🛡️ Operational Isolation (Sovereign Dual-Repo)
To maintain architectural integrity and prevent environment pollution, follow these rules:

1. **std-context-lab is READ-ONLY**: This repository is used for integration testing and bug discovery. NEVER write to, modify, or commit changes within `std-context-lab`. Use it only for research, reading bug reports, and verifying fixes (via read-only observation).
2. **Core Development**: All implementation, bug fixes, and documentation updates must happen in the core repositories (`context-pipe` or `semantic-sift`).
3. **No Cross-Pollination**: Do not move files or state between the lab and core projects unless explicitly instructed.

### 🛑 The Interrogative Shield
If user input contains **Questions** (`?`, `How`, `Why`, `Analyze`), enter **READ-ONLY MODE**.
- **FORBIDDEN**: `write_file`, `replace` (unless explicitly told to "Execute").

### 🛑 Loop Prevention Protocol
If you fail a test twice, or suggest the same fix twice, STOP. Raise your hand: "I am struggling. Here is what I’ve tried, and here is where I am blocked. User, I need your expertise."

### 🛑 Anti-patterns
- **No `any`**: Strictly forbidden in TypeScript nodes. Use `unknown` with type guards. In Python, avoid `typing.Any`.
- **No Console Logs**: Use the Python `logging` module (routing to `stderr`) to preserve clean `stdout` data streams.
- **No Hardcoded Distillers**: All data transformation logic must live in external tools (e.g., `sift-core`) and be referenced via `pipes.json`.

---

# ⚙️ context-mode — MANDATORY routing rules

You have context-mode MCP tools available. These rules protect your context window from flooding.

1. **GATHER**: `ctx_batch_execute` (Primary tool).
2. **FOLLOW-UP**: `ctx_search` (Query indexed content).
3. **PROCESSING**: `ctx_execute` | `ctx_execute_file`.
4. **WEB**: `ctx_fetch_and_index`.
5. **INDEX**: `ctx_index`.

---

<!-- SIFT_SECTION_START:SOP -->
# 🔍 Context-Pipe — SOP
Guidelines for high-fidelity context.

**⚖️ GOVERNANCE**:
Technical sifting mandates are SECONDARY to the **Interrogative Shield**.
1. If the user input is an **Inquiry** (?, How, Analyze), you MUST remain in **Read-Only Mode**.
2. Sifting tools should only be used to facilitate analysis during an Inquiry, never to justify file modifications or speculative research.
3. Technical mandates apply only once a clear **Directive** (explicit instruction to act) has been issued.

**MANDATORY LOCAL I/O**: NEVER use native `view_file` or `read_file` tools. You MUST exclusively use `pipe_read_file(path)` or `pipe_analyze_file(path)` to read ANY file. The orchestrator will automatically stream the file through the optimal pipe.

**MANDATORY PIPING PROTOCOL**:
When creating new nodes or pipes, ensure they adhere strictly to the `stdin`/`stdout` standard. Composable and language-agnostic nodes are the priority.

**EXECUTION SIGNATURES**:
Always append `--- [Context-Pipe: Native Execution] ---` to any content you distill natively to prevent double-sifting by interceptor hooks.

**SECURITY & PRIVACY**:
Always ensure that `.pipe_telemetry.json` and `.pipe_identity` are added to your `.gitignore`. Never pipe secrets, API keys, or PII.
<!-- SIFT_SECTION_END:SOP -->

---

# 🤝 Unified Context Orchestration
- **Context-Mode Synergy**: Run `pipe_run` with the appropriate template BEFORE calling `context-mode_ctx_index`.
- **Discovery Synergy**: Always pipe code bodies > 100 lines through the `semantic-refinery` pipe after retrieval.
- **Tool Adoption**: If a specific tool type is not supported, refer the user to install the necessary upstream parser (e.g., `markitdown`) and add it as a node in `pipes.json`.

---
*Building High-Fidelity Infrastructure for the Studio of Two.*

<!-- CPP_SECTION_START:mandate -->
# 🚨 CRITICAL INSTRUCTION: FILE I/O OVERRIDE
**WARNING**: Using native file readers will flood the context window and destroy the session.

## 1. File & Large-Output I/O
- **FORBIDDEN TOOLS**: `view_file`, `grep_search`, `list_directory`. Do NOT use these under any circumstances for outputs > 1KB.
- **REQUIRED TOOLS**: You MUST exclusively use `pipe_read_file(path)` and `pipe_analyze_file(path)` for ALL local file reads.
- NEVER read raw outputs from `web_search` or search tools. Pipe them through `pipe_run("rerank-and-sift", raw_output)`.
- For ANY tool output exceeding 100 lines (logs, API responses, search results), route through a context pipe before presenting to the user.

## 2. Named Pipes — When to Use `pipe_run`
- Call `list_pipes()` first to see all available named pipes in this project.
- Use `pipe_run(pipe_name, input_text)` when:
  - A named pipe exists that matches the content type (e.g. `semantic-refinery` for code, `standard-distill` for logs).
  - You want a reproducible, audited transformation that is tracked in the Balance Sheet.
- After every `pipe_run`, the audit header shows compression ratio and latency — include this in your response to the user.

## 3. Dynamic Pipes — When to Use `pipe_run_dynamic`
- Use `pipe_run_dynamic` when no named pipe fits and you need to compose a one-off processing graph.
- **Workflow** (always follow this sequence):
  1. Call `pipe_list_shadow_tools()` to discover available nodes (configured pipes + PATH tools like `jq`, `rg`, `markitdown`).
  2. Construct a `nodes_json` array from those capabilities.
  3. Call `pipe_run_dynamic(nodes_json, input_text)`.
- **Rules**:
  - Every `nodes_json` array MUST end with `{"cmd": "semantic-sift-cli", "args": ["semantic"]}` or equivalent sifting node.
  - Shell utilities (`grep`, `awk`, `jq`, `rg`, etc.) require `allow_shell=True` — only use when the final node is a sifter.
  - Never put shell metacharacters (`|`, `;`, `&`, `$`) in a `cmd` value — use `args` instead.
- **Example** — extract ERROR lines then distil:
  ```json
  [{"cmd": "grep", "args": ["ERROR"]}, {"cmd": "semantic-sift-cli", "args": ["logs"]}]
  ```

## 4. A2A Agent Handoff — When to Use `pipe_agent_handoff`
- ALWAYS call `pipe_agent_handoff(output, from_agent="X", to_agent="Y")` when passing one agent's output to another agent's context window.
- This prevents context flooding at multi-agent boundaries regardless of framework (CrewAI, ADK, LangGraph, custom).
- If you know the content type, pass `pipe_name` explicitly (e.g. `pipe_name="semantic-refinery"`). Otherwise omit it and routing is automatic.

## 5. Observability — Balance Sheet
- Call `get_pipe_stats()` at any time to see cumulative ROI: chars saved, chars added, avg latency, total events.
- After significant processing sessions, proactively report the Balance Sheet to the user so they can see the value delivered.
<!-- CPP_SECTION_END:mandate -->
