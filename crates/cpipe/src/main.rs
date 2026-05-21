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
#[command(version = "0.4.0")]
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
        #[arg(long, default_value = "pipes.json")]
        config: String,
        /// Read input from this file instead of stdin
        #[arg(long)]
        input_file: Option<String>,
        /// Prepend audit header (node trace + latency) to output
        #[arg(short, long)]
        verbose: bool,
    },
    /// Run an ad-hoc node array on stdin or a file
    RunDynamic {
        /// JSON array of node objects
        nodes_json: String,
        /// Read input from this file instead of stdin
        #[arg(long)]
        input_file: Option<String>,
        /// Prepend audit header to output
        #[arg(short, long)]
        verbose: bool,
    },
    /// List configured pipes and PATH tools
    List {
        /// Path to pipes configuration
        #[arg(long, default_value = "pipes.json")]
        config: String,
    },
    /// Print the Context Balance Sheet (ROI)
    Stats,
    /// Start the MCP server (stdio transport)
    Serve,
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

async fn cmd_run(pipe_name: &str, config_path: &str, input_file: Option<&str>, verbose: bool) {
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
    
    let start_time_str = chrono::Utc::now().to_rfc3339();
    let start_t = std::time::Instant::now();
    let (result, trace) = run_pipe(
        pipe,
        &input,
        Some("cli:run"),
        None,
        &config.servers,
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

async fn cmd_run_dynamic(nodes_json: &str, input_file: Option<&str>, verbose: bool) {
    let nodes: Vec<Node> = match serde_json::from_str(nodes_json) {
        Ok(n) => n,
        Err(e) => {
            eprintln!("cpipe: error: nodes_json is not valid JSON: {}", e);
            std::process::exit(1);
        }
    };
    
    if let Err(e) = validate_nodes(&nodes, false) {
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
        nodes,
    };
    
    let start_time_str = chrono::Utc::now().to_rfc3339();
    let start_t = std::time::Instant::now();
    let (result, trace) = run_pipe(
        &pipe,
        &input,
        Some("cli:run-dynamic"),
        None,
        &config.servers,
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

#[tokio::main]
async fn main() {
    let cli = Cli::parse();
    
    match cli.command {
        Commands::Run { pipe_name, config, input_file, verbose } => {
            cmd_run(&pipe_name, &config, input_file.as_deref(), verbose).await;
        }
        Commands::RunDynamic { nodes_json, input_file, verbose } => {
            cmd_run_dynamic(&nodes_json, input_file.as_deref(), verbose).await;
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
    }
}
