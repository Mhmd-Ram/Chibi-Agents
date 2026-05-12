from __future__ import annotations

import os
from pathlib import Path

HOST = "127.0.0.1"
PORT = int(os.environ.get("CHIBI_PORT", "47821"))

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "assets"

# Animations are sticky: they only change when an explicit event arrives.
# Stop (turn ended) is what returns the chibi to idle. The decay timer is kept
# as a long-tail safety net in case Stop never fires.
IDLE_DECAY_SECONDS = float(os.environ.get("CHIBI_DECAY", "86400"))
SUBAGENT_OFFSET_PX = 80
DEFAULT_ANCHOR = "bottom-right"
