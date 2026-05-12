from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from daemon import catalog as cat


def write_chibi(folder: Path, name: str | None = None, *, sheet: str = "spritesheet.webp"):
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {
        "sheet": sheet,
        "frame_width": 8,
        "frame_height": 8,
        "fps": 4,
        "animations": {"idle": {"frames": [0], "loop": True}},
    }
    if name is not None:
        manifest["name"] = name
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # Empty sheet file is fine; discover_chibis only checks existence.
    (folder / sheet).write_bytes(b"")


def test_discover_picks_up_named_chibis(tmp_path):
    write_chibi(tmp_path / "main", name="Zubair")
    write_chibi(tmp_path / "general-purpose", name="Ali")
    found = cat.discover_chibis(tmp_path)
    assert set(found.keys()) == {"Zubair", "Ali"}


def test_discover_dedups_same_name(tmp_path):
    write_chibi(tmp_path / "main", name="Zubair")
    write_chibi(tmp_path / "_default", name="Zubair")
    found = cat.discover_chibis(tmp_path)
    assert list(found.keys()) == ["Zubair"]
    # First sorted-by-name folder wins (_default comes before main).
    assert found["Zubair"].name == "_default"


def test_discover_skips_folders_missing_sheet(tmp_path):
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "manifest.json").write_text(
        json.dumps({"name": "Ghost", "sheet": "missing.webp", "animations": {}}),
        encoding="utf-8",
    )
    found = cat.discover_chibis(tmp_path)
    assert "Ghost" not in found


def test_resolve_role_uses_assignment(tmp_path, monkeypatch):
    write_chibi(tmp_path / "main", name="Zubair")
    write_chibi(tmp_path / "general-purpose", name="Ali")
    monkeypatch.setattr(cat, "ASSETS_DIR", tmp_path)
    catalog = cat.discover_chibis(tmp_path)
    assignments = {"main": "Ali"}
    resolved = cat.resolve_role("main", assignments, catalog)
    assert resolved is not None
    assert resolved.name == "general-purpose"  # Ali's folder


def test_resolve_role_falls_back_to_slug(tmp_path, monkeypatch):
    write_chibi(tmp_path / "general-purpose", name="Ali")
    monkeypatch.setattr(cat, "ASSETS_DIR", tmp_path)
    catalog = cat.discover_chibis(tmp_path)
    resolved = cat.resolve_role("general-purpose", {}, catalog)
    assert resolved.name == "general-purpose"


def test_resolve_role_falls_back_to_default(tmp_path, monkeypatch):
    write_chibi(tmp_path / "_default", name="Zubair")
    monkeypatch.setattr(cat, "ASSETS_DIR", tmp_path)
    catalog = cat.discover_chibis(tmp_path)
    resolved = cat.resolve_role("UnknownAgent", {}, catalog)
    assert resolved is not None
    assert resolved.name == "_default"
