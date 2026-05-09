# Context-Pipe — Strategic Backlog

Items listed here are confirmed findings that require upstream action or a dedicated design phase before implementation can begin. They are **not** bugs — they are architectural gaps with known workarounds.

---

## Phase 4.5 — OpenCode Native Hook Interception

**Status**: BLOCKED (upstream)
**Priority**: HIGH (trust / feature completeness)
**Tracking**: [sst/opencode#21149](https://github.com/sst/opencode/issues/21149), [sst/opencode#25918](https://github.com/sst/opencode/issues/25918)

### Technical Finding

The `tool.execute.after` hook is declared in the OpenCode plugin `Hooks` interface but is **never triggered** by the OpenCode runtime. Confirmed via full source audit of:

- `packages/opencode/src/session/processor.ts`
- `packages/opencode/src/session/llm.ts`
- `packages/opencode/src/tool/registry.ts`
- `packages/opencode/src/agent.ts`
- All v2 session files

The plugin's output mutation code (`output.output = parsed.result`) was silently a no-op. The plugin has been updated to a documented placeholder with the mutation handler commented out.

### User Impact

Users running Context-Pipe with OpenCode as their IDE will **not** have MCP tool outputs automatically piped through context refineries. The "subconscious interceptor" feature is effectively disabled for OpenCode users. This impacts any workflow that relies on automatic noise reduction of tool outputs (e.g., `read_file`, `bash`, `grep`).

### Current Workaround

The `AGENTS.md` SOP mandate is the active strategy:
- All file reads use `pipe_read_file()` (an explicit MCP tool call that routes through the pipe).
- The mandate is injected automatically by `pipe_onboard(environment='OpenCode')`.

This workaround requires AI agent cooperation (the agent must follow the `AGENTS.md` SOP). It does not intercept native tool outputs transparently.

### Unblocking Criteria

One of the following must occur:
1. OpenCode implements `tool.execute.after` hook dispatch in its runtime.
2. OpenCode exposes a different plugin interception point that fires after tool execution.
3. A community-maintained OpenCode fork adds hook support.

### Proposed Implementation (post-unblock)

Once upstream support lands:
1. Restore the output mutation handler in `opencode.json` plugin scaffold.
2. Update `pipe_onboard(environment='OpenCode')` to write the active (not placeholder) plugin.
3. Add an integration test that validates hook firing end-to-end.
4. Update `doc/INTEGRATION_ENCYCLOPEDIA.md` to mark OpenCode as fully supported.

---

*Last updated: 2026-05-08 | Studio of Two*
