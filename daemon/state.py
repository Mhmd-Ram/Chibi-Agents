from __future__ import annotations

import time
from dataclasses import dataclass

STATE_PRIORITY = {
    "idle": 0,
    "thinking": 1,
    "reviewing": 2,
    "writing": 2,
    "planning": 3,
    "working": 2,
    "alert": 5,
    "spawn_in": 4,
    "spawn_out": 4,
    "sleeping": 0,
}


@dataclass
class ChibiState:
    current: str = "idle"
    set_at: float = 0.0
    decay_seconds: float = 4.0

    def request(self, new_state: str, *, force: bool = False) -> bool:
        if force:
            self.current = new_state
            self.set_at = time.monotonic()
            return True
        cur = STATE_PRIORITY.get(self.current, 0)
        nxt = STATE_PRIORITY.get(new_state, 0)
        if nxt >= cur:
            self.current = new_state
            self.set_at = time.monotonic()
            return True
        return False

    def tick(self, now: float | None = None) -> bool:
        if self.current == "idle":
            return False
        now = now if now is not None else time.monotonic()
        if now - self.set_at >= self.decay_seconds:
            self.current = "idle"
            self.set_at = now
            return True
        return False
