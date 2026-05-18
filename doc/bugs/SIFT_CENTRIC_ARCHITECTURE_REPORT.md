# Architectural Refinement: Sift-Centric Telemetry & Transparency

**Date:** May 17, 2026
**Status:** Approved / Pending Implementation
**Target repositories:** `context-pipe`, `semantic-sift`

## 1. Problem Statement
The current "Dual-Layer" architecture (Orchestrator + Engine) causes several operational friction points:
- **Header Bloat**: Both layers attempt to add audit headers, cluttering the agent's context.
- **Bypass Rigidity**: The orchestrator's `CPP_SIGNATURE` detection is too aggressive, bypassing the *entire* pipe even when non-sift nodes (like `grep`) should still run.
- **Telemetry Gaps/Double-Counting**: Ambiguity over which layer should "pulse" to Supabase, leading to either silent operations or duplicate ROI records.

## 2. The "Studio of Two" Refined Model: Sift-as-Identity
We are moving to a model where **Semantic-Sift** is the sole source of visible identity and cloud telemetry, while **Context-Pipe** becomes a transparent, "invisible" orchestrator.

### A. Bypass Logic (Self-Aware Nodes)
- **Engine Level**: The `sift` node will now be responsible for its own bypass logic. If `semantic-sift-cli` detects its own audit header (`--- [Semantic-Sift Audit] ---`) in the input stream, it will immediately pass the input to `stdout` and exit.
- **Orchestrator Level**: `context-pipe` will remove its own signature-based bypass. It will **always** run the pipe, allowing subsequent nodes (e.g., `grep`) to process the text even if a previous `sift` node in the chain decided to bypass itself.

### B. Header & Signature Cleanup
- **Orchestrator Silence**: `context-pipe` will stop generating its own audit headers and will no longer append the `CPP_SIGNATURE`.
- **Engine Vocalization**: `semantic-sift` remains vocal by default. If it is the final node in a pipe, its header persists. If followed by a destructive node (e.g., `grep`), the header is naturally stripped, which is acceptable as the telemetry is already recorded.

### C. Telemetry Synchronization
- **One Pulse**: Only the engine (`sift`) is authorized to perform the HTTP POST "pulse" to the Supabase API.
- **Shared Local Ledger**: `context-pipe` will call the `semantic-sift` telemetry library strictly to update the **local JSON file** (for ROI balance sheets). It will pass a `pulse=False` flag to ensure the orchestrator-level event does not double-count in the cloud.
- **Environment Support**: `SIFT_TELEMETRY_OPTED_IN: "true"` will be propagated through the orchestrator to ensure child nodes can sync to the cloud.

## 3. Expected Behavioral Matrix

| Scenario | Final Header | Cloud Telemetry | Local ROI |
| :--- | :--- | :--- | :--- |
| `sift` only | Sift Header | Sift Pulse | Recorded |
| `sift -> grep` | None (Stripped) | Sift Pulse | Recorded |
| Re-reading sifted file | Sift Header (Existing) | 0 (Bypassed) | 0 (Bypassed) |
| `grep` only | None | None | 0 (System) |

---
**Verified by:** Gemini CLI (Studio of Two) - Implemented on May 17, 2026.
Implementation Summary:
- **Silent Orchestrator**: `context-pipe` wrapper now transparently executes pipes without adding headers or signatures.
- **Vocal Engine**: `semantic-sift-cli` now generates and prepends its own `--- [Semantic-Sift Audit] ---` headers.
- **Self-Aware Bypass**: `semantic-sift` kernel and CLI now detect existing headers and bypass processing to prevent double-sifting.
- **Shared Ledger**: Telemetry is synchronized via delegation to `semantic_sift.telemetry` (with cloud pulses disabled for the orchestrator layer).
- **Stability**: Fixed date-parsing and Windows encoding regressions in the telemetry engine.
