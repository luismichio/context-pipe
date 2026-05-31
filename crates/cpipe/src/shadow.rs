// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Luis Kobayashi. All rights reserved.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use crate::config::load_config_file;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DiscoveredTool {
    pub name: String,
    pub source: String,
    pub description: String,
    pub nodes: Vec<String>,
}

lazy_static::lazy_static! {
    static ref KNOWN_PATH_TOOLS: HashMap<&'static str, &'static str> = {
        let mut m = HashMap::new();
        m.insert("jq", "Command-line JSON processor");
        m.insert("yq", "Command-line YAML/JSON/XML processor");
        m.insert("markitdown", "Converts Office/PDF/HTML documents to Markdown");
        m.insert("pandoc", "Universal document format converter");
        m.insert("rg", "Fast line-oriented search (ripgrep)");
        m.insert("fd", "Fast file finder (fd-find)");
        m.insert("bat", "Syntax-highlighted cat replacement");
        m
    };
}

pub fn which(cmd: &str, path_env: Option<&str>) -> Option<PathBuf> {
    let path_val = path_env
        .map(|s| s.to_string())
        .or_else(|| std::env::var("PATH").ok())?;
    
    let separator = if cfg!(windows) { ";" } else { ":" };
    let paths = path_val.split(separator);
    
    for p in paths {
        let dir = PathBuf::from(p);
        let exe_candidates = if cfg!(windows) {
            vec![
                dir.join(cmd),
                dir.join(format!("{}.exe", cmd)),
                dir.join(format!("{}.bat", cmd)),
                dir.join(format!("{}.cmd", cmd))
            ]
        } else {
            vec![dir.join(cmd)]
        };
        
        for candidate in exe_candidates {
            if candidate.is_file() {
                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    if let Ok(metadata) = candidate.metadata() {
                        if metadata.permissions().mode() & 0o111 != 0 {
                            return Some(candidate);
                        }
                    }
                }
                #[cfg(not(unix))]
                {
                    return Some(candidate);
                }
            }
        }
    }
    None
}

pub fn list_shadow_tools(config_path: Option<&Path>) -> Vec<DiscoveredTool> {
    let mut tools = Vec::new();
    
    // 1. Configured pipes and servers
    if let Some(path) = config_path {
        if path.exists() {
            if let Ok(config) = load_config_file(path) {
                // Configured pipes
                for pipe in config.pipes {
                    let mut nodes_desc = Vec::new();
                    for n in &pipe.nodes {
                        if n.node_type == "mcp" {
                            let server = n.server.as_deref().unwrap_or("unknown");
                            let tool = n.tool.as_deref().unwrap_or("unknown");
                            nodes_desc.push(format!("mcp:{}/{}", server, tool));
                        } else if !n.cmd.is_empty() {
                            nodes_desc.push(n.cmd.clone());
                        } else {
                            nodes_desc.push(format!("{:?}", n));
                        }
                    }
                    tools.push(DiscoveredTool {
                        name: pipe.name,
                        source: "pipes.json".to_string(),
                        description: pipe.description,
                        nodes: nodes_desc,
                    });
                }

                // Configured servers
                let mut server_names: Vec<&String> = config.servers.keys().collect();
                server_names.sort();
                for name in server_names {
                    if name.starts_with('_') {
                        continue;
                    }
                    let srv_cfg = &config.servers[name];
                    let desc = srv_cfg.description.as_deref().unwrap_or("Registered MCP server. Can be run in custom pipes.");
                    tools.push(DiscoveredTool {
                        name: name.clone(),
                        source: "pipes.json".to_string(),
                        description: desc.to_string(),
                        nodes: Vec::new(),
                    });
                }
            }
        }
    }
    
    // 2. Curated CLI tools on PATH
    let path_val = std::env::var("PATH").ok();
    let path_ref = path_val.as_deref();
    
    // Sort keys to maintain deterministic output order
    let mut keys: Vec<&&str> = KNOWN_PATH_TOOLS.keys().collect();
    keys.sort();
    
    for &cmd in keys {
        if which(cmd, path_ref).is_some() {
            if let Some(&desc) = KNOWN_PATH_TOOLS.get(cmd) {
                tools.push(DiscoveredTool {
                    name: cmd.to_string(),
                    source: "PATH".to_string(),
                    description: desc.to_string(),
                    nodes: vec![cmd.to_string()],
                });
            }
        }
    }
    
    tools
}
