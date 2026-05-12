from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtGui import QPixmap


@dataclass
class Animation:
    name: str
    frames: list[int]
    loop: bool = True
    next: str | None = None
    despawn: bool = False


@dataclass
class SpriteSheet:
    sheet_path: Path
    frame_width: int
    frame_height: int
    fps: int
    animations: dict[str, Animation]
    scale: float = 1.0
    frames: list[QPixmap] = field(default_factory=list)

    @property
    def frame_duration_ms(self) -> int:
        return max(1, int(1000 / max(1, self.fps)))

    def animation(self, name: str) -> Animation:
        if name not in self.animations:
            return self.animations.get("idle") or next(iter(self.animations.values()))
        return self.animations[name]

    def pixmap(self, frame_index: int) -> QPixmap:
        return self.frames[frame_index]


def load_sprite_sheet(chibi_dir: Path) -> SpriteSheet:
    manifest_path = chibi_dir / "manifest.json"
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    sheet_path = chibi_dir / manifest["sheet"]
    frame_w = int(manifest["frame_width"])
    frame_h = int(manifest["frame_height"])
    fps = int(manifest.get("fps", 8))

    animations: dict[str, Animation] = {}
    for name, spec in manifest["animations"].items():
        animations[name] = Animation(
            name=name,
            frames=list(spec["frames"]),
            loop=bool(spec.get("loop", True)),
            next=spec.get("next"),
            despawn=bool(spec.get("despawn", False)),
        )

    sheet = SpriteSheet(
        sheet_path=sheet_path,
        frame_width=frame_w,
        frame_height=frame_h,
        fps=fps,
        animations=animations,
        scale=float(manifest.get("scale", 1.0)),
    )
    sheet.frames = _slice_frames(sheet)
    return sheet


def _slice_frames(sheet: SpriteSheet) -> list[QPixmap]:
    pix = QPixmap(str(sheet.sheet_path))
    if pix.isNull():
        raise FileNotFoundError(f"Could not load sprite sheet: {sheet.sheet_path}")

    cols = pix.width() // sheet.frame_width
    rows = pix.height() // sheet.frame_height
    total = cols * rows

    frames: list[QPixmap] = []
    for i in range(total):
        col = i % cols
        row = i // cols
        x = col * sheet.frame_width
        y = row * sheet.frame_height
        frames.append(pix.copy(x, y, sheet.frame_width, sheet.frame_height))
    return frames
