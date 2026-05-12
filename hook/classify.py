from __future__ import annotations

import os
from typing import Any


def _is_error_response(tool_response: Any) -> bool:
    """Best-effort detection that a tool returned an error.

    Claude Code's tool_response shape varies by tool, so we check the union of
    common failure signals: explicit is_error flag, non-zero exit_code, and
    leading error text in output/content/stdout/stderr.
    """
    if not isinstance(tool_response, dict):
        return False
    if tool_response.get("is_error") is True:
        return True
    exit_code = tool_response.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return True
    if tool_response.get("error"):
        return True
    for key in ("output", "content", "stdout", "stderr", "text"):
        val = tool_response.get(key)
        if not val:
            continue
        s = str(val).lstrip()
        if not s:
            continue
        lower = s.lower()
        if (
            s.startswith("Error:")
            or s.startswith("<tool_use_error>")
            or lower.startswith("error ")
            or "traceback (most recent call last)" in lower
        ):
            return True
    return False


def _truncate(s: str, n: int = 32) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"  # ellipsis


def _label_for_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Make a short, conversational caption from a tool's arguments.

    e.g. "Editing foo.py", "Reading bar.json", "Running pytest".
    """
    fp = tool_input.get("file_path") or tool_input.get("notebook_path")
    basename = os.path.basename(fp) if fp else ""

    if tool_name == "Read" and basename:
        return f"Reading {_truncate(basename, 22)}"
    if tool_name == "Edit" and basename:
        return f"Editing {_truncate(basename, 22)}"
    if tool_name == "Write" and basename:
        return f"Creating {_truncate(basename, 22)}"
    if tool_name == "NotebookEdit" and basename:
        return f"Editing {_truncate(basename, 22)}"

    if tool_name == "Bash":
        cmd = tool_input.get("command") or ""
        first = cmd.split(None, 1)[0] if cmd else ""
        if first:
            return f"Running {_truncate(first, 22)}"
        return "Running shell"

    if tool_name == "Grep":
        pat = tool_input.get("pattern") or ""
        return f"Searching {_truncate(pat, 20)}" if pat else "Searching"
    if tool_name == "Glob":
        pat = tool_input.get("pattern") or ""
        return f"Listing {_truncate(pat, 22)}" if pat else "Listing files"

    if tool_name == "WebFetch":
        url = tool_input.get("url") or ""
        host = url.split("//", 1)[-1].split("/", 1)[0]
        return f"Fetching {_truncate(host, 20)}" if host else "Fetching"
    if tool_name == "WebSearch":
        q = tool_input.get("query") or ""
        return f"Googling {_truncate(q, 20)}" if q else "Searching the web"

    if tool_name == "TodoWrite":
        n = len(tool_input.get("todos") or [])
        return f"Planning ({n} steps)" if n else "Planning"
    if tool_name == "ExitPlanMode":
        return "Presenting plan"
    if tool_name == "AskUserQuestion":
        return "Asking you"
    if tool_name == "Agent":
        desc = tool_input.get("description")
        if desc:
            return _truncate(desc, 28)
        st = tool_input.get("subagent_type") or "Agent"
        return f"Spawning {st}"
    if tool_name == "Skill":
        return f"Skill: {_truncate(tool_input.get('skill') or '', 20)}"
    if tool_name and tool_name.startswith("mcp__"):
        parts = tool_name.split("__")
        return f"Using {parts[-1]}" if parts else f"Using {tool_name}"

    return tool_name or ""


def classify(payload: dict[str, Any]) -> dict[str, Any] | None:
    event = payload.get("hook_event_name") or payload.get("event")
    session_id = payload.get("session_id")
    transcript = payload.get("transcript_path")
    common = {"session_id": session_id}
    if transcript:
        common["transcript_path"] = transcript

    if event == "UserPromptSubmit":
        return {"type": "prompt_submit", **common}

    if event == "Stop":
        return {"type": "stop", **common}

    if event == "Notification":
        return {"type": "notification", **common}

    if event == "SubagentStop":
        return {
            "type": "subagent_stop",
            "agent_id": payload.get("agent_id") or session_id or "?",
            **common,
        }

    if event == "PreToolUse":
        tool_name = payload.get("tool_name") or ""
        tool_input = payload.get("tool_input") or {}
        tool_use_id = payload.get("tool_use_id")
        if tool_name == "Agent":
            return {
                "type": "subagent_start",
                "agent_id": tool_input.get("subagent_type") or tool_use_id or "?",
                "agent": tool_input.get("subagent_type") or "general-purpose",
                "label": _label_for_tool(tool_name, tool_input),
                "tool_use_id": tool_use_id,
                **common,
            }
        return {
            "type": "tool_start",
            "tool": tool_name,
            "label": _label_for_tool(tool_name, tool_input),
            "tool_use_id": tool_use_id,
            **common,
        }

    if event == "PostToolUse":
        return {
            "type": "tool_end",
            "tool": payload.get("tool_name", ""),
            "error": _is_error_response(payload.get("tool_response")),
            "tool_use_id": payload.get("tool_use_id"),
            **common,
        }

    return None
