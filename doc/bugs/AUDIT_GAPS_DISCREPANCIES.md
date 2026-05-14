# Bug Report: Codebase Gaps & Discrepancies

**Filed**: 2026-05-14  
**Status**: ✅ All Gaps Resolved (2026-05-14)
**Scope**: Codebase audit findings — gaps between documentation and implementation, quality regressions, and architectural debt

---

## 1. `shell: true` Documented but Removed

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Category** | Documentation staleness |
| **Files** | `doc/OPERATOR_GUIDE.md` §3.B, `doc/CHANGELOG.md` v0.2.0 entry |
| **Status** | ✅ Resolved |

**The problem**  
`doc/OPERATOR_GUIDE.md` §3.B describes "Bash Nodes (`shell: true`)" as an active feature with configuration examples. However, `shell: true` node support was **removed in v0.2.0** (per `doc/CHANGELOG.md`): "Removed `shell: true` node support (`orchestrator.py`): All subprocess invocations now use `shell=False` unconditionally."

**Impact**  
Users reading the Operator Guide will attempt to use a feature that no longer exists. The error message on `shell: true` is not helpful — the orchestrator simply ignores the flag.

**Fix**  
Remove or rewrite §3.B in `doc/OPERATOR_GUIDE.md` to reflect current architecture. Cross-reference the removal in `doc/CHANGELOG.md`.

---

## 2. CI Coverage Gate 24% vs Local 83%

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Category** | Quality regression path |
| **Files** | `.github/workflows/ci.yml` line 40, `pyproject.toml` line 68 |
| **Status** | ✅ Resolved |

**The problem**  
Local test enforcement (`pyproject.toml`) sets `fail_under = 83`, requiring 83% line coverage to pass. CI (`ci.yml`) runs `pytest --cov-fail-under=24`, which passes at just 24%. This means PRs can merge with coverage as low as 24% without CI failing, silently bypassing the quality gate.

**Impact**  
Coverage can erode from 83% to 24% over time without any CI signal. The local ratchet is meaningless if CI doesn't enforce it.

**Fix**  
Align CI's `--cov-fail-under` with the local `fail_under` value in `pyproject.toml`. Both should use the same threshold. Use `--cov-fail-under=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['tool']['pytest']['ini_options']['fail_under'])")` or simply hardcode the same value.

---

## 3. `bandit` Missing from Dev Dependencies

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Category** | Broken audit script |
| **Files** | `scripts/audit.bat` line 28, `pyproject.toml` |
| **Status** | ✅ Resolved |

**The problem**  
`scripts/audit.bat` runs `python -m bandit -r context_pipe pipe_hook.py -ll -q` but `bandit` is **not listed** in `pyproject.toml` under `[project.optional-dependencies] dev`. Running `scripts/audit.bat` on a fresh install will fail with "No module named bandit."

**Impact**  
The primary quality gate script is broken out of the box. Developers who run `scripts/audit.bat` before committing (per `AGENTS.md` working protocol) will get a false failure.

**Fix**  
Add `bandit>=1.7` to `[project.optional-dependencies] dev` in `pyproject.toml`.

---

## 4. Stale Legacy Signatures in Two Docs

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Documentation staleness |
| **Files** | `doc/CONTEXT_PIPE_PROTOCOL.md` line 20, `doc/INTEGRATION_ENCYCLOPEDIA.md` line 149 |
| **Status** | ✅ Resolved |

**The problem**  
Two documents reference the legacy execution signature `--- [Semantic-Sift: Native Execution] ---`. The codebase uses `--- [Context-Pipe: Native Execution] ---` (defined as `CPP_SIGNATURE` in `orchestrator.py` line 22).  

- `doc/CONTEXT_PIPE_PROTOCOL.md` line 20: "The wrapper must also append `--- [Semantic-Sift: Native Execution] ---`"  
- `doc/INTEGRATION_ENCYCLOPEDIA.md` line 149: Mentions `--- [Semantic-Sift Audit] ---` bypass

**Impact**  
Agents or integrations implementing the protocol from these docs will use the wrong signature, breaking Echo Guard deduplication (signature mismatch means content won't be recognized as already-processed).

**Fix**  
Replace `--- [Semantic-Sift: Native Execution] ---` with `--- [Context-Pipe: Native Execution] ---` in both documents.

---

## 5. Allowlist Mismatch: Doc vs Code (6 Tools Diff)

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Documentation staleness |
| **Files** | `doc/ARCHITECTURE.md` §9, `context_pipe/dynamic.py` lines 29–51 |
| **Status** | ✅ Resolved |

**The problem**  
`doc/ARCHITECTURE.md` §9 documents `SHELL_UTILITY_ALLOWLIST` as containing 21 tools:

```
bash, sh, zsh, fish, python, python3, node, npx, curl, wget,
grep, awk, sed, cut, sort, uniq, wc, head, tail, cat, echo
```

The actual code (`dynamic.py` lines 29–51) contains a **different** set of 20 tools:

```
bash, sh, awk, sed, grep, cut, sort, uniq, tr, head, tail,
wc, cat, echo, printf, xargs, python, python3, jq, yq
```

**Missing from docs**: `tr`, `printf`, `xargs`, `jq`, `yq` (5 tools present in code)  
**Missing from code**: `zsh`, `fish`, `node`, `npx`, `curl`, `wget` (6 tools present in docs)

**Impact**  
Documentation-driven development (e.g., agents generating dynamic pipes from the doc) will fail when attempting to use tools that aren't actually in the allowlist, or will miss available tools.

**Fix**  
Align `doc/ARCHITECTURE.md` §9 with the actual `frozenset` in `dynamic.py`. The code is the source of truth. Either add `zsh`, `fish`, `node`, `npx`, `curl`, `wget` to the code allowlist (with security review) or remove them from the doc.

---

## 6. No Logging in `orchestrator.py` / `server.py`

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Code quality |
| **Files** | `context_pipe/orchestrator.py`, `context_pipe/server.py` |
| **Status** | ✅ Resolved |

**The problem**  
Neither `orchestrator.py` nor `server.py` set up or use Python's `logging` module. Error conditions in the core execution engine and MCP surface go entirely silent — no warnings, no debugging output. The project's own anti-patterns policy (`AGENTS.md`) mandates: "No Console Logs: Use the Python `logging` module (routing to `stderr`)."

Compare with `config_loader.py`, `dynamic.py`, `a2a.py`, `cli.py`, `shadow.py` — all properly use `logging.getLogger(__name__)` at module level.

**Impact**  
- Production errors are invisible without stracing
- No way to enable debug logging without code changes
- Contradicts the project's own coding standards

**Fix**  
Add module-level `logger = logging.getLogger(__name__)` to both files. Replace relevant `print`/`sys.stderr.write` calls with `logger.warning()`, `logger.error()`, `logger.debug()`.

---

## 7. `wrapper.py` Uses `sys.stderr.write` Not Logging

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Anti-pattern violation |
| **Files** | `context_pipe/wrapper.py` lines 38, 50, 56, 66, 76, 85, 91, 101 |
| **Status** | ✅ Resolved |

**The problem**  
`wrapper.py` writes debug output directly to `sys.stderr.write()` in multiple conditional blocks (`CPP_DEBUG=true`). This violates the project's anti-patterns policy (`AGENTS.md`): "No Console Logs: Use the Python `logging` module."

This is especially problematic in the CPP_DEBUG path — when debugging is enabled, output goes to raw stderr instead of a structured logging pipeline.

**Impact**  
- Debug output bypasses log formatting, levels, and handlers
- Cannot filter or redirect debug output independently
- Contradicts project coding standards

**Fix**  
Replace all `sys.stderr.write()` calls with `logger.debug()`. Wire the `CPP_DEBUG` env var to a `logging.DEBUG` level set on the wrapper's logger.

---

## 8. `inject_hooks()` is a 400-Line Monolith

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Maintainability |
| **Files** | `context_pipe/onboarding.py` lines 738–1137 |
| **Status** | ✅ Resolved |

**The problem**  
`inject_hooks()` handles hook injection for **11+ IDE/CLI platforms** (Cursor, Gemini CLI, VS Code, Claude Code, Windsurf, Cline, OpenCode, etc.) in a single 400-line function. Each IDE has different config schemas, file paths, and injection mechanisms — all entangled in one if-elif chain.

Compare with the project's own standard: "If a pipe node is > 200 lines, refactor" (`AGENTS.md` Orchestrator role).

**Impact**  
- Adding a new IDE requires modifying the monolith, risking regression in existing integrations
- Testing a single IDE path requires mocking the entire function
- Cognitive load: understanding one IDE's injection means parsing all 11

**Fix**  
Extract per-IDE injection into separate functions (e.g., `_inject_cursor_hooks()`, `_inject_gemini_hooks()`) or a dispatch dict mapping `environment` → callable. Maintain the existing function signature as a dispatcher.

---

## 9. Telemetry O(n) Full-File Rewrite Per Event

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Performance |
| **Files** | `context_pipe/telemetry.py` — `log_telemetry()` line 25, `log_fallback_event()` line 126 |
| **Status** | ✅ Resolved |

**The problem**  
Every telemetry event reads the entire JSON file from disk, appends to the in-memory list, and writes the entire file back. This is O(n) in the number of past events. Under concurrent pipe execution or high-frequency sifting, this creates a write contention pattern (mitigated but not solved by `threading.Lock()`).

**Impact**  
- Latency per telemetry event grows linearly with session length
- Write contention under concurrent pipes
- Unbounded file growth — no rotation or truncation

**Fix**  
Options (choose one):
- Append-only log format (one JSON object per line, no rewrite)
- In-memory aggregation with periodic flush
- Pre-allocated fixed-size ring buffer
- SQLite-backed telemetry store

---

## 10. No `PIPE_WINDOW_PRESSURE` Computation

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Missing feature |
| **Files** | `README.md` (env var table), `context_pipe/orchestrator.py` `run_pipe()` |
| **Status** | ✅ Resolved |

**The problem**  
`PIPE_WINDOW_PRESSURE` is documented in `README.md` as an environment variable that the orchestrator uses to dynamically adjust sifting rate based on context pressure. However, the orchestrator **never computes or sets this variable** — it only passes the variable through to child processes in `process_env` if it happens to be set externally.

The `backlog.md` Phase 3 lists "Adaptive Thresholding" as "In Progress" but no implementation exists in the codebase.

**Impact**  
- Documented feature is non-functional
- Users who set this variable expect adaptive behavior but get a static pass-through
- Misleading documentation erodes trust

**Fix**  
Either implement adaptive window pressure computation in `run_pipe()` (e.g., based on input size relative to a threshold, or based on telemetry history) or remove the documentation and mark the feature as deferred in `backlog.md`.

---

## Summary by Priority

| Priority | Count | Items |
|----------|-------|-------|
| High | 3 | 1 (shell:true docs), 2 (CI coverage gap), 3 (bandit missing) |
| Medium | 4 | 4 (legacy signatures), 5 (allowlist diff), 6 (no logging), 7 (stderr not logging) |
| Low | 3 | 8 (monolith), 9 (telemetry O(n)), 10 (window pressure) |

---

## References

- Audit conducted 2026-05-14 via `context_pipe/orchestrator.py`, `context_pipe/server.py`, `context_pipe/wrapper.py`, `context_pipe/telemetry.py`, `context_pipe/dynamic.py`, `context_pipe/onboarding.py`, `doc/ARCHITECTURE.md`, `doc/OPERATOR_GUIDE.md`, `doc/CONTEXT_PIPE_PROTOCOL.md`, `doc/INTEGRATION_ENCYCLOPEDIA.md`, `.github/workflows/ci.yml`, `pyproject.toml`, `scripts/audit.bat`, `README.md`
