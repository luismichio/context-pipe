# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
context_pipe/config_loader.py  Local + global config merge.

Loads pipes configuration from a project-level ``pipes.json`` and/or the
user-global ``~/.mcp-pipe.json``, merging them with local entries taking
precedence over global ones.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

GLOBAL_CONFIG_PATH: str = os.path.expanduser("~/.mcp-pipe.json")


def load_pipes_config(local_path: str = "pipes.json") -> dict:
    """
    Loads the pipes configuration, merging local and global sources.

    Resolution order:
    1. ``local_path`` (project-level pipes.json)
    2. ``~/.mcp-pipe.json`` (user-global config)

    Merging rules:
    - ``"pipes"`` arrays are combined; local entries appear first.
      Local name wins on conflict.
    - ``"servers"`` dicts are merged; local keys win on conflict.
    - ``"mappings"`` arrays are combined; local entries appear first.

    Never raises  all errors are logged to stderr and the safest possible
    fallback (``{"pipes": [], "servers": {}, "mappings": []}``) is returned.

    Args:
        local_path: Path to the project-level pipes.json file.

    Returns:
        Merged config dict with ``"pipes"``, ``"servers"``, and ``"mappings"`` keys.
    """
    local_config: dict | None = _try_load(local_path, label="local")
    global_config: dict | None = _try_load(GLOBAL_CONFIG_PATH, label="global")

    if local_config is None and global_config is None:
        return {"pipes": [], "servers": {}, "mappings": []}

    # 1. Merge Pipes (local name wins)
    local_pipes: list = (local_config or {}).get("pipes", [])
    global_pipes: list = (global_config or {}).get("pipes", [])
    local_names = {p.get("name") for p in local_pipes if p.get("name")}
    merged_pipes = list(local_pipes)
    for pipe in global_pipes:
        if pipe.get("name") not in local_names:
            merged_pipes.append(pipe)

    # 2. Merge Servers (local key wins)
    local_servers: dict = (local_config or {}).get("servers", {})
    global_servers: dict = (global_config or {}).get("servers", {})
    merged_servers = {**global_servers, **local_servers}

    # 3. Merge Mappings (local first, no dedup needed)
    local_mappings: list = (local_config or {}).get("mappings", [])
    global_mappings: list = (global_config or {}).get("mappings", [])
    merged_mappings = list(local_mappings) + [
        m for m in global_mappings if m not in local_mappings
    ]

    # 4. Merge Authorized Roots (local first, deduped)
    local_roots: list = (local_config or {}).get("authorized_roots", [])
    global_roots: list = (global_config or {}).get("authorized_roots", [])
    seen_roots: set[str] = set()
    merged_roots: list[str] = []
    for r in list(local_roots) + list(global_roots):
        key = os.path.normcase(r.strip())
        if key and key not in seen_roots:
            seen_roots.add(key)
            merged_roots.append(r.strip())
    return {
        "version": (local_config or global_config or {}).get("version", "1.0"),
        "pipes": merged_pipes,
        "servers": merged_servers,
        "mappings": merged_mappings,
        "authorized_roots": merged_roots,
    }


def resolve_placeholders(obj: Any, env: dict | None = None) -> Any:
    """
    Recursively resolves ``${VAR}`` placeholders in strings, lists, and dicts.

    Args:
        obj: The object to resolve placeholders within.
        env: Optional environment dictionary. Defaults to os.environ.
    """
    import os
    import re as _re

    # Use a local copy or the provided dict to ensure type safety
    effective_env: dict = dict(os.environ) if env is None else env

    if isinstance(obj, str):

        def _replace(m: _re.Match) -> str:
            var = m.group(1)
            if var not in effective_env:
                raise ValueError(f"Missing pipe variable: {var}")
            return str(effective_env[var])

        return _re.sub(r"\$\{([^}]+)\}", _replace, obj)

    if isinstance(obj, list):
        return [resolve_placeholders(item, effective_env) for item in obj]

    if isinstance(obj, dict):
        return {k: resolve_placeholders(v, effective_env) for k, v in obj.items()}

    return obj


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _try_load(path: str, label: str) -> dict | None:
    """
    Attempts to load and parse a JSON config file.

    Returns the parsed dict on success, or ``None`` if the file is absent or
    unreadable.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.debug("%s config not found at '%s'.", label.capitalize(), path)
        return None
    except json.JSONDecodeError as exc:
        logger.warning("Malformed JSON in %s config '%s': %s  skipping.", label, path, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read %s config '%s': %s.", label, path, exc)
        return None
