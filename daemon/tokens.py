"""Token + cost accounting for the current Claude Code session.

Reads `transcript_path` (a JSONL file Claude Code writes per session) and
aggregates usage from each assistant message's `usage` block.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# US-dollar rates per 1,000,000 tokens. Keep these in sync with Anthropic's
# public pricing page. Conservative fallback to Sonnet rates if the model
# string isn't recognised.
MODEL_RATES: dict[str, dict[str, float]] = {
    # family substring -> {input, cache_write, cache_read, output}
    "opus":   {"in": 15.0, "cache_w": 18.75, "cache_r": 1.50, "out": 75.0},
    "sonnet": {"in":  3.0, "cache_w":  3.75, "cache_r": 0.30, "out": 15.0},
    "haiku":  {"in":  1.0, "cache_w":  1.25, "cache_r": 0.10, "out":  5.0},
}
DEFAULT_RATES = MODEL_RATES["sonnet"]


def model_rates(model: str | None) -> dict[str, float]:
    if not model:
        return DEFAULT_RATES
    name = model.lower()
    for fragment, rates in MODEL_RATES.items():
        if fragment in name:
            return rates
    return DEFAULT_RATES


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    model: str | None = None

    @property
    def total_input(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    def cost_usd(self) -> float:
        r = model_rates(self.model)
        return (
            self.input_tokens * r["in"]
            + self.cache_write_tokens * r["cache_w"]
            + self.cache_read_tokens * r["cache_r"]
            + self.output_tokens * r["out"]
        ) / 1_000_000

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.cache_read_tokens += other.cache_read_tokens
        if other.model and not self.model:
            self.model = other.model

    def sub(self, other: "Usage") -> "Usage":
        """Return (self - other) clamped at zero per field (delta since baseline)."""
        return Usage(
            input_tokens=max(0, self.input_tokens - other.input_tokens),
            output_tokens=max(0, self.output_tokens - other.output_tokens),
            cache_write_tokens=max(0, self.cache_write_tokens - other.cache_write_tokens),
            cache_read_tokens=max(0, self.cache_read_tokens - other.cache_read_tokens),
            model=self.model or other.model,
        )

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "Usage":
        d = d or {}
        return cls(
            input_tokens=int(d.get("input_tokens", 0)),
            output_tokens=int(d.get("output_tokens", 0)),
            cache_write_tokens=int(d.get("cache_write_tokens", 0)),
            cache_read_tokens=int(d.get("cache_read_tokens", 0)),
            model=d.get("model"),
        )


def _iter_messages(path: Path) -> Iterable[dict]:
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def parse_transcript(path: str | Path | None) -> Usage:
    """Aggregate usage across all assistant turns in the transcript."""
    if not path:
        return Usage()
    p = Path(path)
    if not p.exists():
        return Usage()
    total = Usage()
    for raw in _iter_messages(p):
        # Claude Code wraps messages under either "message" or at the top level.
        msg = raw.get("message") if isinstance(raw.get("message"), dict) else raw
        usage = msg.get("usage") if isinstance(msg, dict) else None
        if not isinstance(usage, dict):
            continue
        u = Usage(
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            cache_write_tokens=int(usage.get("cache_creation_input_tokens", 0) or 0),
            cache_read_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
            model=msg.get("model"),
        )
        total.add(u)
    return total


def _short(n: int) -> str:
    if n >= 1_000_000:
        s = f"{n/1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{s}M"
    if n >= 1_000:
        s = f"{n/1_000:.1f}".rstrip("0").rstrip(".")
        return f"{s}k"
    return str(n)


def format_compact(u: Usage) -> str:
    """Single-line summary for tray tooltip / hover."""
    return f"{_short(u.total_input)} in / {_short(u.output_tokens)} out · ~${u.cost_usd():.3f}"


def format_breakdown(u: Usage) -> str:
    """Multi-line breakdown for verbose displays."""
    r = model_rates(u.model)
    return (
        f"Model: {u.model or 'unknown'}\n"
        f"Input: {_short(u.input_tokens)} (${u.input_tokens * r['in'] / 1_000_000:.4f})\n"
        f"Cache write: {_short(u.cache_write_tokens)} (${u.cache_write_tokens * r['cache_w'] / 1_000_000:.4f})\n"
        f"Cache read: {_short(u.cache_read_tokens)} (${u.cache_read_tokens * r['cache_r'] / 1_000_000:.4f})\n"
        f"Output: {_short(u.output_tokens)} (${u.output_tokens * r['out'] / 1_000_000:.4f})\n"
        f"Total: ~${u.cost_usd():.4f}"
    )
