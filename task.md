# Task Plan: Update TypeScript Port Requirements

## Overview
Update the client-side TypeScript pipeline requirements (`plans/ts_version_requirements.md`) to clarify platform parity limitations (subprocess vs sandboxed, MCP transport options), specify error-handling policies, add `AbortSignal` cancellation support, and fix code block formatting typos.

---

## Phase 1: Changelog Entry [COMPLETED]
Add an entry in `doc/CHANGELOG.md` under `## [Unreleased]` documenting the updates to the TypeScript port requirements.

- **File**: `C:/Users/luism/Workbench/GitHub/context-pipe/doc/CHANGELOG.md`
- **Action**: Insert entry documenting the requirements expansion.

---

## Phase 2: Requirements Document Update [COMPLETED]
Modify `plans/ts_version_requirements.md` with the updated design.

- **File**: `C:/Users/luism/Workbench/GitHub/context-pipe/plans/ts_version_requirements.md`
- **Edits**:
  - Fix brackets/duplicates syntax typo at the end of the `PipelineEngine` code block.
  - Update `NodeExecutor` type signature to support `AbortSignal`.
  - Update `PipelineEngine.runPipe` to pass an optional `AbortSignal` to the node executor.
  - Add Section 5: "Platform Parity & Limitations Matrix" explaining what is supported/unsupported in browser vs. sidecar.
  - Add Section 6: "Engine Operational Policies" specifying standard error handling (`failFast`) and streaming capabilities (`AsyncIterable`).

---

## Phase 3: Scaffolding and Implementation [COMPLETED]
Establish the codebase scaffolding for the TypeScript engine (`packages/cpipe-js`).

- **Tasks**:
  - [x] Create directory `packages/cpipe-js/`.
  - [x] Create `packages/cpipe-js/package.json` build/dependency config.
  - [x] Create `packages/cpipe-js/tsconfig.json` compiler config.
  - [x] Create types interface file `packages/cpipe-js/src/types.ts`.
  - [x] Create built-in executors in `packages/cpipe-js/src/nodes/` (`grep.ts`, `replace.ts`, `passthrough.ts`).
  - [x] Create `packages/cpipe-js/src/engine.ts` ([PipelineEngine](file:///C:/Users/luism/Workbench/GitHub/context-pipe/packages/cpipe-js/src/engine.ts) implementation).
  - [x] Create `packages/cpipe-js/src/index.ts` entry point.
  - [x] Create `packages/cpipe-js/tests/engine.test.ts` for unit testing.
  - [x] Run package setup, installs, and unit tests via vitest (all passing).
  - [x] Bundle packages to CJS and ESM formats with type definitions via tsup.
  - [x] Create [README.md](packages/cpipe-js/README.md) documenting core features and examples.

