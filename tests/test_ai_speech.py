from __future__ import annotations

import sys
import types

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QCoreApplication  # noqa: E402

from daemon.ai_speech import AISpeechProvider, _build_context  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


def test_build_context_includes_tool_and_caption():
    ctx = _build_context("tool_start", tool="Edit", caption="Editing app.py")
    assert "Edit" in ctx
    assert "Editing app.py" in ctx


def test_build_context_dedups_when_tool_equals_caption():
    ctx = _build_context("tool_start", tool="Read", caption="Read")
    # Caption shouldn't be duplicated when it just equals the tool name.
    assert ctx.count("Read") == 1


def test_request_does_nothing_when_no_api_key(qapp, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = AISpeechProvider(api_key=None)
    assert not p.available()
    # Should not emit anything / not raise.
    p.request("k", "tool_start", tool="Edit")


def test_response_cleans_quotes_and_truncates(qapp, monkeypatch):
    """Stub the anthropic SDK to return a noisy line; verify cleanup."""
    fake_block = types.SimpleNamespace(type="text", text="\"tweaking app.py...\"")
    fake_msg = types.SimpleNamespace(content=[fake_block])

    class FakeMessages:
        def create(self, **kwargs):
            return fake_msg

    class FakeAnthropic:
        def __init__(self, api_key=None):
            self.messages = FakeMessages()

    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    p = AISpeechProvider(api_key="fake-key")
    p._sdk_ok = True

    captured: list[tuple[str, str]] = []
    p.line_ready.connect(lambda k, t: captured.append((k, t)))

    # Run the worker synchronously (no thread) for test determinism.
    p._worker("k1", "Event: tool_start · Tool: Edit")

    assert captured, "expected at least one line_ready emission"
    k, text = captured[0]
    assert k == "k1"
    assert "tweaking app.py" in text
    assert not text.startswith('"')
    assert not text.endswith('"')
    assert not text.endswith(".")
