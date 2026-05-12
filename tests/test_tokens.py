from __future__ import annotations

import json
from pathlib import Path

import pytest

from daemon.tokens import (
    Usage,
    format_compact,
    model_rates,
    parse_transcript,
)


def write_transcript(tmp_path: Path, messages: list[dict]) -> Path:
    p = tmp_path / "transcript.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")
    return p


def test_model_rates_falls_back_to_sonnet():
    r = model_rates("unknown-model")
    assert r["in"] == 3.0
    assert r["out"] == 15.0


def test_model_rates_picks_opus():
    r = model_rates("claude-opus-4-5-20251030")
    assert r["in"] == 15.0
    assert r["out"] == 75.0


def test_model_rates_picks_haiku():
    r = model_rates("claude-haiku-4-5")
    assert r["in"] == 1.0


def test_cost_math_sonnet():
    u = Usage(input_tokens=1_000_000, output_tokens=1_000_000, model="claude-sonnet-4-5")
    # 1M in (sonnet $3) + 1M out (sonnet $15) = $18
    assert abs(u.cost_usd() - 18.0) < 1e-6


def test_parse_transcript_aggregates_usage(tmp_path):
    msgs = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "model": "claude-sonnet-4-5-20250929",
            "usage": {"input_tokens": 1200, "output_tokens": 300,
                      "cache_creation_input_tokens": 100, "cache_read_input_tokens": 50},
        },
        {
            "role": "assistant",
            "model": "claude-sonnet-4-5-20250929",
            "usage": {"input_tokens": 800, "output_tokens": 200},
        },
    ]
    path = write_transcript(tmp_path, msgs)
    u = parse_transcript(path)
    assert u.input_tokens == 2000
    assert u.output_tokens == 500
    assert u.cache_write_tokens == 100
    assert u.cache_read_tokens == 50
    assert "sonnet" in (u.model or "")


def test_parse_transcript_handles_wrapped_message_envelope(tmp_path):
    msgs = [
        {"type": "assistant", "message": {
            "model": "claude-opus-4-5",
            "usage": {"input_tokens": 500, "output_tokens": 100},
        }},
    ]
    path = write_transcript(tmp_path, msgs)
    u = parse_transcript(path)
    assert u.input_tokens == 500
    assert u.output_tokens == 100
    assert "opus" in (u.model or "")


def test_parse_transcript_missing_file_returns_empty():
    u = parse_transcript("/nope/does/not/exist.jsonl")
    assert u.total_input == 0
    assert u.cost_usd() == 0.0


def test_format_compact_sane():
    u = Usage(input_tokens=42_000, output_tokens=8_000, model="claude-sonnet-4-5")
    s = format_compact(u)
    assert "42k" in s
    assert "8k" in s
    assert "$" in s


def test_sub_clamps_negatives():
    a = Usage(input_tokens=100)
    b = Usage(input_tokens=200)
    delta = a.sub(b)
    assert delta.input_tokens == 0


def test_usage_round_trip_dict():
    u = Usage(input_tokens=10, output_tokens=20, cache_read_tokens=3, model="claude-haiku")
    d = u.as_dict()
    u2 = Usage.from_dict(d)
    assert u2.input_tokens == 10
    assert u2.output_tokens == 20
    assert u2.cache_read_tokens == 3
    assert u2.model == "claude-haiku"
