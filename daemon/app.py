from __future__ import annotations

import random
import sys
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from datetime import date

from .ai_speech import AISpeechProvider
from .catalog import discover_chibis, resolve_role
from .config import IDLE_DECAY_SECONDS, SUBAGENT_OFFSET_PX
from .memory import (
    begin_session,
    context_for_ai,
    load_memory,
    record_file_touch,
    record_tool,
    save_memory,
    summary_stats,
    update_last_seen,
    welcome_line,
)
from .persist import load_state, save_state
from .registry import chibi_dir_for_agent, main_chibi_dir
from .server import EventServer
from .sprite import load_sprite_sheet
from .state import ChibiState
from .tokens import Usage, format_compact, parse_transcript
from .window import ChibiWindow

# Roles users can assign a chibi to via the tray menu.
ASSIGNABLE_ROLES: list[str] = [
    "main", "general-purpose", "Explore", "Plan", "_default",
]


SLOW_TOOL_THRESHOLD_SEC = 30.0
TERMINAL_BUBBLE_FADE_MS = 30_000  # auto-clear bubble 30s after a stop/idle
SNACK_BREAK_IDLE_MS = 180_000     # 3 minutes of idle before chibi gets snacky

# Playful one-liners the chibi says in response to Claude actions.
SPEECH_LINES: dict[str, list[str]] = {
    "prompt_submit": ["on it!", "let's go", "thinking…", "hmm", "got it"],
    "error":     ["yikes!", "that didn't work", "oof", "uh oh", "error!"],
    "slow":      ["still going…", "this is taking a while", "hang on…", "almost there?"],
    # Main chibi delegates a task to a subagent.
    "main_delegating": ["go check it!", "you got this", "scope it out", "head out!", "report back!"],
    # Main thanks/acknowledges a returning subagent.
    "main_thanking":   ["nice work!", "thanks!", "good find", "saved me!", "appreciate it"],
    # Subagent acknowledges getting a task (its own bubble).
    "subagent_self_start": ["on it!", "scouting!", "going!", "got it!", "be right back"],
    # Subagent reports back when finishing.
    "subagent_self_stop":  ["back!", "found it!", "done!", "scoped!", "results in!"],
    "snack_break":         ["snack break!", "ramen time", "brb eating", "lunch!", "noodle break"],
    "Read":      ["reading…", "let me see", "what's this?", "skimming"],
    "Grep":      ["searching…", "where is it?", "scanning", "hunting"],
    "Glob":      ["listing files", "finding…"],
    "Edit":      ["editing…", "fixing it", "small tweak"],
    "Write":     ["writing it out", "new file!", "drafting"],
    "Bash":      ["running it", "shell time", "executing"],
    "TodoWrite": ["planning", "step by step", "organizing"],
    "ExitPlanMode": ["plan ready!", "check this", "done planning"],
    "AskUserQuestion": ["a question for you", "your call", "thoughts?"],
    "WebFetch":  ["fetching…", "let me grab that"],
    "WebSearch": ["googling", "looking it up"],
    "Agent":     ["calling for help!", "delegating"],
    "subagent_start": ["nice, a teammate!", "team work!"],
    "subagent_stop":  ["thanks!", "all done", "ggwp"],
    "notification": ["wait!", "needs you!", "heads up!"],
    "stop":      ["all set!", "done!", "your turn", "back to you"],
}


def _pick_line(key: str) -> str:
    pool = SPEECH_LINES.get(key) or []
    return random.choice(pool) if pool else ""


class ChibiController(QObject):
    event_received = pyqtSignal(dict)
    quit_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        # Build the chibi catalog and load role assignments from state.
        self._catalog: dict[str, Path] = discover_chibis()
        saved_initial = load_state()
        self._role_assignments: dict[str, str] = dict(
            saved_initial.get("role_assignments") or {}
        )
        main_dir = resolve_role("main", self._role_assignments, self._catalog) or main_chibi_dir()
        self._main_sheet = load_sprite_sheet(main_dir)
        self._main_window = ChibiWindow(self._main_sheet)

        saved = load_state()
        saved_scale = saved.get("scale")
        if isinstance(saved_scale, (int, float)) and 0.1 <= saved_scale <= 4.0:
            self._main_window.set_scale(float(saved_scale))
        saved_pos = saved.get("main_position") or {}
        if isinstance(saved_pos.get("x"), int) and isinstance(saved_pos.get("y"), int):
            self._main_window.move(saved_pos["x"], saved_pos["y"])
        else:
            self._main_window.anchor_bottom_right()
        self._speech_enabled = bool(saved.get("speech_enabled", True))
        self._ai_enabled = bool(saved.get("ai_speech_enabled", True))
        self._ai = AISpeechProvider()
        self._ai.line_ready.connect(self._on_ai_line, Qt.ConnectionType.QueuedConnection)
        # Token / cost accounting state — restored from disk.
        self._tray: QSystemTrayIcon | None = None
        self._transcripts: dict[str, str] = {}        # session_id -> path
        self._session_baselines: dict[str, Usage] = {  # last-seen totals per session
            sid: Usage.from_dict(d)
            for sid, d in (saved.get("session_baselines") or {}).items()
        }
        self._daily_usage: dict[str, dict] = saved.get("daily_usage") or {}
        self._current_session_usage = Usage()
        # Long-term cross-session memory.
        self._memory = load_memory()
        begin_session(self._memory)
        save_memory(self._memory)
        self._main_window.show()

        self._main_window.close_requested.connect(self._hide_main)
        self._main_window.close_all_requested.connect(self.quit_requested.emit)
        self._main_window.scale_requested.connect(self.set_scale)
        self._main_window.position_committed.connect(self._persist)
        self._main_state = ChibiState(decay_seconds=IDLE_DECAY_SECONDS)

        self._subagents: dict[str, tuple[ChibiWindow, ChibiState]] = {}

        # tool_use_id -> {tool, label, start_time, warned}
        self._pending_tools: dict[str, dict] = {}

        # Event-type key for the currently-displayed state. Used so a repeated
        # event (e.g. consecutive Edit calls) keeps the same bubble line on
        # screen instead of flickering. Bubble + animation only change when the
        # event TYPE changes; caption always reflects the latest specific label.
        self._last_event_key: str | None = None
        # Timer that clears the main bubble after a quiet stretch following a
        # terminal event (Stop). Active events cancel it.
        self._bubble_fade_timer = QTimer(self)
        self._bubble_fade_timer.setSingleShot(True)
        self._bubble_fade_timer.timeout.connect(lambda: self._main_window.say(""))

        # Snack-break timer: after a long idle (post-Stop), the chibi takes a
        # ramen break if its sprite sheet has an "eating" animation defined.
        self._snack_timer = QTimer(self)
        self._snack_timer.setSingleShot(True)
        self._snack_timer.timeout.connect(self._maybe_snack_break)

        self._decay_timer = QTimer(self)
        self._decay_timer.timeout.connect(self._tick_decay)
        self._decay_timer.start(500)

        self._slow_timer = QTimer(self)
        self._slow_timer.timeout.connect(self._check_slow_tools)
        self._slow_timer.start(2000)

        # Token + cost tracker: re-parse the current transcript every 10 s and
        # refresh tray tooltip. Cheap to re-parse since transcripts are small
        # JSONL files; for large sessions we could incrementalise later.
        self._usage_timer = QTimer(self)
        self._usage_timer.timeout.connect(self._refresh_usage)
        self._usage_timer.start(10_000)

        # Welcome bubble: fire 2.5s after start so it doesn't clash with the
        # first real hook event from Claude Code.
        QTimer.singleShot(2500, self._show_welcome)

        # HTTP server fires events from a background thread; force a queued
        # connection so all chibi window mutations happen on the Qt main thread.
        self.event_received.connect(self._on_event, Qt.ConnectionType.QueuedConnection)

    def dispatch(self, payload: dict) -> None:
        self.event_received.emit(payload)

    @pyqtSlot(dict)
    def _on_event(self, payload: dict) -> None:
        etype = payload.get("type")

        # Snapshot transcript_path for usage accounting.
        tp = payload.get("transcript_path")
        sid = payload.get("session_id")
        if tp and sid:
            self._transcripts[sid] = tp

        # Any non-stop, non-tool_end event means Claude is doing something —
        # cancel any pending bubble fade so the new bubble persists.
        if etype not in ("stop", "tool_end"):
            self._bubble_fade_timer.stop()
            self._snack_timer.stop()

        if etype == "prompt_submit":
            self._transition("prompt", "thinking", caption="", speech_key="prompt_submit")

        elif etype == "tool_start":
            tool = payload.get("tool", "")
            caption = payload.get("label") or tool
            anim = _tool_to_anim(tool)
            self._transition(f"tool:{tool}", anim, caption=caption, speech_key=tool)
            # Memory bookkeeping.
            record_tool(self._memory, tool)
            label = payload.get("label") or ""
            # Heuristic: caption like "Reading foo.py" → extract filename token.
            if " " in label:
                maybe_file = label.rsplit(" ", 1)[-1]
                if "." in maybe_file or "/" in maybe_file:
                    record_file_touch(self._memory, maybe_file)
            # Watchdog bookkeeping.
            tid = payload.get("tool_use_id") or f"{tool}@{time.monotonic()}"
            self._pending_tools[tid] = {
                "tool": tool, "label": caption,
                "start_time": time.monotonic(), "warned": False,
            }

        elif etype == "tool_end":
            tid = payload.get("tool_use_id")
            if tid and tid in self._pending_tools:
                self._pending_tools.pop(tid, None)
            else:
                tool_name = payload.get("tool", "")
                for k, v in list(self._pending_tools.items()):
                    if v["tool"] == tool_name:
                        self._pending_tools.pop(k, None)
                        break
            if payload.get("error"):
                self._transition("error", "alert", caption="error", speech_key="error")
            # Clean tool_end: NO visual change — chibi stays in the tool's
            # state until the next event arrives.

        elif etype == "subagent_start":
            self._spawn_subagent(
                payload.get("agent_id") or payload.get("agent") or "?",
                payload.get("agent") or "_default",
                caption=payload.get("label") or payload.get("agent"),
            )
            # Main delegates; subagent will respond a beat later from inside
            # _spawn_subagent's staggered timer.
            self._transition_bubble_only("main_delegating")

        elif etype == "subagent_stop":
            self._despawn_subagent(payload.get("agent_id") or payload.get("agent") or "?")
            # Main acknowledges; the subagent already bubbled its farewell
            # from inside _despawn_subagent before waving out.
            QTimer.singleShot(800, lambda: self._transition_bubble_only("main_thanking"))

        elif etype == "stop":
            self._transition("stop", "idle", caption="", speech_key="stop")
            update_last_seen(self._memory)
            save_memory(self._memory)
            # After a Stop, schedule a fade so the bubble doesn't sit there
            # forever if no follow-up prompt comes.
            self._bubble_fade_timer.start(TERMINAL_BUBBLE_FADE_MS)
            # And queue a snack break for chibis that support it.
            self._snack_timer.start(SNACK_BREAK_IDLE_MS)

        elif etype == "notification":
            self._transition("alert", "alert", caption="needs you", speech_key="notification")

        elif etype == "say":
            self._say_main(str(payload.get("text") or ""))
        elif etype == "toggle_speech":
            self.set_speech_enabled(not self._speech_enabled)
        elif etype == "close":
            target = payload.get("agent_id") or payload.get("agent")
            if target:
                self._despawn_subagent(target)
        elif etype == "close_subagents":
            self.close_all_subagents()
        elif etype == "close_all":
            self.quit_requested.emit()
        elif etype == "hide_main":
            self._hide_main()
        elif etype == "show_main":
            self._show_main()
        elif etype == "set_scale":
            self.set_scale(float(payload.get("scale", 1.0)))
        elif etype == "set_role":
            role = str(payload.get("role") or "")
            chibi = payload.get("chibi")
            if role:
                self.assign_role(role, chibi if chibi else None)
        elif etype == "play_anim":
            anim = str(payload.get("anim") or "")
            if anim:
                self._main_window.play(anim)
                # Optional caption / bubble passthrough.
                cap = payload.get("caption")
                if cap is not None:
                    self._main_window.set_caption(str(cap))
                text = payload.get("text")
                if text:
                    self._say_main(str(text))

    def _transition(self, key: str, anim: str | None, *,
                    caption: str | None, speech_key: str) -> None:
        """Apply animation + caption + bubble for a logical state.

        Caption updates every call (so Edit foo.py → Edit bar.py refreshes the
        filename). Bubble only re-picks a line when the event TYPE key changes
        — consecutive Edits keep the same bubble showing.
        """
        if anim:
            self._set_main(anim, force=True, caption=caption if caption is not None else "")
        elif caption is not None:
            self._main_window.set_caption(caption)
        if key != self._last_event_key:
            line = _pick_line(speech_key)
            if line:
                self._say_main(line)
            self._last_event_key = key
            # Fire-and-forget AI line. If/when it returns, _on_ai_line will
            # replace the static bubble — but only if the chibi is still in
            # the same state (key match guard).
            if self._ai_enabled and self._speech_enabled:
                self._ai.request(key, speech_key, tool=speech_key, caption=caption or "")

    def _transition_bubble_only(self, speech_key: str) -> None:
        """Bubble-only update for events that don't claim the main chibi's
        animation/caption (e.g. subagent spawn / despawn)."""
        line = _pick_line(speech_key)
        if line:
            self._say_main(line)
        # AI follow-up for these too (subagent spawn/despawn are short events).
        if self._ai_enabled and self._speech_enabled:
            self._ai.request("transient", speech_key, tool=speech_key)

    @pyqtSlot(str, str)
    def _on_ai_line(self, key: str, text: str) -> None:
        if not self._ai_enabled or not self._speech_enabled:
            return
        # Stale check: only apply if the chibi is still in the state we asked
        # the API about (or it was a transient request).
        if key != "transient" and key != self._last_event_key:
            return
        self._say_main(text)

    def set_scale(self, scale: float) -> None:
        self._main_window.set_scale(scale)
        for i, (win, _) in enumerate(self._subagents.values(), start=1):
            win.set_scale(scale)
            base = self._main_window.geometry()
            win.move(base.x() - SUBAGENT_OFFSET_PX * i, base.y())
        self._persist()

    def _say_main(self, text: str) -> None:
        if not text or not self._speech_enabled:
            return
        self._main_window.say(text)

    def set_speech_enabled(self, enabled: bool) -> None:
        self._speech_enabled = bool(enabled)
        if not enabled:
            # Force-hide any visible bubble immediately.
            self._main_window.say("")
            for win, _ in self._subagents.values():
                win.say("")
        self._persist()

    def speech_enabled(self) -> bool:
        return self._speech_enabled

    def set_ai_enabled(self, enabled: bool) -> None:
        self._ai_enabled = bool(enabled)
        self._persist()

    def ai_enabled(self) -> bool:
        return self._ai_enabled

    def ai_available(self) -> bool:
        """True iff API key + SDK present (regardless of the user toggle)."""
        return self._ai.available()

    def _persist(self) -> None:
        geo = self._main_window.geometry()
        save_state({
            "scale": self._main_window.scale(),
            "main_position": {"x": geo.x(), "y": geo.y()},
            "speech_enabled": self._speech_enabled,
            "ai_speech_enabled": self._ai_enabled,
            "daily_usage": self._daily_usage,
            "session_baselines": {
                sid: u.as_dict() for sid, u in self._session_baselines.items()
            },
            "role_assignments": self._role_assignments,
        })

    # --- Role assignment ----------------------------------------------------

    def chibi_catalog(self) -> dict[str, Path]:
        return dict(self._catalog)

    def role_assignment(self, role: str) -> str | None:
        return self._role_assignments.get(role)

    def assign_role(self, role: str, chibi_name: str | None) -> None:
        """Map a role to a chibi by name. Pass None to clear (use fallback).

        `main` triggers an immediate sprite swap; other roles take effect on
        the next time that subagent spawns.
        """
        if chibi_name and chibi_name not in self._catalog:
            sys.stderr.write(f"[chibi] unknown chibi '{chibi_name}', ignoring\n")
            return
        if chibi_name:
            self._role_assignments[role] = chibi_name
        else:
            self._role_assignments.pop(role, None)
        if role == "main":
            self._reload_main_chibi()
        self._persist()

    def _reload_main_chibi(self) -> None:
        """Swap the main chibi's sprite sheet, preserving position/scale."""
        new_dir = resolve_role("main", self._role_assignments, self._catalog) \
            or main_chibi_dir()
        try:
            new_sheet = load_sprite_sheet(new_dir)
        except Exception as exc:
            sys.stderr.write(f"[chibi] could not reload main from {new_dir}: {exc}\n")
            return
        # Preserve current geometry + scale.
        old = self._main_window
        old_geo = old.geometry()
        old_scale = old.scale()
        # Close the old chibi (and its bubble/caption windows).
        old.close()
        # Build a fresh window.
        self._main_sheet = new_sheet
        new_win = ChibiWindow(new_sheet)
        new_win.set_scale(old_scale)
        new_win.move(old_geo.x(), old_geo.y())
        new_win.show()
        new_win.close_requested.connect(self._hide_main)
        new_win.close_all_requested.connect(self.quit_requested.emit)
        new_win.scale_requested.connect(self.set_scale)
        new_win.position_committed.connect(self._persist)
        self._main_window = new_win
        # Update tray icon to the new face.
        if self._tray:
            self._tray.setIcon(QIcon(new_sheet.pixmap(0)))
        # Quick wave so the change is visible.
        new_win.play("spawn_in")

    def close_all_subagents(self) -> None:
        for agent_id in list(self._subagents):
            self._despawn_subagent(agent_id)

    def _hide_main(self) -> None:
        self._main_window.hide()

    def _show_main(self) -> None:
        self._main_window.show()

    def _set_main(self, state: str, *, force: bool = False, caption: str | None = None) -> None:
        if self._main_state.request(state, force=force):
            self._main_window.play(state)
            if caption is not None:
                self._main_window.set_caption(caption)

    def _refresh_usage(self) -> None:
        """Re-parse current transcripts; update tray tooltip + daily totals."""
        if not self._transcripts:
            return
        # Aggregate current state across all known sessions.
        current = Usage()
        most_recent = Usage()
        memory_dirty = False
        for sid, path in self._transcripts.items():
            session_now = parse_transcript(path)
            current.add(session_now)
            most_recent = session_now
            # Credit the delta-since-baseline to today's running total.
            baseline = self._session_baselines.get(sid, Usage())
            delta = session_now.sub(baseline)
            if (delta.input_tokens or delta.output_tokens
                    or delta.cache_read_tokens or delta.cache_write_tokens):
                self._add_to_today(delta)
                self._memory["lifetime_cost_usd"] = round(
                    float(self._memory.get("lifetime_cost_usd", 0.0)) + delta.cost_usd(), 6
                )
                self._session_baselines[sid] = session_now
                memory_dirty = True
        self._current_session_usage = most_recent
        self._update_tray_tooltip()
        self._persist()
        # Memory file is critical for lifetime totals; persist immediately when
        # it changes so a hard-kill (taskkill, daemon crash) doesn't lose the
        # delta. Saving is cheap — small JSON file.
        if memory_dirty:
            save_memory(self._memory)

    def _add_to_today(self, delta: Usage) -> None:
        key = date.today().isoformat()
        today = self._daily_usage.setdefault(key, {
            "input_tokens": 0, "output_tokens": 0,
            "cache_write_tokens": 0, "cache_read_tokens": 0, "cost_usd": 0.0,
        })
        today["input_tokens"] += delta.input_tokens
        today["output_tokens"] += delta.output_tokens
        today["cache_write_tokens"] += delta.cache_write_tokens
        today["cache_read_tokens"] += delta.cache_read_tokens
        today["cost_usd"] = round(today["cost_usd"] + delta.cost_usd(), 6)

    def _update_tray_tooltip(self) -> None:
        if not self._tray:
            return
        today_key = date.today().isoformat()
        today_cost = (self._daily_usage.get(today_key) or {}).get("cost_usd", 0.0)
        session_line = format_compact(self._current_session_usage)
        model = self._current_session_usage.model or "—"
        lifetime = float(self._memory.get("lifetime_cost_usd", 0.0))
        sessions = int(self._memory.get("session_count", 0))
        streak = int(self._memory.get("streak_days", 0))
        # Dollar amounts are "API-equivalent cost" — what Anthropic would bill if
        # you were paying per-token. Claude Code subscriptions are flat-fee, so
        # this is informational, not your actual billed cost.
        self._tray.setToolTip(
            f"Chibi Pets · session #{sessions}\n"
            f"Session: {session_line}\n"
            f"Model: {model}\n"
            f"Today: ~${today_cost:.3f} (API-equivalent)\n"
            f"Lifetime: ~${lifetime:.2f}  ·  streak: {streak}d"
        )

    def attach_tray(self, tray: QSystemTrayIcon) -> None:
        self._tray = tray
        self._update_tray_tooltip()

    def _maybe_snack_break(self) -> None:
        """Play the eating animation if the current chibi has one."""
        if "eating" not in self._main_sheet.animations:
            return
        self._main_window.play("eating")
        self._main_window.set_caption("")
        if self._speech_enabled:
            line = _pick_line("snack_break")
            if line:
                self._main_window.say(line)

    def _check_slow_tools(self) -> None:
        """Bubble a 'still going…' nudge for any tool past the threshold.

        Each pending tool only triggers one warning to avoid spamming the
        bubble during truly long runs.
        """
        now = time.monotonic()
        for info in self._pending_tools.values():
            if info["warned"]:
                continue
            if now - info["start_time"] < SLOW_TOOL_THRESHOLD_SEC:
                continue
            info["warned"] = True
            self._say_main(_pick_line("slow"))

    def _tick_decay(self) -> None:
        if self._main_state.tick():
            self._main_window.play(self._main_state.current)
            self._main_window.set_caption("")
        for agent_id, (win, st) in list(self._subagents.items()):
            if st.tick():
                win.play(st.current)

    def _spawn_subagent(self, agent_id: str, agent_type: str, caption: str | None = None) -> None:
        if agent_id in self._subagents:
            return
        chibi_dir = (
            resolve_role(agent_type, self._role_assignments, self._catalog)
            or chibi_dir_for_agent(agent_type)
        )
        try:
            sheet = load_sprite_sheet(chibi_dir)
        except Exception as exc:
            sys.stderr.write(f"[chibi] failed to load {chibi_dir}: {exc}\n")
            return
        win = ChibiWindow(sheet)
        offset = SUBAGENT_OFFSET_PX * (len(self._subagents) + 1)
        win.anchor_bottom_right(x_offset=offset)
        win.show()
        win.close_requested.connect(lambda aid=agent_id: self._despawn_subagent(aid))
        win.close_all_requested.connect(self.quit_requested.emit)
        win.scale_requested.connect(self.set_scale)
        # Match current main chibi scale.
        win.set_scale(self._main_window.scale())
        state = ChibiState(decay_seconds=IDLE_DECAY_SECONDS)
        self._subagents[agent_id] = (win, state)
        win.play("spawn_in")
        win.set_caption(caption or agent_type)
        # After the spawn_in animation completes, subagent answers main.
        QTimer.singleShot(1400, lambda w=win: self._say_subagent(w, "subagent_self_start"))

    def _say_subagent(self, win: ChibiWindow, speech_key: str) -> None:
        """Show a bubble on a specific subagent window (no-op if speech off)."""
        if not self._speech_enabled:
            return
        line = _pick_line(speech_key)
        if line:
            win.say(line)

    def _despawn_subagent(self, agent_id: str) -> None:
        entry = self._subagents.pop(agent_id, None)
        if not entry:
            return
        win, _ = entry
        # Subagent says farewell, then waves out after a beat (so user can read).
        self._say_subagent(win, "subagent_self_stop")
        QTimer.singleShot(1500, lambda w=win: w.play("spawn_out", on_finished=lambda x: x.close()))

    def shutdown(self) -> None:
        self._persist()
        update_last_seen(self._memory)
        save_memory(self._memory)
        self._main_window.close()
        for win, _ in self._subagents.values():
            win.close()

    def _show_welcome(self) -> None:
        """Bubble a context-aware welcome on startup, drawn from long-term memory."""
        if not self._speech_enabled:
            return
        line = welcome_line(self._memory)
        if line:
            self._say_main(line)
        # Try to refine via AI if available.
        if self._ai_enabled and self._ai.available():
            self._ai.request(
                "welcome",
                "welcome_back",
                tool="welcome",
                caption=context_for_ai(self._memory),
            )

    def stats(self) -> dict:
        """Snapshot for the /stats HTTP endpoint."""
        today_key = date.today().isoformat()
        return {
            "session": format_compact(self._current_session_usage),
            "session_cost_usd": round(self._current_session_usage.cost_usd(), 6),
            "session_model": self._current_session_usage.model,
            "today": self._daily_usage.get(today_key) or {},
            "pending_tools": [
                {"tool": v["tool"], "label": v["label"],
                 "elapsed_sec": round(time.monotonic() - v["start_time"], 1)}
                for v in self._pending_tools.values()
            ],
            "speech_enabled": self._speech_enabled,
            "ai_enabled": self._ai_enabled,
            "ai_available": self._ai.available(),
            "memory": summary_stats(self._memory),
        }


def _tool_to_anim(tool: str) -> str | None:
    if tool in {"Read", "Grep", "Glob", "WebFetch", "WebSearch"}:
        return "reviewing"
    if tool in {"Edit", "Write", "NotebookEdit"}:
        return "writing"
    if tool in {"ExitPlanMode", "TodoWrite", "AskUserQuestion"}:
        return "planning"
    if tool == "Bash":
        return "working"
    if tool == "Agent":
        return "thinking"
    return None


def run() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    controller = ChibiController()
    controller.quit_requested.connect(app.quit)

    server = EventServer(controller.dispatch, controller.stats)
    server.start()

    # Use the chibi's idle frame as the tray icon so it's actually findable.
    tray_pixmap = controller._main_sheet.pixmap(0)
    tray = QSystemTrayIcon(QIcon(tray_pixmap), parent=app)
    tray.setToolTip("Chibi Pets")
    controller.attach_tray(tray)
    menu = QMenu()

    hide_action = QAction("Hide main chibi")
    hide_action.triggered.connect(controller._hide_main)
    menu.addAction(hide_action)

    show_action = QAction("Show main chibi")
    show_action.triggered.connect(controller._show_main)
    menu.addAction(show_action)

    menu.addSeparator()

    # Roles submenu: pick which chibi plays each role.
    roles_menu = menu.addMenu("Roles")
    catalog_names = sorted(controller.chibi_catalog().keys())
    if not catalog_names:
        no_chibi = QAction("(no chibis found in assets/)", roles_menu)
        no_chibi.setEnabled(False)
        roles_menu.addAction(no_chibi)
    else:
        for role in ASSIGNABLE_ROLES:
            sub = roles_menu.addMenu(role)
            current = controller.role_assignment(role)
            # "Default (auto)" entry to clear the override.
            auto_act = QAction("Default (auto)", sub)
            auto_act.setCheckable(True)
            auto_act.setChecked(current is None)
            auto_act.triggered.connect(
                lambda _checked=False, r=role: controller.assign_role(r, None)
            )
            sub.addAction(auto_act)
            sub.addSeparator()
            for name in catalog_names:
                act = QAction(name, sub)
                act.setCheckable(True)
                act.setChecked(name == current)
                act.triggered.connect(
                    lambda _checked=False, r=role, n=name: controller.assign_role(r, n)
                )
                sub.addAction(act)

    size_menu = menu.addMenu("Size")
    for label, factor in (("Tiny (25%)", 0.25), ("Small (50%)", 0.5), ("Medium (75%)", 0.75),
                          ("Original (100%)", 1.0), ("Large (150%)", 1.5), ("Huge (200%)", 2.0)):
        act = QAction(label, size_menu)
        act.triggered.connect(lambda _checked=False, f=factor: controller.set_scale(f))
        size_menu.addAction(act)

    speech_action = QAction("Speech bubbles")
    speech_action.setCheckable(True)
    speech_action.setChecked(controller.speech_enabled())
    speech_action.toggled.connect(controller.set_speech_enabled)
    menu.addAction(speech_action)

    ai_action = QAction("AI-generated speech (Haiku)")
    ai_action.setCheckable(True)
    ai_action.setChecked(controller.ai_enabled())
    ai_action.setEnabled(controller.ai_available())
    if not controller.ai_available():
        ai_action.setToolTip("Set ANTHROPIC_API_KEY and `pip install anthropic` to enable.")
    ai_action.toggled.connect(controller.set_ai_enabled)
    menu.addAction(ai_action)

    menu.addSeparator()

    close_subs_action = QAction("Close all subagent chibis")
    close_subs_action.triggered.connect(controller.close_all_subagents)
    menu.addAction(close_subs_action)

    clear_bubble_action = QAction("Clear bubble")
    clear_bubble_action.triggered.connect(lambda: controller._main_window.say(""))
    menu.addAction(clear_bubble_action)

    menu.addSeparator()

    quit_action = QAction("Quit (close all)")
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.show()

    rc = app.exec()
    server.stop()
    controller.shutdown()
    return rc
