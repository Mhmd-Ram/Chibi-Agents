"""Minimal .env file loader.

Reads KEY=VALUE pairs from a dotfile and pushes any that aren't already in
os.environ. Real shell env always wins, so users can override per-session
without editing the file.

Why not python-dotenv? One less dependency, and the format we need is tiny.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def load_dotenv(path: Path) -> int:
    """Load KEY=VALUE pairs from `path` into os.environ. Returns the count
    of new variables added. Existing env vars are never overwritten."""
    if not path.exists():
        return 0
    added = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Trim matched surrounding quotes ("..." or '...').
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
                    value = value[1:-1]
                if not key:
                    continue
                if key in os.environ:
                    continue
                os.environ[key] = value
                added += 1
    except OSError as exc:
        sys.stderr.write(f"[chibi] failed to read {path}: {exc}\n")
    return added


def autoload() -> None:
    """Load .env from the project root and the user-scoped fallback."""
    # Project root (one level above the daemon package).
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")
    # User-scoped fallback (so several copies of chibi-pets can share keys).
    load_dotenv(Path.home() / ".chibi-pets" / ".env")
