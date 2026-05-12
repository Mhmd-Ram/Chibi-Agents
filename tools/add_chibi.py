#!/usr/bin/env python3
"""Add, list, preview, or remove chibis with one command.

Drops a sprite sheet into `assets/<slug>/`, autodetects frame size from the
grid, and writes a manifest with sensible defaults that mirror the bundled
Zubair / Ali sheets (8 cols x 9 rows, 192x208 frames). Override anything via
flags if your sheet uses a different layout.

Examples:
    # Most common - sheet matches the bundled layout:
    python tools/add_chibi.py path/to/sheet.webp "Bob"

    # Custom grid:
    python tools/add_chibi.py sheet.png "Cleo" --cols 6 --rows 5 --fps 4

    # See a frame-numbered preview without installing:
    python tools/add_chibi.py preview path/to/sheet.webp

    # List installed chibis:
    python tools/add_chibi.py list

    # Remove an installed chibi:
    python tools/add_chibi.py remove "Bob"
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "assets"

# Default animation map. Matches the bundled Zubair/Ali sheets (8x9 grid).
# Each entry: animation_name -> {row, count, loop, optional extras}.
# Frames are row-major: row N starts at frame N * cols.
#
# Four animations are *required* to drive the daemon's event-to-animation
# mapping: idle, alert, thinking, reviewing.
# The rest are optional polish — if a sheet has rows for them, they get wired;
# if not, the chibi falls back gracefully.
DEFAULT_ANIMATIONS = {
    # --- core (required) ---
    "idle":         {"row": 0, "count": 6, "loop": True},
    "alert":        {"row": 5, "count": 8, "loop": True},   # tool errors / notifications
    "thinking":     {"row": 7, "count": 6, "loop": True},   # also used for working / writing
    "reviewing":    {"row": 8, "count": 6, "loop": True},   # also used for planning

    # --- aliases of the core animations (point at the same rows) ---
    "working":      {"row": 7, "count": 6, "loop": True},
    "writing":      {"row": 7, "count": 6, "loop": True},
    "planning":     {"row": 8, "count": 6, "loop": True},

    # --- subagent in/out wave (uses row 3 forward + reversed) ---
    "spawn_in":     {"row": 3, "count": 4, "loop": False, "next": "idle"},
    "spawn_out":    {"row": 3, "count": 4, "loop": False, "despawn": True, "reverse": True},

    # --- optional "personality" row (e.g. Ali's noodle break) ---
    # If a sheet has a unique custom row at index 6, it'll be exposed as "eating".
    # If not, it just stays unused — the daemon never plays it unless triggered.
    "eating":       {"row": 6, "count": 6, "loop": True},

    # --- subtle quiet-idle alternative ---
    "sleeping":     {"row": 0, "count": 2, "loop": True},
}


def slugify(name: str) -> str:
    slug = name.strip().lower().replace("_", "-").replace(" ", "-")
    return "".join(c for c in slug if c.isalnum() or c == "-")


def build_animations(cols: int) -> dict:
    """Resolve the default animation table into concrete frame indices."""
    out = {}
    for anim, spec in DEFAULT_ANIMATIONS.items():
        start = spec["row"] * cols
        frames = list(range(start, start + spec["count"]))
        if spec.get("reverse"):
            frames = list(reversed(frames))
        entry = {"frames": frames, "loop": spec["loop"]}
        if spec.get("next"):
            entry["next"] = spec["next"]
        if spec.get("despawn"):
            entry["despawn"] = True
        out[anim] = entry
    return out


def autodetect_dims(sheet_path: Path, cols: int, rows: int) -> tuple[int, int]:
    """Use Pillow to read the sheet's dimensions and divide by the grid."""
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is required. Install with: pip install pillow", file=sys.stderr)
        sys.exit(2)
    with Image.open(sheet_path) as img:
        w, h = img.size
    if w % cols != 0 or h % rows != 0:
        print(
            f"WARN: sheet {w}x{h} doesn't divide evenly into {cols}x{rows}. "
            f"Frame will be {w // cols}x{h // rows} (some pixels truncated).",
            file=sys.stderr,
        )
    return w // cols, h // rows


def cmd_add(args: argparse.Namespace) -> int:
    sheet_src = Path(args.sheet).resolve()
    if not sheet_src.exists():
        print(f"ERROR: sheet not found: {sheet_src}", file=sys.stderr)
        return 2

    slug = args.slug or slugify(args.name)
    if not slug:
        print(f"ERROR: cannot derive a folder name from '{args.name}'", file=sys.stderr)
        return 2

    target_dir = ASSETS_DIR / slug
    if target_dir.exists() and not args.force:
        print(f"ERROR: '{target_dir}' already exists. Use --force to overwrite.",
              file=sys.stderr)
        return 2

    fw = args.frame_width
    fh = args.frame_height
    if not fw or not fh:
        auto_w, auto_h = autodetect_dims(sheet_src, args.cols, args.rows)
        fw = fw or auto_w
        fh = fh or auto_h

    target_dir.mkdir(parents=True, exist_ok=True)
    sheet_ext = sheet_src.suffix.lower() or ".webp"
    target_sheet = target_dir / f"spritesheet{sheet_ext}"
    shutil.copy2(sheet_src, target_sheet)

    manifest = {
        "name": args.name,
        "sheet": target_sheet.name,
        "frame_width": fw,
        "frame_height": fh,
        "fps": args.fps,
        "scale": args.scale,
        "animations": build_animations(args.cols),
    }
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[OK]Added chibi '{args.name}' at {target_dir}")
    print(f"  sheet: {target_sheet.name} ({fw}x{fh} per frame, {args.cols}x{args.rows} grid)")
    print(f"  animations: {len(manifest['animations'])} defined")
    print("")
    print("Next steps:")
    print("  1. Restart the daemon (.\\stop-chibi.bat && .\\start-chibi.vbs)")
    print(f"  2. Tray menu -> Roles -> assign '{args.name}' to a slot")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    """Render a frame-numbered grid overlay so users can see which frame is which."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("ERROR: Pillow required for preview. pip install pillow", file=sys.stderr)
        return 2
    sheet_path = Path(args.sheet).resolve()
    if not sheet_path.exists():
        print(f"ERROR: not found: {sheet_path}", file=sys.stderr)
        return 2
    img = Image.open(sheet_path).convert("RGBA")
    cols, rows = args.cols, args.rows
    fw, fh = img.size[0] // cols, img.size[1] // rows

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("arial.ttf", max(14, fh // 12))
    except OSError:
        font = ImageFont.load_default()
    for r in range(rows):
        for c in range(cols):
            x, y = c * fw, r * fh
            draw.rectangle([x, y, x + fw - 1, y + fh - 1],
                           outline=(255, 255, 0, 200), width=2)
            idx = r * cols + c
            draw.text((x + 4, y + 4), str(idx), fill=(255, 255, 0, 255), font=font)

    out_path = sheet_path.with_name(sheet_path.stem + "_preview.png")
    Image.alpha_composite(img, overlay).save(out_path)
    print(f"[OK]Wrote {out_path}")
    print(f"  Grid: {cols}x{rows} (frame {fw}x{fh})")
    print(f"  Total frames: {cols * rows} (indices 0..{cols * rows - 1})")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    if not ASSETS_DIR.exists():
        print(f"no assets dir at {ASSETS_DIR}")
        return 0
    rows = []
    for folder in sorted(ASSETS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("name", folder.name)
        sheet = data.get("sheet", "?")
        anims = len(data.get("animations") or {})
        rows.append((name, folder.name, sheet, anims))

    if not rows:
        print("(no chibis installed)")
        return 0
    name_w = max(len(r[0]) for r in rows)
    folder_w = max(len(r[1]) for r in rows)
    print(f"{'NAME'.ljust(name_w)}  {'FOLDER'.ljust(folder_w)}  ANIMS  SHEET")
    print(f"{'-' * name_w}  {'-' * folder_w}  -----  -----")
    for name, folder, sheet, anims in rows:
        print(f"{name.ljust(name_w)}  {folder.ljust(folder_w)}  {anims:5d}  {sheet}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    target = args.name
    # Try as slug first, then as name (matching against manifests).
    slug_dir = ASSETS_DIR / slugify(target)
    if slug_dir.exists() and (slug_dir / "manifest.json").exists():
        shutil.rmtree(slug_dir)
        print(f"[OK]removed {slug_dir}")
        return 0
    # Search by name field in manifests.
    for folder in ASSETS_DIR.iterdir():
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("name", "").lower() == target.lower():
            shutil.rmtree(folder)
            print(f"[OK]removed {folder}")
            return 0
    print(f"ERROR: no chibi found matching '{target}'", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=False)

    # Default "add" sub-parser (also works as the bare invocation).
    add_p = sub.add_parser("add", help="Install a sprite sheet as a chibi.")
    add_p.add_argument("sheet", help="Path to sprite sheet (PNG / WEBP / JPG)")
    add_p.add_argument("name", help="Display name, e.g. 'Bob'")
    add_p.add_argument("--slug", help="Folder name (default: slugified name)")
    add_p.add_argument("--cols", type=int, default=8)
    add_p.add_argument("--rows", type=int, default=9)
    add_p.add_argument("--fps", type=int, default=3)
    add_p.add_argument("--scale", type=float, default=0.5)
    add_p.add_argument("--frame-width", type=int)
    add_p.add_argument("--frame-height", type=int)
    add_p.add_argument("--force", action="store_true")
    add_p.set_defaults(func=cmd_add)

    prev_p = sub.add_parser("preview", help="Save a frame-numbered grid overlay.")
    prev_p.add_argument("sheet")
    prev_p.add_argument("--cols", type=int, default=8)
    prev_p.add_argument("--rows", type=int, default=9)
    prev_p.set_defaults(func=cmd_preview)

    list_p = sub.add_parser("list", help="Show all installed chibis.")
    list_p.set_defaults(func=cmd_list)

    rm_p = sub.add_parser("remove", help="Delete a chibi by name or slug.")
    rm_p.add_argument("name")
    rm_p.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
