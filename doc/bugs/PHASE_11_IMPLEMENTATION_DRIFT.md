# Bug Report: Phase 11 Implementation Drift & Premature Documentation

**Filed**: 2026-05-29  
**Status**: 🟢 Resolved (2026-05-29)
**Severity**: High  
**Category**: Implementation Drift / Documentation Accuracy

---

## 1. Description

The `doc/CHANGELOG.md` file for the `[Unreleased]` section claims that **Phase 11: Conditional Branching & Validator Nodes** has been added to both the Python and Rust orchestration engines. However, a code audit reveals that while the Rust engine (`cpipe`) is fully updated, the Python engine (`context-pipe`) remains in a linear execution state.

## 2. Gaps & Discrepancies

| Field | Python (`orchestrator.py`) | Rust (`orchestrator.rs`) | Status |
|-------|----------------------------|--------------------------|--------|
| **Execution Model** | Linear `for` loop | **DAG Traversal Engine** | ❌ Drift |
| **`condition` Key** | Missing | Implemented | ❌ Drift |
| **`validator` Nodes**| Missing | Implemented | ❌ Drift |
| **Branch Sequences** | Missing | Implemented | ❌ Drift |
| **Loop Guard** | Missing | Implemented (100 steps) | ❌ Drift |

## 3. Evidence

### Rust (Target State)
`crates/cpipe/src/orchestrator.rs` contains the "Phase 11-C: DAG Traversal Engine" block (lines 759+), which builds an adjacency map and uses a `while` loop with `current_node_id` to navigate branches.

### Python (Actual State)
`context_pipe/orchestrator.py` still uses the legacy linear loop:
```python
for node_index, node in enumerate(pipe_config.get("nodes", [])):
    # ... linear execution ...
```
It has no logic to handle `id`, `next`, `branches`, or `condition` fields on nodes.

## 4. Impact

Users or agents relying on the documentation in `CHANGELOG.md` or `ARCHITECTURE.md` will attempt to use declarative branching (e.g., Figma-to-code self-healing workflows) which will silently fail or execute linearly in the Python environment, leading to brittle pipelines and unexpected behavior.

## 5. Fix Plan

1.  **Refactor `run_pipe` in `context_pipe/orchestrator.py`**: Convert the linear `for` loop to a `while` loop driven by node IDs.
2.  **Implement `_evaluate_condition`**: Port the predicate logic (`size`, `artifact`, `contains`) from Rust to Python.
3.  **Implement Validator logic**: Add support for `type: "validator"` and exit-code based branching.
4.  **Support `branch_sequences`**: Ensure the engine can enter named sub-graphs.
5.  **Add Loop Guard**: Implement the 100-step execution limit.
6.  **Update `config_loader.py`**: Ensure all new schema fields are permitted during validation.

---

## 6. Resolution

- **DAG Traversal Engine**: Fully ported to Python `context_pipe/orchestrator.py`, matching the Rust adjacency list structure and `while` loop driven by node IDs.
- **`condition` Key**: Implemented `_evaluate_condition()` helper with full support for `size:>N`, `size:<N`, `artifact:missing:<path>`, `artifact:exists:<path>`, and `contains:<string>` predicates.
- **`validator` Nodes & Exit-Code Branching**: Implemented `type: "validator"` nodes and `branches` routing logic.
- **Branch Sequences**: Fully supported traversal into named sub-graphs in `branch_sequences`.
- **Loop Guard**: Added a 100-step guard that raises a loop guard error to prevent infinite cycles.
- **Verification**: Verified using 291 Python tests (`pytest`) and 20 Rust core tests (`cargo test`), all passing.
