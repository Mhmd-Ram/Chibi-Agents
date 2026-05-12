from __future__ import annotations

from datetime import datetime, timedelta

from daemon import memory as mem


def test_begin_session_first_time_initialises():
    m = dict(mem.DEFAULT_MEMORY)
    mem.begin_session(m)
    assert m["session_count"] == 1
    assert m["streak_days"] == 1
    assert m["first_seen"]
    assert m["last_seen"]


def test_begin_session_extends_streak_next_day():
    m = dict(mem.DEFAULT_MEMORY)
    m["session_count"] = 5
    m["streak_days"] = 3
    m["last_seen"] = (datetime.now() - timedelta(days=1)).isoformat()
    mem.begin_session(m)
    assert m["streak_days"] == 4
    assert m["session_count"] == 6


def test_begin_session_resets_streak_after_long_gap():
    m = dict(mem.DEFAULT_MEMORY)
    m["session_count"] = 10
    m["streak_days"] = 7
    m["last_seen"] = (datetime.now() - timedelta(days=5)).isoformat()
    mem.begin_session(m)
    assert m["streak_days"] == 1


def test_begin_session_same_day_keeps_streak():
    m = dict(mem.DEFAULT_MEMORY)
    m["session_count"] = 4
    m["streak_days"] = 3
    m["last_seen"] = datetime.now().isoformat()
    mem.begin_session(m)
    assert m["streak_days"] == 3  # unchanged
    assert m["session_count"] == 5


def test_record_file_touch_increments_and_orders_recent():
    m = dict(mem.DEFAULT_MEMORY)
    m["file_touches"] = {}
    m["last_files"] = []
    mem.record_file_touch(m, "/work/app.py")
    mem.record_file_touch(m, "/work/window.py")
    mem.record_file_touch(m, "/work/app.py")
    assert m["file_touches"]["app.py"] == 2
    assert m["file_touches"]["window.py"] == 1
    # Most recent first; no dupes in last_files
    assert m["last_files"][0] == "app.py"
    assert m["last_files"].count("app.py") == 1


def test_record_tool_increments():
    m = dict(mem.DEFAULT_MEMORY)
    m["tool_counts"] = {}
    mem.record_tool(m, "Edit")
    mem.record_tool(m, "Edit")
    mem.record_tool(m, "Read")
    assert m["tool_counts"] == {"Edit": 2, "Read": 1}


def test_welcome_first_time():
    m = dict(mem.DEFAULT_MEMORY)
    m["session_count"] = 1
    assert "hello" in mem.welcome_line(m).lower()


def test_welcome_after_long_gap():
    m = dict(mem.DEFAULT_MEMORY)
    m["session_count"] = 5
    m["last_seen"] = (datetime.now() - timedelta(days=10)).isoformat()
    assert "while" in mem.welcome_line(m).lower() or "back" in mem.welcome_line(m).lower()


def test_welcome_streak():
    m = dict(mem.DEFAULT_MEMORY)
    m["session_count"] = 10
    m["streak_days"] = 5
    m["last_seen"] = datetime.now().isoformat()
    line = mem.welcome_line(m).lower()
    assert "5" in line or "streak" in line


def test_summary_stats_shape():
    m = dict(mem.DEFAULT_MEMORY)
    m["session_count"] = 3
    m["lifetime_cost_usd"] = 1.234567
    m["tool_counts"] = {"Edit": 5, "Read": 3}
    m["file_touches"] = {"app.py": 7}
    s = mem.summary_stats(m)
    assert s["session_count"] == 3
    assert s["lifetime_cost_usd"] == 1.2346
    assert ("Edit", 5) in s["top_tools"]
    assert ("app.py", 7) in s["top_files"]


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(mem, "memory_path", lambda: tmp_path / "memory.json")
    m = dict(mem.DEFAULT_MEMORY)
    m["session_count"] = 42
    m["tool_counts"] = {"Bash": 10}
    mem.save_memory(m)
    loaded = mem.load_memory()
    assert loaded["session_count"] == 42
    assert loaded["tool_counts"] == {"Bash": 10}
