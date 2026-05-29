// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Luis Kobayashi. All rights reserved.

use std::process::Command;

#[test]
fn test_cli_help() {
    let mut cmd = Command::new("cargo");
    cmd.args(&["run", "--", "--help"]);
    let output = cmd.output().expect("Failed to execute command");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("High-performance Context-Pipe orchestrator"));
}

#[test]
fn test_cli_list() {
    let mut cmd = Command::new("cargo");
    cmd.args(&["run", "--", "list"]);
    let output = cmd.output().expect("Failed to execute command");
    // Since there might not be a pipes.json, we just check that it terminates (either successfully or with error).
    let status = output.status;
    assert!(status.code().is_some());
}

#[test]
fn test_cli_stats() {
    let mut cmd = Command::new("cargo");
    cmd.args(&["run", "--", "stats"]);
    let output = cmd.output().expect("Failed to execute command");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("Context-Pipe Balance Sheet"));
}

fn run_cpipe_with_config(config_content: &str, pipe_name: &str, input: &str, envs: &[(&str, &str)]) -> (String, String, bool) {
    use std::fs::File;
    use std::io::Write;
    
    let id = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let temp_dir = std::env::temp_dir();
    let config_path = temp_dir.join(format!("test_config_{}.json", id));
    let mut file = File::create(&config_path).unwrap();
    file.write_all(config_content.as_bytes()).unwrap();
    
    let mut cmd = Command::new("cargo");
    cmd.args(&["run", "--", "run", pipe_name, "--config", config_path.to_str().unwrap()]);
    for (k, v) in envs {
        cmd.env(k, v);
    }
    
    let mut child = cmd
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .expect("Failed to spawn cargo run");
        
    child.stdin.as_mut().unwrap().write_all(input.as_bytes()).unwrap();
    
    let output = child.wait_with_output().unwrap();
    
    let _ = std::fs::remove_file(config_path);
    
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    
    (stdout, stderr, output.status.success())
}

#[test]
fn test_run_pipe_logging_disabled() {
    let python_exe = cpipe::orchestrator::find_python_interpreter();
    let python_exe_escaped = python_exe.replace("\\", "\\\\");
    let config_content = format!(
        r#"{{
            "version": "1.0",
            "pipes": [
                {{
                    "name": "test-log-disabled",
                    "logging": {{
                        "enabled": false,
                        "prefix": "[MYPREFIX]",
                        "level": "compact",
                        "fields": ["node", "tokens"]
                    }},
                    "nodes": [
                        {{
                            "cmd": "{}",
                            "args": ["-c", "import sys; sys.stdout.write('x'*10)"]
                        }}
                    ]
                }}
            ]
        }}"#,
        python_exe_escaped
    );
    let (_, stderr, success) = run_cpipe_with_config(&config_content, "test-log-disabled", "y", &[]);
    assert!(success);
    assert!(!stderr.contains("[MYPREFIX]"));
}

#[test]
fn test_run_pipe_logging_compact() {
    let python_exe = cpipe::orchestrator::find_python_interpreter();
    let python_exe_escaped = python_exe.replace("\\", "\\\\");
    let config_content = format!(
        r#"{{
            "version": "1.0",
            "pipes": [
                {{
                    "name": "test-log-compact",
                    "logging": {{
                        "enabled": true,
                        "prefix": "[MYPREFIX]",
                        "level": "compact",
                        "fields": ["node", "tokens"]
                    }},
                    "nodes": [
                        {{
                            "cmd": "{}",
                            "args": ["-c", "import sys; sys.stdout.write('x'*10)"]
                        }}
                    ]
                }}
            ]
        }}"#,
        python_exe_escaped
    );
    let (_, stderr, success) = run_cpipe_with_config(&config_content, "test-log-compact", "y", &[]);
    assert!(success);
    assert!(!stderr.contains("[MYPREFIX] →"));
    assert!(stderr.contains("[MYPREFIX] ✓"));
    assert!(stderr.contains("1 → 10 chars"));
}

#[test]
fn test_run_pipe_logging_verbose() {
    let python_exe = cpipe::orchestrator::find_python_interpreter();
    let python_exe_escaped = python_exe.replace("\\", "\\\\");
    let config_content = format!(
        r#"{{
            "version": "1.0",
            "pipes": [
                {{
                    "name": "test-log-verbose",
                    "logging": {{
                        "enabled": true,
                        "prefix": "[VERB]",
                        "level": "verbose",
                        "fields": ["trigger", "node", "tokens", "timing"]
                    }},
                    "nodes": [
                        {{
                            "cmd": "{}",
                            "args": ["-c", "import sys; sys.stdout.write('output')"]
                        }}
                    ]
                }}
            ]
        }}"#,
        python_exe_escaped
    );
    let (_, stderr, success) = run_cpipe_with_config(&config_content, "test-log-verbose", "input", &[]);
    assert!(success);
    let lines: Vec<&str> = stderr.lines().filter(|l| l.contains("[VERB]")).collect();
    assert!(lines.len() >= 2);
    assert!(lines[0].contains("→"));
    assert!(lines[1].contains("✓"));
    assert!(lines[1].contains("5 → 6 chars"));
}

#[test]
fn test_run_pipe_logging_precedence() {
    let python_exe = cpipe::orchestrator::find_python_interpreter();
    let python_exe_escaped = python_exe.replace("\\", "\\\\");
    let config_content = format!(
        r#"{{
            "version": "1.0",
            "pipes": [
                {{
                    "name": "test-log-override",
                    "logging": {{
                        "enabled": false
                    }},
                    "nodes": [
                        {{
                            "cmd": "{}",
                            "args": ["-c", "import sys; sys.stdout.write('hello')"]
                        }}
                    ]
                }}
            ]
        }}"#,
        python_exe_escaped
    );
    let (_, stderr, success) = run_cpipe_with_config(
        &config_content,
        "test-log-override",
        "input",
        &[("PIPE_LOG_LEVEL", "compact"), ("PIPE_LOG_PREFIX", "[ENVPREFIX]")]
    );
    assert!(success);
    assert!(!stderr.contains("[ENVPREFIX]"));
}

// ── Phase 11-C: evaluate_condition unit tests ─────────────────────────────────

#[test]
fn test_evaluate_condition_size_gt() {
    use cpipe::orchestrator::evaluate_condition;
    assert!(evaluate_condition("size:>5", "hello world"), "11 chars > 5");
    assert!(!evaluate_condition("size:>100", "hello"), "5 chars not > 100");
}

#[test]
fn test_evaluate_condition_size_lt() {
    use cpipe::orchestrator::evaluate_condition;
    assert!(evaluate_condition("size:<100", "hello"), "5 chars < 100");
    assert!(!evaluate_condition("size:<3", "hello"), "5 chars not < 3");
}

#[test]
fn test_evaluate_condition_contains() {
    use cpipe::orchestrator::evaluate_condition;
    assert!(evaluate_condition("contains:ERROR", "line 1\nERROR: oops"), "should contain ERROR");
    assert!(!evaluate_condition("contains:WARNING", "all good"), "should not contain WARNING");
}

#[test]
fn test_evaluate_condition_artifact_missing() {
    use cpipe::orchestrator::evaluate_condition;
    // A path that definitely does not exist
    assert!(evaluate_condition("artifact:missing:/tmp/does_not_exist_cpipe_test_98765.txt", "data"));
    // Use the manifest dir to get an absolute path that definitely exists
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let cargo_toml = format!("{}/Cargo.toml", manifest_dir);
    assert!(!evaluate_condition(&format!("artifact:missing:{}", cargo_toml), "data"));
}

#[test]
fn test_evaluate_condition_artifact_exists() {
    use cpipe::orchestrator::evaluate_condition;
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let cargo_toml = format!("{}/Cargo.toml", manifest_dir);
    assert!(evaluate_condition(&format!("artifact:exists:{}", cargo_toml), "data"));
    assert!(!evaluate_condition("artifact:exists:/tmp/does_not_exist_cpipe_test_98765.txt", "data"));
}

#[test]
fn test_evaluate_condition_unknown_returns_true() {
    use cpipe::orchestrator::evaluate_condition;
    // Unknown predicates must return true (fail-open, log warning)
    assert!(evaluate_condition("unknown:xyz", "data"));
}

// ── Phase 11-C: DAG traversal integration tests ───────────────────────────────

/// A node with a false condition should be skipped; only the echo node runs.
#[test]
fn test_dag_condition_skip() {
    let python_exe = cpipe::orchestrator::find_python_interpreter();
    let python_exe_escaped = python_exe.replace("\\", "\\\\");
    // Node 0: condition size:>999 is false for "hello" → skip
    // Node 1: echo node that passes through input
    let config = format!(
        r#"{{
  "version": "1.0",
  "pipes": [
    {{
      "name": "test-condition-skip",
      "nodes": [
        {{
          "cmd": "{python}",
          "args": ["-c", "import sys; sys.stdout.write('SHOULD_NOT_APPEAR')"],
          "condition": "size:>999"
        }},
        {{
          "cmd": "{python}",
          "args": ["-c", "import sys; sys.stdout.write(sys.stdin.read())"]
        }}
      ]
    }}
  ]
}}"#,
        python = python_exe_escaped
    );
    let (stdout, _stderr, success) = run_cpipe_with_config(&config, "test-condition-skip", "hello", &[]);
    assert!(success, "pipe should succeed");
    assert!(!stdout.contains("SHOULD_NOT_APPEAR"), "conditional node must be skipped");
    assert!(stdout.contains("hello"), "pass-through node should output input");
}

/// Validator node: exit 0 → branch to a named "pass-node" which is separate from
/// the natural linear sequence. fail-node lives in branch_sequences and can only
/// be reached if the validator exits 1.
#[test]
fn test_dag_validator_branch_on_exit_zero() {
    let python_exe = cpipe::orchestrator::find_python_interpreter();
    let python_exe_escaped = python_exe.replace("\\", "\\\\");
    // Validator exits 0. Branch "0" points to "pass-node" (separate from linear flow).
    // Branch "1" points to "on-fail" sequence. After pass-node there are no more nodes.
    let config = format!(
        r#"{{
  "version": "1.0",
  "pipes": [
    {{
      "name": "test-validator-branch",
      "nodes": [
        {{
          "cmd": "{python}",
          "args": ["-c", "import sys; sys.exit(0)"],
          "type": "validator",
          "id": "validate",
          "branches": {{
            "0": "pass-node",
            "1": "on-fail"
          }}
        }}
      ],
      "branch_sequences": {{
        "pass-node": [
          {{
            "cmd": "{python}",
            "args": ["-c", "import sys; sys.stdout.write('PASS')"]
          }}
        ],
        "on-fail": [
          {{
            "cmd": "{python}",
            "args": ["-c", "import sys; sys.stdout.write('FAIL')"]
          }}
        ]
      }}
    }}
  ]
}}"#,
        python = python_exe_escaped
    );
    let (stdout, _stderr, success) = run_cpipe_with_config(&config, "test-validator-branch", "data", &[]);
    assert!(success, "pipe should succeed");
    assert!(stdout.contains("PASS"), "exit 0 should branch to pass-node, got: {}", stdout);
    assert!(!stdout.contains("FAIL"), "should not reach fail-node");
}

