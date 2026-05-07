# Context-Pipe: Integration Encyclopedia

This document serves as the master compatibility map and configuration authority for the **Context-Pipe Platform (CPP)**. It details how the system orchestrates context across a highly fragmented ecosystem of IDEs, AI coding assistants, and CLI agents.

---

## 1. Supported Environments & Compatibility Map

The ecosystem of MCP clients falls into specific architectural categories regarding how they handle tool execution and middleware interception.

### Explicitly Supported (Smart & Blind Hooks)
These environments have dedicated logic implemented in `pipe_hook.py` for payload extraction and reinjection.

*   **Gemini CLI**: 
    *   **Architecture**: Native platform event hooks (`AfterTool`, `PreCompress`). 
    *   **Support**: Full support for standard piping and lifecycle "Compaction" events.
*   **Claude Code, Qwen CLI & Codex CLI**:
    *   **Architecture**: `PostToolUse` deterministic shell command execution with regex matching (`mcp__.*__.*`).
    *   **Support**: Injected into `~/.claude/settings.json`, `~/.qwen/settings.json`, or `~/.codex/settings.json`.
*   **VS Code (Copilot)**:
    *   **Architecture**: `PostToolUse` shell command execution.
    *   **Support**: Injected into `.github/hooks/context-pipe.json`.
*   **Cursor & Roo Code**:
    *   **Architecture**: `postToolUse` and `beforeMCPExecution` triggers via `hooks.json`.
    *   **Support**: Merges hook execution commands into `.cursor/hooks.json`. Relies on the **Echo Guard** to prevent loops.
*   **OpenCode & OpenClaw**:
    *   **Architecture**: Native TypeScript Plugins via `tool.execute.after` hook.
    *   **Support**: Generates a TypeScript plugin at `.opencode/plugins/context-pipe.ts`. **Note**: As of OpenCode v1.14.39, `tool.execute.after` fires with the raw `CallToolResult` shape for MCP tools (not the declared `{title, output, metadata}` shape), making output mutation a no-op for all MCP tools. The generated plugin is currently a documented placeholder. Interception will be re-enabled once the upstream fix lands ([sst/opencode#21149](https://github.com/sst/opencode/issues/21149)). In the interim, the `AGENTS.md` SOP mandate (`pipe_read_file` for all file reads) is the active interception strategy.
*   **Windsurf & Cline**:
    *   **Architecture**: Security Gateway.
    *   **Support**: Injected into `.windsurf/hooks.json` or `.clinerules/hooks/`. Automatically blocks native file readers > 1KB to force the use of `pipe_read_file`.

---

## 2. Master Configuration Matrix (Installation)

To install the Context-Pipe server, find your software in the matrix below and copy the appropriate schema from Section 3.

| Software | Configuration Path | Target Key | Expected Schema |
| :--- | :--- | :--- | :--- |
| **Claude Desktop** | Win: `%APPDATA%\Claude\claude_desktop_config.json` / Mac: `~/Library/Application Support/Claude/claude_desktop_config.json` | `mcpServers` | **A** (Standard) |
| **Claude Code** | `~/.claude/settings.json` | `mcp_servers` | **A** (Standard) |
| **Qwen CLI** | `~/.qwen/settings.json` | `mcp_servers` | **A** (Standard) |
| **Codex CLI** | `~/.codex/mcp-config.json` | `mcpServers` | **A** (Standard) |
| **Continue.dev** | `~/.continue/config.json` | `mcpServers` | **D** (Unified) |
| **Zed** | `~/.config/zed/settings.json` | `context_servers` | **A** (Standard) |
| **VS Code Copilot**| `~/.copilot/mcp-config.json` | `mcpServers` | **A** (Standard) |
| **OpenCode** | `<project-root>/opencode.json` (project-level) or `%APPDATA%/opencode/opencode.json` (global) | `mcp` | **B** (Array) |
| **Google Antigravity**| `~/.gemini/antigravity/mcp_config.json` | `mcpServers` | **A** (Standard) |
| **Cline / Roo Code** | IDE settings menu | `mcpServers` | **C** (Extended) |

---

## 3. Configuration Schemas

### A. Standard Schema (JSON Object)
```json
"context-pipe": {
  "command": "/path/to/python.exe",
  "args": ["-m", "context_pipe.server"],
  "env": {
    "PIPE_CONFIG_PATH": "/path/to/your/pipes.json",
    "PIPE_NODE_TIMEOUT_MS": "10000"
  }
}
```

### B. Local Array Schema (OpenCode)
```json
"context-pipe": {
  "type": "local",
  "command": [
    "/path/to/python.exe", 
    "-m", 
    "context_pipe.server"
  ],
  "environment": {
    "PIPE_CONFIG_PATH": "/path/to/your/pipes.json"
  }
}
```

### C. Extended Schema (Cline / Roo Code)
```json
"context-pipe": {
  "command": "/path/to/python.exe",
  "args": ["-m", "context_pipe.server"],
  "env": {
    "PIPE_CONFIG_PATH": "/path/to/your/pipes.json"
  },
  "autoApprove": ["pipe_read_file", "pipe_analyze_file", "pipe_run", "get_pipe_stats"]
}
```

### D. Unified Schema (Windsurf, Continue.dev)
```json
"context-pipe": {
  "type": "stdio",
  "command": "/path/to/python.exe",
  "args": ["-m", "context_pipe.server"],
  "env": {
    "PIPE_CONFIG_PATH": "/path/to/your/pipes.json"
  }
}
```

---

## 4. Onboarding & Hook Injection (`onboarding.py`)

The `pipe_onboard` tool acts as the automated configuration engine, ensuring that all available security gateways, hook registries, and agent instruction files are primed for Context-Pipe.

### A. Mandate Enforcement
The `inject_mandates` function targets specific files to enforce the "Path-Native" standard.
*   **Targets**: `AGENTS.md`, `GEMINI.md`, `.clinerules`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`.
*   **Mandate**: Demands the use of `pipe_read_file(path)` for all file access, ensuring every byte is processed by the optimal pipe.

### B. Automated Hook Injection
Safely merges execution commands into existing IDE configurations:
*   **Post-Tool Shell Hooks**: Injects `context-pipe wrap` into Cursor, VS Code, Claude Code, Qwen CLI, and Codex CLI.
*   **Pre-Tool Security Gateways**: Injects blocking logic into Windsurf (`hooks.json`) and Cline (`PreToolUse.ps1`).

### C. Recursive Subagent Discovery
During onboarding, the engine performs a recursive crawl of the workspace (up to 3 levels deep) to shield isolated background threads:
*   **Specialized Agent Folders**: Specifically targets `.cursor/agents/`, `.codex/agents/`, `.junie/agents/`, and `.agents/`.
*   **Scoped Mandates**: Identifies any `AGENTS.md` files located in subdirectories and injects the context protection SOP.

---

## 5. Payload Structures & Interception Logic (`wrapper.py`)

### 1. Smart Hooks (CLI Agents & Plugins)
*   **Gemini/OpenClaw**: Detects `AfterTool` or `Compacting` event names. Extracts `tool_response.llmContent`.
*   **Reinjection**: Injects ROI metrics into Gemini's `additionalContext` or prepends the **Audit Header** to the text result.
*   **OpenCode**: Plugin hook (`tool.execute.after`) is registered but currently inactive for MCP tools — see compatibility note in Section 1. The `AGENTS.md` SOP mandate is the active strategy.

### 2. Blind Hooks (IDEs)
*   **VS Code & Cursor**: Scans the incoming JSON for keys like `result` or `tool_response.llmContent`.
*   **Reinjection**: Overwrites the found key with the piped text, prepended with the Audit Header and the CPP Signature.

---

## 6. The Context-Pipe Signature (Bypass)

To prevent **Double-Sifting** and infinite loops:
1.  All processed content is appended with: `\n\n--- [Context-Pipe: Native Execution] ---`.
2.  The wrapper explicitly scans content for this signature and the legacy `--- [Semantic-Sift Audit] ---` signature. If found, it instantly bypasses processing.

---
*Building High-Fidelity Infrastructure for the Studio of Two.*
