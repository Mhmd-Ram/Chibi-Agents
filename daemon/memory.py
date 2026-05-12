"""Cross-session memory for the chibi.

Lives at ~/.chibi-pets/memory.json. Persists lightweight facts so the chibi
can greet you with continuity across daemon restarts ("welcome back — last
session you were editing auth.py").

Distinct from state.json (UI/position/today's tokens). Memory is long-term
*about you and your work*; state is short-term *about the chibi window*.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_MEMORY: dict = {
    "session_count": 0,
    "last_seen": None,            # ISO timestamp
    "first_seen": None,
    "streak_days": 0,
    "lifetime_cost_usd": 0.0,
    "tool_counts": {},            # tool name -> total calls
    "file_touches": {},           # filename -> total touches
    "last_files": [],             # recent unique files (most recent first)
    "last_summary": None,         # AI-generated summary of last session
    "current_project": None,      # cwd basename, or None
}


def memory_path() -> Path:
    return Path.home() / ".chibi-pets" / "memory.json"


def load_memory() -> dict:
    p = memory_path()
    if not p.exists():
        return dict(DEFAULT_MEMORY)
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_MEMORY)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"[chibi] failed to read memory: {exc}\n")
        return dict(DEFAULT_MEMORY)


def save_memory(memory: dict) -> None:
    p = memory_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2)
        os.replace(tmp, p)
    except OSError as exc:
        sys.stderr.write(f"[chibi] failed to save memory: {exc}\n")


def record_file_touch(memory: dict, file_path: str) -> None:
    """Increment counters for a file (any tool that names a file)."""
    if not file_path:
        return
    name = os.path.basename(file_path)
    if not name:
        return
    memory["file_touches"][name] = int(memory["file_touches"].get(name, 0)) + 1
    last = [f for f in memory.get("last_files", []) if f != name]
    last.insert(0, name)
    memory["last_files"] = last[:10]


def record_tool(memory: dict, tool: str) -> None:
    if not tool:
        return
    memory["tool_counts"][tool] = int(memory["tool_counts"].get(tool, 0)) + 1


def begin_session(memory: dict) -> None:
    """Called when the daemon starts. Updates streak and seen timestamps."""
    now = datetime.now()
    if not memory.get("first_seen"):
        memory["first_seen"] = now.isoformat()
    last_seen_raw = memory.get("last_seen")
    if last_seen_raw:
        try:
            last_seen = datetime.fromisoformat(last_seen_raw)
            gap_days = (now.date() - last_seen.date()).days
            if gap_days == 1:
                memory["streak_days"] = int(memory.get("streak_days", 0)) + 1
            elif gap_days > 1:
                memory["streak_days"] = 1
            # gap_days == 0 → same calendar day, streak unchanged
        except ValueError:
            memory["streak_days"] = 1
    else:
        memory["streak_days"] = 1
    memory["last_seen"] = now.isoformat()
    memory["session_count"] = int(memory.get("session_count", 0)) + 1


def update_last_seen(memory: dict) -> None:
    memory["last_seen"] = datetime.now().isoformat()


def top_files(memory: dict, n: int = 5) -> list[tuple[str, int]]:
    return Counter(memory.get("file_touches", {})).most_common(n)


def top_tools(memory: dict, n: int = 5) -> list[tuple[str, int]]:
    return Counter(memory.get("tool_counts", {})).most_common(n)


def welcome_line(memory: dict) -> str:
    """Pick a context-aware welcome line (used as fallback when AI is off)."""
    session_count = int(memory.get("session_count", 0))
    if session_count <= 1:
        return "hello, I'm your chibi!"
    streak = int(memory.get("streak_days", 0))
    last_files = memory.get("last_files") or []
    last_seen_raw = memory.get("last_seen")
    days_away = None
    if last_seen_raw:
        try:
            ls = datetime.fromisoformat(last_seen_raw)
            days_away = (datetime.now().date() - ls.date()).days
        except ValueError:
            pass

    if days_away is not None and days_away >= 7:
        return "back at last! it's been a while"
    if days_away is not None and days_away >= 2:
        return f"welcome back — {days_away} days!"
    if streak >= 3:
        return f"day {streak} of the streak!"
    if last_files:
        return f"still on {last_files[0]}?"
    return "welcome back!"


def context_for_ai(memory: dict) -> str:
    """Compact context string for AI welcome generation."""
    bits = [f"session {memory.get('session_count', 1)}"]
    last_seen = memory.get("last_seen")
    if last_seen:
        try:
            ls = datetime.fromisoformat(last_seen)
            mins = int((datetime.now() - ls).total_seconds() // 60)
            if mins < 60:
                bits.append(f"last seen {mins}m ago")
            elif mins < 60 * 24:
                bits.append(f"last seen {mins // 60}h ago")
            else:
                bits.append(f"last seen {mins // (60*24)}d ago")
        except ValueError:
            pass
    streak = int(memory.get("streak_days", 0))
    if streak:
        bits.append(f"streak {streak}d")
    last_files = memory.get("last_files") or []
    if last_files:
        bits.append(f"recent files: {', '.join(last_files[:3])}")
    return " · ".join(bits)


def summary_stats(memory: dict) -> dict:
    """Compact stats payload for the /stats endpoint."""
    return {
        "session_count": memory.get("session_count", 0),
        "streak_days": memory.get("streak_days", 0),
        "lifetime_cost_usd": round(float(memory.get("lifetime_cost_usd", 0.0)), 4),
        "top_files": top_files(memory),
        "top_tools": top_tools(memory),
        "last_files": memory.get("last_files", []),
        "last_summary": memory.get("last_summary"),
    }
