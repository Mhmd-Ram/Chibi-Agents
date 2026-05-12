from __future__ import annotations

from pathlib import Path

from .config import ASSETS_DIR


def chibi_dir_for_agent(agent_type: str | None) -> Path:
    if agent_type:
        slug = agent_type.strip().lower().replace("_", "-").replace(" ", "-")
        candidate = ASSETS_DIR / slug
        if (candidate / "manifest.json").exists():
            return candidate
    fallback = ASSETS_DIR / "_default"
    if (fallback / "manifest.json").exists():
        return fallback
    main = ASSETS_DIR / "main"
    return main


def main_chibi_dir() -> Path:
    return ASSETS_DIR / "main"
