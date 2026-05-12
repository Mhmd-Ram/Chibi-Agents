<div align="center">

#  Chibi Agents for Claude Code

A live desktop sidekick for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). <br/>
Animates in real time as Claude thinks, edits, runs tools, and spawns subagents.

<img src="docs/screenshots/hero.png" alt="Chibis" width="520"/>

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-41cd52)
![Platform Windows](https://img.shields.io/badge/platform-windows-0078d4)

</div>

> ⚠️ **Windows-only for now.** The daemon uses Win32 APIs for the transparent overlay and is launched via a `.vbs` script. macOS / Linux support is on the roadmap.

---

## ✨ What it does

![alt text](image.png)

Every time Claude Code does something — read a file, edit code, run a shell command, spawn a subagent — your chibi reacts. **Different animation per action**, a tiny speech bubble above its head, and a live caption like `Editing app.py` below.

| When Claude is... | Chibi | Caption | Bubble |
|---|---|---|---|
| Thinking | <img src="docs/screenshots/zubair-thinking.png" width="56"/> | (none) | `on it!` |
| Reading / Grepping | <img src="docs/screenshots/zubair-reviewing.png" width="56"/> | `Reading app.py` | `scanning` |
| Editing a file | <img src="docs/screenshots/zubair-thinking.png" width="56"/> | `Editing window.py` | `tweaking it` |
| Running a tool that fails | <img src="docs/screenshots/zubair-alert.png" width="56"/> | `error` | `yikes!` |
| Spawning a subagent | <img src="docs/screenshots/ali-flag.png" width="56"/> | (subagent name) | `go check it!` |
| Idle 3+ minutes | <img src="docs/screenshots/ali-eating.png" width="56"/> | (none) | `ramen time` |

---

## 🚀 Quick start (3 commands)

```powershell
git clone https://github.com/Mhmd-Ram/Chibi-Agents.git
cd Chibi-Agents
python -m pip install -e .[dev]
python tools/install_hooks.py
```

Then double-click `start-chibi.vbs` to launch the daemon and open Claude Code. Your chibi appears at the bottom-right of your screen.

> 🛎 **Everything is controlled from the system-tray icon.** It's next to your clock (click the `^` arrow if hidden). Hover it for live token / cost stats; right-click for the full menu. See [System tray](#-the-system-tray-icon) below.

> 💡 The `install_hooks.py` script merges the chibi hooks into `~/.claude/settings.json`, backing up your existing settings first. To remove later: `python tools/install_hooks.py --uninstall`.

---

## 🧩 Features

- **🎬 Animation per hook event** — `thinking`, `reviewing`, `writing`, `working`, `planning`, `alert`, `eating`. Reacts in real time to every tool call.
- **🤖 Per-subagent chibis** — `general-purpose`, `Explore`, `Plan` etc. each get their own animated character that spawns alongside the main one and waves goodbye when done.
- **💸 Live token + cost meter** — parses Claude Code's transcript and shows current-session, today, and lifetime API-equivalent cost in the system tray tooltip.
- **🧠 Cross-session memory** — streak counter, top files, top tools, contextual welcome bubble on every launch (`"day 5 of the streak!"`).
- **⚠️ Tool-failure detection** — switches to the alert animation with a `yikes` bubble when a tool errors out.
- **⏱ Slow-tool watchdog** — bubbles `still going…` after 30 seconds on a single tool.
- **🎨 Multi-chibi roster** — swap which chibi plays main, who plays each subagent role. Persisted across restarts.

---

## 📸 Screenshots

### Main chibi reacting to a real Claude turn
The caption updates with the actual filename Claude is touching. The bubble shows a personality line that holds until the event type changes.

<img src="docs/screenshots/zubair-idle.png" width="120"/> <img src="docs/screenshots/zubair-thinking.png" width="120"/> <img src="docs/screenshots/zubair-reviewing.png" width="120"/>

### Subagent spawn
When Claude delegates to a subagent, a second chibi waves in next to the main one, sits at its laptop while the subagent works, then waves out when it finishes.

<img src="docs/screenshots/zubair-idle.png" width="120"/> <img src="docs/screenshots/ali-flag.png" width="120"/>

### Long idle
After 3 minutes with no Claude activity, the chibi takes a snack break.

<img src="docs/screenshots/ali-eating.png" width="120"/>

### Errors
When a tool fails, the chibi panics — laptop on fire.

<img src="docs/screenshots/zubair-alert.png" width="120"/> 

---

## ⚙️ How it works

```
┌────────────────┐  hook fires  ┌────────────────────┐   POST   ┌───────────────────┐
│  Claude Code   │ ───────────▶ │ hook/chibi-hook.py │ ───────▶ │  daemon (PyQt6)   │
└────────────────┘              └────────────────────┘          │  transparent      │
                                                                 │  overlay window   │
                                                                 └───────────────────┘
```

1. Claude Code fires a hook (`PreToolUse`, `Stop`, etc.) defined in `~/.claude/settings.json`.
2. A tiny Python script (`hook/chibi-hook.py`) classifies the payload and POSTs an event to the daemon on `127.0.0.1:47821`.
3. The daemon picks the right animation, caption, and bubble for the event and updates the on-screen chibi.

The hook script exits silently if the daemon isn't running — **Claude Code is never blocked**.

---

## 🛠 The system tray icon

**Almost every setting lives in the tray icon.** Find it next to your clock — Windows hides background-app icons by default, so you may need to click the **`^`** arrow in the taskbar and drag the chibi icon out so it's always visible. The icon itself is your active main chibi's face.

### Hover the icon → live status tooltip

```
Chibi Pets · session #12
Session: 4.2k in / 800 out · ~$0.018 (API-equivalent)
Model: claude-sonnet-4-5-20250929
Today: ~$0.487
Lifetime: ~$2.74  ·  streak: 5d
```

Updates every 10 seconds while Claude is active. The cost is what Anthropic *would* charge per-token; if you're on a Claude Code subscription, your actual bill is your flat fee.

### Right-click the icon → full menu

```
Roles ▶                            ← swap which chibi plays each role
  main, general-purpose, Explore, Plan, _default
    → Default (auto) / [chibi names from assets/]

Size ▶                             ← scale all chibis at once
  Tiny / Small / Medium / Original / Large / Huge (25% – 200%)

☑ Speech bubbles                   ← turn the personality lines on/off
☑ AI-generated speech (Haiku)      ← contextual lines via Claude API (greyed if no key)

Hide main chibi                    ← stash without quitting
Show main chibi
Close all subagent chibis          ← but keep the main one
Clear bubble                       ← manually dismiss the current bubble

Quit (close all)                   ← shut the whole daemon down
```

### Right-click a chibi → same menu

The right-click context menu on any chibi sprite exposes the same **Roles** submenu and **Size** picker, so you can re-skin or resize without hunting for the tray icon.

### One-line scripting (HTTP)

The daemon listens on `127.0.0.1:47821`. Anything in the tray menu can also be driven from a script:

```powershell
# In examples/fake-events.ps1
.\examples\fake-events.ps1 stats              # full JSON dump of current state
.\examples\fake-events.ps1 scale 0.75         # resize live
.\examples\fake-events.ps1 set_role main Ali  # swap who's main
.\examples\fake-events.ps1 say "deploying"    # custom bubble
.\examples\fake-events.ps1 close_all          # quit
```

Useful for CI integrations or hotkey scripts.

---

## 🎨 Adding your own chibi

**One command.** Drop your sprite sheet anywhere, then:

```powershell
python tools/add_chibi.py add path\to\sheet.webp "MyChibi"
```

That copies the sheet into `assets/mychibi/`, autodetects frame dimensions, and writes a `manifest.json` wired with all the standard animations. Restart the daemon — your chibi appears in the **Roles** tray submenu, ready to be assigned to any slot.

### Sprite-sheet layout

There are **only four animations the daemon actually needs:** `idle`, `alert`, `thinking`, `reviewing`. Everything else is optional polish.

Defaults assume an **8-column × 9-row** grid (matches the bundled sheets). Recommended row mapping:

| Row | Animation(s) | Required? | Notes |
|---|---|---|---|
| 0 | `idle`, `sleeping` | ✅ required | standing pose |
| 3 | `spawn_in`, `spawn_out` | recommended | subagent wave-in / wave-out |
| 5 | `alert` | ✅ required | panic / error reactions |
| 6 | `eating` | optional | for any **special / personality row** your chibi has (snack break, dance, anything one-of-a-kind) |
| 7 | `thinking`, `working`, `writing` | ✅ required | at the keyboard |
| 8 | `reviewing`, `planning` | ✅ required | at the whiteboard / notes |

**Rows 1, 2, and 4 are unused** — they were originally `running-right`, `running-left`, and `jumping`, but the daemon never plays them, so the installer skips them. If your sheet has frames there, they just sit unused on disk (no harm). If you don't have those rows at all, no problem either.

If your sheet uses a different grid, pass `--cols` and `--rows`:

```powershell
python tools/add_chibi.py add sheet.png "Cleo" --cols 6 --rows 5 --fps 4
```

### Other commands

```powershell
python tools/add_chibi.py preview path\to\sheet.webp   # save a frame-numbered grid overlay (helps debug indices)
python tools/add_chibi.py list                         # show every installed chibi
python tools/add_chibi.py remove "MyChibi"             # delete a chibi
```

For full schema details (custom animations, non-standard layouts), see [assets/README.md](assets/README.md).

---

## 🗺 Project layout

```
Chibi-Agents/
├── daemon/              # PyQt6 overlay + HTTP server + token tracker
├── hook/                # Claude Code hook entrypoint + classifier
├── assets/              # Sprite sheets and manifests (one folder per chibi)
├── examples/            # Fake-event scripts for testing without Claude
├── tools/
│   ├── install_hooks.py  # Auto-wire hooks into ~/.claude/settings.json
│   └── add_chibi.py      # Install / list / preview / remove chibis
├── start-chibi.vbs      # Launch daemon hidden
├── start-chibi.bat      # Launch daemon with visible console
└── stop-chibi.bat       # Stop the daemon
```

---

## 🚧 Roadmap

Planned additions, no specific dates:

- **🖥 Cross-platform support** — macOS and Linux ports of the overlay (replace the Win32 DWM calls and `.vbs` launcher with platform-equivalent paths).
- **🧑‍🤝‍🧑 More chibis** — a growing roster of character sheets shipped in `assets/`, plus a community gallery for sharing custom ones.
- **🤝 Smoother task delegation** — the main chibi and subagents narrate their handoff in real conversational dialogue, with context-aware lines pulled from the active session.
- **🌐 Other LLM CLIs** — wrappers for [Codex](https://github.com/openai/codex), Gemini CLI, and any tool that exposes hook-like events. Drop-in adapters that POST to the same daemon endpoint, so a single chibi can react to whichever assistant you're using.
