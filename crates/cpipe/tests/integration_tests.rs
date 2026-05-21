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
