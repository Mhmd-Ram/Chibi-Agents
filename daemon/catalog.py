"""Discover the chibis available on disk.

Each chibi is a folder under `assets/` with a `manifest.json` containing a
top-level `name` field. The name is the cross-folder identifier (multiple
role folders can share the same chibi sheet — only the first occurrence per
name wins in the catalog).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import ASSETS_DIR


def discover_chibis(assets_dir: Path | None = None) -> dict[str, Path]:
    """Return `{name: folder}` for every unique chibi.

    A folder qualifies if it contains a `manifest.json` and the sheet referenced
    by that manifest exists on disk. The chibi's name is `manifest["name"]` if
    present; otherwise the folder's own name (capitalised).
    """
    base = Path(assets_dir or ASSETS_DIR)
    out: dict[str, Path] = {}
    if not base.exists():
        return out
    for sub in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if not sub.is_dir():
            continue
        manifest_path = sub / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"[chibi] catalog skipped {sub.name}: {exc}\n")
            continue
        name = (manifest.get("name") or sub.name.replace("_", " ").title()).strip()
        if not name or name in out:
            continue
        sheet_path = sub / (manifest.get("sheet") or "")
        if not sheet_path.exists():
            continue
        out[name] = sub
    return out


def resolve_role(role: str, assignments: dict[str, str],
                 catalog: dict[str, Path]) -> Path | None:
    """Pick the sprite folder for a given role using assignments + fallbacks.

    Resolution order:
      1. If role_assignments[role] names a known chibi → that chibi's folder.
      2. Slug-match the role to an assets/<slug>/ folder (legacy behavior).
      3. assets/_default/.
      4. assets/main/ (last resort).
      5. None if nothing exists.
    """
    name = assignments.get(role)
    if name and name in catalog:
        return catalog[name]
    base = Path(ASSETS_DIR)
    slug = role.strip().lower().replace("_", "-").replace(" ", "-")
    candidate = base / slug
    if (candidate / "manifest.json").exists():
        return candidate
    fallback = base / "_default"
    if (fallback / "manifest.json").exists():
        return fallback
    main = base / "main"
    if (main / "manifest.json").exists():
        return main
    return None
