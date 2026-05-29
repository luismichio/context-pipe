// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Luis Kobayashi. All rights reserved.

use clap::{Parser, Subcommand};
use cpipe::config::{load_pipes_config, load_pipes_config_with_path, Pipe, Node};
use cpipe::orchestrator::run_pipe;
use cpipe::telemetry::{get_balance_sheet, generate_audit_header, log_telemetry};
use cpipe::server::{start_mcp_server, validate_nodes};
use std::fs;
use std::io::{self, Read, IsTerminal};
use std::path::PathBuf;


#[derive(Parser)]
#[command(name = "cpipe")]
#[command(version = env!("CARGO_PKG_VERSION"))]
#[command(about = "cpipe - High-performance Context-Pipe orchestrator", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Run a named pipe on stdin or a file
    Run {
        /// Name of the pipe
        pipe_name: String,
        /// Path to pipes configuration
        #[arg(long, default_value = "pipes.json", aliases = ["config_path"])]
        config: String,
        /// Read input from this file instead of stdin
        #[arg(long, aliases = ["input_file"])]
        input_file: Option<String>,
        /// 1-indexed start line (inclusive) to slice from input
        #[arg(long, aliases = ["start_line"])]
        start_line: Option<usize>,
        /// 1-indexed end line (inclusive) to slice from input
        #[arg(long, aliases = ["end_line"])]
        end_line: Option<usize>,
        /// Runtime variable to substitute into the pipe (repeatable).
        #[arg(long, aliases = ["var"])]
        var: Vec<String>,
        /// Path to write the run manifest JSON (overrides pipe definition).
        #[arg(long)]
        manifest: Option<String>,
        /// Prepend audit header (node trace + latency) to output
        #[arg(short, long)]
        verbose: bool,
    },
    /// Run an ad-hoc node array on stdin or a file
    RunDynamic {
        /// JSON array of node objects
        nodes_json: String,
        /// Read input from this file instead of stdin
        #[arg(long, aliases = ["input_file"])]
        input_file: Option<String>,
        /// Allow shell utilities as dynamic pipe nodes
        #[arg(long, aliases = ["allow_shell"])]
        allow_shell: bool,
        /// Prepend audit header to output
        #[arg(short, long)]
        verbose: bool,
    },
    /// List configured pipes and PATH tools
    List {
        /// Path to pipes configuration
        #[arg(long, default_value = "pipes.json", aliases = ["config_path"])]
        config: String,
    },
    /// Print the Context Balance Sheet (ROI)
    Stats,
    /// Start the MCP server (stdio transport)
    Serve,
    /// Directly invoke an MCP tool from the shell
    Tool {
        /// MCP server registry key
        server: String,
        /// Name of the tool to call
        tool_name: Option<String>,
        /// Static arguments (key=value). May be repeated.
        #[arg(long, short = 'a')]
        arg: Vec<String>,
        /// Argument key for stdin content
        #[arg(long, default_value = "content")]
        input_key: String,
        /// Read input from this file instead of stdin
        #[arg(long, aliases = ["input_file"])]
        input_file: Option<String>,
        /// Path to pipes configuration
        #[arg(long, default_value = "pipes.json", aliases = ["config_path"])]
        config: String,
        /// List all tools available on the named server and exit
        #[arg(long)]
        list_tools: bool,
        /// Print timing/telemetry to stderr
        #[arg(short, long)]
        verbose: bool,
    },
    /// Install or remove the cpipe shell alias
    Aliases {
        #[command(subcommand)]
        action: AliasAction,
    },
    /// Verify the health of the context-pipe + semantic-sift installation
    Verify {
        /// Path to pipes configuration
        #[arg(long, default_value = "pipes.json", aliases = ["config_path"])]
        config: String,
    },
    /// Distil agent output before passing it to another agent
    Handoff {
        /// Label for the producing agent
        #[arg(long, aliases = ["from", "from-agent", "from_agent"], default_value = "a2a")]
        from: String,
        /// Label for the consuming agent
        #[arg(long, aliases = ["to", "to-agent", "to_agent"], default_value = "a2a")]
        to: String,
        /// The raw output to distil (if empty, reads from stdin)
        #[arg(long)]
        output: Option<String>,
        /// Explicit pipe name to use
        #[arg(long, aliases = ["pipe-name", "pipe_name"])]
        pipe_name: Option<String>,
        /// Path to pipes configuration
        #[arg(long, default_value = "pipes.json", aliases = ["config_path"])]
        config: String,
    },
}

#[derive(Subcommand)]
enum AliasAction {
    /// Add cpipe alias to shell profile(s)
    Install {
        /// Explicit shell(s) to target
        #[arg(long, value_parser = ["bash", "zsh", "sh", "pwsh"])]
        shells: Vec<String>,
    },
    /// Remove the managed cpipe alias block
    Remove,
}

fn read_input(input_file: Option<&str>) -> io::Result<String> {
    if let Some(file) = input_file {
        fs::read_to_string(file)
    } else {
        if io::stdin().is_terminal() {
            Ok(String::new())
        } else {
            let mut buffer = String::new();
            io::stdin().read_to_string(&mut buffer)?;
            Ok(buffer)
        }
    }
}

fn slice_lines(text: &str, start_line: Option<usize>, end_line: Option<usize>) -> String {
    if start_line.is_none() && end_line.is_none() {
        return text.to_string();
    }
    let mut lines = Vec::new();
    let mut start = 0;
    for (i, c) in text.char_indices() {
        if c == '\n' {
            lines.push(&text[start..=i]);
            start = i + 1;
        }
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    let start_idx = match start_line {
        Some(s) => if s > 0 { s - 1 } else { 0 },
        None => 0,
    };
    let end_idx = match end_line {
        Some(e) => e,
        None => lines.len(),
    };
    let start_idx = std::cmp::min(start_idx, lines.len());
    let end_idx = std::cmp::min(end_idx, lines.len());
    if start_idx >= end_idx {
        return String::new();
    }
    lines[start_idx..end_idx].concat()
}

async fn cmd_run(
    pipe_name: &str,
    config_path: &str,
    input_file: Option<&str>,
    start_line: Option<usize>,
    end_line: Option<usize>,
    verbose: bool,
    vars_list: Vec<String>,
    manifest: Option<String>,
) {
    let path = std::path::PathBuf::from(config_path);
    let config = load_pipes_config_with_path(Some(&path));
    let pipe = config.pipes.iter().find(|p| p.name == pipe_name);
    let pipe = match pipe {
        Some(p) => p,
        None => {
            let available = config.pipes.iter().map(|p| p.name.as_str()).collect::<Vec<&str>>().join(", ");
            eprintln!(
                "cpipe: error: Pipe '{}' not found.\n  Available: {}",
                pipe_name, available
            );
            std::process::exit(1);
        }
    };

    let mut input = match read_input(input_file) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("cpipe: error: Cannot read input: {}", e);
            std::process::exit(1);
        }
    };
    if input.is_empty() {
        return;
    }
    input = slice_lines(&input, start_line, end_line);
    if input.is_empty() {
        return;
    }

    let start_time_str = chrono::Utc::now().to_rfc3339();
    let start_t = std::time::Instant::now();
    let mut vars_map = std::collections::HashMap::new();
    for v in vars_list {
        if let Some((k, val)) = v.split_once('=') {
            vars_map.insert(k.to_string(), val.to_string());
        } else {
            eprintln!("cpipe: error: Invalid var format '{}'. Expected KEY=VALUE.", v);
            std::process::exit(1);
        }
    }
    let (result, trace) = run_pipe(
        pipe,
        &input,
        Some("cli:run"),
        None,
        &config.servers,
        Some(&vars_map),
        manifest.as_deref(),
    ).await;
    let latency_ms = start_t.elapsed().as_secs_f64() * 1000.0;
    
    let platform = "Generic CLI";
    log_telemetry(
        "cli",
        &start_time_str,
        "cli:run",
        input.len(),
        result.len(),
        latency_ms,
        false,
        platform,
        None,
        pipe_name,
        "tier",
    );

    if verbose {
        let header = generate_audit_header(pipe_name, &trace, latency_ms);
        print!("{}", header);
    }
    print!("{}", result);
    if !result.is_empty() && !result.ends_with('\n') {
        println!();
    }
}

fn normalize_relaxed_json(raw: &str) -> String {
    let mut result = String::new();
    let mut chars = raw.chars().peekable();
    while let Some(&c) = chars.peek() {
        match c {
            '"' => {
                chars.next();
                result.push('"');
                while let Some(nc) = chars.next() {
                    result.push(nc);
                    if nc == '\\' {
                        if let Some(next_c) = chars.next() {
                            result.push(next_c);
                        }
                    } else if nc == '"' {
                        break;
                    }
                }
            }
            '\'' => {
                chars.next();
                result.push('"');
                while let Some(nc) = chars.next() {
                    if nc == '\\' {
                        result.push('\\');
                        if let Some(next_c) = chars.next() {
                            result.push(next_c);
                        }
                    } else if nc == '\'' {
                        result.push('"');
                        break;
                    } else {
                        result.push(nc);
                    }
                }
            }
            c if c.is_whitespace() => {
                chars.next();
                result.push(c);
            }
            '{' | '}' | '[' | ']' | ':' | ',' => {
                chars.next();
                result.push(c);
            }
            _ => {
                let mut word = String::new();
                while let Some(&nc) = chars.peek() {
                    match nc {
                        '{' | '}' | '[' | ']' | ':' | ',' | '"' | '\'' => break,
                        nc if nc.is_whitespace() => break,
                        _ => {
                            word.push(nc);
                            chars.next();
                        }
                    }
                }
                if word == "true" || word == "false" || word == "null" {
                    result.push_str(&word);
                } else if let Ok(_) = word.parse::<f64>() {
                    result.push_str(&word);
                } else {
                    result.push('"');
                    let escaped = word.replace('\\', "\\\\").replace('"', "\\\"");
                    result.push_str(&escaped);
                    result.push('"');
                }
            }
        }
    }
    result
}

async fn cmd_run_dynamic(nodes_json: &str, input_file: Option<&str>, allow_shell: bool, verbose: bool) {
    let parsed_json = normalize_relaxed_json(nodes_json);
    let nodes: Vec<Node> = match serde_json::from_str(&parsed_json) {
        Ok(n) => n,
        Err(e) => {
            eprintln!("cpipe: error: nodes_json is not valid JSON: {}", e);
            std::process::exit(1);
        }
    };
    
    if let Err(e) = validate_nodes(&nodes, allow_shell) {
        eprintln!("cpipe: error: {}", e);
        std::process::exit(1);
    }

    let input = match read_input(input_file) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("cpipe: error: Cannot read input: {}", e);
            std::process::exit(1);
        }
    };
    if input.is_empty() {
        return;
    }

    let config = load_pipes_config();
    let pipe = Pipe {
        name: "dynamic".to_string(),
        description: "Ad-hoc dynamic pipe".to_string(),
        logging: None,
        vars: None,
        nodes,
        branch_sequences: None,
    };

    let start_time_str = chrono::Utc::now().to_rfc3339();
    let start_t = std::time::Instant::now();
    let (result, trace) = run_pipe(
        &pipe,
        &input,
        Some("cli:run-dynamic"),
        None,
        &config.servers,
        None,
        None,
    ).await;
    let latency_ms = start_t.elapsed().as_secs_f64() * 1000.0;

    let platform = "Generic CLI";
    log_telemetry(
        "cli",
        &start_time_str,
        "cli:run-dynamic",
        input.len(),
        result.len(),
        latency_ms,
        false,
        platform,
        None,
        "dynamic",
        "tier",
    );

    if verbose {
        let header = generate_audit_header("dynamic", &trace, latency_ms);
        print!("{}", header);
    }
    print!("{}", result);
    if !result.is_empty() && !result.ends_with('\n') {
        println!();
    }
}

fn cmd_list(config_path: &str) {
    let path = PathBuf::from(config_path);
    let tools = cpipe::shadow::list_shadow_tools(Some(&path));
    if tools.is_empty() {
        println!("No pipes configured and no known CLI tools found on PATH.");
        let abs_path = std::fs::canonicalize(&path).unwrap_or(path);
        println!("  Config searched: {:?}  |  ~/.mcp-pipe.json", abs_path);
        return;
    }

    let pipe_tools: Vec<_> = tools.iter().filter(|t| t.source != "PATH").collect();
    let path_tools: Vec<_> = tools.iter().filter(|t| t.source == "PATH").collect();

    if !pipe_tools.is_empty() {
        println!("\nConfigured Pipes:");
        for t in pipe_tools {
            println!("  {:<24} {}", t.name, t.description);
            if !t.nodes.is_empty() {
                println!("    Nodes: {}", t.nodes.join(" ➔ "));
            }
        }
    }

    if !path_tools.is_empty() {
        println!("\nCurated CLI Tools on PATH:");
        for t in path_tools {
            println!("  {:<24} {}", t.name, t.description);
        }
    }
    println!();
}

fn cmd_stats() {
    let sheet = get_balance_sheet();
    let net_label = if sheet.net_change < 0 { "Saved" } else { "Added" };
    println!("\n## Context-Pipe Balance Sheet");
    println!("- **Signal Injected (Augmentation):** +{} chars", sheet.signal_added);
    println!("- **Noise Incinerated (Reduction):** -{} chars", sheet.noise_removed);
    println!("- **Net Context {}:** {} chars", net_label, sheet.net_change.abs());
    println!("- **Platform Events:** {}", sheet.total_events);
    println!("- **Avg Node Latency:** {:.2}ms\n", sheet.avg_latency_ms);
}

async fn cmd_verify(config_path: &str) {
    let py_interpreter = cpipe::orchestrator::find_python_interpreter();
    let py_code = format!(
        "import json; \
        from context_pipe.onboarding import verify_installation, resolve_pipes_config; \
        resolve_pipes_config(r'{}'); \
        print(json.dumps(verify_installation(r'{}')))",
        config_path,
        config_path
    );

    let output = match std::process::Command::new(&py_interpreter)
        .args(&["-c", &py_code])
        .output()
    {
        Ok(out) => out,
        Err(e) => {
            eprintln!("cpipe: verify error: Failed to run python verification script: {}", e);
            std::process::exit(1);
        }
    };

    if !output.status.success() {
        eprintln!(
            "cpipe: verify error: Python script failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        std::process::exit(1);
    }

    let stdout_str = String::from_utf8_lossy(&output.stdout);
    let report_val: serde_json::Value = match serde_json::from_str(&stdout_str) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("cpipe: verify error: Failed to parse JSON: {}. Output: {}", e, stdout_str);
            std::process::exit(1);
        }
    };
    let report = cpipe::server::format_verify_report(report_val);
    println!("{}", report);
}

fn cmd_aliases(action: AliasAction) {
    let py_interpreter = cpipe::orchestrator::find_python_interpreter();
    let py_code = match action {
        AliasAction::Install { shells } => {
            let shells_str = shells.join(" ");
            format!(
                "from context_pipe.onboarding import inject_shell_aliases; \
                inject_shell_aliases('{}'.split())",
                shells_str
            )
        }
        AliasAction::Remove => {
            "from context_pipe.onboarding import remove_shell_aliases; \
            remove_shell_aliases()".to_string()
        }
    };

    let output = match std::process::Command::new(&py_interpreter)
        .args(&["-c", &py_code])
        .output()
    {
        Ok(out) => out,
        Err(e) => {
            eprintln!("cpipe: aliases error: Failed to run python script: {}", e);
            std::process::exit(1);
        }
    };

    if !output.status.success() {
        eprintln!(
            "cpipe: aliases error: Python script failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        std::process::exit(1);
    }
    
    print!("{}", String::from_utf8_lossy(&output.stdout));
}

async fn cmd_tool(
    server_key: &str,
    tool_name: Option<&str>,
    args: &[String],
    input_key: &str,
    input_file: Option<&str>,
    config_path: &str,
    list_tools: bool,
    verbose: bool,
) {
    let path = std::path::PathBuf::from(config_path);
    let config = load_pipes_config_with_path(Some(&path));
    
    if !config.servers.contains_key(server_key) {
        eprintln!("cpipe: error: MCP server '{}' not found in config.", server_key);
        std::process::exit(1);
    }

    if list_tools {
        eprintln!("cpipe: list-tools not yet implemented in Rust core.");
        std::process::exit(1);
    }

    let tool_name = match tool_name {
        Some(n) => n,
        None => {
            eprintln!("cpipe: error: tool_name is required unless --list-tools is used.");
            std::process::exit(1);
        }
    };

    let mut static_args = serde_json::Map::new();
    for a in args {
        if let Some((k, v)) = a.split_once('=') {
            static_args.insert(k.to_string(), serde_json::Value::String(v.to_string()));
        }
    }

    let node = Node {
        cmd: String::new(), 
        args: serde_json::Value::Object(static_args),
        node_type: "mcp".to_string(),
        server: Some(server_key.to_string()),
        tool: Some(tool_name.to_string()),
        input_key: Some(input_key.to_string()),
        ..Default::default()
    };

    let input = match read_input(input_file) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("cpipe: error: Cannot read input: {}", e);
            std::process::exit(1);
        }
    };

    let start_t = std::time::Instant::now();
    let env = std::collections::HashMap::new();
    match cpipe::orchestrator::run_mcp_node(&node, &input, &config.servers, &env).await {
        Ok(result) => {
            if verbose {
                let latency_ms = start_t.elapsed().as_secs_f64() * 1000.0;
                eprintln!("[cpipe:tool] Latency: {:.2}ms", latency_ms);
            }
            print!("{}", result);
            if !result.ends_with('\n') {
                println!();
            }
        }
        Err(e) => {
            eprintln!("cpipe: tool error: {}", e);
            std::process::exit(1);
        }
    }
}

async fn cmd_handoff(
    from_agent: &str,
    to_agent: &str,
    output: Option<&str>,
    pipe_name: Option<&str>,
    config_path: &str,
) {
    let input = match output {
        Some(s) if !s.is_empty() => s.to_string(),
        _ => match read_input(None) {
            Ok(s) => s,
            Err(e) => {
                eprintln!("cpipe: handoff error: Cannot read input: {}", e);
                std::process::exit(1);
            }
        }
    };
    if input.is_empty() {
        return;
    }

    let path = std::path::PathBuf::from(config_path);
    let config = load_pipes_config_with_path(Some(&path));
    let tool_name = if from_agent.is_empty() { "a2a" } else { from_agent };
    let resolved_name = match pipe_name {
        Some(name) if !name.is_empty() => Some(name.to_string()),
        _ => cpipe::orchestrator::resolve_pipe_from_context(&config, tool_name, input.len()),
    };

    let resolved_name = match resolved_name {
        Some(name) => name,
        None => {
            print!("{}", input);
            if !input.ends_with('\n') {
                println!();
            }
            return;
        }
    };

    let pipe = match config.pipes.iter().find(|p| p.name == resolved_name) {
        Some(p) => p,
        None => {
            print!("{}", input);
            if !input.ends_with('\n') {
                println!();
            }
            return;
        }
    };

    let start_time_str = chrono::Utc::now().to_rfc3339();
    let start_t = std::time::Instant::now();
    let (result, _trace) = cpipe::orchestrator::run_pipe(
        pipe,
        &input,
        Some(tool_name),
        None,
        &config.servers,
        None,
        None,
    ).await;
    let latency_ms = start_t.elapsed().as_secs_f64() * 1000.0;
    let session_id = format!("a2a-{}-{}", from_agent, to_agent);

    cpipe::telemetry::log_telemetry(
        &session_id,
        &start_time_str,
        tool_name,
        input.len(),
        result.len(),
        latency_ms,
        false,
        "a2a",
        None,
        &resolved_name,
        "tier",
    );

    print!("{}", result);
    if !result.is_empty() && !result.ends_with('\n') {
        println!();
    }
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();
    
    match cli.command {
        Commands::Run { pipe_name, config, input_file, start_line, end_line, verbose, var, manifest } => {
            cmd_run(&pipe_name, &config, input_file.as_deref(), start_line, end_line, verbose, var, manifest).await;
        }
        Commands::RunDynamic { nodes_json, input_file, allow_shell, verbose } => {
            cmd_run_dynamic(&nodes_json, input_file.as_deref(), allow_shell, verbose).await;
        }
        Commands::List { config } => {
            cmd_list(&config);
        }
        Commands::Stats => {
            cmd_stats();
        }
        Commands::Serve => {
            if let Err(e) = start_mcp_server().await {
                eprintln!("cpipe: serve error: {}", e);
                std::process::exit(1);
            }
        }
        Commands::Tool { server, tool_name, arg, input_key, input_file, config, list_tools, verbose } => {
            cmd_tool(&server, tool_name.as_deref(), &arg, &input_key, input_file.as_deref(), &config, list_tools, verbose).await;
        }
        Commands::Aliases { action } => {
            cmd_aliases(action);
        }
        Commands::Verify { config } => {
            cmd_verify(&config).await;
        }
        Commands::Handoff { from, to, output, pipe_name, config } => {
            cmd_handoff(&from, &to, output.as_deref(), pipe_name.as_deref(), &config).await;
        }
    }
}
