// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Luis Kobayashi. All rights reserved.

use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::fs;

fn deserialize_servers<'de, D>(deserializer: D) -> Result<HashMap<String, ServerConfig>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let map = HashMap::<String, serde_json::Value>::deserialize(deserializer)?;
    let mut servers = HashMap::new();
    for (k, v) in map {
        if let Ok(server_cfg) = serde_json::from_value::<ServerConfig>(v) {
            servers.insert(k, server_cfg);
        }
    }
    Ok(servers)
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct Config {
    #[serde(default = "default_version")]
    pub version: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub pipes: Vec<Pipe>,
    #[serde(deserialize_with = "deserialize_servers", default)]
    pub servers: HashMap<String, ServerConfig>,
    #[serde(default)]
    pub mappings: Vec<Mapping>,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct Pipe {
    pub name: String,
    #[serde(default)]
    pub description: String,
    pub nodes: Vec<Node>,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct Node {
    pub cmd: String,
    #[serde(default = "default_args")]
    pub args: serde_json::Value,
    #[serde(default)]
    pub help_msg: Option<String>,
    #[serde(default)]
    pub optional: bool,
    #[serde(default)]
    pub tee: Option<TeeConfig>,
    #[serde(rename = "type", default = "default_node_type")]
    pub node_type: String, // "binary", "script", "mcp"
    // MCP fields:
    #[serde(default)]
    pub server: Option<String>,
    #[serde(default)]
    pub tool: Option<String>,
    #[serde(default)]
    pub input_key: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TeeConfig {
    pub sink: String, // e.g. "file"
    pub path: String, // e.g. "teefile_{iso_date}.txt"
    #[serde(default = "default_tee_mode")]
    pub mode: String, // "append" or "overwrite"
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(untagged)]
pub enum CommandValue {
    Single(String),
    Multiple(Vec<String>),
}

impl Default for CommandValue {
    fn default() -> Self {
        CommandValue::Multiple(Vec::new())
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct ServerConfig {
    pub command: CommandValue,
    #[serde(default)]
    pub env: HashMap<String, String>,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Default)]
pub struct Mapping {
    pub trigger: String,
    pub pipe: String,
}

fn default_version() -> String {
    "1.0".to_string()
}

fn default_args() -> serde_json::Value {
    serde_json::Value::Array(Vec::new())
}

fn default_node_type() -> String {
    "binary".to_string()
}

fn default_tee_mode() -> String {
    "append".to_string()
}

pub fn find_local_config(filename: &str) -> Option<PathBuf> {
    let mut curr = std::env::current_dir().ok()?;
    loop {
        let candidate = curr.join(filename);
        if candidate.exists() {
            return Some(candidate);
        }
        // Stop at .git boundary
        if curr.join(".git").exists() {
            break;
        }
        if !curr.pop() {
            break;
        }
    }
    // Fallback to CWD
    let candidate = std::env::current_dir().ok()?.join(filename);
    if candidate.exists() {
        return Some(candidate);
    }
    None
}

pub fn load_config_file(path: &Path) -> Result<Config, String> {
    let content = fs::read_to_string(path)
        .map_err(|e| format!("Failed to read file: {}", e))?;
    let extension = path.extension().and_then(|s| s.to_str()).unwrap_or("");
    if extension == "toml" {
        toml::from_str(&content).map_err(|e| format!("TOML parse error: {}", e))
    } else {
        serde_json::from_str(&content).map_err(|e| format!("JSON parse error: {}", e))
    }
}

pub fn load_pipes_config() -> Config {
    load_pipes_config_with_path(None)
}

pub fn load_pipes_config_with_path(custom_path: Option<&Path>) -> Config {
    // Look for local configs
    let local_config = if let Some(path) = custom_path {
        if path.is_absolute() {
            match load_config_file(path) {
                Ok(cfg) => Some(cfg),
                Err(e) => {
                    eprintln!("cpipe: error: Could not load local pipes config at {:?}: {}", path, e);
                    std::process::exit(1);
                }
            }
        } else {
            let mut resolved_path = None;
            if path.exists() {
                resolved_path = Some(path.to_path_buf());
            } else if let Ok(mut curr) = std::env::current_dir() {
                loop {
                    let candidate = curr.join(path);
                    if candidate.exists() {
                        resolved_path = Some(candidate);
                        break;
                    }
                    if curr.join(".git").exists() {
                        break;
                    }
                    if !curr.pop() {
                        break;
                    }
                }
            }
            
            // Fallback to executable parent directory
            if resolved_path.is_none() {
                if let Ok(exe_path) = std::env::current_exe() {
                    if let Some(exe_dir) = exe_path.parent() {
                        let candidate = exe_dir.join(path);
                        if candidate.exists() {
                            resolved_path = Some(candidate);
                        } else if let Some(parent) = exe_dir.parent() {
                            let candidate = parent.join(path);
                            if candidate.exists() {
                                resolved_path = Some(candidate);
                            }
                        }
                    }
                }
            }
            
            let final_path = resolved_path.unwrap_or_else(|| path.to_path_buf());
            match load_config_file(&final_path) {
                Ok(cfg) => Some(cfg),
                Err(e) => {
                    eprintln!("cpipe: error: Could not load local pipes config at {:?}: {}", final_path, e);
                    std::process::exit(1);
                }
            }
        }
    } else {
        let local_json = find_local_config("pipes.json");
        let local_toml = find_local_config("pipes.toml");
        if let Some(path) = local_toml {
            match load_config_file(&path) {
                Ok(cfg) => Some(cfg),
                Err(e) => {
                    log::warn!("Could not load local pipes.toml at {:?}: {}", path, e);
                    None
                }
            }
        } else if let Some(path) = local_json {
            match load_config_file(&path) {
                Ok(cfg) => Some(cfg),
                Err(e) => {
                    log::warn!("Could not load local pipes.json at {:?}: {}", path, e);
                    None
                }
            }
        } else {
            None
        }
    };

    // Look for global configs
    let global_config = if let Some(home) = dirs::home_dir() {
        let global_toml = home.join(".mcp-pipe.toml");
        let global_json = home.join(".mcp-pipe.json");
        
        if global_toml.exists() {
            match load_config_file(&global_toml) {
                Ok(cfg) => Some(cfg),
                Err(e) => {
                    log::warn!("Could not load global .mcp-pipe.toml: {}", e);
                    None
                }
            }
        } else if global_json.exists() {
            match load_config_file(&global_json) {
                Ok(cfg) => Some(cfg),
                Err(e) => {
                    log::warn!("Could not load global .mcp-pipe.json: {}", e);
                    None
                }
            }
        } else {
            None
        }
    } else {
        None
    };

    merge_configs(local_config, global_config)
}

pub fn merge_configs(local: Option<Config>, global: Option<Config>) -> Config {
    if local.is_none() && global.is_none() {
        return Config::default();
    }
    let local = local.unwrap_or_default();
    let global = global.unwrap_or_default();
    let version = if !local.version.is_empty() && local.version != "1.0" {
        local.version.clone()
    } else if !global.version.is_empty() {
        global.version.clone()
    } else {
        "1.0".to_string()
    };

    let mut merged_pipes = local.pipes.clone();
    let local_names: HashSet<String> = local.pipes.iter().map(|p| p.name.clone()).collect();
    for pipe in global.pipes {
        if !local_names.contains(&pipe.name) {
            merged_pipes.push(pipe);
        }
    }

    let mut merged_servers = global.servers.clone();
    for (k, v) in local.servers {
        merged_servers.insert(k, v);
    }

    let mut merged_mappings = local.mappings.clone();
    for mapping in global.mappings {
        if !merged_mappings.contains(&mapping) {
            merged_mappings.push(mapping);
        }
    }

    Config {
        version,
        description: local.description.clone(),
        pipes: merged_pipes,
        servers: merged_servers,
        mappings: merged_mappings,
    }
}

pub fn resolve_placeholders(value: serde_json::Value, env: &HashMap<String, String>) -> serde_json::Value {
    match value {
        serde_json::Value::String(s) => {
            let re = regex::Regex::new(r"\$\{([^}]+)\}").unwrap();
            let resolved_str = re.replace_all(&s, |caps: &regex::Captures| {
                let var_name = &caps[1];
                if let Some(val) = env.get(var_name) {
                    val.clone()
                } else if let Ok(val) = std::env::var(var_name) {
                    val
                } else {
                    caps[0].to_string()
                }
            });
            serde_json::Value::String(resolved_str.into_owned())
        }
        serde_json::Value::Array(arr) => {
            serde_json::Value::Array(arr.into_iter().map(|v| resolve_placeholders(v, env)).collect())
        }
        serde_json::Value::Object(obj) => {
            serde_json::Value::Object(obj.into_iter().map(|(k, v)| (k, resolve_placeholders(v, env))).collect())
        }
        _ => value,
    }
}

pub fn get_config_path() -> String {
    std::env::var("PIPE_CONFIG_PATH").unwrap_or_else(|_| "pipes.json".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_resolve_placeholders() {
        let mut env = HashMap::new();
        env.insert("FOO".to_string(), "bar".to_string());
        std::env::set_var("BAZ", "qux");

        let val = json!({
            "key1": "hello ${FOO}",
            "key2": "value ${BAZ}",
            "key3": ["nested ${FOO}", "other"]
        });

        let resolved = resolve_placeholders(val, &env);
        assert_eq!(resolved["key1"], "hello bar");
        assert_eq!(resolved["key2"], "value qux");
        assert_eq!(resolved["key3"][0], "nested bar");
    }

    #[test]
    fn test_merge_configs() {
        let local = Some(Config {
            version: "1.0".to_string(),
            description: "Local description".to_string(),
            pipes: vec![Pipe {
                name: "pipe-1".to_string(),
                description: "Local pipe-1".to_string(),
                nodes: vec![],
            }],
            servers: HashMap::new(),
            mappings: vec![],
        });
        let global = Some(Config {
            version: "2.0".to_string(),
            description: "Global description".to_string(),
            pipes: vec![
                Pipe {
                    name: "pipe-1".to_string(),
                    description: "Global pipe-1".to_string(),
                    nodes: vec![],
                },
                Pipe {
                    name: "pipe-2".to_string(),
                    description: "Global pipe-2".to_string(),
                    nodes: vec![],
                },
            ],
            servers: HashMap::new(),
            mappings: vec![],
        });

        let merged = merge_configs(local, global);
        assert_eq!(merged.version, "2.0");
        assert_eq!(merged.pipes.len(), 2);
        assert_eq!(merged.pipes[0].name, "pipe-1");
        assert_eq!(merged.pipes[0].description, "Local pipe-1");
        assert_eq!(merged.pipes[1].name, "pipe-2");
    }
}
