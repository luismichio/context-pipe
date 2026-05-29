// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Luis Kobayashi. All rights reserved.

use std::path::Path;
use std::sync::Mutex;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::Command;
use crate::orchestrator::detect_client_id;

lazy_static::lazy_static! {
    static ref CLIENT_ROOTS: Mutex<Vec<String>> = Mutex::new(Vec::new());
    
    static ref SESSION_ID: String = {
        use std::time::SystemTime;
        let now = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let pid = std::process::id();
        format!("{:016x}{:08x}", now, pid)
    };
}

fn canonicalize_path(p: &str) -> Result<String, String> {
    let path = Path::new(p);
    let abs_path = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir()
            .map_err(|e| e.to_string())?
            .join(path)
    };
    
    let canonical = match std::fs::canonicalize(&abs_path) {
        Ok(cp) => cp,
        Err(_) => abs_path, // Fallback if file doesn't exist
    };
    
    let path_str = canonical.to_string_lossy().to_string();
    let cleaned = if path_str.starts_with(r"\\?\") {
        path_str[4..].to_string()
    } else {
        path_str
    };
    
    if cfg!(windows) {
        Ok(cleaned.to_lowercase())
    } else {
        Ok(cleaned)
    }
}

fn file_uri_to_path(uri: &str) -> Option<String> {
    if !uri.starts_with("file://") {
        return None;
    }
    let path_part = uri.strip_prefix("file://")?;
    // Windows might have file:///C:/path or file://C:/path
    let cleaned = if path_part.starts_with('/') {
        if path_part.len() >= 3 && &path_part[2..3] == ":" {
            // e.g. "/c:/path"
            &path_part[1..]
        } else {
            path_part
        }
    } else {
        path_part
    };
    
    let decoded = percent_decode(cleaned)?;
    
    if cfg!(windows) {
        Some(decoded.replace('/', "\\"))
    } else {
        Some(decoded)
    }
}

fn percent_decode(s: &str) -> Option<String> {
    let mut bytes = Vec::new();
    let mut chars = s.as_bytes().iter().copied();
    while let Some(b) = chars.next() {
        if b == b'%' {
            let h1 = chars.next()?;
            let h2 = chars.next()?;
            let buf = [h1, h2];
            let hex_str = std::str::from_utf8(&buf).ok()?;
            let val = u8::from_str_radix(hex_str, 16).ok()?;
            bytes.push(val);
        } else {
            bytes.push(b);
        }
    }
    String::from_utf8(bytes).ok()
}

pub fn resolve_safe_path(p: &str) -> Result<String, String> {
    let resolved = canonicalize_path(p)?;
    
    let mut workspace_roots = Vec::new();
    if let Ok(auth_root) = std::env::var("PIPE_AUTHORIZED_ROOT") {
        if !auth_root.is_empty() {
            for path_part in std::env::split_paths(&auth_root) {
                if let Ok(c) = canonicalize_path(&path_part.to_string_lossy()) {
                    workspace_roots.push(c);
                }
            }
        }
    }
    
    let roots = CLIENT_ROOTS.lock().unwrap();
    for r in roots.iter() {
        workspace_roots.push(r.clone());
    }
    
    let mut workspace_roots = workspace_roots;
    if workspace_roots.is_empty() {
        if let Ok(cwd) = std::env::current_dir() {
            if let Ok(c) = canonicalize_path(&cwd.to_string_lossy()) {
                workspace_roots.push(c);
            }
        }
    }
    
    for root in &workspace_roots {
        let has_prefix = if cfg!(windows) {
            let root_slash = if root.ends_with('\\') { root.clone() } else { format!("{}\\", root) };
            let resolved_slash = if resolved.ends_with('\\') { resolved.clone() } else { format!("{}\\", resolved) };
            resolved_slash.starts_with(&root_slash)
        } else {
            let root_slash = if root.ends_with('/') { root.clone() } else { format!("{}/", root) };
            let resolved_slash = if resolved.ends_with('/') { resolved.clone() } else { format!("{}/", resolved) };
            resolved_slash.starts_with(&root_slash)
        };
        
        if has_prefix {
            return Ok(resolved);
        }
    }
    
    Err(format!(
        "Access denied for path: {}. The path must be within the authorized workspace roots.",
        p
    ))
}

pub async fn start_mcp_server() -> Result<(), String> {
    let stdin = tokio::io::stdin();
    let mut stdout = tokio::io::stdout();
    let mut reader = BufReader::new(stdin).lines();
    
    loop {
        let line_opt = reader.next_line().await.map_err(|e| e.to_string())?;
        let line = match line_opt {
            Some(l) => l,
            None => break,
        };
        let req: serde_json::Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(e) => {
                let err_resp = serde_json::json!({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": format!("Parse error: {}", e)
                    },
                    "id": serde_json::Value::Null
                });
                send_response(&mut stdout, err_resp).await;
                continue;
            }
        };
        
        let id = req.get("id").cloned();
        let method = req.get("method").and_then(|m| m.as_str()).unwrap_or("");
        let is_notification = req.get("id").is_none();
        
        if method == "initialize" {
            if let Some(params) = req.get("params") {
                let mut roots = Vec::new();
                if let Some(folders) = params.get("workspaceFolders").and_then(|f| f.as_array()) {
                    for f in folders {
                        if let Some(uri) = f.get("uri").and_then(|u| u.as_str()) {
                            if let Some(path) = file_uri_to_path(uri) {
                                if let Ok(c) = canonicalize_path(&path) {
                                    roots.push(c);
                                }
                            }
                        }
                    }
                }
                if let Some(root_uri) = params.get("rootUri").and_then(|u| u.as_str()) {
                    if let Some(path) = file_uri_to_path(root_uri) {
                        if let Ok(c) = canonicalize_path(&path) {
                            roots.push(c);
                        }
                    }
                }
                if let Some(root_path) = params.get("rootPath").and_then(|u| u.as_str()) {
                    if let Ok(c) = canonicalize_path(root_path) {
                        roots.push(c);
                    }
                }
                let mut client_roots = CLIENT_ROOTS.lock().unwrap();
                for r in roots {
                    if !client_roots.contains(&r) {
                        client_roots.push(r);
                    }
                }
            }
            
            if !is_notification {
                let resp = serde_json::json!({
                    "jsonrpc": "2.0",
                    "id": id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {
                                "listChanged": false
                            },
                            "prompts": {
                                "listChanged": false
                            }
                        },
                        "serverInfo": {
                            "name": "cpipe-rust-mcp",
                            "version": "0.1.0"
                        }
                    }
                });
                send_response(&mut stdout, resp).await;
            }
        } else if method == "notifications/initialized" {
            // No response needed
        } else if method == "tools/list" {
            if !is_notification {
                let resp = serde_json::json!({
                    "jsonrpc": "2.0",
                    "id": id,
                    "result": {
                        "tools": get_tools_definition()
                    }
                });
                send_response(&mut stdout, resp).await;
            }
        } else if method == "tools/call" {
            if !is_notification {
                let params = req.get("params");
                let tool_name = params.and_then(|p| p.get("name")).and_then(|n| n.as_str()).unwrap_or("");
                let arguments = params.and_then(|p| p.get("arguments")).cloned().unwrap_or(serde_json::Value::Object(serde_json::Map::new()));
                
                let result_text = handle_tool_call(tool_name, arguments).await;
                
                let resp = serde_json::json!({
                    "jsonrpc": "2.0",
                    "id": id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text
                            }
                        ]
                    }
                });
                send_response(&mut stdout, resp).await;
            }
        } else if method == "prompts/list" {
            if !is_notification {
                let resp = serde_json::json!({
                    "jsonrpc": "2.0",
                    "id": id,
                    "result": {
                        "prompts": [
                            {
                                "name": "pipe_dashboard",
                                "description": "Returns a dashboard overview of the current context-pipe configuration."
                            }
                        ]
                    }
                });
                send_response(&mut stdout, resp).await;
            }
        } else if method == "prompts/get" {
            if !is_notification {
                let params = req.get("params");
                let prompt_name = params.and_then(|p| p.get("name")).and_then(|n| n.as_str()).unwrap_or("");
                
                if prompt_name == "pipe_dashboard" {
                    let dashboard_text = handle_pipe_dashboard().await;
                    let resp = serde_json::json!({
                        "jsonrpc": "2.0",
                        "id": id,
                        "result": {
                            "description": "Returns a dashboard overview of the current context-pipe configuration.",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": {
                                        "type": "text",
                                        "text": dashboard_text
                                    }
                                }
                            ]
                        }
                    });
                    send_response(&mut stdout, resp).await;
                } else {
                    let resp = serde_json::json!({
                        "jsonrpc": "2.0",
                        "id": id,
                        "error": {
                            "code": -32601,
                            "message": format!("Prompt not found: {}", prompt_name)
                        }
                    });
                    send_response(&mut stdout, resp).await;
                }
            }
        } else if !method.is_empty() {
            if !is_notification {
                let resp = serde_json::json!({
                    "jsonrpc": "2.0",
                    "id": id,
                    "error": {
                        "code": -32601,
                        "message": format!("Method not found: {}", method)
                    }
                });
                send_response(&mut stdout, resp).await;
            }
        }
    }
    Ok(())
}

async fn send_response(stdout: &mut tokio::io::Stdout, val: serde_json::Value) {
    if let Ok(mut s) = serde_json::to_string(&val) {
        s.push('\n');
        let _ = stdout.write_all(s.as_bytes()).await;
        let _ = stdout.flush().await;
    }
}

fn get_tools_definition() -> serde_json::Value {
    serde_json::json!([
        {
            "name": "list_pipes",
            "description": "Lists all available context pipes and their descriptions.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "pipe_run",
            "description": "Executes a specific context pipe on the provided input text.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pipe_name": {
                        "type": "string",
                        "description": "The name of the pipe to run (e.g., 'standard-distill', 'semantic-refinery')."
                    },
                    "input_text": {
                        "type": "string",
                        "description": "The raw text to be processed through the pipe."
                    }
                },
                "required": ["pipe_name", "input_text"]
            }
        },
        {
          "name": "pipe_read_file",
          "description": "Reads a local file safely and streams it directly through a context pipe. Use this instead of native file readers to prevent context window flooding.",
          "inputSchema": {
            "type": "object",
            "properties": {
              "path": {
                "type": "string",
                "description": "Absolute or relative path to the file."
              },
              "pipe_name": {
                "type": "string",
                "description": "The name of the pipe to run (e.g., 'standard-distill', 'full-refinery').",
                "default": "standard-distill"
              },
              "start_line": {
                "type": "integer",
                "description": "1-indexed start line (inclusive)."
              },
              "end_line": {
                "type": "integer",
                "description": "1-indexed end line (inclusive)."
              }
            },
            "required": ["path"]
          }
        },
        {
            "name": "pipe_analyze_file",
            "description": "Analyzes a file's size and structure to recommend the optimal context pipe, without flooding the context window. Call this BEFORE pipe_read_file when you are unsure which pipe to use.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file."
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "get_pipe_stats",
            "description": "Returns the Context Balance Sheet (ROI) for the entire pipeline ecosystem.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "pipe_verify",
            "description": "Verifies the context-pipe + semantic-sift installation health. Reports what is working, what is missing, and how to fix it.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "pipe_audit_last",
            "description": "Returns the absolute last recorded telemetry event for manual auditing.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "pipe_onboard",
            "description": "Initializes Context-Pipe hooks and commands in the current project.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "description": "The IDE/CLI environment (e.g., 'Cursor', 'VSCode', 'Gemini')."
                    },
                    "target_dir": {
                        "type": "string",
                        "description": "Optional directory to onboard. Defaults to current directory."
                    }
                },
                "required": ["environment"]
            }
        },
        {
            "name": "pipe_agent_handoff",
            "description": "Distil Agent A's output before passing it to Agent B's context window. ALWAYS call this at agent-to-agent handoff boundaries.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output": {
                        "type": "string",
                        "description": "The raw output from Agent A."
                    },
                    "pipe_name": {
                        "type": "string",
                        "description": "Optional explicit pipe name. Auto-routed if omitted.",
                        "default": ""
                    },
                    "from_agent": {
                        "type": "string",
                        "description": "Label for the producing agent (e.g. 'researcher').",
                        "default": ""
                    },
                    "to_agent": {
                        "type": "string",
                        "description": "Label for the consuming agent (e.g. 'writer').",
                        "default": ""
                    }
                },
                "required": ["output"]
            }
        },
        {
            "name": "pipe_run_dynamic",
            "description": "Executes an ad-hoc context pipe defined as a JSON array of node objects. The final node MUST end with a sifting node to guarantee context safety.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "nodes_json": {
                        "type": "string",
                        "description": "JSON array of node objects."
                    },
                    "input_text": {
                        "type": "string",
                        "description": "The raw text to process through the graph."
                    },
                    "allow_shell": {
                        "type": "boolean",
                        "description": "When True, shell utilities from allowlist are permitted. Default False.",
                        "default": false
                    }
                },
                "required": ["nodes_json", "input_text"]
            }
        },
        {
            "name": "pipe_list_shadow_tools",
            "description": "Lists all available context-processing tools.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "pipe_install_aliases",
            "description": "Installs the cpipe shell alias into the user's profile file(s).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "shells": {
                        "type": "string",
                        "description": "Optional space-separated list of shells to target (bash, zsh, pwsh).",
                        "default": ""
                    }
                }
            }
        },
        {
            "name": "pipe_remove_aliases",
            "description": "Removes the managed cpipe alias block from all known shell profile files.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        }
    ])
}

async fn run_pipe_internal(pipe_name: &str, input_text: &str, tool_name: &str) -> String {
    let config = crate::config::load_pipes_config();
    let pipe = config.pipes.iter().find(|p| p.name == pipe_name);
    let pipe = match pipe {
        Some(p) => p,
        None => return format!("Error: Pipe '{}' not found.\n", pipe_name),
    };
    
    let start_time_str = chrono::Utc::now().to_rfc3339();
    let start_t = std::time::Instant::now();
    let (result, _trace) = crate::orchestrator::run_pipe(
            pipe,
            input_text,
            Some(tool_name),
            None,
            &config.servers,
            None,
            None,
        ).await;
    let latency_ms = start_t.elapsed().as_secs_f64() * 1000.0;
    
    let platform = detect_client_id();
    crate::telemetry::log_telemetry(
        &SESSION_ID,
        &start_time_str,
        tool_name,
        input_text.len(),
        result.len(),
        latency_ms,
        false,
        &platform,
        None,
        pipe_name,
        "tier",
    );
    
    result
}

async fn handle_tool_call(name: &str, args: serde_json::Value) -> String {
    match name {
        "list_pipes" => {
            let config = crate::config::load_pipes_config();
            if config.pipes.is_empty() {
                return "No pipes configured.\n".to_string();
            }
            let mut summary = vec!["Available Context Pipes:".to_string()];
            for p in &config.pipes {
                summary.push(format!("- {}: {}", p.name, if p.description.is_empty() { "No description" } else { &p.description }));
            }
            summary.join("\n")
        }
        "pipe_run" => {
            let pipe_name = args.get("pipe_name").and_then(|v| v.as_str()).unwrap_or("");
            let input_text = args.get("input_text").and_then(|v| v.as_str()).unwrap_or("");
            run_pipe_internal(pipe_name, input_text, "mcp:pipe_run").await
        }
        "pipe_read_file" => {
          let path = args.get("path").and_then(|v| v.as_str()).unwrap_or("");
          let pipe_name = args.get("pipe_name").and_then(|v| v.as_str()).unwrap_or("standard-distill");
          let start_line = args.get("start_line").and_then(|v| v.as_u64()).map(|n| n as usize);
          let end_line = args.get("end_line").and_then(|v| v.as_u64()).map(|n| n as usize);
          let resolved_path = match resolve_safe_path(path) {
              Ok(p) => p,
              Err(e) => return format!("Error reading file: {}\n", e),
          };
          let content = match std::fs::read_to_string(&resolved_path) {
              Ok(c) => c,
              Err(e) => return format!("Error reading file: {}\n", e),
          };
          let content_to_pipe = if start_line.is_some() || end_line.is_some() {
              let lines: Vec<&str> = content.lines().collect();
              let start_idx = start_line.map(|n| n.saturating_sub(1)).unwrap_or(0);
              let end_idx = end_line.unwrap_or(lines.len());
              let start_idx = start_idx.min(lines.len());
              let end_idx = end_idx.min(lines.len());
              if start_idx < end_idx {
                  let mut sliced = lines[start_idx..end_idx].join("\n");
                  if !sliced.is_empty() && content.ends_with('\n') {
                      sliced.push('\n');
                  }
                  sliced
              } else {
                  String::new()
              }
          } else {
              content
          };
          run_pipe_internal(pipe_name, &content_to_pipe, "mcp:pipe_read_file").await
        }
        "pipe_analyze_file" => {
            let path = args.get("path").and_then(|v| v.as_str()).unwrap_or("");
            let resolved_path = match resolve_safe_path(path) {
                Ok(p) => p,
                Err(e) => return format!("Error analyzing file: {}\n", e),
            };
            
            let size = match std::fs::metadata(&resolved_path) {
                Ok(m) => m.len(),
                Err(e) => return format!("Error analyzing file: {}\n", e),
            };
            
            let recommendation = if size > 10000 {
                "semantic-refinery"
            } else {
                "standard-distill"
            };
            
            let file_name = Path::new(path).file_name().and_then(|s| s.to_str()).unwrap_or(path);
            format!(
                "File: {}\nSize: {} bytes\nRecommendation: Use pipe_read_file with pipe_name='{}'.",
                file_name, size, recommendation
            )
        }
        "get_pipe_stats" => {
            let sheet = crate::telemetry::get_balance_sheet();
            let net_label = if sheet.net_change < 0 { "Saved" } else { "Added" };
            format!(
                "## dY\"S Context-Pipe Balance Sheet\n\
                 - **Signal Injected (Augmentation):** +{} chars\n\
                 - **Noise Incinerated (Reduction):** -{} chars\n\
                 - **Net Context {}:** {} chars\n\
                 - **Platform Events:** {}\n\
                 - **Avg Node Latency:** {:.2}ms\n",
                sheet.signal_added,
                sheet.noise_removed,
                net_label,
                sheet.net_change.abs(),
                sheet.total_events,
                sheet.avg_latency_ms
            )
        }
        "pipe_verify" => {
            let py_interpreter = crate::orchestrator::find_python_interpreter();
            let config_path = crate::config::get_config_path();
            
            let py_code = format!(
                "import json; \
                 from context_pipe.onboarding import verify_installation, resolve_pipes_config; \
                 resolve_pipes_config(r'{}'); \
                 print(json.dumps(verify_installation(r'{}')))",
                config_path,
                config_path
            );
            
            let output = match Command::new(&py_interpreter)
                .args(&["-c", &py_code])
                .output()
                .await
            {
                Ok(out) => out,
                Err(e) => return format!("Error running verify script: {}", e),
            };
            
            if !output.status.success() {
                return format!(
                    "Error executing verification python script: {}",
                    String::from_utf8_lossy(&output.stderr)
                );
            }
            
            let stdout_str = String::from_utf8_lossy(&output.stdout);
            let report_val: serde_json::Value = match serde_json::from_str(&stdout_str) {
                Ok(v) => v,
                Err(e) => return format!("Failed to parse verify script JSON: {}. Output: {}", e, stdout_str),
            };
            
            format_verify_report(report_val)
        }
        "pipe_audit_last" => {
            let last = crate::telemetry::get_latest_telemetry();
            let last = match last {
                Some(l) => l,
                None => return "No telemetry events found in the ledger.\n".to_string(),
            };
            
            let reduction = if last.original_chars > 0 {
                (1.0 - (last.final_chars as f64 / last.original_chars as f64)) * 100.0
            } else {
                0.0
            };
            
            format!(
                "## Last Telemetry Event Audit\n\
                 - **Pipe Name:** {}\n\
                 - **Tool Name:** {}\n\
                 - **Original Size:** {} chars\n\
                 - **Final Size:** {} chars\n\
                 - **Reduction:** {:.2}%\n\
                 - **Latency:** {:.2}ms\n\
                 - **Platform:** {}\n\
                 - **Agent Label:** {}\n\
                 - **Session ID:** `{}`\n",
                last.pipe_name,
                last.tool_name,
                last.original_chars,
                last.final_chars,
                reduction,
                last.latency_ms,
                last.platform,
                last.agent,
                last.session_id
            )
        }
        "pipe_onboard" => {
            let environment = args.get("environment").and_then(|v| v.as_str()).unwrap_or("");
            let target_dir = args.get("target_dir").and_then(|v| v.as_str())
                .map(|s| s.to_string())
                .unwrap_or_else(|| {
                    std::env::current_dir()
                        .map(|d| d.to_string_lossy().to_string())
                        .unwrap_or_default()
                });
                
            let py_interpreter = crate::orchestrator::find_python_interpreter();
            let py_code = format!(
                "import json; \
                 from context_pipe.onboarding import inject_hooks; \
                 print(json.dumps(inject_hooks(r'{}', r'{}')))",
                target_dir, environment
            );
            
            let output = match Command::new(&py_interpreter)
                .args(&["-c", &py_code])
                .output()
                .await
            {
                Ok(out) => out,
                Err(e) => return format!("Error running onboard script: {}", e),
            };
            
            if !output.status.success() {
                return format!(
                    "Error executing onboarding python script: {}",
                    String::from_utf8_lossy(&output.stderr)
                );
            }
            
            let stdout_str = String::from_utf8_lossy(&output.stdout);
            let actions: Vec<String> = match serde_json::from_str(&stdout_str) {
                Ok(v) => v,
                Err(e) => return format!("Failed to parse onboard script JSON: {}. Output: {}", e, stdout_str),
            };
            
            if actions.is_empty() {
                return format!("Context-Pipe is already active or no targets found in {}.\n", target_dir);
            }
            
            let mut summary = vec!["Onboarding Successful:".to_string()];
            for a in actions {
                summary.push(format!("- {}", a));
            }
            summary.join("\n")
        }
        "pipe_agent_handoff" => {
            let output_text = args.get("output").and_then(|v| v.as_str()).unwrap_or("");
            let pipe_name = args.get("pipe_name").and_then(|v| v.as_str()).unwrap_or("");
            let from_agent = args.get("from_agent").and_then(|v| v.as_str()).unwrap_or("");
            let to_agent = args.get("to_agent").and_then(|v| v.as_str()).unwrap_or("");
            
            let config = crate::config::load_pipes_config();
            
            let routed_pipe_name = if pipe_name.is_empty() {
                let tool_name = if !from_agent.is_empty() {
                    format!("handoff:{}", from_agent)
                } else {
                    "handoff".to_string()
                };
                crate::orchestrator::resolve_pipe_from_context(&config, &tool_name, output_text.len())
                    .unwrap_or_else(|| "standard-distill".to_string())
            } else {
                pipe_name.to_string()
            };
            
            let pipe = config.pipes.iter().find(|p| p.name == routed_pipe_name);
            let pipe = match pipe {
                Some(p) => p,
                None => return output_text.to_string(),
            };
            
            let start_time_str = chrono::Utc::now().to_rfc3339();
            let start_t = std::time::Instant::now();
            let (result, _trace) = crate::orchestrator::run_pipe(
            pipe,
            output_text,
            Some("mcp:pipe_agent_handoff"),
            if from_agent.is_empty() { None } else { Some(from_agent) },
            &config.servers,
            None,
            None,
        ).await;
            let latency_ms = start_t.elapsed().as_secs_f64() * 1000.0;
            
            let platform = detect_client_id();
            let agent_label = if !to_agent.is_empty() {
                Some(format!("->{}", to_agent))
            } else {
                None
            };
            
            crate::telemetry::log_telemetry(
                &SESSION_ID,
                &start_time_str,
                "mcp:pipe_agent_handoff",
                output_text.len(),
                result.len(),
                latency_ms,
                false,
                &platform,
                agent_label.as_deref(),
                &routed_pipe_name,
                "tier",
            );
            
            result
        }
        "pipe_run_dynamic" => {
            let nodes_json = args.get("nodes_json").and_then(|v| v.as_str()).unwrap_or("");
            let input_text = args.get("input_text").and_then(|v| v.as_str()).unwrap_or("");
            let allow_shell = args.get("allow_shell").and_then(|v| v.as_bool()).unwrap_or(false);
            
            let nodes: Vec<crate::config::Node> = match serde_json::from_str(nodes_json) {
                Ok(n) => n,
                Err(e) => return format!("Error: nodes_json is not valid JSON - {}\n", e),
            };
            
            if let Err(e) = validate_nodes(&nodes, allow_shell) {
                return format!("Error: {}\n", e);
            }
            
            let pipe = crate::config::Pipe {
                name: "dynamic".to_string(),
                description: "Ad-hoc dynamic pipe".to_string(),
                logging: None,
                vars: None,
                nodes,
                branch_sequences: None,
            };
            
            let config = crate::config::load_pipes_config();
            
            let start_time_str = chrono::Utc::now().to_rfc3339();
            let start_t = std::time::Instant::now();
            let (result, _trace) = crate::orchestrator::run_pipe(
            &pipe,
            input_text,
            Some("mcp:pipe_run_dynamic"),
            None,
            &config.servers,
            None,
            None,
        ).await;
            let latency_ms = start_t.elapsed().as_secs_f64() * 1000.0;
            
            let platform = detect_client_id();
            crate::telemetry::log_telemetry(
                &SESSION_ID,
                &start_time_str,
                "mcp:pipe_run_dynamic",
                input_text.len(),
                result.len(),
                latency_ms,
                false,
                &platform,
                None,
                "dynamic",
                "tier",
            );
            
            result
        }
        "pipe_list_shadow_tools" => {
            let config_path = crate::config::get_config_path();
            let tools = crate::shadow::list_shadow_tools(Some(Path::new(&config_path)));
            if tools.is_empty() {
                return "No context-processing tools found (no pipes.json and no known CLI tools on PATH).\n".to_string();
            }
            
            let mut lines = vec![
                "| Name | Source | Description | Nodes |".to_string(),
                "|---|---|---|---|".to_string(),
            ];
            for t in tools {
                let nodes_str = if t.nodes.is_empty() {
                    "-".to_string()
                } else {
                    t.nodes.iter().map(|n| format!("`{}`", n)).collect::<Vec<String>>().join(", ")
                };
                lines.push(format!("| {} | {} | {} | {} |", t.name, t.source, t.description, nodes_str));
            }
            lines.join("\n")
        }
        "pipe_install_aliases" => {
            let shells = args.get("shells").and_then(|v| v.as_str()).unwrap_or("");
            let py_interpreter = crate::orchestrator::find_python_interpreter();
            
            let py_code = format!(
                "import json; \
                 from context_pipe.onboarding import inject_shell_aliases; \
                 print(json.dumps(inject_shell_aliases(shells=[s for s in r'{}'.split() if s.strip()] if r'{}'.strip() else None)))",
                shells, shells
            );
            
            let output = match Command::new(&py_interpreter)
                .args(&["-c", &py_code])
                .output()
                .await
            {
                Ok(out) => out,
                Err(e) => return format!("Error running install aliases script: {}", e),
            };
            
            if !output.status.success() {
                return format!(
                    "Error executing install aliases python script: {}",
                    String::from_utf8_lossy(&output.stderr)
                );
            }
            
            let stdout_str = String::from_utf8_lossy(&output.stdout);
            let results: Vec<String> = match serde_json::from_str(&stdout_str) {
                Ok(v) => v,
                Err(e) => return format!("Failed to parse install aliases JSON: {}. Output: {}", e, stdout_str),
            };
            
            if results.is_empty() {
                return "cpipe alias already up-to-date - no profile files were modified.\n".to_string();
            }
            
            let mut lines = vec!["cpipe alias installed:".to_string()];
            for r in results {
                lines.push(format!("  - {}", r));
            }
            lines.push("\nRestart your shell (or source the profile) to activate `cpipe`.".to_string());
            lines.join("\n")
        }
        "pipe_remove_aliases" => {
            let py_interpreter = crate::orchestrator::find_python_interpreter();
            let py_code = "import json; from context_pipe.onboarding import remove_shell_aliases; print(json.dumps(remove_shell_aliases()))";
            
            let output = match Command::new(&py_interpreter)
                .args(&["-c", &py_code])
                .output()
                .await
            {
                Ok(out) => out,
                Err(e) => return format!("Error running remove aliases script: {}", e),
            };
            
            if !output.status.success() {
                return format!(
                    "Error executing remove aliases python script: {}",
                    String::from_utf8_lossy(&output.stderr)
                );
            }
            
            let stdout_str = String::from_utf8_lossy(&output.stdout);
            let results: Vec<String> = match serde_json::from_str(&stdout_str) {
                Ok(v) => v,
                Err(e) => return format!("Failed to parse remove aliases JSON: {}. Output: {}", e, stdout_str),
            };
            
            if results.is_empty() {
                return "No cpipe alias block found in any profile - nothing removed.\n".to_string();
            }
            
            let mut lines = vec!["cpipe alias removed:".to_string()];
            for r in results {
                lines.push(format!("  - {}", r));
            }
            lines.join("\n")
        }
        _ => format!("Tool not found: {}\n", name)
    }
}

pub fn format_verify_report(report: serde_json::Value) -> String {
    let mut lines = vec!["## Context-Pipe Installation Report".to_string(), String::new()];
    
    if let Some(cp) = report.get("context_pipe") {
        let ok = cp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
        let detail = cp.get("detail").and_then(|v| v.as_str()).unwrap_or("");
        lines.push(format!("{} **context-pipe**: {}", if ok { "✔️" } else { "❌" }, detail));
    }
    
    if let Some(pc) = report.get("pipes_config") {
        let ok = pc.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
        let path = pc.get("path").and_then(|v| v.as_str()).unwrap_or("");
        let detail = pc.get("detail").and_then(|v| v.as_str()).unwrap_or("");
        lines.push(format!("{} **pipes.json** (`{}`): {}", if ok { "✔️" } else { "❌" }, path, detail));
    }
    
    if let Some(ss) = report.get("semantic_sift") {
        let ok = ss.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
        if ok {
            let version = ss.get("version").and_then(|v| v.as_str()).unwrap_or("");
            let path = ss.get("path").and_then(|v| v.as_str()).unwrap_or("");
            lines.push(format!("✔️ **semantic-sift-cli**: {} ➔ `{}`", version, path));
        } else {
            let detail = ss.get("detail").and_then(|v| v.as_str()).unwrap_or("");
            lines.push(format!("❌ **semantic-sift-cli**: {}", detail));
        }
    }
    
    if let Some(nodes) = report.get("nodes").and_then(|v| v.as_array()) {
        if !nodes.is_empty() {
            lines.push(String::new());
            lines.push("### Pipe Node Resolution".to_string());
            for node in nodes {
                let ok = node.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
                let cmd = node.get("cmd").and_then(|v| v.as_str()).unwrap_or("");
                let resolved = node.get("resolved").and_then(|v| v.as_str()).unwrap_or("not found in PATH");
                lines.push(format!("{} `{}` ➔ `{}`", if ok { "✔️" } else { "❌" }, cmd, resolved));
            }
        }
    }
    
    if let Some(update_warning) = report.get("update_warning").and_then(|v| v.as_str()) {
        if !update_warning.is_empty() {
            lines.push(String::new());
            lines.push(update_warning.to_string());
        }
    }
    
    lines.push(String::new());
    let overall = report.get("overall").and_then(|v| v.as_bool()).unwrap_or(false);
    if overall {
        lines.push("**Overall: ✔️ All systems operational.**".to_string());
    } else {
        lines.push("**Overall: ❌ Action required ➔ see items above.**".to_string());
    }
    
    lines.join("\n")
}

pub fn validate_nodes(nodes: &[crate::config::Node], allow_shell: bool) -> Result<(), String> {
    let shell_meta = regex::Regex::new(r"[|;&$`>]").unwrap();
    let shell_utility_allowlist: std::collections::HashSet<&str> = [
        "bash", "sh", "awk", "sed", "grep", "cut", "sort", "uniq", "tr",
        "head", "tail", "wc", "cat", "echo", "printf", "xargs", "python",
        "python3", "jq", "yq"
    ].iter().copied().collect();
    let sift_terminal_cmds: std::collections::HashSet<&str> = ["semantic-sift-cli", "sift"].iter().copied().collect();
    
    let mut has_shell_utility = false;
    
    for (i, node) in nodes.iter().enumerate() {
        if node.node_type == "mcp" {
            if node.server.is_none() {
                return Err(format!("MCP node at index {} is missing required key 'server'.", i));
            }
            if node.tool.is_none() {
                return Err(format!("MCP node at index {} is missing required key 'tool'.", i));
            }
            continue;
        }
        
        if node.cmd.is_empty() {
            return Err(format!("Node at index {} is missing required key 'cmd'.", i));
        }
        
        if shell_meta.is_match(&node.cmd) {
            return Err(format!(
                "Node cmd '{}' contains shell metacharacters. Use args[] for arguments - cmd must be a bare executable name.",
                node.cmd
            ));
        }
        
        let exe = node.cmd.split_whitespace().next().unwrap_or(&node.cmd);
        if shell_utility_allowlist.contains(exe) {
            if !allow_shell {
                return Err(format!(
                    "Node cmd '{}' is a shell utility. Set allow_shell=True to enable shell utility nodes. The final node must be semantic-sift-cli to guarantee context safety.",
                    exe
                ));
            }
            has_shell_utility = true;
        }
    }
    
    if has_shell_utility {
        if let Some(last_node) = nodes.last() {
            let last_exe = last_node.cmd.split_whitespace().next().unwrap_or(&last_node.cmd);
            if !sift_terminal_cmds.contains(last_exe) {
                return Err(format!(
                    "Pipes containing shell utilities must end with a semantic-sift-cli node to guarantee context safety. Last node cmd was '{}'. Add a terminal node: {{\"cmd\": \"semantic-sift-cli\", \"args\": [\"--rate\", \"0.5\"]}}.",
                    last_exe
                ));
            }
        } else {
            return Err("Dynamic pipe has no nodes.".to_string());
        }
    }
    
    Ok(())
}

async fn handle_pipe_dashboard() -> String {
    let pipes = handle_tool_call("list_pipes", serde_json::Value::Null).await;
    let stats = handle_tool_call("get_pipe_stats", serde_json::Value::Null).await;
    format!(
        "# dYZr Context-Pipe Dashboard\n\
         You are currently connected to the Context-Pipe Orchestrator.\n\n\
         ## Active Pipes\n\
         {}\n\n\
         ## Current ROI (Balance Sheet)\n\
         {}\n\n\
         ## Instructions\n\
         To protect your context window, always consider streaming large tool outputs through the optimal pipe.\n",
        pipes, stats
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resolve_safe_path_multi() {
        let temp_dir_1 = std::env::temp_dir().join("cpipe_test_dir1");
        let temp_dir_2 = std::env::temp_dir().join("cpipe_test_dir2");
        std::fs::create_dir_all(&temp_dir_1).unwrap();
        std::fs::create_dir_all(&temp_dir_2).unwrap();

        let file_1 = temp_dir_1.join("file1.txt");
        let file_2 = temp_dir_2.join("file2.txt");
        std::fs::write(&file_1, "hello").unwrap();
        std::fs::write(&file_2, "world").unwrap();

        let paths = vec![temp_dir_1.clone(), temp_dir_2.clone()];
        let path_os_string = std::env::join_paths(paths).unwrap();
        
        std::env::set_var("PIPE_AUTHORIZED_ROOT", path_os_string);

        let res1 = resolve_safe_path(&file_1.to_string_lossy());
        let res2 = resolve_safe_path(&file_2.to_string_lossy());

        assert!(res1.is_ok());
        assert!(res2.is_ok());

        let _ = std::fs::remove_file(file_1);
        let _ = std::fs::remove_file(file_2);
        let _ = std::fs::remove_dir(temp_dir_1);
        let _ = std::fs::remove_dir(temp_dir_2);
    }
}
