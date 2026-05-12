# Assets

Each chibi lives in its own folder:

```
assets/
  main/                 # main agent (Claude itself)
  explore/              # Explore subagent
  plan/                 # Plan subagent
  general-purpose/      # general-purpose subagent
  _default/             # fallback for any unknown agent_type
```

Each folder needs two files:

- `sheet.png` — a sprite sheet laid out in a fixed grid.
- `manifest.json` — declares `frame_width`, `frame_height`, `fps`, and an `animations` map.

Required animations: `idle`, `thinking`, `reviewing`, `writing`, `planning`, `working`, `alert`, `sleeping`, `spawn_in`, `spawn_out`.

Frame indices are zero-based in row-major order. Drop your sheet in; the loader handles the rest.

`spawn_out` should set `"despawn": true` so the window closes when the animation ends. `spawn_in` should set `"next": "idle"` so it transitions in after spawning.

The folder name is matched against the Claude Code `subagent_type` lowercased with underscores/spaces converted to hyphens — e.g. agent `Explore` → folder `explore`, `general-purpose` → folder `general-purpose`.
