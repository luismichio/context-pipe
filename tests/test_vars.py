import pytest
from context_pipe.orchestrator import _build_vars

def test_build_vars_substitution():
    pipe_config = {"vars": {"A": "1", "B": "2"}}
    invocation_vars = {"A": "override", "C": "3"}
    # B comes from defaults, A is overridden, C is new
    res = _build_vars(pipe_config, invocation_vars)
    assert res == {"A": "override", "B": "2", "C": "3"}

def test_build_vars_missing_error(monkeypatch):
    pipe_config = {"vars": {"REQUIRED": ""}}
    # Not provided in invocation_vars or env
    monkeypatch.delenv("REQUIRED", raising=False)
    with pytest.raises(ValueError, match="Missing pipe variable: REQUIRED"):
        _build_vars(pipe_config, {})

def test_build_vars_env_fallback(monkeypatch):
    pipe_config = {"vars": {"ENV_VAR": ""}}
    monkeypatch.setenv("ENV_VAR", "from_env")
    res = _build_vars(pipe_config, {})
    assert res["ENV_VAR"] == "from_env"

def test_build_vars_invalid_name():
    with pytest.raises(ValueError, match="Invalid pipe variable name"):
        _build_vars({"vars": {"invalid-name!": "1"}}, {})

    with pytest.raises(ValueError, match="Invalid invocation variable name"):
        _build_vars({}, {"invalid-name!": "1"})

