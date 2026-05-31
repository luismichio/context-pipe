// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Luis Kobayashi. All rights reserved.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use chrono::Utc;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TelemetryEvent {
    #[serde(rename = "type")]
    pub event_type: String,
    #[serde(default)]
    pub session_id: String,
    #[serde(default)]
    pub start_time: String,
    #[serde(default)]
    pub tool_name: String,
    #[serde(default)]
    pub original_chars: usize,
    #[serde(default)]
    pub final_chars: usize,
    #[serde(default)]
    pub original_tokens: usize,
    #[serde(default)]
    pub final_tokens: usize,
    #[serde(default)]
    pub latency_ms: f64,
    #[serde(default)]
    pub cache_hit: bool,
    #[serde(default)]
    pub platform: String,
    #[serde(default)]
    pub agent: String,
    #[serde(default)]
    pub pipe_name: String,
    #[serde(default)]
    pub tier: String,
    #[serde(default)]
    pub reason: String,
    #[serde(default)]
    pub timestamp: String,
}

pub fn resolve_telemetry_path() -> PathBuf {
    if let Some(val) = std::env::var("CPP_TELEMETRY_FILE").ok().or_else(|| std::env::var("PIPE_TELEMETRY_FILE").ok()) {
        if !val.is_empty() {
            return PathBuf::from(val);
        }
    }
    
    let mut curr = std::env::current_dir().unwrap_or_default();
    loop {
        if curr.join(".pipe_identity").exists() || curr.join("pipes.json").exists() || curr.join("pipes.toml").exists() {
            return curr.join(".pipe_telemetry.jsonl");
        }
        if !curr.pop() {
            break;
        }
    }
    std::env::current_dir().unwrap_or_default().join(".pipe_telemetry.jsonl")
}

pub fn check_telemetry_disabled() -> bool {
    if std::env::var("CPP_TELEMETRY_DISABLED").map(|s| s.to_lowercase() == "true").unwrap_or(false)
        || std::env::var("PIPE_TELEMETRY_DISABLED").map(|s| s.to_lowercase() == "true").unwrap_or(false) {
        return true;
    }
    
    let mut curr = std::env::current_dir().unwrap_or_default();
    loop {
        let settings_path = curr.join(".gemini").join("settings.json");
        if settings_path.exists() {
            if let Ok(content) = std::fs::read_to_string(settings_path) {
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                    if let Some(opt_in) = val.get("SIFT_TELEMETRY_OPTED_IN") {
                        if opt_in.as_str().map(|s| s.to_lowercase() == "false").unwrap_or(false) {
                            return true;
                        }
                    }
                }
            }
        }
        if !curr.pop() {
            break;
        }
    }
    false
}

pub fn log_telemetry(
    session_id: &str,
    start_time: &str,
    tool_name: &str,
    original_size: usize,
    final_size: usize,
    latency_ms: f64,
    cache_hit: bool,
    platform: &str,
    agent_label: Option<&str>,
    pipe_name: &str,
    tier: &str,
) {
    if check_telemetry_disabled() {
        return;
    }

    let orig_tokens = original_size / 4;
    let final_tokens = final_size / 4;

    let event = TelemetryEvent {
        event_type: "tool_call".to_string(),
        session_id: session_id.to_string(),
        start_time: start_time.to_string(),
        tool_name: format!("{}:{}", pipe_name, tool_name),
        original_chars: original_size,
        final_chars: final_size,
        original_tokens: orig_tokens,
        final_tokens: final_tokens,
        latency_ms,
        cache_hit,
        platform: platform.to_string(),
        agent: agent_label.unwrap_or("Main").to_string(),
        pipe_name: pipe_name.to_string(),
        tier: tier.to_string(),
        reason: String::new(),
        timestamp: String::new(),
    };

    if let Ok(serialized) = serde_json::to_string(&event) {
        let path = resolve_telemetry_path();
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(file, "{}", serialized);
        }
    }
}

pub fn log_bypass_event(
    tool_name: &str,
    reason: &str,
    platform: &str,
    pipe_name: &str,
    agent_label: Option<&str>,
) {
    if check_telemetry_disabled() {
        return;
    }

    let event = TelemetryEvent {
        event_type: "bypass".to_string(),
        session_id: String::new(),
        start_time: String::new(),
        tool_name: tool_name.to_string(),
        original_chars: 0,
        final_chars: 0,
        original_tokens: 0,
        final_tokens: 0,
        latency_ms: 0.0,
        cache_hit: false,
        platform: platform.to_string(),
        agent: agent_label.unwrap_or("Main").to_string(),
        pipe_name: pipe_name.to_string(),
        tier: String::new(),
        reason: reason.to_string(),
        timestamp: Utc::now().to_rfc3339(),
    };

    if let Ok(serialized) = serde_json::to_string(&event) {
        let path = resolve_telemetry_path();
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(file, "{}", serialized);
        }
    }
}

pub fn log_unmapped_event(
    tool_name: &str,
    original_size: usize,
    platform: &str,
    agent_label: Option<&str>,
) {
    if check_telemetry_disabled() {
        return;
    }

    let event = TelemetryEvent {
        event_type: "unmapped".to_string(),
        session_id: String::new(),
        start_time: String::new(),
        tool_name: tool_name.to_string(),
        original_chars: original_size,
        final_chars: 0,
        original_tokens: original_size / 4,
        final_tokens: 0,
        latency_ms: 0.0,
        cache_hit: false,
        platform: platform.to_string(),
        agent: agent_label.unwrap_or("Main").to_string(),
        pipe_name: String::new(),
        tier: String::new(),
        reason: String::new(),
        timestamp: Utc::now().to_rfc3339(),
    };

    if let Ok(serialized) = serde_json::to_string(&event) {
        let path = resolve_telemetry_path();
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(file, "{}", serialized);
        }
    }
}

pub fn log_fallback_event(tool_name: &str, reason: &str) {
    if check_telemetry_disabled() {
        return;
    }

    let event = TelemetryEvent {
        event_type: "fallback".to_string(),
        session_id: String::new(),
        start_time: String::new(),
        tool_name: tool_name.to_string(),
        original_chars: 0,
        final_chars: 0,
        original_tokens: 0,
        final_tokens: 0,
        latency_ms: 0.0,
        cache_hit: false,
        platform: String::new(),
        agent: String::new(),
        pipe_name: String::new(),
        tier: String::new(),
        reason: reason.to_string(),
        timestamp: Utc::now().to_rfc3339(),
    };

    if let Ok(serialized) = serde_json::to_string(&event) {
        let path = resolve_telemetry_path();
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(file, "{}", serialized);
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct BalanceSheet {
    pub signal_added: usize,
    pub noise_removed: usize,
    pub net_change: isize,
    pub total_events: usize,
    pub avg_latency_ms: f64,
    pub fallback_events: usize,
    pub bypass_events: usize,
    pub unmapped_events: usize,
}

fn parse_time_string(time_str: &str) -> Option<chrono::DateTime<chrono::Utc>> {
    use chrono::TimeZone;
    if time_str.is_empty() {
        return None;
    }
    if let Ok(naive) = chrono::NaiveDateTime::parse_from_str(time_str, "%a %b %d %H:%M:%S %Y") {
        return Some(chrono::Utc.from_utc_datetime(&naive));
    }
    if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(time_str) {
        return Some(dt.with_timezone(&chrono::Utc));
    }
    if let Ok(dt) = chrono::DateTime::parse_from_rfc2822(time_str) {
        return Some(dt.with_timezone(&chrono::Utc));
    }
    if let Ok(val) = time_str.parse::<f64>() {
        let secs = val.trunc() as i64;
        let nsecs = (val.fract() * 1_000_000_000.0) as u32;
        if let Some(naive) = chrono::NaiveDateTime::from_timestamp_opt(secs, nsecs) {
            return Some(chrono::Utc.from_utc_datetime(&naive));
        }
    }
    None
}

pub fn get_balance_sheet(
    session_id: Option<&str>,
    last_hours: Option<f64>,
) -> BalanceSheet {
    let mut sheet = BalanceSheet::default();
    let path = resolve_telemetry_path();
    let now = chrono::Utc::now();

    if path.exists() {
        if let Ok(content) = std::fs::read_to_string(path) {
            let mut total_latency = 0.0;
            let mut tool_calls = 0;
            for line in content.lines() {
                if line.trim().is_empty() {
                    continue;
                }
                if let Ok(event) = serde_json::from_str::<TelemetryEvent>(line) {
                    // Apply filters
                    if let Some(sid) = session_id {
                        if event.session_id != sid {
                            continue;
                        }
                    }
                    if let Some(hours) = last_hours {
                        let ts_str = if !event.start_time.is_empty() {
                            &event.start_time
                        } else if !event.timestamp.is_empty() {
                            &event.timestamp
                        } else {
                            ""
                        };
                        if let Some(event_time) = parse_time_string(ts_str) {
                            let duration = now.signed_duration_since(event_time);
                            if duration.num_seconds() as f64 > hours * 3600.0 {
                                continue;
                            }
                        }
                    }

                    match event.event_type.as_str() {
                        "fallback" => sheet.fallback_events += 1,
                        "bypass" => sheet.bypass_events += 1,
                        "unmapped" => sheet.unmapped_events += 1,
                        "tool_call" => {
                            sheet.total_events += 1;
                            tool_calls += 1;
                            total_latency += event.latency_ms;
                            
                            let orig = event.original_chars;
                            let fin = event.final_chars;
                            if fin > orig {
                                sheet.signal_added += fin - orig;
                            } else {
                                sheet.noise_removed += orig - fin;
                            }
                        }
                        _ => {}
                    }
                }
            }
            if tool_calls > 0 {
                sheet.avg_latency_ms = total_latency / tool_calls as f64;
            }
        }
    }
    
    sheet.net_change = sheet.signal_added as isize - sheet.noise_removed as isize;
    sheet
}

pub fn get_recent_telemetry(limit: usize) -> Vec<TelemetryEvent> {
    let path = resolve_telemetry_path();
    if !path.exists() {
        return Vec::new();
    }
    if let Ok(content) = std::fs::read_to_string(path) {
        let mut events = Vec::new();
        for line in content.lines() {
            if line.trim().is_empty() {
                continue;
            }
            if let Ok(event) = serde_json::from_str::<TelemetryEvent>(line) {
                if event.event_type == "tool_call" {
                    events.push(event);
                }
            }
        }
        events.reverse();
        events.truncate(limit);
        return events;
    }
    Vec::new()
}

pub fn generate_audit_header(pipe_name: &str, trace: &[HashMap<String, serde_json::Value>], latency_ms: f64) -> String {
    if trace.is_empty() {
        return String::new();
    }
    
    let start_size = trace[0].get("input_size").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
    let end_size = trace[trace.len() - 1].get("output_size").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
    
    let reduction = if start_size > 0 {
        (1.0 - (end_size as f64 / start_size as f64)) * 100.0
    } else {
        0.0
    };
    
    let reduction_label = if reduction >= 0.0 {
        format!("{:.1}% Reduction", reduction)
    } else {
        format!("{:.1}% Augmentation", reduction.abs())
    };
    
    let warning_line = if reduction > 0.0 {
        "⚠️ WARNING: Content distilled. Line numbers DO NOT match raw source."
    } else {
        "✔ Guard: Trace-Verified (No Echo)"
    };
    
    let nodes_str = trace.iter()
        .filter_map(|t| t.get("node").and_then(|v| v.as_str()))
        .collect::<Vec<&str>>()
        .join(" -> ");

    format!(
        "--- [Context-Pipe: {}] ---\n\
         📊 Context: {} ({:.1}KB -> {:.1}KB)\n\
         {}\n\
         ⚡ Latency: {:.1}ms\n\
         Nodes: {}\n\
         -----------------------------\n",
        pipe_name,
        reduction_label,
        start_size as f64 / 1024.0,
        end_size as f64 / 1024.0,
        warning_line,
        latency_ms,
        nodes_str
    )
}

pub fn get_latest_telemetry() -> Option<TelemetryEvent> {
    let path = resolve_telemetry_path();
    if !path.exists() {
        return None;
    }
    let content = std::fs::read_to_string(path).ok()?;
    for line in content.lines().rev() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        if let Ok(event) = serde_json::from_str::<TelemetryEvent>(trimmed) {
            if event.event_type == "tool_call" {
                return Some(event);
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    struct TempEnv {
        key: &'static str,
        old_val: Option<String>,
    }

    impl TempEnv {
        fn set(key: &'static str, val: &str) -> Self {
            let old_val = std::env::var(key).ok();
            std::env::set_var(key, val);
            Self { key, old_val }
        }
    }

    impl Drop for TempEnv {
        fn drop(&mut self) {
            if let Some(ref val) = self.old_val {
                std::env::set_var(self.key, val);
            } else {
                std::env::remove_var(self.key);
            }
        }
    }

    #[test]
    fn test_parse_time_string() {
        assert!(parse_time_string("").is_none());
        
        // ctime format
        let dt_ctime = parse_time_string("Sun May 31 10:08:47 2026");
        assert!(dt_ctime.is_some());
        assert_eq!(dt_ctime.unwrap().format("%Y-%m-%d %H:%M:%S").to_string(), "2026-05-31 10:08:47");

        // RFC 3339
        let dt_rfc = parse_time_string("2026-05-31T10:08:47Z");
        assert!(dt_rfc.is_some());
        assert_eq!(dt_rfc.unwrap().format("%Y-%m-%d %H:%M:%S").to_string(), "2026-05-31 10:08:47");

        // Epoch f64 string
        let dt_epoch = parse_time_string("1772359727.0");
        assert!(dt_epoch.is_some());
    }

    #[test]
    fn test_get_recent_telemetry_and_balance_sheet() {
        let temp_dir = std::env::temp_dir();
        let file_path = temp_dir.join("test_rust_telemetry.jsonl");
        if file_path.exists() {
            let _ = std::fs::remove_file(&file_path);
        }

        let _guard = TempEnv::set("CPP_TELEMETRY_FILE", file_path.to_str().unwrap());

        // Log events
        log_bypass_event("tool1", "reason1", "platform1", "pipe1", Some("agent1"));

        // Use custom log writing since log_telemetry usually delegates/validates opt-in
        let event1 = TelemetryEvent {
            event_type: "tool_call".to_string(),
            session_id: "s1".to_string(),
            start_time: "Sun May 31 10:00:00 2026".to_string(),
            tool_name: "tool1".to_string(),
            original_chars: 100,
            final_chars: 40,
            original_tokens: 25,
            final_tokens: 10,
            latency_ms: 10.0,
            cache_hit: false,
            platform: "platform1".to_string(),
            agent: "agent1".to_string(),
            pipe_name: "pipe1".to_string(),
            tier: "tier1".to_string(),
            reason: String::new(),
            timestamp: String::new(),
        };

        let event2 = TelemetryEvent {
            event_type: "tool_call".to_string(),
            session_id: "s2".to_string(),
            start_time: "Sun May 31 10:05:00 2026".to_string(),
            tool_name: "tool2".to_string(),
            original_chars: 200,
            final_chars: 80,
            original_tokens: 50,
            final_tokens: 20,
            latency_ms: 20.0,
            cache_hit: false,
            platform: "platform2".to_string(),
            agent: "agent2".to_string(),
            pipe_name: "pipe2".to_string(),
            tier: "tier2".to_string(),
            reason: String::new(),
            timestamp: String::new(),
        };

        {
            let mut file = OpenOptions::new().create(true).append(true).open(&file_path).unwrap();
            let _ = writeln!(file, "{}", serde_json::to_string(&event1).unwrap());
            let _ = writeln!(file, "{}", serde_json::to_string(&event2).unwrap());
        }

        // Test get_recent_telemetry
        let recent = get_recent_telemetry(2);
        assert_eq!(recent.len(), 2);
        assert_eq!(recent[0].session_id, "s2");
        assert_eq!(recent[1].session_id, "s1");

        // Test get_balance_sheet session filtering
        let sheet_s1 = get_balance_sheet(Some("s1"), None);
        assert_eq!(sheet_s1.total_events, 1);
        assert_eq!(sheet_s1.noise_removed, 60);

        let sheet_s2 = get_balance_sheet(Some("s2"), None);
        assert_eq!(sheet_s2.total_events, 1);
        assert_eq!(sheet_s2.noise_removed, 120);

        // Cleanup
        let _ = std::fs::remove_file(file_path);
    }
}
