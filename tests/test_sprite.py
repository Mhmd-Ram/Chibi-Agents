from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtGui import QImage, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from daemon.sprite import load_sprite_sheet  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make_sheet(tmp_path: Path, cols: int, rows: int, w: int, h: int) -> Path:
    img = QImage(w * cols, h * rows, QImage.Format.Format_ARGB32)
    img.fill(0xFF0000FF)
    sheet_path = tmp_path / "sheet.png"
    assert img.save(str(sheet_path), "PNG")
    return sheet_path


def test_load_sprite_sheet_round_trip(qapp, tmp_path):
    _make_sheet(tmp_path, cols=4, rows=2, w=8, h=8)
    manifest = {
        "sheet": "sheet.png",
        "frame_width": 8,
        "frame_height": 8,
        "fps": 4,
        "animations": {
            "idle": {"frames": [0, 1], "loop": True},
            "alert": {"frames": [4, 5], "loop": False, "next": "idle"},
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    sheet = load_sprite_sheet(tmp_path)
    assert sheet.frame_width == 8
    assert sheet.fps == 4
    assert sheet.frame_duration_ms == 250
    assert len(sheet.frames) == 8
    assert sheet.animation("idle").loop is True
    assert sheet.animation("alert").next == "idle"
    assert isinstance(sheet.pixmap(0), QPixmap)


def test_unknown_animation_falls_back_to_idle(qapp, tmp_path):
    _make_sheet(tmp_path, cols=2, rows=1, w=4, h=4)
    manifest = {
        "sheet": "sheet.png",
        "frame_width": 4,
        "frame_height": 4,
        "fps": 8,
        "animations": {"idle": {"frames": [0], "loop": True}},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    sheet = load_sprite_sheet(tmp_path)
    assert sheet.animation("does-not-exist").name == "idle"
