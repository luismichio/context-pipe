# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

"""
context_pipe/config_loader.py — Local + global config merge.

Loads pipes configuration from a project-level ``pipes.json`` and/or the
user-global ``~/.mcp-pipe.json``, merging them with local entries taking
precedence over global ones.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

GLOBAL_CONFIG_PATH: str = os.path.expanduser("~/.mcp-pipe.json")


def load_pipes_config(local_path: str = "pipes.json") -> dict:
    """
    Loads the pipes configuration, merging local and global sources.

    Resolution order:
    1. ``local_path`` (project-level pipes.json)
    2. ``~/.mcp-pipe.json`` (user-global config)

    Merging rules:
    - Both ``"pipes"`` arrays are combined; local entries appear first.
    - If both define a pipe with the same ``name``, the local entry wins
      (the global duplicate is silently dropped).

    Never raises — all errors are logged to stderr and the safest possible
    fallback (``{"pipes": []}``) is returned.

    Args:
        local_path: Path to the project-level pipes.json file.

    Returns:
        Merged config dict with at least a ``"pipes"`` key.
    """
    local_config: dict | None = _try_load(local_path, label="local")
    global_config: dict | None = _try_load(GLOBAL_CONFIG_PATH, label="global")

    if local_config is None and global_config is None:
        return {"pipes": []}

    local_pipes: list = (local_config or {}).get("pipes", [])
    global_pipes: list = (global_config or {}).get("pipes", [])

    # Build merged list: local first, then global entries whose name is not
    # already present in local.
    local_names = {p.get("name") for p in local_pipes if p.get("name")}
    merged = list(local_pipes)
    for pipe in global_pipes:
        if pipe.get("name") not in local_names:
            merged.append(pipe)

    return {"pipes": merged}


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
        logger.warning("Malformed JSON in %s config '%s': %s — skipping.", label, path, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read %s config '%s': %s.", label, path, exc)
        return None
