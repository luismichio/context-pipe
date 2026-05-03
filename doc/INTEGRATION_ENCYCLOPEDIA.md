# Context-Pipe: Integration Encyclopedia

This document serves as the master compatibility map and payload specification authority for the **Context-Pipe Platform (CPP)**. It details how the system orchestrates context across a highly fragmented ecosystem of IDEs, AI coding assistants, and CLI agents.

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
    *   **Architecture**: Native TypeScript Plugins.
    *   **Support**: Generates custom TypeScript wrappers at `.opencode/plugins/context-pipe.ts` or `.openclaw/plugins/context-pipe.ts`.
*   **Windsurf & Cline**:
    *   **Architecture**: Security Gateway.
    *   **Support**: Injected into `.windsurf/hooks.json` or `.clinerules/hooks/`. Automatically blocks native file readers > 1KB to force the use of `pipe_read_file`.

---

## 2. Onboarding & Mandate Injection (`onboarding.py`)

The `pipe_onboard` tool acts as the automated configuration engine, ensuring that all available security gateways, hook registries, and agent instruction files are primed for Context-Pipe.

### A. Mandate Enforcement
The `inject_mandates` function targets specific files to enforce the "Path-Native" standard.
*   **Targets**: `AGENTS.md`, `GEMINI.md`, `.clinerules`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`.
*   **Mandate**: Demands the use of `pipe_read_file(path)` for all file access, ensuring every byte is processed by the optimal pipe.

### B. Automated Hook Injection
Safely merges execution commands into existing IDE configurations:
*   **Post-Tool Shell Hooks**: Injects `context-pipe wrap` into Cursor, VS Code, Claude Code, Qwen CLI, and Codex CLI.
*   **Pre-Tool Security Gateways**: Injects blocking logic into Windsurf (`hooks.json`) and Cline (`PreToolUse.ps1`).

---

## 3. Payload Structures & Interception Logic (`wrapper.py`)

### 1. Smart Hooks (CLI Agents & Plugins)
*   **Gemini/OpenCode/OpenClaw**: Detects `AfterTool` or `Compacting` event names. Extracts `tool_response.llmContent`.
*   **Reinjection**: Injects ROI metrics into Gemini's `additionalContext` or prepends the **Audit Header** to the text result.

### 2. Blind Hooks (IDEs)
*   **VS Code & Cursor**: Scans the incoming JSON for keys like `result` or `tool_response.llmContent`.
*   **Reinjection**: Overwrites the found key with the piped text, prepended with the Audit Header and the CPP Signature.

---

## 4. The Context-Pipe Signature (Bypass)

To prevent **Double-Sifting** and infinite loops:
1.  All processed content is appended with: `\n\n--- [Context-Pipe: Native Execution] ---`.
2.  The wrapper explicitly scans content for this signature and the legacy `--- [Semantic-Sift Audit] ---` signature. If found, it instantly bypasses processing.

---

## 5. Master Configuration Matrix (MCP Server Installation)

| Software | Configuration Path | Target Key | Expected Schema Style |
| :--- | :--- | :--- | :--- |
| **Claude Desktop** | `~/AppData/Roaming/Claude/claude_desktop_config.json` | `mcpServers` | Standard |
| **Claude Code** | `~/.claude/settings.json` | `mcp_servers` | Standard |
| **Qwen CLI** | `~/.qwen/settings.json` | `mcp_servers` | Standard |
| **Codex CLI** | `~/.codex/mcp-config.json` | `mcpServers` | Standard |
| **Continue.dev** | `~/.continue/config.json` | `mcpServers` | Unified |
| **Zed** | `~/.config/zed/settings.json` | `context_servers` | Standard |
| **VS Code Copilot**| `~/.copilot/mcp-config.json` | `mcpServers` | Standard |
| **OpenCode** | `~/.opencode.json` | `mcpServers` | Local Array |
| **Google Antigravity**| `~/.gemini/antigravity/mcp_config.json` | `mcpServers` | Standard |

### A. Standard Schema (Gemini, Claude, Cursor, Copilot, Zed, Codex)
```json
"context-pipe": {
  "command": "python",
  "args": ["-m", "context_pipe.server"]
}
```

### B. Local Array Schema (OpenCode, Kilo Code)
```json
"context-pipe": {
  "type": "local",
  "command": ["python", "-m", "context_pipe.server"]
}
```

### C. Extended Schema (Cline / Roo Code)
```json
"context-pipe": {
  "command": "python",
  "args": ["-m", "context_pipe.server"],
  "autoApprove": ["pipe_read_file", "pipe_analyze_file", "pipe_run", "get_pipe_stats"]
}
```

### D. Unified Schema (Continue, Windsurf)
```json
"context-pipe": {
  "type": "stdio",
  "command": "python",
  "args": ["-m", "context_pipe.server"]
}
```

---
*Building High-Fidelity Infrastructure for the Studio of Two.*
