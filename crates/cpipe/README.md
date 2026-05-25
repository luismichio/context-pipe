# 🦀 cpipe

[![Crates.io](https://img.shields.io/crates/v/cpipe.svg)](https://crates.io/crates/cpipe)
[![Docs.rs](https://docs.rs/cpipe/badge.svg)](https://docs.rs/cpipe)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](../../LICENSE.md)

**High-performance Context-Pipe orchestrator and library for local-first AI applications.**

`cpipe` is the native Rust core of the Context-Pipe ecosystem. It provides an ultra-low-latency orchestration engine, dynamic stream routing, and a lightweight JSON-RPC Model Context Protocol (MCP) stdio server implementation. It is designed to be embedded directly as a library in Rust/Tauri applications or run as a standalone pre-compiled executable sidecar.

---

## 🚀 Why cpipe?

The original `context-pipe` engine was built in Python. While powerful and easy to extend, Python's runtime environment introduces a cold-start startup tax (~1000ms+ latency) that makes it too slow for real-time IDE tools or interactive shell hooks. 

`cpipe` solves this latency tax:
- **⚡ Built for Speed**: Startup latency is reduced to under **2ms** (over 500x faster than Python!).
- **📦 Zero Python Dependencies**: No virtual environments, no interpreters, no dependency version mismatch.
- **🛠️ Tauri-Ready**: Ideal as a high-performance sidecar for local AI desktop applications.
- **🛡️ Protocol Guarded**: Features the self-aware bypass logic to prevent infinite sifting/compression loops.
- **🔄 Coexistence First**: Coexists harmoniously with the Python package in the same workspace.

---

## ⛓️ Unix Piping Lineage & Philosophy

`cpipe` is directly and deliberately inspired by Unix terminal piping. The same primitive that made `cmd1 | cmd2 | cmd3` the most durable composition pattern in computing underlies every architectural decision here.

The mapping is exact:
- **OS process** ➔ Pipe node (binary, script, MCP tool)
- **`stdout` ➔ `stdin` byte stream** ➔ Context stream between nodes
- **Shell pipe operator (`|`)** ➔ `pipes.json`/`pipes.toml` node sequence
- **`/dev/stderr` for diagnostics** ➔ Per-node `stderr` trace map
- **Process timeout / `SIGKILL`** ➔ Timeout Guard (`PIPE_NODE_TIMEOUT_MS`)
- **`tee` for stream splitting** ➔ T-Pipe (save raw copy mid-chain)

This lineage means `cpipe` is **`stdin`/`stdout` first** (any tool that honors this can be a node, no SDK required), uses **single-responsibility nodes**, and is **language-agnostic** (Rust, Python, Node, and bash utilities are interchangeable at the pipe level).

---

## 🛠️ Installation

### Pre-built Binaries
You can download pre-built binaries for Windows, macOS (Intel & Apple Silicon), and Linux from the [**GitHub Releases**](https://github.com/luismichio/context-pipe/releases) page.

Alternatively, you can use the helper script (requires Python):
```bash
python scripts/fetch_cpipe.py
```

### As a Rust Library

Add this to your `Cargo.toml`:
```toml
[dependencies]
cpipe = { git = "https://github.com/luismichio/context-pipe", path = "crates/cpipe" }
```

### Build from Source

Build the binary:
```bash
cargo build --release --bin cpipe
```

The resulting binary in `target/release/cpipe` can be used as a standalone tool or a Tauri sidecar.

---

## ⚙️ Configuration (`pipes.json` / `pipes.toml`)

`cpipe` reads its pipeline definitions from a local config file — either `pipes.json` or `pipes.toml`. Both formats express identical schemas; use whichever you prefer.

### File Discovery Order

When `load_pipes_config()` is called (or `cpipe` is invoked without `--config`), the engine searches for config files in this order:

1. **`pipes.toml`** — walks up from the current directory, stops at the `.git` boundary. Takes priority over JSON when both exist.
2. **`pipes.json`** — same walk-up search, used if no TOML is found.
3. **`~/.mcp-pipe.toml`** — global user config (merged, local takes precedence).
4. **`~/.mcp-pipe.json`** — global user config fallback.

You can also override discovery with an explicit path:

```bash
cpipe run my-pipe --config /path/to/custom-pipes.json
```

Or via environment variable:

```bash
PIPE_CONFIG_PATH=/path/to/pipes.toml cpipe run my-pipe
```

---

### Full Schema Reference

#### `pipes.json`

```json
{
  "version": "1.0",
  "description": "Human-readable description of this config file.",

  "pipes": [
    {
      "name": "standard-distill",
      "description": "The flagship log sifting pipeline.",
      "nodes": [
        {
          "cmd": "semantic-sift-cli",
          "args": ["logs"],
          "optional": false,
          "help_msg": "Install via: pip install semantic-sift"
        }
      ]
    },
    {
      "name": "rerank-and-sift",
      "description": "Search result optimization: rank then distil.",
      "nodes": [
        { "cmd": "semantic-sift-cli", "args": ["rank", "--top-n", "5"] },
        { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.6"] }
      ]
    }
  ],

  "mappings": [
    { "trigger": "tool:search|grep|find", "pipe": "rerank-and-sift" },
    { "trigger": "size:>10000",           "pipe": "semantic-refinery"  },
    { "trigger": "size:>500",             "pipe": "standard-distill"   }
  ],

  "servers": {
    "firecrawl": {
      "command": ["python", "-m", "firecrawl_mcp.server"],
      "env": { "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}" }
    }
  }
}
```

#### `pipes.toml` (equivalent, with comments)

```toml
version = "1.0"
description = "Human-readable description of this config file."

# ── Pipes ──────────────────────────────────────────────────────────────
[[pipes]]
name        = "standard-distill"
description = "The flagship log sifting pipeline."

  [[pipes.nodes]]
  cmd      = "semantic-sift-cli"
  args     = ["logs"]
  optional = false
  help_msg = "Install via: pip install semantic-sift"

[[pipes]]
name        = "rerank-and-sift"
description = "Search result optimization: rank then distil."

  [[pipes.nodes]]
  cmd  = "semantic-sift-cli"
  args = ["rank", "--top-n", "5"]

  [[pipes.nodes]]
  cmd  = "semantic-sift-cli"
  args = ["semantic", "--rate", "0.6"]

# ── Auto-routing mappings ───────────────────────────────────────────────
[[mappings]]
trigger = "tool:search|grep|find"
pipe    = "rerank-and-sift"

[[mappings]]
trigger = "size:>10000"
pipe    = "semantic-refinery"

[[mappings]]
trigger = "size:>500"
pipe    = "standard-distill"

# ── MCP server registry ─────────────────────────────────────────────────
[servers.firecrawl]
command = ["python", "-m", "firecrawl_mcp.server"]

  [servers.firecrawl.env]
  FIRECRAWL_API_KEY = "${FIRECRAWL_API_KEY}"
```

---

### Field Reference

#### `pipes[].nodes[]` — Node fields

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `cmd` | `string` | ✅ | Binary or script to execute. Must be on `PATH` or an absolute path. |
| `args` | `string[]` | — | Command-line arguments. `${VAR}` tokens are resolved from environment. |
| `optional` | `bool` | — | If `true`, a non-zero exit code skips this node instead of failing the pipe. Default: `false`. |
| `help_msg` | `string` | — | Human-readable install hint shown when `cmd` is not found. |
| `type` | `string` | — | `"binary"` (default), `"script"`, or `"mcp"`. |
| `tee` | `object` | — | Stream-splitting: write raw node input to disk before processing. See T-Pipe below. |

**MCP node additional fields** (`"type": "mcp"`):

| Field | Type | Description |
| :--- | :--- | :--- |
| `server` | `string` | Key matching a server entry in `servers`. |
| `tool` | `string` | MCP tool name to invoke on that server. |
| `input_key` | `string` | JSON field name to send stdin into. Default: `"content"`. |

#### `mappings[]` — Auto-routing triggers

| Pattern | Behaviour |
| :--- | :--- |
| `tool:<regex>` | Matches the `tool_name` argument passed by the caller. |
| `size:>N` | Matches when the input payload exceeds `N` bytes. |
| `default` | Fallback when no other trigger matches. |

The first matching mapping wins. Mappings are checked in order.

#### `servers{}` — MCP server registry

Defines servers that can be used as `"type": "mcp"` pipe nodes.

| Field | Type | Description |
| :--- | :--- | :--- |
| `command` | `string` or `string[]` | Command to launch the server process. |
| `env` | `object` | Environment variables injected at launch. Supports `${VAR}` expansion. |

#### T-Pipe (`tee`) — Stream Splitting

Save the raw node input to disk before the node processes it:

```json
{
  "cmd": "semantic-sift-cli",
  "args": ["logs"],
  "tee": {
    "sink": "file",
    "path": "raw_input_{iso_date}.txt",
    "mode": "append"
  }
}
```

| Field | Values | Description |
| :--- | :--- | :--- |
| `sink` | `"file"` | Destination type. |
| `path` | any string | Output file path. Supports `{iso_date}` and `{tool_name}` tokens. |
| `mode` | `"append"` / `"overwrite"` | Write mode. Default: `"append"`. |

---

### Config Merging Rules

When both a local and a global config are found, they are merged with **local precedence**:

- **Pipes**: Local pipes override global pipes with the same name. Unique global pipes are appended.
- **Mappings**: Local mappings are kept as-is. Global mappings not already present are appended.
- **Servers**: Local server entries override global entries with the same key.
- **Version / Description**: Local values take precedence.

---

## 📖 Usage

### 1. As a Rust Library

#### Loading Configuration and Executing a Named Pipe
```rust
use cpipe::config::load_pipes_config;
use cpipe::orchestrator::run_pipe;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // 1. Load the merged configuration (merges local pipes.json/toml and global config)
    let config = load_pipes_config();

    // 2. Locate a specific pipe by name
    let pipe = config.pipes.iter().find(|p| p.name == "standard-distill")
        .ok_or("Pipe 'standard-distill' not found in configuration")?;

    // 3. Define input context data and run the pipeline
    let raw_context = "2026-05-01T12:00:00Z INFO [1/42] Compiling... some signal";
    let (sifted_output, telemetry) = run_pipe(
        pipe,
        raw_context,
        Some("my-rust-client"), // tool_name (optional)
        None,                   // agent_label (optional)
        &config.servers,        // registered servers map
    ).await;

    println!("Sifted context:\n{}", sifted_output);
    Ok(())
}
```

#### Programmatic Ad-hoc (Dynamic) Pipes
```rust
use cpipe::config::{Pipe, Node};
use cpipe::orchestrator::run_pipe;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let config = cpipe::config::load_pipes_config();

    // Programmatically construct an ad-hoc sequence of pipe nodes
    let nodes = vec![
        Node {
            cmd: "rg".to_string(),
            args: vec!["ERROR".to_string()],
            optional: false,
        },
        Node {
            cmd: "jq".to_string(),
            args: vec![".message".to_string()],
            optional: false,
        }
    ];

    let pipe = Pipe {
        name: "dynamic-log-filter".to_string(),
        description: "Programmatic log filter".to_string(),
        nodes,
    };

    let raw_logs = "INFO: success\nERROR: {\"message\": \"failed to connect\"}\n";
    let (result, _telemetry) = run_pipe(
        &pipe,
        raw_logs,
        Some("programmatic-run"),
        None,
        &config.servers,
    ).await;

    println!("Result: {}", result);
    Ok(())
}
```

---

### 2. Standalone CLI Commands

#### `cpipe run` — Execute a named pipe
```bash
# Read from stdin
cat build.log | cpipe run standard-distill

# Read from a file
cpipe run semantic-refinery --input-file report.md

# Explicit config path
cpipe run my-pipe --config /path/to/pipes.toml

# Verbose: prepend per-node audit header to output
cpipe run standard-distill --verbose < input.txt
```

The `--verbose` flag prepends an audit header to stdout showing each node's input/output size and latency:
```
--- [cpipe audit: standard-distill | 3 nodes | 420ms] ---
  node 0 (semantic-sift-cli):  8,400 → 620 chars  |  418ms
--- [End Audit] ---
<distilled output follows>
```

#### `cpipe run-dynamic` — Execute an ad-hoc node chain
```bash
# Chain any tools on the fly (no pipes.json entry needed)
cat error.log | cpipe run-dynamic '[{"cmd": "rg", "args": ["ERROR"]}, {"cmd": "jq", "args": [".message"]}]'

# With relaxed JSON normalization for PowerShell (automatically handles unquoted/single-quoted keys):
cpipe run-dynamic '[{cmd: rg, args: [ERROR]}]' < error.log

# With verbose audit output
cpipe run-dynamic '[{"cmd": "semantic-sift-cli", "args": ["logs"]}]' --verbose < build.log
```

> 💡 **PowerShell Support**: When running in PowerShell, command-line quote stripping can corrupt raw JSON structures. `cpipe` automatically scans and normalizes relaxed JSON formats into RFC-compliant JSON prior to parsing.

> ⚠️ **Security note**: Shell metacharacters in `cmd` are rejected. To enable curated shell utilities (`grep`, `awk`, `sed`, etc.), use the `--allow-shell` flag (or `allow_shell: true` in the `pipe_run_dynamic` MCP call) — but the final node **must** end with a sifting tool (e.g. `semantic-sift-cli`) to guarantee context safety.

#### `cpipe list` — Shadow Tool Discovery
```bash
cpipe list
cpipe list --config /path/to/pipes.toml
```

Prints two sections:
1. **Configured Pipes** — all named pipes from your `pipes.json`/`pipes.toml` with their node chains.
2. **Curated CLI Tools on PATH** — probes the following 7 tools and reports which are installed:

| Tool | Description |
| :--- | :--- |
| `jq` | Command-line JSON processor |
| `yq` | YAML / JSON / XML processor |
| `markitdown` | Office / PDF / HTML → Markdown converter |
| `pandoc` | Universal document format converter |
| `rg` | Fast line-oriented search (ripgrep) |
| `fd` | Fast file finder (fd-find) |
| `bat` | Syntax-highlighted `cat` replacement |

Example output:
```
Configured Pipes:
  standard-distill         The flagship log sifting pipeline.
    Nodes: semantic-sift-cli
  rerank-and-sift          Search result optimization.
    Nodes: semantic-sift-cli ➔ semantic-sift-cli

Curated CLI Tools on PATH:
  bat                      Syntax-highlighted cat replacement
  jq                       Command-line JSON processor
  rg                       Fast line-oriented search (ripgrep)
```

#### `cpipe verify` — Installation Health Check
```bash
cpipe verify
cpipe verify --config /path/to/pipes.toml
```

Performs a structured health check of the Context-Pipe installation. It resolves paths, verifies the presence of configured executables on `PATH`, and automatically links `semantic-sift` to ensure seamless execution.

#### `cpipe handoff` — A2A Agent Handoff
```bash
# Pipe producer output to consumer through a named pipe
cat agent_output.txt | cpipe handoff --from ProducerAgent --to ConsumerAgent --pipe-name semantic-refinery
```

Distills output from a producing agent before passing it to a consuming agent's context window. This prevents context window flooding at multi-agent boundaries. If `--pipe-name` is omitted, the appropriate pipe is resolved automatically based on input length or context.

#### `cpipe stats` — Context Balance Sheet
```bash
cpipe stats
```
Prints the cumulative ROI ledger for the session: chars saved, chars added, net change, event count, and average node latency.

#### `cpipe serve` — Start the stdio MCP Server
```bash
cpipe serve
```
Launches a lightweight JSON-RPC MCP server on stdio. See [§ cpipe serve — MCP Tool Reference](#4-cpipe-serve--mcp-tool-reference) below.

---

### 3. Tauri Sidecar Integration

To embed `cpipe` as a sidecar inside a Tauri application:

1. Put the target-specific binary in your Tauri project under `src-tauri/binaries/cpipe-<target-triple>`.
2. Reference the sidecar in `src-tauri/tauri.conf.json`:
   ```json
   {
     "tauri": {
       "bundle": {
         "externalBin": [
           "binaries/cpipe"
         ]
       }
     }
   }
   ```
3. Spawn the sidecar from your Rust code:
   ```rust
   use tauri::api::process::Command;

   let (mut rx, mut child) = Command::new_sidecar("cpipe")
       .expect("failed to setup sidecar")
       .args(["run", "standard-distill"])
       .spawn()
       .expect("failed to spawn sidecar");
   ```

---

### 4. `cpipe serve` — MCP Tool Reference

`cpipe serve` starts a lightweight stdio MCP server exposing the full context-pipe surface to any MCP-compatible client (AI assistants, IDEs, Tauri front-ends). The server is protocol-compatible with the Python `mcp-context-pipe` package — you can swap one for the other in your MCP config.

| Tool | Description |
| :--- | :--- |
| `list_pipes` | Lists all named pipes from the active config. |
| `pipe_run` | Runs a named pipe on `input_text`. Args: `pipe_name`, `input_text`. |
| `pipe_read_file` | Reads a file through a pipe. Args: `path`, `pipe_name` (default: `standard-distill`). Validated against `PIPE_AUTHORIZED_ROOT`. |
| `pipe_analyze_file` | Reports file size and recommends a pipe — call before `pipe_read_file` for large files. |
| `pipe_run_dynamic` | Runs an ad-hoc node chain. Args: `nodes_json`, `input_text`, `allow_shell`. |
| `pipe_list_shadow_tools` | Returns all configured pipes + curated PATH tools (same as `cpipe list`). |
| `pipe_agent_handoff` | Distils Agent A output before passing to Agent B. Args: `output`, `pipe_name`, `from_agent`, `to_agent`. |
| `get_pipe_stats` | Returns the Context Balance Sheet (ROI ledger). |
| `pipe_verify` | Health-checks the installation: tests each node, reports missing tools and how to fix them. |
| `pipe_audit_last` | Returns the most recent raw telemetry event for debugging. |
| `pipe_onboard` | Injects IDE hooks, slash commands, and SOP into the current project. Args: `environment`, `target_dir`. |
| `pipe_install_aliases` | Installs the `cpipe` shell alias into profile files. Args: `shells`. |
| `pipe_remove_aliases` | Removes the managed alias block from all shell profiles. |

**Register in MCP config** (swap in place of the Python server):
```json
"context-pipe": {
  "command": "/path/to/cpipe",
  "args": ["serve"],
  "env": {
    "PIPE_CONFIG_PATH": "/path/to/pipes.toml",
    "PIPE_AUTHORIZED_ROOT": "/path/to/your/projects"
  }
}
```

---

## 📊 Performance Tiers

| Aspect | Python Wrapper (`mcp-context-pipe`) | Rust Core (`cpipe`) |
| :--- | :--- | :--- |
| **Startup Latency** | ~1000ms+ (due to interpreter startup) | **<2ms** |
| **Memory Footprint** | ~35MB | **<2MB** |
| **Dependencies** | Requires Python 3.10+ | None (Pre-compiled native binary) |
| **Distribution** | PyPI, editable install | Standalone release binaries, Cargo crate |
| **Extension Model** | Easy python scripts, FastMCP | Programmatic Rust modules, subprocesses |

---

## 🏗️ Architecture

`cpipe` ports the exact execution rules defined in the **Context-Pipe Protocol (CPP)**:
1. **Config Merging**: Loads and merges local `pipes.json` (or human-friendly `pipes.toml`) with global `~/.mcp-pipe.json` configs.
2. **Placeholder Resolution**: Recursively resolves `${VAR}` tokens using local and system environment variables.
3. **Stream Routing**: Coordinates standard I/O redirection between sequential pipe nodes with timeout protection.
4. **Self-Aware Bypass**: Detects sifting signatures (`--- [Semantic-Sift Audit] ---`) to prevent redundant double-sifting.

---

## 🌍 Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PIPE_CONFIG_PATH` | `pipes.json` | Explicit path to a `pipes.json` or `pipes.toml` file. Overrides auto-discovery. |
| `PIPE_NODE_TIMEOUT_MS` | `10000` | Per-node subprocess timeout in milliseconds. Nodes that exceed this are killed and the pipe returns the input unchanged. |
| `PIPE_AUTHORIZED_ROOT` | *(cwd)* | Path security boundary for `pipe_read_file`. Files outside these directories are rejected. Supports a list of directories separated by the platform-specific path separator (`;` on Windows, `:` on macOS/Linux). |
| `RUST_LOG` | *(off)* | Log level for the `cpipe` process (`error`, `warn`, `info`, `debug`, `trace`). Logs are written to `stderr` to preserve clean `stdout` data streams. |

---

## ⚖️ License

Apache-2.0. Developed as part of the **Studio of Two** philosophy: *Systems, not Patches.*

Copyright (c) 2026 Luis Kobayashi. All rights reserved.
