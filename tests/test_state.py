from __future__ import annotations

import time

from daemon.state import ChibiState


def test_request_higher_priority_wins():
    s = ChibiState(decay_seconds=10)
    assert s.request("thinking")
    assert s.current == "thinking"
    assert s.request("planning")
    assert s.current == "planning"


def test_request_lower_priority_rejected():
    s = ChibiState(decay_seconds=10)
    s.request("planning")
    assert not s.request("thinking")
    assert s.current == "planning"


def test_force_overrides_priority():
    s = ChibiState(decay_seconds=10)
    s.request("planning")
    assert s.request("idle", force=True)
    assert s.current == "idle"


def test_decay_returns_to_idle():
    s = ChibiState(decay_seconds=0.01)
    s.request("thinking")
    time.sleep(0.02)
    assert s.tick()
    assert s.current == "idle"


def test_idle_does_not_tick():
    s = ChibiState(decay_seconds=0.01)
    assert not s.tick()
