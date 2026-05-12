#!/usr/bin/env python3
"""Claude Code hook entry point. Reads JSON from stdin, POSTs to the chibi daemon.

Fast-path design: never blocks Claude Code. If the daemon isn't running or the
classifier returns nothing, exit 0 silently.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hook.classify import classify  # noqa: E402

HOST = os.environ.get("CHIBI_HOST", "127.0.0.1")
PORT = int(os.environ.get("CHIBI_PORT", "47821"))
TIMEOUT_SEC = float(os.environ.get("CHIBI_HOOK_TIMEOUT", "0.2"))


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return 0

    # Opt-in debug log: set CHIBI_HOOK_DEBUG=1 to record every hook invocation.
    if os.environ.get("CHIBI_HOOK_DEBUG"):
        try:
            from datetime import datetime
            log_path = Path(__file__).resolve().parent.parent / "hook-debug.log"
            with log_path.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} event={payload.get('hook_event_name')} tool={payload.get('tool_name','')}\n")
        except Exception:
            pass

    event = classify(payload)
    if event is None:
        return 0

    body = json.dumps(event).encode("utf-8")
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}/event",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC):
            pass
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
