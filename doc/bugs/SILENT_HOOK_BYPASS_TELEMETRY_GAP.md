# Bug Report: Silent Hook Bypass & Telemetry Recording Gap

**Date:** May 17, 2026
**Severity:** Medium (Operational Blindness)
**Location:** `C:\Users\luism\Workbench\GitHub\context-pipe`
**Status** Fixed May 17, 2026

## 1. Symptoms
- The Gemini CLI hook fires correctly and appends the `--- [Context-Pipe: Native Execution] ---` signature to tool outputs.
- No **Audit Headers** (e.g., `--- [Context-Pipe: semantic-refinery] ---`) appear in the response.
- No telemetry is recorded in the project's `.pipe_telemetry.jsonl`.
- `context-pipe stats` reports **0 events**, even after processing large outputs (e.g., `yarn.lock`).

## 2. Root Cause Analysis
Based on deep-dive research into `context_pipe/wrapper.py` and `context_pipe/telemetry.py`:

### A. Silent Telemetry Loop (`wrapper.py`)
The telemetry logging logic is nested inside a loop that iterates over the `trace` returned by `run_pipe`.
```python
# wrapper.py
for entry in trace:
    if "error" in entry: continue
    log_telemetry(...)
```
If `trace` is empty (which happens if a pipe resolves to 0 nodes, hits the **Echo Guard**, or detects its own signature in the input), `log_telemetry` is never called. This makes it impossible to distinguish between a broken hook and a hook that simply chose to skip processing.

### B. Relative Path Ambiguity (`telemetry.py`)
`TELEMETRY_FILE` defaults to `.pipe_telemetry.jsonl`. When running as a hook in `homepage/`, it attempts to write to `homepage/.pipe_telemetry.jsonl`. 
- If the hook bypasses (as noted in A), the file is never created.
- `context-pipe stats` also uses a relative path, meaning it only shows ROI for the current directory, failing to provide a unified "Studio of Two" balance sheet unless a global environment variable is set.

### C. Signature Bypass Loop
Because the hook appends its signature to the *end* of the response, subsequent reads of the same context (e.g., `read_file` on a file previously output to the chat) trigger the signature-detection bypass logic, preventing further distillation.

## 3. Resolution (Fixed May 17, 2026)

The following changes were implemented and verified:

1. **Unified Telemetry Pathing**: `context_pipe/telemetry.py` now resolves `TELEMETRY_FILE` by traversing parent directories to find the project root (identified by `.pipe_identity` or `pipes.json`). This ensures ROI is tracked in a single location for the entire project.
2. **Bypass Event Tracking**: Added `log_bypass_event` to record reasons for Native Execution (e.g., `Signature detected`, `Echo Guard hit`, `Structured JSON`). 
3. **Echo Guard Collision Fix**: Updated `wrapper.py` to use a distinct `node_index=-1` for the pipe-level echo check, preventing it from colliding with the first node's hash.
4. **Balance Sheet Visibility**: Updated `context-pipe stats` to display `Hook Bypasses`, providing transparency into why the hook opted to skip distillation.

---
**Verified by:** Gemini CLI (Studio of Two) - Implemented May 17, 2026.
Implementation Summary:
- **Silent Orchestrator**: Context-Pipe is now fully transparent.
- **Self-Aware Engine**: Engine nodes handle their own bypass logic via audit headers.
- **Unified ROI**: Stats aggregate from the shared local ledger.
