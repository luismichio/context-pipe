# ⛓️ Context-Pipe: Agent Mandates

## 🛡️ Operational Isolation (Sovereign Dual-Repo)
To maintain architectural integrity and prevent environment pollution, follow these rules:

1. **std-context-lab is READ-ONLY**: This repository is used for integration testing and bug discovery. NEVER write to, modify, or commit changes within `std-context-lab`. Use it only for research, reading bug reports, and verifying fixes (via read-only observation).
2. **Core Development**: All implementation, bug fixes, and documentation updates must happen in the core repositories (`context-pipe` or `semantic-sift`).
3. **No Cross-Pollination**: Do not move files or state between the lab and core projects unless explicitly instructed.

## 🤖 Workflow
- **Plan first**: Always produce an implementation plan in `task.md` or a sibling `.md` before acting.
- **Atomic Commits**: Keep fixes surgical and aligned with the specific bug report being addressed.
- **Validation**: Verify fixes empirically using local test scripts before committing.
