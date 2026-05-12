"""Persist chibi window position and scale across daemon restarts.

State lives at ~/.chibi-pets/state.json. Tiny JSON, written atomically.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _state_dir() -> Path:
    return Path.home() / ".chibi-pets"


def _state_file() -> Path:
    return _state_dir() / "state.json"


def load_state() -> dict[str, Any]:
    try:
        with _state_file().open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"[chibi] failed to load state: {exc}\n")
    return {}


def save_state(state: dict[str, Any]) -> None:
    try:
        _state_dir().mkdir(parents=True, exist_ok=True)
        tmp = _state_file().with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, _state_file())
    except OSError as exc:
        sys.stderr.write(f"[chibi] failed to save state: {exc}\n")
