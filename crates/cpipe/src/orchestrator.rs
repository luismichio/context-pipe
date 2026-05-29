
fn _build_vars(
    pipe_config: &crate::config::Pipe,
    invocation_vars: &HashMap<String, String>,
) -> Result<HashMap<String, String>, String> {
    let mut merged = HashMap::new();
    let mut pipe_defaults = HashMap::new();

    if let Some(vars_map) = &pipe_config.vars {
        for (k, v) in vars_map {
            let re = regex::Regex::new(r"^[A-Z0-9_]+$").unwrap();
            if !re.is_match(k) {
                return Err(format!("Invalid pipe variable name: '{}' (must be [A-Z0-9_]+)", k));
            }
            pipe_defaults.insert(k.clone(), v.clone());
        }
    }

    for k in invocation_vars.keys() {
        let re = regex::Regex::new(r"^[A-Z0-9_]+$").unwrap();
        if !re.is_match(k) {
            return Err(format!("Invalid invocation variable name: '{}' (must be [A-Z0-9_]+)", k));
        }
    }

    // 1. pipe defaults
    for (k, v) in &pipe_defaults {
        merged.insert(k.clone(), v.clone());
    }

    // 2. os.environ
    for k in pipe_defaults.keys() {
        if let Ok(val) = std::env::var(k) {
            merged.insert(k.clone(), val);
        }
    }

    // 3. invocation vars always win
    for (k, v) in invocation_vars {
        merged.insert(k.clone(), v.clone());
    }

    // Fail-fast for required empty vars
    for (k, default_val) in &pipe_defaults {
        if default_val.is_empty() && !invocation_vars.contains_key(k) {
            if let Ok(val) = std::env::var(k) {
                if val.is_empty() {
                    return Err(format!("Missing pipe variable: {}", k));
                }
            } else {
                return Err(format!("Missing pipe variable: {}", k));
            }
        }
    }

    Ok(merged)
}

fn _write_manifest(
    manifest_path: &str,
    pipe_config: &crate::config::Pipe,
    vars_used: &HashMap<String, String>,
    trace: &[HashMap<String, serde_json::Value>],
    result: &str,
    status: &str,
    started_at: &str,
) {
    let pipe_name = &pipe_config.name;
    
    let resolved_path = if manifest_path == "auto" {
        let cache_dir = std::env::current_dir().unwrap_or_default().join(".pipe_cache");
        let _ = std::fs::create_dir_all(&cache_dir);
        let iso_date = chrono::Utc::now().format("%Y%m%dT%H%M%SZ").to_string();
        cache_dir.join(format!("{}-{}.json", pipe_name, iso_date)).to_string_lossy().to_string()
    } else {
        manifest_path.to_string()
    };

    let mut steps = Vec::new();
    for (i, entry) in trace.iter().enumerate() {
        let mut step = serde_json::Map::new();
        step.insert("index".to_string(), serde_json::json!(i + 1));
        let cmd = entry.get("node").cloned().unwrap_or(serde_json::json!("unknown"));
        step.insert("cmd".to_string(), cmd);
        
        if entry.contains_key("error") {
            step.insert("ok".to_string(), serde_json::json!(false));
            step.insert("error".to_string(), entry.get("error").cloned().unwrap_or(serde_json::json!("")));
            step.insert("status".to_string(), serde_json::json!(1));
        } else {
            step.insert("ok".to_string(), serde_json::json!(true));
            step.insert("status".to_string(), serde_json::json!(0));
            step.insert("inputSize".to_string(), entry.get("input_size").cloned().unwrap_or(serde_json::json!(0)));
            step.insert("outputSize".to_string(), entry.get("output_size").cloned().unwrap_or(serde_json::json!(0)));
        }
        
        if entry.contains_key("validator_code") {
            step.insert("validatorExitCode".to_string(), entry.get("validator_code").cloned().unwrap());
            if let Some(br) = entry.get("branch") {
                step.insert("branch".to_string(), br.clone());
            }
        }
        steps.push(serde_json::Value::Object(step));
    }
    
    let mut manifest = serde_json::Map::new();
    manifest.insert("pipe".to_string(), serde_json::json!(pipe_name));
    manifest.insert("vars".to_string(), serde_json::json!(vars_used));
    manifest.insert("startedAt".to_string(), serde_json::json!(started_at));
    manifest.insert("completedAt".to_string(), serde_json::json!(chrono::Utc::now().to_rfc3339()));
    manifest.insert("status".to_string(), serde_json::json!(status));
    manifest.insert("steps".to_string(), serde_json::Value::Array(steps));
    
    let final_out = if result.len() > 2000 {
        &result[0..2000]
    } else {
        result
    };
    manifest.insert("finalOutput".to_string(), serde_json::json!(final_out));
    
    if let Some(parent) = std::path::Path::new(&resolved_path).parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    
    if let Ok(mut f) = std::fs::File::create(&resolved_path) {
        if let Ok(json_str) = serde_json::to_string_pretty(&manifest) {
            let _ = f.write_all(json_str.as_bytes());
        }
    }
}

// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Luis Kobayashi. All rights reserved.

use sha2::{Sha256, Digest};
use std::collections::HashMap;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use chrono::Utc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::Command;
use crate::config::{Config, Node, ServerConfig, TeeConfig, resolve_placeholders};
use crate::shadow::which;

pub const SIFT_SIGNATURE: &str = "--- [Semantic-Sift Audit] ---";

pub fn get_env_with_venv_path() -> HashMap<String, String> {
    let mut env: HashMap<String, String> = std::env::vars().collect();
    
    if let Ok(venv_path) = std::env::var("VIRTUAL_ENV") {
        let venv_bin = if cfg!(windows) {
            PathBuf::from(&venv_path).join("Scripts")
        } else {
            PathBuf::from(&venv_path).join("bin")
        };
        if venv_bin.exists() {
            let path_sep = if cfg!(windows) { ";" } else { ":" };
            let current_path = env.get("PATH").cloned().unwrap_or_default();
            let bin_str = venv_bin.to_string_lossy().to_string();
            if !current_path.contains(&bin_str) {
                env.insert("PATH".to_string(), format!("{}{}{}", bin_str, path_sep, current_path));
            }
        }
    }
    env
}

pub fn resolve_node_cmd(cmd: &str) -> String {
    let path = Path::new(cmd);
    if path.is_absolute() && path.is_file() {
        return cmd.to_string();
    }
    
    let env_vars = get_env_with_venv_path();
    let path_env = env_vars.get("PATH").map(|s| s.as_str());
    if let Some(resolved) = which(cmd, path_env) {
        return resolved.to_string_lossy().to_string();
    }
    
    if let Some(home) = dirs::home_dir() {
        let exe_name = if cfg!(windows) {
            format!("{}.exe", cmd)
        } else {
            cmd.to_string()
        };
        
        let pipx_bin_dir = std::env::var("PIPX_BIN_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| home.join(".local").join("bin"));
            
        let candidates = vec![
            home.join(".local").join("bin").join(&exe_name),
            pipx_bin_dir.join(&exe_name),
        ];
        
        for candidate in candidates {
            if candidate.is_file() {
                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    if let Ok(metadata) = candidate.metadata() {
                        if metadata.permissions().mode() & 0o111 != 0 {
                            return candidate.to_string_lossy().to_string();
                        }
                    }
                }
                #[cfg(not(unix))]
                {
                    return candidate.to_string_lossy().to_string();
                }
            }
        }
    }
    cmd.to_string()
}

pub fn find_python_interpreter() -> String {
    if let Ok(venv_path) = std::env::var("VIRTUAL_ENV") {
        let python_exe = if cfg!(windows) {
            PathBuf::from(venv_path).join("Scripts").join("python.exe")
        } else {
            PathBuf::from(venv_path).join("bin").join("python")
        };
        if python_exe.exists() {
            return python_exe.to_string_lossy().to_string();
        }
    }
    let env_vars = get_env_with_venv_path();
    let path_env = env_vars.get("PATH").map(|s| s.as_str());
    if let Some(resolved) = which("python", path_env) {
        return resolved.to_string_lossy().to_string();
    }
    if let Some(resolved) = which("python3", path_env) {
        return resolved.to_string_lossy().to_string();
    }
    if cfg!(windows) { "python.exe".to_string() } else { "python3".to_string() }
}

fn format_thousands(n: usize) -> String {
    let s = n.to_string();
    let mut result = String::new();
    let mut count = 0;
    for c in s.chars().rev() {
        if count > 0 && count % 3 == 0 {
            result.push(',');
        }
        result.push(c);
        count += 1;
    }
    result.chars().rev().collect()
}

fn emit_pipe_log(
    pipe_config: &crate::config::Pipe,
    event: &str,
    node_name: &str,
    tool_name: Option<&str>,
    input_size: usize,
    output_size: usize,
    latency_ms: f64,
    error: bool,
) {
    let (enabled, prefix_opt, level_opt, fields_opt) = match &pipe_config.logging {
        Some(cfg) => (cfg.enabled, cfg.prefix.clone(), cfg.level.clone(), cfg.fields.clone()),
        None => (None, None, None, None),
    };

    let is_enabled = if let Some(e) = enabled {
        e
    } else {
        std::env::var("PIPE_LOG_LEVEL").is_ok()
    };

    if !is_enabled {
        return;
    }

    let prefix = prefix_opt
        .or_else(|| std::env::var("PIPE_LOG_PREFIX").ok())
        .unwrap_or_else(|| "[PIPE]".to_string());

    let level = level_opt
        .or_else(|| std::env::var("PIPE_LOG_LEVEL").ok())
        .unwrap_or_else(|| "compact".to_string())
        .to_lowercase();

    // If compact and event is entry, skip
    if level == "compact" && event == "entry" {
        return;
    }

    let fields = fields_opt
        .unwrap_or_else(|| vec![
            "trigger".to_string(),
            "node".to_string(),
            "tokens".to_string(),
            "timing".to_string(),
        ]);

    let mut parts = Vec::new();
    for field in &fields {
        match field.as_str() {
            "trigger" => {
                if let Some(tn) = tool_name {
                    parts.push(format!("trigger:{}", tn));
                }
            }
            "node" => {
                if event == "entry" {
                    parts.push(format!("→ {}", node_name));
                } else {
                    let status_icon = if error { "✗" } else { "✓" };
                    parts.push(format!("{} {}", status_icon, node_name));
                }
            }
            "tokens" => {
                if event == "exit" {
                    let delta = output_size as isize - input_size as isize;
                    let reduction_pct = if input_size > 0 {
                        (delta as f64 / input_size as f64) * 100.0
                    } else {
                        0.0
                    };
                    let input_formatted = format_thousands(input_size);
                    let output_formatted = format_thousands(output_size);
                    let delta_formatted = if delta >= 0 {
                        format!("+{}", format_thousands(delta as usize))
                    } else {
                        format!("-{}", format_thousands(delta.abs() as usize))
                    };
                    parts.push(format!(
                        "{} → {} chars ({} | {:.1}%)",
                        input_formatted, output_formatted, delta_formatted, reduction_pct
                    ));
                }
            }
            "timing" => {
                if event == "exit" {
                    let latency_s = latency_ms / 1000.0;
                    let timing_str = if latency_s < 1.0 {
                        format!("{:.2}s", latency_s)
                    } else {
                        format!("{:.1}s", latency_s)
                    };
                    parts.push(timing_str);
                }
            }
            _ => {}
        }
    }

    if !parts.is_empty() {
        eprintln!("{} {}", prefix, parts.join(" | "));
    }
}

pub fn check_echo(text: &str, pipe_name: &str, node_index: &str) -> bool {
    if text.is_empty() || text.len() < 500 {
        return false;
    }
    
    let cache_dir = std::env::current_dir().unwrap_or_default().join(".pipe_cache");
    let _ = std::fs::create_dir_all(&cache_dir);
    
    let raw_key = format!("{}:{}:{}", pipe_name, node_index, text);
    let mut hasher = Sha256::new();
    hasher.update(raw_key.as_bytes());
    let hash_result = hasher.finalize();
    let content_hash = &hex::encode(hash_result)[..16];
    
    let echo_path = cache_dir.join(format!("echo_{}.tmp", content_hash));
    let now = Utc::now().timestamp() as f64;
    
    if echo_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&echo_path) {
            if let Ok(expiry) = content.trim().parse::<f64>() {
                if now < expiry {
                    return true;
                }
            }
        }
    }
    
    if let Ok(mut file) = std::fs::File::create(&echo_path) {
        let expiry = now + 30.0;
        let _ = write!(file, "{}", expiry);
    }
    false
}

pub fn write_tee(
    tee_config: &TeeConfig,
    data: &str,
    node_cmd: &str,
    tool_name: Option<&str>
) -> Option<String> {
    if tee_config.sink != "file" {
        return None;
    }
    if tee_config.path.is_empty() {
        return None;
    }
    
    let iso_date = Utc::now().format("%Y-%m-%d").to_string();
    let re_tool = regex::Regex::new(r"[^\w\-]").unwrap();
    let safe_tool = re_tool.replace_all(tool_name.unwrap_or("unknown"), "_");
    
    let resolved_path_str = tee_config.path
        .replace("{iso_date}", &iso_date)
        .replace("{tool_name}", &safe_tool);
        
    let resolved_path = Path::new(&resolved_path_str);
    if let Some(parent) = resolved_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    
    let append = tee_config.mode == "append";
    let file_result = OpenOptions::new()
        .create(true)
        .write(true)
        .append(append)
        .truncate(!append)
        .open(resolved_path);
        
    if let Ok(mut file) = file_result {
        let timestamp = Utc::now().to_rfc3339();
        let separator = format!("\n--- [Context-Pipe: Tee @ {} | {}] ---\n", node_cmd, timestamp);
        if file.write_all(data.as_bytes()).is_ok() && file.write_all(separator.as_bytes()).is_ok() {
            return Some(resolved_path_str);
        }
    }
    None
}

pub fn evaluate_condition(predicate: &str, input_data: &str) -> bool {
    let predicate = predicate.trim();
    if predicate.is_empty() {
        return true;
    }

    if predicate.starts_with("size:>") {
        if let Ok(val) = predicate["size:>".len()..].trim().parse::<usize>() {
            return input_data.len() > val;
        }
        eprintln!("[Context-Pipe] Malformed size predicate: {}", predicate);
        return true;
    } else if predicate.starts_with("size:<") {
        if let Ok(val) = predicate["size:<".len()..].trim().parse::<usize>() {
            return input_data.len() < val;
        }
        eprintln!("[Context-Pipe] Malformed size predicate: {}", predicate);
        return true;
    } else if predicate.starts_with("artifact:missing:") {
        let mut path = predicate["artifact:missing:".len()..].trim();
        if (path.starts_with('"') && path.ends_with('"')) || (path.starts_with('\'') && path.ends_with('\'')) {
            path = &path[1..path.len() - 1];
        }
        return !std::path::Path::new(path).exists();
    } else if predicate.starts_with("artifact:exists:") {
        let mut path = predicate["artifact:exists:".len()..].trim();
        if (path.starts_with('"') && path.ends_with('"')) || (path.starts_with('\'') && path.ends_with('\'')) {
            path = &path[1..path.len() - 1];
        }
        return std::path::Path::new(path).exists();
    } else if predicate.starts_with("contains:") {
        let mut sub = predicate["contains:".len()..].trim();
        if (sub.starts_with('"') && sub.ends_with('"')) || (sub.starts_with('\'') && sub.ends_with('\'')) {
            sub = &sub[1..sub.len() - 1];
        }
        let leading: String = input_data.chars().take(300).collect();
        return leading.contains(sub);
    }

    eprintln!("[Context-Pipe] Unknown condition predicate: {}", predicate);
    return true;
}

pub fn resolve_pipe_from_context(config: &Config, tool_name: &str, content_len: usize) -> Option<String> {
    for mapping in &config.mappings {
        let trigger = &mapping.trigger;
        if trigger.starts_with("tool:") {
            let pattern = trigger.trim_start_matches("tool:");
            if let Ok(re) = regex::Regex::new(&format!("(?i){}", pattern)) {
                if re.is_match(tool_name) {
                    return Some(mapping.pipe.clone());
                }
            }
        } else if trigger.starts_with("size:>") {
            if let Ok(threshold) = trigger.trim_start_matches("size:>").parse::<usize>() {
                if content_len > threshold {
                    return Some(mapping.pipe.clone());
                }
            }
        } else if trigger == "default" {
            return Some(mapping.pipe.clone());
        }
    }
    None
}

pub async fn run_mcp_node(
    node: &Node,
    stdin_data: &str,
    server_registry: &HashMap<String, ServerConfig>,
    env: &HashMap<String, String>,
) -> Result<String, String> {
    let server_key = node.server.as_ref()
        .ok_or_else(|| "MCP Node has no server specified".to_string())?;
    let tool_name = node.tool.as_ref()
        .ok_or_else(|| "MCP Node has no tool specified".to_string())?;
    let input_key = node.input_key.as_deref().unwrap_or("content");
    
    let server_cfg = server_registry.get(server_key)
        .ok_or_else(|| format!("MCP server '{}' not found in servers registry.", server_key))?;
        
    let mut resolved_env = get_env_with_venv_path();
    for (k, v) in env {
        resolved_env.insert(k.clone(), v.clone());
    }
    
    for (k, v) in &server_cfg.env {
        let v_val = serde_json::Value::String(v.clone());
        let resolved_v = resolve_placeholders(v_val, &resolved_env);
        if let Some(s) = resolved_v.as_str() {
            resolved_env.insert(k.clone(), s.to_string());
        }
    }
    
    let cmd_list = match &server_cfg.command {
        crate::config::CommandValue::Single(s) => {
            shlex::split(s).ok_or_else(|| "Failed to parse command string".to_string())?
        }
        crate::config::CommandValue::Multiple(v) => v.clone(),
    };
    
    let resolved_cmd_list: Vec<String> = cmd_list.into_iter()
        .map(|c| {
            let c_val = serde_json::Value::String(c);
            let res = resolve_placeholders(c_val, &resolved_env);
            res.as_str().unwrap_or("").to_string()
        })
        .collect();
        
    if resolved_cmd_list.is_empty() {
        return Err(format!("Server '{}' has an empty command list.", server_key));
    }
    
    let exe = resolve_node_cmd(&resolved_cmd_list[0]);
    let mut child = Command::new(&exe)
        .args(&resolved_cmd_list[1..])
        .envs(&resolved_env)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn MCP server '{}' ({}): {}", server_key, exe, e))?;
        
    let mut child_stdin = child.stdin.take().unwrap();
    let mut child_stdout = BufReader::new(child.stdout.take().unwrap());
    
    let mut child_stderr = BufReader::new(child.stderr.take().unwrap());
    tokio::spawn(async move {
        let mut line = String::new();
        while let Ok(n) = child_stderr.read_line(&mut line).await {
            if n == 0 { break; }
            log::warn!("[MCP Server stderr] {}", line.trim());
            line.clear();
        }
    });
    
    // 1. send initialize
    let init_req = serde_json::json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "cpipe-rust",
                "version": "0.1.0"
            }
        }
    });
    let mut init_req_str = serde_json::to_string(&init_req).unwrap();
    init_req_str.push('\n');
    child_stdin.write_all(init_req_str.as_bytes()).await.map_err(|e| e.to_string())?;
    child_stdin.flush().await.map_err(|e| e.to_string())?;
    
    let mut response_line = String::new();
    child_stdout.read_line(&mut response_line).await.map_err(|e| e.to_string())?;
    
    // 2. send initialized
    let initialized_notification = serde_json::json!({
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    });
    let mut init_notif_str = serde_json::to_string(&initialized_notification).unwrap();
    init_notif_str.push('\n');
    child_stdin.write_all(init_notif_str.as_bytes()).await.map_err(|e| e.to_string())?;
    child_stdin.flush().await.map_err(|e| e.to_string())?;
    
    // 3. send call_tool
    let mut static_args = serde_json::Map::new();
    if let serde_json::Value::Object(map) = &node.args {
        for (k, v) in map {
            let resolved_val = resolve_placeholders(v.clone(), &resolved_env);
            static_args.insert(k.clone(), resolved_val);
        }
    }
    
    let mut arguments = static_args;
    arguments.insert(input_key.to_string(), serde_json::Value::String(stdin_data.to_string()));
    
    let tool_req = serde_json::json!({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    });
    
    let mut tool_req_str = serde_json::to_string(&tool_req).unwrap();
    tool_req_str.push('\n');
    child_stdin.write_all(tool_req_str.as_bytes()).await.map_err(|e| e.to_string())?;
    child_stdin.flush().await.map_err(|e| e.to_string())?;
    
    response_line.clear();
    child_stdout.read_line(&mut response_line).await.map_err(|e| e.to_string())?;
    
    let _ = child.kill().await;
    
    let res_json: serde_json::Value = serde_json::from_str(&response_line)
        .map_err(|e| format!("Malformed json-rpc from MCP server: {}", e))?;
        
    if let Some(err) = res_json.get("error") {
        return Err(format!("MCP tool error: {}", err));
    }
    
    let result_content = res_json.get("result").and_then(|r| r.get("content"))
        .ok_or_else(|| "No result content found in MCP response".to_string())?;
        
    let mut parts = Vec::new();
    if let serde_json::Value::Array(arr) = result_content {
        for item in arr {
            if let Some(text) = item.get("text").and_then(|t| t.as_str()) {
                parts.push(text.to_string());
            }
        }
    }
    
    if !parts.is_empty() {
        Ok(parts.join("\n"))
    } else {
        Ok(result_content.to_string())
    }
}

pub async fn run_pipe(
    pipe_config: &crate::config::Pipe,
    input_data: &str,
    tool_name: Option<&str>,
    agent_label: Option<&str>,
    server_registry: &HashMap<String, ServerConfig>,
    vars: Option<&HashMap<String, String>>,
    manifest_path: Option<&str>,
) -> (String, Vec<HashMap<String, serde_json::Value>>) {
    if input_data.contains(SIFT_SIGNATURE) {
        return (input_data.to_string(), Vec::new());
    }
    
    let mut current_input = input_data.to_string();
    let mut trace = Vec::new();
    
    let mut process_env = get_env_with_venv_path();

    let empty_vars = HashMap::new();
    let invocation_vars = vars.unwrap_or(&empty_vars);
    let run_vars = match _build_vars(pipe_config, invocation_vars) {
        Ok(v) => v,
        Err(e) => return (format!("--- [Context-Pipe: Variable Error] ---\n{}", e), vec![]),
    };
    for (k, v) in &run_vars {
        process_env.insert(k.clone(), v.clone());
    }

    if !process_env.contains_key("SIFT_AUDIT_HEADER") {
        process_env.insert("SIFT_AUDIT_HEADER".to_string(), "compact".to_string());
    }
    
    let started_at_str = chrono::Utc::now().to_rfc3339();
    let m_path_str = manifest_path.unwrap_or("").to_string();
    let write_manifest_if_needed = |res: &str, tr: &[HashMap<String, serde_json::Value>]| {
        let final_path = m_path_str.clone();
        if final_path.is_empty() {
            // "manifest": "auto" logic handled by caller or orchestrator if supported
            // Actually, we'll just check if manifest_path is explicitly set to "auto"
        }
        if !final_path.is_empty() {
            let status = if res.starts_with("--- [Context-Pipe:") || res.starts_with("Error") { "fail" } else { "pass" };
            _write_manifest(&final_path, pipe_config, &run_vars, tr, res, status, &started_at_str);
        }
    };
    
    if let Some(tn) = tool_name {
        process_env.insert("SIFT_TOOL_NAME".to_string(), tn.to_string());
    }
    if let Some(al) = agent_label {
        process_env.insert("SIFT_AGENT_LABEL".to_string(), al.to_string());
    }
    
    let raw_timeout = std::env::var("PIPE_NODE_TIMEOUT_MS").unwrap_or_else(|_| "30000".to_string());
    let node_timeout_ms = raw_timeout.parse::<u64>().unwrap_or(30000);
    
    // ── Phase 11-C: DAG Traversal Engine ──────────────────────────────────────
    // Build a flat ordered node list: linear nodes first, then branch_sequences.
    // Each node gets a stable string ID for O(1) lookup and loop detection.
    // ID format: "__node_{i}__" for linear nodes, "__branch_{name}_{i}__" for
    // branch-sequence nodes that have no explicit `id` field set.
    
    // (node_id, node_ref, natural_next_id)
    let mut ordered_nodes: Vec<(String, crate::config::Node, Option<String>)> = Vec::new();
    
    for (i, node) in pipe_config.nodes.iter().enumerate() {
        let auto_id = format!("__node_{}__", i);
        let node_id = node.id.clone().unwrap_or(auto_id);
        let natural_next = if i + 1 < pipe_config.nodes.len() {
            let next_node = &pipe_config.nodes[i + 1];
            let next_auto = format!("__node_{}__", i + 1);
            Some(next_node.id.clone().unwrap_or(next_auto))
        } else {
            None
        };
        ordered_nodes.push((node_id, node.clone(), natural_next));
    }
    
    // Add branch_sequences nodes into the lookup map (they are not in the main flow
    // unless a validator's `branches` references them by sequence name).
    let mut branch_seq_map: HashMap<String, Vec<(String, crate::config::Node, Option<String>)>> = HashMap::new();
    if let Some(sequences) = &pipe_config.branch_sequences {
        for (seq_name, seq_nodes) in sequences {
            let mut seq_ordered = Vec::new();
            for (i, node) in seq_nodes.iter().enumerate() {
                let auto_id = format!("__branch_{}_{}__", seq_name, i);
                let node_id = node.id.clone().unwrap_or(auto_id);
                let natural_next = if i + 1 < seq_nodes.len() {
                    let next_node = &seq_nodes[i + 1];
                    let next_auto = format!("__branch_{}_{}__", seq_name, i + 1);
                    Some(next_node.id.clone().unwrap_or(next_auto))
                } else {
                    None
                };
                seq_ordered.push((node_id, node.clone(), natural_next));
            }
            branch_seq_map.insert(seq_name.clone(), seq_ordered);
        }
    }
    
    // Flatten into a single lookup map: id → (node, natural_next_id)
    let mut node_map: HashMap<String, (crate::config::Node, Option<String>)> = HashMap::new();
    for (id, node, next) in &ordered_nodes {
        node_map.insert(id.clone(), (node.clone(), next.clone()));
    }
    for seq_nodes in branch_seq_map.values() {
        for (id, node, next) in seq_nodes {
            node_map.insert(id.clone(), (node.clone(), next.clone()));
        }
    }
    
    // Determine the start node ID.
    let start_id: Option<String> = ordered_nodes.first().map(|(id, _, _)| id.clone());
    let mut current_node_id: Option<String> = start_id;
    let mut step_count: usize = 0;
    const MAX_STEPS: usize = 100;
    
    while let Some(node_id_str) = current_node_id.clone() {
        if step_count >= MAX_STEPS {
            let msg = format!("--- [Context-Pipe: Loop Guard] ---\nPipe '{}' exceeded {} steps. Possible infinite loop.", pipe_config.name, MAX_STEPS);
            return (msg, trace);
        }
        step_count += 1;
        
        let (node, natural_next) = match node_map.get(&node_id_str) {
            Some(pair) => pair.clone(),
            None => {
                // Unknown node ID — possibly a branch target referencing a sequence by name.
                // Try to enter the sequence at its first node.
                if let Some(seq) = branch_seq_map.get(&node_id_str) {
                    if let Some((first_id, _, _)) = seq.first() {
                        current_node_id = Some(first_id.clone());
                        continue;
                    }
                }
                eprintln!("[Context-Pipe] Unknown node id '{}' in pipe '{}'. Stopping.", node_id_str, pipe_config.name);
                break;
            }
        };
        
        // ── Condition check ───────────────────────────────────────────────────
        if let Some(cond_str) = &node.condition {
            if !evaluate_condition(cond_str, &current_input) {
                current_node_id = natural_next;
                continue;
            }
        }
        
        if check_echo(&current_input, &pipe_config.name, &node_id_str) {
            current_node_id = natural_next;
            continue;
        }
        
        let is_optional = node.optional;
        let node_type = &node.node_type;
        let node_name = if node_type == "mcp" {
            format!("mcp:{}/{}", node.server.as_deref().unwrap_or(""), node.tool.as_deref().unwrap_or(""))
        } else if node_type == "script" {
            let script_name = &node.cmd;
            let script_dir = std::env::var("PIPE_SCRIPT_DIR").unwrap_or_else(|_| ".gemini/scripts".to_string());
            let py_script = std::path::Path::new(&script_dir).join(format!("{}.py", script_name));
            let md_mandate = std::path::Path::new(&script_dir).join(format!("{}.md", script_name));
            if py_script.exists() || md_mandate.exists() {
                format!("script:{}", script_name)
            } else {
                node.cmd.clone()
            }
        } else {
            node.cmd.clone()
        };
        
        emit_pipe_log(pipe_config, "entry", &node_name, tool_name, 0, 0, 0.0, false);
        let node_start_time = std::time::Instant::now();
        
        // ── MCP node ──────────────────────────────────────────────────────────
        if node.node_type == "mcp" {
            let start_size = current_input.len();
            let mut tee_path = None;
            if let Some(tee_config) = &node.tee {
                let mcp_cmd = format!("mcp:{}/{}", node.server.as_deref().unwrap_or(""), node.tool.as_deref().unwrap_or(""));
                tee_path = write_tee(tee_config, &current_input, &mcp_cmd, tool_name);
            }
            
            let mcp_res = tokio::time::timeout(
                tokio::time::Duration::from_millis(node_timeout_ms),
                run_mcp_node(&node, &current_input, server_registry, &process_env)
            ).await;
            
            let stdout = match mcp_res {
                Ok(Ok(s)) => s,
                Ok(Err(e)) => {
                    let mut entry = HashMap::new();
                    entry.insert("node".to_string(), serde_json::json!(format!("mcp:{}/{}", node.server.as_deref().unwrap_or(""), node.tool.as_deref().unwrap_or(""))));
                    entry.insert("error".to_string(), serde_json::json!(e));
                    trace.push(entry);
                    
                    let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
                    emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, 0, latency_ms, true);
                    
                    if is_optional { current_node_id = natural_next; continue; }
                    return (format!("--- [Context-Pipe: MCP Error] ---\n{}", e), trace);
                }
                Err(_) => {
                    let mut entry = HashMap::new();
                    entry.insert("node".to_string(), serde_json::json!(format!("mcp:{}/{}", node.server.as_deref().unwrap_or(""), node.tool.as_deref().unwrap_or(""))));
                    entry.insert("error".to_string(), serde_json::json!("Timeout"));
                    trace.push(entry);
                    
                    let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
                    emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, 0, latency_ms, true);
                    
                    if is_optional { current_node_id = natural_next; continue; }
                    return (format!("--- [Context-Pipe: Timeout] ---\nMCP node {}/{} exceeded {}s.", node.server.as_deref().unwrap_or(""), node.tool.as_deref().unwrap_or(""), node_timeout_ms / 1000), trace);
                }
            };
            
            let end_size = stdout.len();
            let mut entry = HashMap::new();
            entry.insert("node".to_string(), serde_json::json!(format!("mcp:{}/{}", node.server.as_deref().unwrap_or(""), node.tool.as_deref().unwrap_or(""))));
            entry.insert("input_size".to_string(), serde_json::json!(start_size));
            entry.insert("output_size".to_string(), serde_json::json!(end_size));
            entry.insert("delta".to_string(), serde_json::json!((end_size as isize - start_size as isize)));
            if let Some(tp) = tee_path {
                entry.insert("tee_path".to_string(), serde_json::json!(tp));
            }
            trace.push(entry);
            
            let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
            emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, end_size, latency_ms, false);
            
            current_input = stdout;
            current_node_id = node.next.clone().or(natural_next);
            continue;
        }
        
        let resolved_cmd;
        let mut resolved_args = Vec::new();
        
        if node.node_type == "script" {
            let script_name = &node.cmd;
            let script_dir = std::env::var("PIPE_SCRIPT_DIR").unwrap_or_else(|_| ".gemini/scripts".to_string());
            let py_script = std::path::Path::new(&script_dir).join(format!("{}.py", script_name));
            let md_mandate = std::path::Path::new(&script_dir).join(format!("{}.md", script_name));
            
            if py_script.exists() {
                resolved_cmd = find_python_interpreter();
                resolved_args.push(py_script.to_string_lossy().to_string());
                if let serde_json::Value::Array(arr) = &node.args {
                    for val in arr {
                        if let Some(s) = val.as_str() {
                            resolved_args.push(s.to_string());
                        }
                    }
                }
            } else if md_mandate.exists() {
                if let Ok(mandate_text) = std::fs::read_to_string(&md_mandate) {
                    let stdout = format!("--- [Context-Pipe: Mandate ({})] ---\n{}\n\n[Content]\n{}", script_name, mandate_text, current_input);
                    let start_size = current_input.len();
                    let end_size = stdout.len();
                    
                    let mut entry = HashMap::new();
                    entry.insert("node".to_string(), serde_json::json!(format!("script:{} (mandate)", script_name)));
                    entry.insert("input_size".to_string(), serde_json::json!(start_size));
                    entry.insert("output_size".to_string(), serde_json::json!(end_size));
                    entry.insert("delta".to_string(), serde_json::json!((end_size as isize - start_size as isize)));
                    trace.push(entry);
                    
                    let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
                    emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, end_size, latency_ms, false);
                    
                    current_input = stdout;
                    current_node_id = node.next.clone().or(natural_next);
                    continue;
                } else {
                    resolved_cmd = resolve_node_cmd(&node.cmd);
                    if let serde_json::Value::Array(arr) = &node.args {
                        for val in arr {
                            if let Some(s) = val.as_str() {
                                resolved_args.push(s.to_string());
                            }
                        }
                    }
                }
            } else {
                resolved_cmd = resolve_node_cmd(&node.cmd);
                if let serde_json::Value::Array(arr) = &node.args {
                    for val in arr {
                        if let Some(s) = val.as_str() {
                            resolved_args.push(s.to_string());
                        }
                    }
                }
            }
        } else {
            resolved_cmd = resolve_node_cmd(&node.cmd);
            if let serde_json::Value::Array(arr) = &node.args {
                for val in arr {
                    if let Some(s) = val.as_str() {
                        resolved_args.push(s.to_string());
                    }
                }
            }
        }
        
        let mut raw_cmd_args = vec![resolved_cmd.clone()];
        for arg in &resolved_args {
            raw_cmd_args.push(arg.clone());
        }
        
        let resolved_cmd_args: Vec<String> = raw_cmd_args.into_iter()
            .map(|a| {
                let a_val = serde_json::Value::String(a);
                let res = resolve_placeholders(c_val_to_string_compat(a_val), &process_env);
                res.as_str().unwrap_or("").to_string()
            })
            .collect();
            
        let cmd_exe = &resolved_cmd_args[0];
        let cmd_args = &resolved_cmd_args[1..];
        
        let start_size = current_input.len();
        let mut tee_path = None;
        if let Some(tee_config) = &node.tee {
            tee_path = write_tee(tee_config, &current_input, &node.cmd, tool_name);
        }
        
        let child = Command::new(cmd_exe)
            .args(cmd_args)
            .envs(&process_env)
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn();
            
        let mut child = match child {
            Ok(c) => c,
            Err(e) => {
                let err_reason = if e.kind() == std::io::ErrorKind::NotFound {
                    "FileNotFound"
                } else {
                    "SpawnError"
                };
                let mut entry = HashMap::new();
                entry.insert("node".to_string(), serde_json::json!(node.cmd));
                entry.insert("error".to_string(), serde_json::json!(err_reason));
                trace.push(entry);
                
                let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
                emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, 0, latency_ms, true);
                
                if is_optional { current_node_id = natural_next; continue; }
                
                let help_msg = node.help_msg.as_deref().unwrap_or_else(|| "Dependency not found in PATH.");
                let error_text = format!("--- [Context-Pipe: Dependency Error] ---\n{}", help_msg);
                {
                write_manifest_if_needed(&error_text, &trace);
                return (error_text, trace);
            }
            }
        };
        
        let mut child_stdin = child.stdin.take().unwrap();
        let input_bytes = current_input.as_bytes().to_vec();
        
        let stdin_write = async move {
            let _ = child_stdin.write_all(&input_bytes).await;
            let _ = child_stdin.flush().await;
        };
        
        let stdout_stream = child.stdout.take();
        let stderr_stream = child.stderr.take();
        
        let stdout_read = async move {
            let mut out = Vec::new();
            if let Some(mut stdout) = stdout_stream {
                let _ = tokio::io::copy(&mut stdout, &mut out).await;
            }
            out
        };
        
        let stderr_read = async move {
            let mut err = Vec::new();
            if let Some(mut stderr) = stderr_stream {
                let _ = tokio::io::copy(&mut stderr, &mut err).await;
            }
            err
        };
        
        let wait_task = async {
            let _ = tokio::join!(stdin_write);
            child.wait().await
        };
        
        let run_result = tokio::select! {
            res = async { tokio::join!(stdout_read, stderr_read, wait_task) } => {
                let (out, err, status): (Vec<u8>, Vec<u8>, Result<std::process::ExitStatus, std::io::Error>) = res;
                match status {
                    Ok(st) => {
                        let out_str = String::from_utf8_lossy(&out).into_owned();
                        let err_str = String::from_utf8_lossy(&err).into_owned();
                        Ok((out_str, err_str, st.code().unwrap_or(0)))
                    }
                    Err(e) => Err(format!("Wait Error: {}", e)),
                }
            }
            _ = tokio::time::sleep(tokio::time::Duration::from_millis(node_timeout_ms)) => {
                let _ = child.kill().await;
                Err("Timeout".to_string())
            }
        };
        
        match run_result {
            Ok((stdout, stderr, code)) => {
                // ── Validator branching ───────────────────────────────────────
                if node.node_type == "validator" {
                    if let Some(branches) = &node.branches {
                        let code_key = code.to_string();
                        let branch_target = branches.get(&code_key)
                            .or_else(|| branches.get("default"))
                            .cloned();
                        match branch_target {
                            Some(target) => {
                                let mut entry = HashMap::new();
                                entry.insert("node".to_string(), serde_json::json!(node.cmd));
                                entry.insert("validator_code".to_string(), serde_json::json!(code));
                                entry.insert("branch".to_string(), serde_json::json!(target));
                                trace.push(entry);
                                let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
                                emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, stdout.len(), latency_ms, false);
                                // Pass validator stdout as next input
                                if !stdout.is_empty() {
                                    current_input = stdout;
                                }
                                // target may be a sequence name or a node id
                                current_node_id = Some(target);
                                continue;
                            }
                            None => {
                                // No branch matched and no default — fail fast
                                let mut entry = HashMap::new();
                                entry.insert("node".to_string(), serde_json::json!(node.cmd));
                                entry.insert("error".to_string(), serde_json::json!(format!("Validator exited {} with no matching branch", code)));
                                trace.push(entry);
                                let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
                                emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, 0, latency_ms, true);
                                if is_optional { current_node_id = natural_next; continue; }
                                { let e = format!("Error in node {}: {}", node.cmd, stderr); write_manifest_if_needed(&e, &trace); return (e, trace); }
                            }
                        }
                    }
                    // Validator with no branches: treat as binary (pass-through on 0)
                }
                
                if code != 0 {
                    let mut entry = HashMap::new();
                    entry.insert("node".to_string(), serde_json::json!(node.cmd));
                    entry.insert("error".to_string(), serde_json::json!(stderr.trim()));
                    trace.push(entry);
                    
                    let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
                    emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, 0, latency_ms, true);
                    
                    if is_optional { current_node_id = natural_next; continue; }
                    return (format!("Error in node {}: {}", node.cmd, stderr), trace);
                }
                
                let end_size = stdout.len();
                let mut entry = HashMap::new();
                entry.insert("node".to_string(), serde_json::json!(node.cmd));
                entry.insert("input_size".to_string(), serde_json::json!(start_size));
                entry.insert("output_size".to_string(), serde_json::json!(end_size));
                entry.insert("delta".to_string(), serde_json::json!((end_size as isize - start_size as isize)));
                if let Some(tp) = tee_path {
                    entry.insert("tee_path".to_string(), serde_json::json!(tp));
                }
                trace.push(entry);
                
                let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
                emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, end_size, latency_ms, false);
                
                current_input = stdout;
                current_node_id = node.next.clone().or(natural_next);
            }
            Err(e) => {
                let mut entry = HashMap::new();
                entry.insert("node".to_string(), serde_json::json!(node.cmd));
                entry.insert("error".to_string(), serde_json::json!(e));
                trace.push(entry);
                
                let latency_ms = node_start_time.elapsed().as_secs_f64() * 1000.0;
                emit_pipe_log(pipe_config, "exit", &node_name, tool_name, start_size, 0, latency_ms, true);
                
                if is_optional { current_node_id = natural_next; continue; }
                
                let error_text = if e == "Timeout" {
                    format!("--- [Context-Pipe: Timeout] ---\nNode {} exceeded {}s.", node.cmd, node_timeout_ms / 1000)
                } else {
                    format!("--- [Context-Pipe: Error] ---\n{}", e)
                };
                {
                write_manifest_if_needed(&error_text, &trace);
                return (error_text, trace);
            }
            }
        }
    }
    
    write_manifest_if_needed(&current_input, &trace);
    (current_input, trace)
}

fn c_val_to_string_compat(val: serde_json::Value) -> serde_json::Value {
    val
}

pub fn detect_client_id() -> String {
    let env_map = [
        ("ANTIGRAVITY_AGENT", "Google Antigravity"),
        ("OPENCODE", "OpenCode"),
        ("OPENCODE_PID", "OpenCode"),
        ("PI_CODING_AGENT_DIR", "pi.dev"),
        ("CURSOR_TRACE_ID", "Cursor"),
        ("VSCODE_PID", "VSCode"),
        ("WINDSURF_TOOL_ARGS", "Windsurf"),
        ("__KIRO_MCP", "Kiro"),
        ("CONTINUE_SERVER_PORT", "Continue"),
        ("JETBRAINS_IDE_URL", "JetBrains"),
        ("CLINE_TASK_ID", "Cline"),
        ("CLAUDE_TOOL_NAME", "Claude Desktop"),
        ("GEMINI_SESSION_ID", "Gemini CLI"),
    ];

    for (var, label) in env_map {
        if std::env::var(var).is_ok() {
            return label.to_string();
        }
    }

    "Generic CLI".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{Config, Mapping};

    #[test]
    fn test_resolve_pipe_from_context() {
        let config = Config {
            mappings: vec![
                Mapping {
                    trigger: "tool:semantic-sift".to_string(),
                    pipe: "sift-pipe".to_string(),
                },
                Mapping {
                    trigger: "size:>1000".to_string(),
                    pipe: "large-pipe".to_string(),
                },
                Mapping {
                    trigger: "default".to_string(),
                    pipe: "default-pipe".to_string(),
                },
            ],
            ..Default::default()
        };

        // tool match
        assert_eq!(
            resolve_pipe_from_context(&config, "semantic-sift", 100),
            Some("sift-pipe".to_string())
        );

        // size match (exceeds 1000)
        assert_eq!(
            resolve_pipe_from_context(&config, "some-other-tool", 2000),
            Some("large-pipe".to_string())
        );

        // default match
        assert_eq!(
            resolve_pipe_from_context(&config, "small-tool", 100),
            Some("default-pipe".to_string())
        );
    }

    #[test]
    fn test_detect_client_id() {
        let keys = vec![
            "ANTIGRAVITY_AGENT", "OPENCODE", "OPENCODE_PID", "CURSOR_TRACE_ID",
            "VSCODE_PID", "WINDSURF_TOOL_ARGS", "__KIRO_MCP", "CONTINUE_SERVER_PORT",
            "JETBRAINS_IDE_URL", "CLINE_TASK_ID", "CLAUDE_TOOL_NAME", "GEMINI_SESSION_ID"
        ];
        let mut saved = HashMap::new();
        for key in &keys {
            if let Ok(val) = std::env::var(key) {
                saved.insert(*key, val);
                std::env::remove_var(key);
            }
        }

        std::env::set_var("GEMINI_SESSION_ID", "test-session-123");
        assert_eq!(detect_client_id(), "Gemini CLI");
        std::env::remove_var("GEMINI_SESSION_ID");

        std::env::set_var("CURSOR_TRACE_ID", "cursor-123");
        assert_eq!(detect_client_id(), "Cursor");
        std::env::remove_var("CURSOR_TRACE_ID");

        assert_eq!(detect_client_id(), "Generic CLI");

        for (key, val) in saved {
            std::env::set_var(key, val);
        }
    }
}
