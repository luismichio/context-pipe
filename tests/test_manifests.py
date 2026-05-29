import os
import json
import pytest
from datetime import datetime, timezone
from context_pipe.orchestrator import _write_manifest

def test_write_manifest_auto_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipe_config = {"name": "test-pipe"}
    vars_used = {"A": "1"}
    trace = [{"node": "cmd1", "input_size": 10, "output_size": 5}]
    result = "output text"
    status = "pass"
    started_at = datetime.now(timezone.utc).isoformat()

    _write_manifest("auto", pipe_config, vars_used, trace, result, status, started_at)

    cache_dir = tmp_path / ".pipe_cache"
    assert cache_dir.exists()
    files = list(cache_dir.glob("test-pipe-*.json"))
    assert len(files) == 1

    manifest = json.loads(files[0].read_text(encoding="utf-8"))
    assert manifest["pipe"] == "test-pipe"
    assert manifest["vars"] == {"A": "1"}
    assert manifest["status"] == "pass"
    assert len(manifest["steps"]) == 1
    assert manifest["steps"][0]["cmd"] == "cmd1"
    assert manifest["steps"][0]["ok"] is True
    assert manifest["finalOutput"] == "output text"

def test_write_manifest_explicit_path(tmp_path):
    pipe_config = {"name": "error-pipe"}
    manifest_path = str(tmp_path / "custom" / "run.json")
    trace = [{"node": "cmd1", "error": "failed to run"}]
    
    _write_manifest(manifest_path, pipe_config, {}, trace, "Error output", "fail", "2024-01-01T00:00:00Z")

    assert os.path.exists(manifest_path)
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    assert manifest["status"] == "fail"
    assert manifest["steps"][0]["ok"] is False
    assert manifest["steps"][0]["error"] == "failed to run"

