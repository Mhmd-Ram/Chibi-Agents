#!/usr/bin/env python3
"""Merge chibi-pets hooks into ~/.claude/settings.json.

Safe to run multiple times. Backs up the existing settings.json (if any) to
settings.json.bak before writing. Existing non-hook keys are preserved; the
"hooks" key is replaced with the chibi-pets hook commands so the wiring always
points at this checkout.

Usage:
    python tools/install_hooks.py
    python tools/install_hooks.py --dry-run   # show what would change
    python tools/install_hooks.py --uninstall # remove chibi-pets hooks
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "hook" / "chibi-hook.py"
CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"

HOOK_EVENTS = (
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "SubagentStop",
    "Stop",
    "Notification",
)


def hook_command() -> str:
    return f'python "{HOOK_PATH}"'


def build_hooks_block() -> dict:
    cmd = hook_command()
    return {
        evt: [{"hooks": [{"type": "command", "command": cmd}]}]
        for evt in HOOK_EVENTS
    }


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot parse {SETTINGS_PATH}: {exc}", file=sys.stderr)
        sys.exit(2)


def write_settings(data: dict) -> None:
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    if SETTINGS_PATH.exists():
        backup = SETTINGS_PATH.with_suffix(".json.bak")
        shutil.copy2(SETTINGS_PATH, backup)
        print(f"backup: {backup}")
    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"wrote:  {SETTINGS_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="don't write, just show")
    parser.add_argument("--uninstall", action="store_true", help="remove the hooks key")
    args = parser.parse_args()

    if not HOOK_PATH.exists():
        print(f"ERROR: cannot find {HOOK_PATH}", file=sys.stderr)
        return 2

    settings = load_settings()
    if args.uninstall:
        if "hooks" not in settings:
            print("nothing to remove: settings.json has no 'hooks' key")
            return 0
        settings.pop("hooks")
        action = "remove 'hooks' key"
    else:
        settings["hooks"] = build_hooks_block()
        action = f"install hooks pointing at {HOOK_PATH}"

    if args.dry_run:
        print(f"DRY RUN — would {action}")
        print(json.dumps(settings, indent=2))
        return 0

    write_settings(settings)
    print(f"done: {action}")
    print("→ start the daemon (start-chibi.vbs) and Claude Code will drive it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
