"""AI-generated speech bubble lines via Claude Haiku.

Each call is run on a worker thread so it never blocks the Qt event loop.
When the API responds, a Qt signal carries (event_key, text) back to the
main thread, where the controller verifies the chibi is still in that state
before replacing the bubble.

Costs (Haiku 4.5 rates): ~85 in + ~15 out tokens per call ≈ $0.00016/call.
At 200 events/day that's about $1/month.
"""
from __future__ import annotations

import os
import threading
from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal

DEFAULT_MODEL = "claude-haiku-4-5"
MAX_OUTPUT_TOKENS = 24
RESPONSE_CHAR_CAP = 38  # bubble layout safety
RECENT_HISTORY_LEN = 5  # how many recent lines to feed back for variety

SYSTEM_PROMPT = (
    "You are a chibi desktop pet sitting on a developer's screen, reacting to "
    "what Claude Code is doing. Reply with ONE short playful line, max 6 words, "
    "max 30 characters. No quotes, no emoji, no period. Be cute, casual, varied. "
    "Sound like a tiny enthusiastic teammate, not a status report."
)


def _build_context(event_type: str, tool: str = "", caption: str = "") -> str:
    """Compose the user message describing the current action."""
    parts = [f"Event: {event_type}"]
    if tool:
        parts.append(f"Tool: {tool}")
    if caption and caption.lower() != tool.lower():
        parts.append(f"Context: {caption}")
    return " · ".join(parts)


class AISpeechProvider(QObject):
    """Async producer of bubble lines.

    Connect to `line_ready` to receive results. Caller passes a `key` with
    each `request()`; the same key comes back so the receiver can verify the
    chibi is still in that state before applying the line.
    """
    line_ready = pyqtSignal(str, str)  # (event_key, text)

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        super().__init__()
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = os.environ.get("CHIBI_AI_MODEL", model)
        self._recent: deque[str] = deque(maxlen=RECENT_HISTORY_LEN)
        self._sdk_ok = self._probe_sdk()

    @staticmethod
    def _probe_sdk() -> bool:
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def available(self) -> bool:
        return bool(self.api_key) and self._sdk_ok

    def request(self, key: str, event_type: str, tool: str = "", caption: str = "") -> None:
        if not self.available():
            return
        ctx = _build_context(event_type, tool, caption)
        threading.Thread(
            target=self._worker, args=(key, ctx), daemon=True
        ).start()

    def _worker(self, key: str, ctx: str) -> None:
        try:
            from anthropic import Anthropic
        except ImportError:
            return
        try:
            client = Anthropic(api_key=self.api_key)
            avoid = ""
            if self._recent:
                avoid = f"\nDon't repeat any of these recent lines: {list(self._recent)}"
            msg = client.messages.create(
                model=self.model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": ctx + avoid}],
            )
            text = "".join(
                getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
            ).strip()
            # Clean common nuisances (model quoting itself, trailing punctuation).
            text = text.strip("\"'`")
            text = text.rstrip(".!?,;: ")
            if not text:
                return
            text = text[:RESPONSE_CHAR_CAP]
            self._recent.append(text)
            self.line_ready.emit(key, text)
        except Exception:
            # Silent fallback — static SPEECH_LINES already gave the user a line.
            return
