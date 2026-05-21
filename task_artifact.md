# Task Checklist: Context-Pipe Rust Core (`cpipe`)

- `[x]` Initialize Cargo project `crates/cpipe`
  - `[x]` Create `crates/cpipe` directory and initialize workspace
  - `[x]` Configure `crates/cpipe/Cargo.toml` with dependencies (`serde`, `serde_json`, `toml`, `tokio`, `clap`, `log`, `env_logger`)
- `[x]` Implement Core Library Modules
  - `[x]` `src/lib.rs`: Expose core API
  - `[x]` `src/config.rs`: Parse JSON/TOML configurations and resolve placeholders
  - `[x]` `src/orchestrator.rs`: Route stdin/stdout streams with timeout guards and self-aware bypass logic
  - `[x]` `src/shadow.rs`: Capability detection / system PATH probing
  - `[x]` `src/telemetry.rs`: Write balance sheet JSON/markdown audits
  - `[x]` `src/server.rs`: Stdio JSON-RPC server implementing the MCP tools
- `[x]` Implement Command-Line Interface (`src/main.rs`)
  - `[x]` Integrate `clap` CLI parser for `run`, `run-dynamic`, `list`, `stats`, `serve` commands
- `[x]` Write Automated Tests
  - `[x]` Unit tests (config parsing, bypass logic, path parsing)
  - `[x]` Integration tests (pipeline runs, mock MCP messages)
- `[x]` Verify Performance & Latency
  - `[x]` Run speed audit using `Measure-Command` (target < 10ms startup)
  - `[x]` Perform standard audit checks
