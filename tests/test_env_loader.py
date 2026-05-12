from __future__ import annotations

import os
from pathlib import Path

from daemon.env_loader import load_dotenv


def test_load_dotenv_adds_new_keys(tmp_path: Path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    added = load_dotenv(env)
    assert added == 2
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "qux"


def test_existing_env_is_not_overwritten(tmp_path: Path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOO=fromfile\n", encoding="utf-8")
    monkeypatch.setenv("FOO", "fromshell")
    load_dotenv(env)
    assert os.environ["FOO"] == "fromshell"


def test_handles_quotes_comments_blanks(tmp_path: Path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# this is a comment\n"
        "\n"
        "QUOTED=\"hello world\"\n"
        "SINGLE='hello world'\n"
        "PLAIN=value\n"
        "WITHEQUAL=a=b=c\n",
        encoding="utf-8",
    )
    for k in ("QUOTED", "SINGLE", "PLAIN", "WITHEQUAL"):
        monkeypatch.delenv(k, raising=False)
    load_dotenv(env)
    assert os.environ["QUOTED"] == "hello world"
    assert os.environ["SINGLE"] == "hello world"
    assert os.environ["PLAIN"] == "value"
    assert os.environ["WITHEQUAL"] == "a=b=c"


def test_missing_file_returns_zero(tmp_path: Path):
    assert load_dotenv(tmp_path / "nope.env") == 0
