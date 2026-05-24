# BUG REPORT: Gemini CLI Hook Regression & Discrepancies

## Status: Identified & Plan Approved
**Date**: May 24, 2026
**Environment**: Gemini CLI (Node.js based) on Windows
**Severity**: High (Breaks all transparent sifting and proactive gating)

---

## 1. Identified Gaps & Discrepancies

### Gap A: Missing Event Inference in `wrapper.py`
The refactored `wrap_payload` logic expects a `hook_event_name` key in the incoming JSON payload to distinguish between `BeforeTool`, `AfterTool`, and `PreCompress`. 
*   **Problem**: Gemini CLI does not natively inject `hook_event_name`. 
*   **Impact**: The wrapper fails to identify the context, defaults to a bypass state, and never invokes the engine nodes (like Semantic-Sift).

### Gap B: Incorrect Parameter Extraction for Gating
The proactive size gate attempts to extract the target file path via `data.get("tool_input", {})`.
*   **Problem**: Gemini CLI's payload schema uses the `arguments` key for tool inputs.
*   **Impact**: The gate fails to find the file path and silently allows large native reads to flood the context.

### Gap C: Brittle Environment in `onboarding.py`
The latest `_inject_gemini` logic drops explicit environment variable prefixes.
*   **Problem**: `PYTHONPATH` is missing from the command injected into `.gemini/settings.json`.
*   **Impact**: When the hook is triggered from a different working directory, it crashes with `ModuleNotFoundError: No module named 'context_pipe'`.

### Gap D: Zombie Code causing Logic Noise
The function `generate_audit_header` persists in `telemetry.py`.
*   **Problem**: This function generates a legacy `--- [Context-Pipe] ---` signature which contradicts the "Pure Switchboard" mandate (where only the Engine signs).
*   **Impact**: Leads to logic drift and confusion regarding which layer is responsible for the UI.

---

## 2. Fix Plan (Approved)

### Step 1: Fix Payload Plumbing (`context_pipe/wrapper.py`)
1.  **Event Inference**: Implement heuristic detection. If `hook_event_name` is missing:
    *   `response` or `tool_response` in payload -> `AfterTool`.
    *   `arguments` or `command` in payload -> `BeforeTool`.
2.  **Argument Parity**: Update the gatekeeper to check both `tool_input` and `arguments`.

### Step 2: Fix Onboarding Injection (`context_pipe/onboarding.py`)
1.  **Path Robustness**: Restore `$env:PYTHONPATH='{root_dir}'` (Windows) and `PYTHONPATH='{root_dir}'` (Unix) prefixes to the Gemini CLI hook command.

### Step 3: Incinerate Legacy Noise (`context_pipe/telemetry.py`)
1.  **Code Cleanup**: Delete the unused `generate_audit_header` function.

---

## 3. Verification Strategy

1.  **Proactive Gating**: Attempt a `read_file` on a >1KB file. Should be denied with a custom message.
2.  **Transparent Sifting**: Run `git log -n 500`. Should display the `--- [Semantic-Sift Audit] ---` signature. No Context-Pipe header should be present.
3.  **Telemetry Audit**: Verify `.pipe_telemetry.jsonl` contains a `tool_call` entry for the sifting event.

---

## 4. Codebase Audit (May 24, 2026)

> **Auditor**: OpenCode (claude-sonnet-4.6)
> **Scope**: Full codebase review against the bug report claims + environment-agnosticism audit.

### Bug Report Verdict

| Gap | Claim | Actual State | Verdict |
|-----|-------|--------------|---------|
| A | `wrap_payload` reads `hook_event_name` and fails without it | `wrap_payload` never reads `hook_event_name`; uses `extract_content()` shape-detection directly | **Stale / Does Not Match Code** |
| B | Gating reads `data.get("tool_input", {})` and misses `arguments` | `get_security_gateway_command()` uses `WINDSURF_TOOL_ARGS` env var (shell-level), not `tool_input`/`arguments` | **Stale / Does Not Match Code** |
| C | `PYTHONPATH` missing from `_inject_gemini` | `onboarding.py:867,869` — `PYTHONPATH` is present on both Windows and Unix paths | **Already Fixed** |
| D | `generate_audit_header` is unused zombie code | Actively imported and called in `cli.py:40,78` (used by `cpipe run` CLI path) | **Inaccurate — Live Code** |

### Real Gaps Found (Environment-Agnosticism Audit)

#### [REAL-1] PYTHONPATH Not Injected for Most Environments — **High**
`_inject_cursor`, `_inject_vscode_github`, `_inject_windsurf`, `_inject_claude`, `_inject_qwen`, and `_inject_codex` all pass the bare `cmd_str` to their hook configs **without any `PYTHONPATH` prefix**. Only `_inject_gemini` (`onboarding.py:867`) and `_inject_antigravity` (`onboarding.py:1181`) inject the env prefix.

*   **Impact**: Any of these environments will crash with `ModuleNotFoundError: No module named 'context_pipe'` when the hook fires from a directory other than the project root. This is the same root cause as Gap C, but affects the majority of supported environments.
*   **Fix**: Move `PYTHONPATH` prefix injection into `build_runtime_hook_command()` so all environments inherit it uniformly.

#### [REAL-2] Proactive Gating Is Windsurf-Only — **High**
`get_security_gateway_command()` (`onboarding.py`) is the only gating mechanism. It reads the `WINDSURF_TOOL_ARGS` environment variable — a Windsurf-specific convention. No equivalent gating exists for Cursor, Claude Code, VSCode, Gemini CLI, or any other environment.

*   **Impact**: The ">1KB file blocking" feature described in the Verification Strategy only works in Windsurf. All other environments silently allow large native reads.
*   **Fix**: Design a generic `BeforeTool` interception path in `wrapper.py` that reads file paths from the payload (under both `tool_input` and `arguments` keys) to enable cross-environment proactive gating.

#### [REAL-3] `inject_content()` Has No `BeforeTool` Shape — **Medium**
`platforms.py:inject_content()` only handles `AfterTool`-style responses (injecting processed content back). There is no response shape for blocking/denying a call in non-Gemini environments.

*   **Impact**: Even if a `BeforeTool` intercept were added, there is no standardized way to signal a block to Cursor, Claude, or VSCode hooks.

#### [REAL-4] `agent_label` Detection Is Partial — **Low**
Subagent labeling in `extract_content()` is implemented only for Cursor and Gemini CLI. All other platforms return `None`, reducing telemetry attribution fidelity.

#### [REAL-5] Claude / Qwen / Codex Hook Matcher Is Too Narrow — **Medium**
`_inject_claude`, `_inject_qwen`, `_inject_codex` use the matcher `mcp__.*__.*`, which only intercepts MCP tool calls. Native tool hooks (e.g., bash execution, file reads via built-in tools) are not covered.

---

### Revised Fix Priority

1.  **[REAL-1]** Centralise `PYTHONPATH` injection in `build_runtime_hook_command()` — unblocks all non-Gemini environments.
2.  **[REAL-2]** Design generic `BeforeTool` gating in `wrapper.py` reading both `tool_input` and `arguments`.
3.  **[REAL-5]** Broaden Claude/Qwen/Codex hook matchers to cover native tools.
4.  **[REAL-3]** Add cross-platform deny/block response shape to `inject_content()`.
5.  **[REAL-4]** Extend `agent_label` detection to remaining platforms.
