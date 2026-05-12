from __future__ import annotations

from hook.classify import classify


def test_user_prompt_submit():
    out = classify({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
    assert out == {"type": "prompt_submit", "session_id": "s1"}


def test_stop():
    assert classify({"hook_event_name": "Stop"})["type"] == "stop"


def test_pretool_read_label():
    out = classify({
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": "/work/foo.txt"},
    })
    assert out["type"] == "tool_start"
    assert out["tool"] == "Read"
    assert out["label"] == "Reading foo.txt"


def test_pretool_edit_label():
    out = classify({
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": "C:\\proj\\bar.py"},
    })
    assert out["label"] == "Editing bar.py"


def test_pretool_write_label():
    out = classify({
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "new_module.py"},
    })
    assert out["label"] == "Creating new_module.py"


def test_pretool_bash_label():
    out = classify({
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/ -v --tb=short"},
    })
    assert out["label"] == "Running pytest"


def test_pretool_agent_is_subagent_start():
    out = classify({
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "Explore", "description": "find auth code"},
        "tool_use_id": "tu-1",
    })
    assert out["type"] == "subagent_start"
    assert out["agent"] == "Explore"
    assert out["agent_id"] == "Explore"
    assert out["label"] == "find auth code"


def test_subagent_stop():
    out = classify({"hook_event_name": "SubagentStop", "agent_id": "abc"})
    assert out["type"] == "subagent_stop"
    assert out["agent_id"] == "abc"


def test_posttool_ok():
    out = classify({"hook_event_name": "PostToolUse", "tool_name": "Bash"})
    assert out["type"] == "tool_end"
    assert out["tool"] == "Bash"
    assert out["error"] is False


def test_posttool_error_via_exit_code():
    out = classify({
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_response": {"exit_code": 2, "output": "some failure"},
    })
    assert out["error"] is True


def test_posttool_error_via_is_error_flag():
    out = classify({
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_response": {"is_error": True, "content": "File not found"},
    })
    assert out["error"] is True


def test_posttool_error_via_text():
    out = classify({
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_response": {"content": "Error: ENOENT: no such file"},
    })
    assert out["error"] is True


def test_posttool_traceback_is_error():
    out = classify({
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_response": {"output": "Traceback (most recent call last):\n  ..."},
    })
    assert out["error"] is True


def test_posttool_clean_output_is_not_error():
    out = classify({
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_response": {"exit_code": 0, "output": "ok\n"},
    })
    assert out["error"] is False


def test_unknown_event_returns_none():
    assert classify({"hook_event_name": "Mystery"}) is None
    assert classify({}) is None
