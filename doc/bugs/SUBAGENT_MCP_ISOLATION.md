# Bug Report: Subagent MCP Tool Isolation

**Filed**: 2026-05-14  
**Status**: Confirmed — OpenCode Bug ([#16491](https://github.com/anomalyco/opencode/issues/16491))  
**Affects**: OpenCode sessions using `Task` subagents  
**Priority**: Medium  
**Environment**: OpenCode 1.14.50

---

## Summary

OpenCode subagents spawned via the `Task` tool can **see** MCP tools in their tool registry but **cannot execute** them. The permission check at call time denies execution because MCP tools are never granted permissions during subagent session creation.

This is an OpenCode defect ([#16491](https://github.com/anomalyco/opencode/issues/16491)), not an architectural constraint. The subagent *should* be able to use MCP tools; the session creation logic simply forgot to wire the permissions.

The issue is **not exclusive to OpenCode** — any platform that isolates subagent sessions from the parent's MCP permissions exhibits the same problem.

---

## Symptom Observed

During the 2026-05-14 codebase audit (session `ses_1d993af1dffe0eMl8Od7XHeCI5`):

1. The parent agent delegated the audit to a subagent via `Task(subagent_type="explore")`.
2. The subagent could not call context-pipe MCP tools (`pipe_read_file`, `pipe_agent_handoff`, etc.).
3. It fell back to native `Read`/`Glob`/`Grep` tools — violating the **Context-Pipe Mandate** in `AGENTS.md` line 100:
   > "NEVER use native `view_file` or `read_file` tools. You MUST exclusively use `pipe_read_file(path)` to read ANY file."
4. The subagent's full reasoning and all tool call results entered the parent's context window **raw and un-distilled** — defeating context-pipe's purpose entirely.
5. The parent could not retroactively pipe the output because it had already crossed the handoff boundary.

---

## Root Cause

Identified in OpenCode issue [#16491](https://github.com/anomalyco/opencode/issues/16491):

**File**: `packages/opencode/src/tool/task.ts`, lines 66–102

When creating a subagent session, only native tools (`todowrite`, `todoread`, `task`) are granted explicit permissions. MCP tools are **not included** in the session's permission array:

```typescript
return await Session.create({
  parentID: ctx.sessionID,
  title: params.description + ` (@${agent.name} subagent)`,
  permission: [
    {
      permission: "todowrite",
      pattern: "*",
      action: "deny",
    },
    {
      permission: "todoread",
      pattern: "*",
      action: "deny",
    },
    // MCP tools are NOT granted permission here
  ],
})
```

**File**: `packages/opencode/src/session/prompt.ts`, lines 773–780

When MCP tools are added to the subagent's tool registry, they are wrapped with a permission check via `ctx.ask()`. The permissions are merged from `input.agent.permission` and `input.session.permission` (line 778), but since the subagent session has no MCP tool permissions, the check fails at call time.

**Result**: MCP tools appear in the subagent's `available_functions` list but return a permission-denied error when invoked.

---

## Impact on Context-Pipe

1. **Mandate Violation**: Any file read delegated to a subagent silently bypasses context-pipe distillation. The parent bears responsibility but cannot enforce compliance inside the subagent.

2. **Context Window Inflation**: Raw file contents + subagent reasoning + tool call output all enter the parent context unprocessed. A task meant to *save* context (by delegating) actually *costs* more context.

3. **No Post-Hoc Recovery**: By the time the subagent returns, the damage is done. The output is already in context. `pipe_agent_handoff` can distil *future* handoffs but cannot retroactively compress already-loaded content.

4. **False Economy**: The subagent pattern appears to reduce context (get a summary, not the raw work) but in practice returns all internal tool calls and reasoning. For exploration tasks, the subagent's internal trace is often larger than the result it produces.

---

## Affected Scenarios

| Scenario | Risk | Reason |
|----------|------|--------|
| Delegating file reads to subagent | **Critical** | Direct mandate violation; raw file content bypasses pipe |
| Delegating large-codebase exploration | **High** | Subagent reads dozens of files natively; all enter parent context raw |
| Delegating multi-step research | **Medium** | Subagent produces large intermediate output; no pipe distillation on return |
| Delegating narrow single-glob/grep task | **Low** | Small output; minimal context cost; subagent's file access is acceptable |
| Subagent piping its own output through `semantic-sift-cli` via bash | **Low** | Subagent has bash access and can run sift in-process; output is pre-distilled |

---

## Workarounds

### Workaround A: Pre-Distil, Then Delegate (Recommended)

Parent reads files through context-pipe first, then feeds the already-distilled output to the subagent:

```
Parent: pipe_read_file("orchestrator.py", pipe_name="semantic-refinery")
     → receives ~500 tokens of distilled content
Parent: Task(prompt="Analyze this distilled content: <500 tokens>")
     → subagent never touches raw files; mandate preserved
```

### Workaround B: Subagent Self-Pipes Through Semantic-Sift

Since subagents have `bash` access and `semantic-sift-cli` is on `PATH`, the subagent can pipe its own output before returning:

```
# Inside subagent prompt:
"After your analysis, run: echo <result> | semantic-sift-cli semantic"
```

Or for larger output, the subagent writes to a temp file and pipes it:

```
"Write your full analysis to a temp file, then run:
  type temp.txt | semantic-sift-cli semantic
Return only the distilled output."
```

**Caveat**: `semantic-sift-cli` must be on `PATH` inside the subagent runtime. Verified discoverable on this system.

### Workaround C: `pipe_agent_handoff` on Return

The parent calls `pipe_agent_handoff` immediately on the subagent's return text:

```
distilled = pipe_agent_handoff(
    output=subagent_result,
    pipe_name="semantic-refinery",
    from_agent="explore",
    to_agent="planner"
)
```

**Caveat**: The subagent's raw output is already in the parent's context by this point. This helps for *subsequent* context pressure but does not undo the initial inflation. Call `pipe_agent_handoff` **before** processing the result further.

---

## Upstream Fix

The permanent fix is in OpenCode's `packages/opencode/src/tool/task.ts` — MCP tools need to be granted explicit permissions when creating the subagent session, similar to how `todowrite` and `todoread` are handled. The issue is tracked at [anomalyco/opencode#16491](https://github.com/anomalyco/opencode/issues/16491), assigned to `rekram1-node`, and remains open as of 2026-05-14.

---

## References

- [anomalyco/opencode#16491](https://github.com/anomalyco/opencode/issues/16491) — Upstream bug report
- `AGENTS.md` lines 100–107 — Current subagent isolation warning and SOP
- `doc/ARCHITECTURE.md` §3 — Switchboard design (assumes MCP access)
- `context_pipe/a2a.py` — `pipe_agent_handoff` implementation (Workaround C tooling exists)
- `doc/CHANGELOG.md` v0.2.0 — "Subagent Tracking" feature added agent_label extraction
