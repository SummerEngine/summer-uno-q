# Summer × Arduino Uno Q

Everything an AI coding agent needs to build a game for the **Arduino Uno Q** with Summer
Engine and get it running on the board.

Built for the AI Game Console Hackathon, and just as useful for anyone making a game for
their own Uno Q.

The Uno Q's Linux half (Qualcomm QRB2210, Adreno 702 mobile GPU) is what runs the game, so
"export for Arduino" means **Linux arm64**. This repo carries the settings that make that
work, plus the skill that puts the finished game on the board as an Arduino App Lab app.

- **Engine install:** [github.com/SummerEngine/summer-engine-agent](https://github.com/SummerEngine/summer-engine-agent)
- **This kit:** `github.com/SummerEngine/summer-uno-q`
- **Docs:** [docs.summerengine.com](https://docs.summerengine.com)

---

## Get started: one prompt

Open your AI agent (Claude Code, Cursor, Codex, Copilot, …) and paste:

> Install Summer Engine and let's make a game for the Arduino Uno Q. Read
> `github.com/SummerEngine/summer-uno-q`, check what I already have installed, install
> whatever is missing, and log me in.

The agent reads this README and installs what's missing. Then it asks what kind of game
you're thinking about, suggests a template if one fits, and only creates the project once
you've picked. Board-specific settings go in before any art exists, so nothing has to be
undone later.

---

## AGENTS READING THIS: playbook

You are an AI coding agent. The user is building a game for the Arduino Uno Q.
Detection first, then only do what's missing.

**This repo has two documents and you will need both.** This README is the build
playbook — install, project settings, export preset, performance. [`SKILL.md`](SKILL.md)
is the deploy runbook: it exports the game and puts it on the board, and it is the only
thing that should ever talk to the hardware. Steps 1–5 below are yours; Step 6 hands off
to `SKILL.md`. Read it when you get there rather than improvising `adb` commands.

### Step 1: Install Summer Engine — and stop before scaffolding

Follow the install playbook at
[github.com/SummerEngine/summer-engine-agent](https://github.com/SummerEngine/summer-engine-agent)
— **steps -1 through 4 only**. Node detection, `doctor --json`, `setup <agent>` (skills plus
the MCP server entry), the engine app, browser login. Then stop.

Two things that playbook leaves to you:

- **`setup` takes the name of the agent you are running as** — `claude-code`, `cursor`,
  `codex`, … — and you run it even when `doctor` is all green. `doctor` checks the
  machine, not your session: its MCP checks prove the server *can* start, not that *your*
  tool host has it. A green doctor with no Summer tools in your session is the normal
  failure, not a rare one.
- **Prove the MCP connection before any other work.** Call one harmless tool,
  `summer_is_running`, and read what happens:
  - **The tool does not exist in your session** — the config was written but your host
    loaded its tool list at startup and has not re-read it. Nothing you run fixes that.
    Tell the person, in one line, to restart their editor or agent app, then call the tool
    again once they are back. Do not start Step 2 without it: every build skill assumes
    these tools, and without them you will hand-write scenes, invent results, and be
    unable to generate a single asset.
  - **The tool exists but answers that no editor or local API is reachable** — that is
    fine for now. It proves the wiring; the editor starts in Step 5.
  - **It answers** — you are connected. Carry on.

  Run the same check once more right after Step 5b, when the project is up: a
  `summer_get_project_context` that returns the project is the green light to build. If
  it fails there, the 5b wait loop has not finished — keep waiting, do not start writing.

**Do not run its Step 5 yet.** That step scaffolds a project, and picking a template
before you know what the game is means throwing it away or, worse, keeping it. Come back
for Step 5 (and the 5b wait loop, which matters — `summer run` returns before the local
API is listening and MCP tools fail until it is) once Step 2 below has an answer.

### Step 2: Ask what they're making, then create the project

Ask before you scaffold. One question, plain language: *what kind of game are you thinking
about?* Expect a rough shape rather than a design — "a Game Boy-ish puzzler", "an arcade
high-score thing", "a little racer".

**The controller is decided before the game is: a joystick and three buttons, printed
A, B and C.** That is the entire input surface. Every mechanic, menu, and interaction must
be playable with those four controls and nothing else: no mouse, no text entry, no fourth
button. The controls reach the game as keystrokes and Step 5 has the exact bindings, but
those key names are plumbing — **call them the joystick and buttons A/B/C whenever you
speak to the person, from this question onward.** Treat it the way a Game Boy dev treated
four directions and two buttons — a creative constraint to design *into* from the first
idea, not a port target for later. If a proposed mechanic needs more inputs, reshape the
mechanic now; carry this constraint into `brainstorm-game` so the design never drifts off
the pad.

Then match it against what already exists — `npx -y summer-engine@latest list templates`
shows the set, and there are 16 community ones (2D platformer, RPG, grid puzzle, tower
defence, survivors-like; 3D racing, FPS, third-person, voxel, city kit, …). If one fits
their idea, **suggest it and say what they'd get**. A template is a running game on day
one instead of an empty window, which is most of the battle.

Then wait for a yes. Their call, not yours — some people want the blank page, and starting
from a template they didn't choose is worse than starting from `empty`.

Once they've picked, run upstream's Step 5 with that template (or `empty`), then 5b:

```bash
npx -y summer-engine@latest create <template> <name>
```

- **`3d-basic` is fine to suggest for a 3D game, but it arrives unconfigured**: Forward+
  renderer (which this board cannot run) and no `[display]` block at all. That is not a
  reason to avoid it — Step 3 converts it in a minute — it is a reason Step 3 must run
  before anything else goes in, including the 3D profile and the display block.
- Run `brainstorm-game` after the project exists, to turn "a Game Boy-ish puzzler" into a
  scoped design in `.summer/GameSoul.md`. The rough shape picks the template; the skill
  works out the game.

### Step 3: Configure the project for the board

**Steps 3 and 4 are not questions.** The person chose a game; they did not choose a renderer,
a resolution or an export target, and asking them to is asking them to know the board.
Apply everything in these two steps the moment the project exists, then tell them in one
line what you did — "Set the project up for the Uno Q" is plenty. The only time a value here
is up for discussion is when the person explicitly asks for a different one.

Do this immediately after `create`, before anything of their own goes in. A template
arrives with scenes and art already, which is exactly why this can't wait: these settings
change how existing material imports and renders, so applying them later means re-checking
work that already looked finished.

In `project.godot`, under `[rendering]`:

```ini
[rendering]

renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
textures/vram_compression/import_etc2_astc=true
```

**A 3D game needs five more lines in that same block.** Skip them entirely for 2D:

```ini
lights_and_shadows/directional_shadow/size=1024
lights_and_shadows/directional_shadow/soft_shadow_filter_quality=0
scaling_3d/mode=0
scaling_3d/scale=0.7
shading/overrides/force_vertex_shading=true
```

Godot's defaults assume a desktop GPU, and a Linux arm64 export never carries the `mobile`
feature tag — so without these the board renders with a 4096 shadow map and soft filtering on
a phone-class GPU. Measured on a stock 3D scaffold: 34 fps without these lines, 82 with.
What each line buys, and what to try when a 3D game is still slow, is in Step 5.
**Never enable `msaa_3d`** — it is catastrophic on this GPU. And don't try to inherit the
engine's `.mobile` values by putting `mobile` in the preset's `custom_features`: that tag also
flips `OS.has_feature("mobile")`, and a game that checks it switches to touchscreen controls
on a handheld with physical buttons.

Under `[application]`:

```ini
run/max_fps=60
```

And under `[display]`:

```ini
[display]

window/size/viewport_width=960
window/size/viewport_height=540
window/stretch/mode="viewport"
```

`max_fps=60` is about pacing, not thrift: a game that oscillates between 60 and 98
against a 60 Hz screen microstutters; locked at 60 it feels smoother than the higher
average ever did.

**The design resolution IS the render resolution — cap it at 960x540.** Games launch
fullscreen, and with `stretch/mode="viewport"` the game renders at the design size and
scales to whatever screen is attached, so the frame cost never depends on the monitor.
Any other configuration renders at screen resolution: this board manages roughly 38 fps
pushing a 2D canvas at 1080p and 60+ at 960x540 — and while the jam's handheld screen
is small, the same game plugged into a TV afterwards must not fall off a cliff.
Pixel-art games should go lower still (480x270), or keep 960x540 and render the world
through a `SubViewportContainer` with `stretch_shrink=2` for fat pixels under a
crisp HUD.

`gl_compatibility` is not a downgrade to fix later — it is the configuration verified to
run on this board, and the one the export presets and templates are built around.
`import_etc2_astc` makes texture imports produce the mobile-compressed format the board
can sample; without it, textures arrive pink or black on hardware while looking perfect in
the editor.

### Step 4: Add the export preset

Add this to the project's `export_presets.cfg` — again without asking; a game that cannot
export for the board is not a game for the board. These values are known-good — a game built
with exactly this preset runs on a real board.

**Check for existing presets first.** Most templates already ship an `export_presets.cfg`
with a `[preset.0]` named "Linux" — the community 2D templates all do. **Append** using the
next free index instead of overwriting it, and keep both headers in step: if the file
already ends at `[preset.0]`, yours is `[preset.1]` **and** `[preset.1.options]`. Two
sections with the same index is a malformed file, and which one wins is anyone's guess.

```ini
[preset.0]

name="Linux arm64 (Uno Q)"
platform="Linux"
runnable=true
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="build/game-linux-arm64.zip"
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.0.options]

custom_template/debug=""
custom_template/release=""
debug/export_console_wrapper=0
binary_format/embed_pck=false
binary_format/architecture="arm64"
texture_format/s3tc_bptc=false
texture_format/etc2_astc=true
ssh_remote_deploy/enabled=false
```

The lines that matter: `architecture="arm64"` (the board is aarch64), `etc2_astc=true` and
`s3tc_bptc=false` (mobile GPU texture formats — the desktop defaults are the exact
inverse), and **`embed_pck=false`**.

`embed_pck` must be off. The installer expects the binary and the `.pck` as two files and
refuses a build without a separate pck. Embedding also inflates one file past App Lab's
**100 MB per-file import limit** on any game with real assets, which breaks sharing the app
as a drag-and-drop zip — split out, the binary stays a fixed ~70 MB and only the pck grows.

Export **release**, to a **`.zip`**. Debug builds are larger and slower, and this board
has no headroom to spare.

You don't export by hand — the `ship-to-unoq` skill does it for you (Step 6). This preset
is what it looks for, which is why it goes in at scaffold time.

### Step 5: Controls, presentation and performance

2D games run well on this board, and light 3D is fine too — provided Step 3's `[display]`
block and, for 3D, its profile are in place. Everything below is about what the player
holds and sees.

**Everything runs on keyboard — gameplay AND every menu.** Buttons wired to the board
arrive as keystrokes, and there is no mouse in a player's hands. Title screen, pause,
game over, level select: all of it must work with the keyboard alone. A mouse-only
"Play" button is a game nobody can start. In practice: `grab_focus()` the first button
of every menu when it appears, set focus neighbors, and **add W/A/S/D to the built-in
`ui_up`/`ui_down`/`ui_left`/`ui_right` actions and J to `ui_accept`** (Project Settings
> Input Map) — the handheld's joystick sends WASD, and Godot's menu focus listens to the
`ui_*` actions, not raw keys. Walk every screen start-to-finish with only WASD + J
before calling it done.

**Bind exactly the handheld's keys — this is the controller, decided before the first
line of gameplay code:**

| Physical control | Key the game must bind |
|---|---|
| Joystick | **W / A / S / D** — fixed, not remappable. Bind arrow keys too, as aliases of the same actions |
| Button A | J |
| Button B | K |
| Button C | L |

**Every word anyone reads names the handheld's controls, never the keys.** J/K/L and
W/A/S/D are the wires under the floor; the person is holding a joystick and three buttons
printed **A**, **B**, **C**. This covers your own messages while building, every tutorial
line, HUD hint, button prompt and menu label, and the game's Controls screen — all of it
says the control the way the player sees it:

| Write this | Not this |
|---|---|
| "Press **A** to jump" | "Press J to jump" |
| "**B** swings, **C** pauses" | "K swings, L pauses" |
| "Move with the **joystick**" | "Move with WASD" / "arrow keys" |
| "the joystick and three buttons" | "a D-pad plus J/K/L" |

A game may *also* mention the keyboard for people playing it on a laptop later, but the
handheld's names come first.

**Hide the mouse pointer in code** — one line in any autoload's `_ready()`:

```gdscript
Input.set_mouse_mode(Input.MOUSE_MODE_HIDDEN)
```

A handheld has no mouse, so X's pointer just sits on top of the game as screen litter.
This hides it for the game's window only — it comes back the moment the game exits.
It must be code: the `display/mouse_cursor/custom_image` project setting gets stripped
from `project.godot` by the editor's settings pass on export, and no window/video mode
hides the pointer on this board (verified — exclusive fullscreen still shows it).

Why J/K/L and not letters near WASD: the same game plays on a PC keyboard too (left hand
WASD, right hand JKL), and action keys must never collide with movement keys. Control
changes go through the agent: prefer rebinding the game's own Input Map; if a binding truly
can't match, the deploy skill (`SKILL.md`, "Modulino input") has a config-file remap.

**Tuning the 3D profile.** The shadow lines carry most of the win and cost only harder
shadow edges — don't reach for `shadow_enabled=false` instead, which looks worse and gains
less than shrinking the map. `scaling_3d` renders the 3D scene at 70% while UI and text stay
full resolution; prefer it over dropping the design resolution again, which softens the HUD
too. `force_vertex_shading` gains the least and changes the look the most, so it is the
first to drop if the lighting reads wrong. `size=2048` is the engine's own mobile default,
worth offering if shadows look coarse.

**`.glb`/`.gltf` scenes plus a shadow-casting Omni or SpotLight need
`meshes/create_shadow_meshes=false` on those imports.** Shadow-mesh surfaces carry no
material of their own and the GLES3 renderer asks for one anyway, once per surface per
shadow light per frame: the log floods with `ERROR: Parameter "material" is null` from
`gles3/storage/material_storage.cpp` and the scene crawls. A directional light alone never
triggers it.

**Texture import settings are a transfer-size and load-time fix, not a frame-rate fix.**
`compress/mode=2`, `mipmaps/generate=true` and `process/size_limit=1024` cut the zip and the
board's memory use substantially and buy no frames — don't reach for them when the
complaint is frame rate.

If a 3D game still drops frames after Step 3's profile, work out which kind of slow it is
before touching settings again. The profile fixes fill rate and shading; it does nothing for
draw calls, transparent overdraw or per-frame GDScript. A scene drawing thousands of small
meshes — one draw call each — sits in single digits while barely using the CPU, and no setting
moves it. That needs fewer draw calls, fewer particles and cheaper generation, not another
settings pass.

If frames drop, measure before optimising — `tune-performance`.

### Step 6: Ship it to the board

**Clone this repo somewhere stable** — not a temp folder. `SKILL.md` drives
`board/setup-board.sh` and `board/install-game.sh`, which have to exist on disk to be
pushed to the board, so reading the markdown alone is not enough:

```bash
git clone https://github.com/SummerEngine/summer-uno-q ~/summer-uno-q
```

**Then register it with the tool**, so it's still there in the next chat instead of
something you re-explain every session. Do the one that matches:

**Claude Code** — copy the skill directory:

```bash
mkdir -p ~/.claude/skills/ship-to-unoq
cp -r ~/summer-uno-q/SKILL.md ~/summer-uno-q/board ~/.claude/skills/ship-to-unoq/
```

Copy those two things only. Not this README — two overlapping playbooks inside one skill
is worse than one that sends you back to the repo.

**Cursor** — write `.cursor/rules/ship-to-unoq.mdc` in the game project:

```markdown
---
description: Deploy a Summer Engine game to an Arduino Uno Q over USB
alwaysApply: false
---

To put the game on the board, follow ~/summer-uno-q/SKILL.md exactly, including the
scripts in ~/summer-uno-q/board/. Do not improvise adb or docker commands.
```

**Codex** — add the same pointer to `AGENTS.md` in the game project, or to
`~/.codex/AGENTS.md` to have it everywhere:

```markdown
## Deploying to the Arduino Uno Q

Follow ~/summer-uno-q/SKILL.md exactly, including the scripts in ~/summer-uno-q/board/.
Do not improvise adb or docker commands.
```

Use absolute paths in the pointer, not relative ones: the agent's working directory is the
game project, not the clone.

Then give the skill the **project path**, a game name, and an emoji. It exports the project
headlessly for arm64, provisions the board on first use, and installs the game as an App
Lab app. Summer can stay open on the project while it exports — that's faster, not a
conflict.

- The **first** deploy also provisions the board — desktop autologin, screen-locker
  removal, the runner image, the Modulino input service and its offline kit. The ~105 MB
  runner image downloads to the laptop first and is pushed over USB, so the board itself
  needs no network. Later deploys skip all of it.
- On a verified factory image, provisioning needs no App Lab onboarding and no board
  password. The reviewed setup helper uses the factory `arduino` user's existing
  root-equivalent Docker access only for the required host operations. See
  [`docs/passwordless-provisioning.md`](docs/passwordless-provisioning.md) for the
  mechanism, security boundary, exact flow, and verification gates.
- **Deploying is not the same as seeing it.** The game starts on the board whether or not
  a screen is attached, so plug the board into a monitor (HDMI/DSI) to actually play it.
- **Nothing counts as working until it has been played on the board** — on a screen, with
  hands on the controls. `running` is not a playtest and neither is a clean type check.

### Anti-patterns (do NOT do these)

- **Don't leave the project on `forward_plus`.** It looks fine in the editor and fails on
  the board. `3d-basic` ships with it.
- **Don't export with debug.** Bigger, slower, and this board has no headroom to spare.
- **Don't export x86_64.** The board is aarch64; the installer rejects the wrong binary.
- **Don't copy the desktop texture defaults.** `s3tc_bptc=true` / `etc2_astc=false` is the
  desktop preset and the exact inverse of what this board needs.
- **Don't improvise `adb`, `docker`, `apt`, or SSH repairs on the board.** Use the skill's
  scripts. An agent improvising on hardware can burn a team's whole day, and the damage
  shows up looking like a game bug.
- **Don't ask permission for Steps 3 and 4.** "Shall I switch to 960×540 and add the arm64
  preset?" hands the person a decision they have no basis to make. Apply, then mention.
- **Don't report settings as results.** `max_fps=60` is a ceiling, not a frame rate;
  `etc2_astc=true` is an import setting, not a texture that has been seen working;
  "Uno Q-ready" is something only the board can say. Until it has run there, say what you
  configured — "set to 960×540 with a 60 fps cap" — never what it achieves.
- **Don't call the game done from the editor.** Play it on the board.

---

## Design

Run `brainstorm-game` before building. It writes the design to `.summer/GameSoul.md`, which
every other Summer skill reads from.

If the game is being made for an event with a theme, that comes from the person — take it
from what they tell you, don't assume one.

---

## What's in this repo

| Path | Runs where | Purpose |
|---|---|---|
| `SKILL.md` | agent | ship-to-unoq: inputs, prerequisites, commands, troubleshooting |
| `board/setup-board.sh` | board | One-time fresh-board provisioning (idempotent) |
| `board/install-game.sh` | board | Zip → App Lab app assembled from the `game_runner` brick and the bridge files → start |
| `board/bridge/` | board | Arduino's Modulino HID bridge, vendored verbatim — see its `ATTRIBUTION.md` |
| `image/Dockerfile` | board | Source of the prebuilt runner image — GL/EGL, X11, audio libs |
| `kit/` | maintainer | Offline provisioning artifacts, committed so a fresh clone is a complete kit — see Kit prep below |
| `docs/passwordless-provisioning.md` | maintainer | No-App-Lab/passwordless factory-board mechanism, security notes, and verification |
| `docs/startup-performance.md` | maintainer | Measured cold-boot timeline, compile/upload bottleneck, and proposed fast path |

The prebuilt runner image (~105 MB) is a release asset:
[`game-runner-0.1.0`](https://github.com/SummerEngine/summer-builds/releases/tag/game-runner-0.1.0).

## Kit prep (maintainers)

Two offline artifacts are committed in `kit/` so a fresh clone works on a board with
no network. Regenerate them only when the pinned versions change:

- `kit/python3-evdev.deb` — on any Debian trixie arm64 (the board works):
  `apt-get download python3-evdev`, then `adb pull` the deb and rename it to
  `kit/python3-evdev.deb` — the push flow and setup script expect that fixed name.
  Verify with `dpkg -I kit/python3-evdev.deb` that Depends lists only python3/libc
  packages the board already has.
- `kit/arduino15-libs.tar.gz` — from a board that has built the bridge sketch once:
  `tar -czf arduino15-libs.tar.gz -C /home/arduino .arduino15/internal` and pull.
  This warms the library cache so the first deploy builds offline; the zephyr
  platform itself is assumed factory-present (verified against a used board only —
  re-check on a factory-fresh one).

## Notes

- Works with any AI coding agent. [`SKILL.md`](SKILL.md) loads as a skill in Claude Code
  once copied into the skills directory (Step 6); everywhere else — and for a human — it
  reads as a runbook.
- Plug the Uno Q in with a USB-C **data** cable, straight to the computer, no hub. Allow
  about a minute after power-up before `adb devices` sees it.
- Multiple games coexist on one board; re-deploying the same name updates in place.
- **Modulino controllers:** every deployed game gets input from attached Modulino
  buttons and a joystick for free, delivered as ordinary keyboard events — see
  `SKILL.md`'s "Modulino input" section for the key map, how remaps work, and
  troubleshooting. The bridge is Arduino's, vendored verbatim in `board/bridge/`;
  see `board/bridge/ATTRIBUTION.md`.
- Remove a game — the `docker rm` matters, `app stop` leaves the container behind and a
  stopped container pins the ~325 MB runner image on the board's cramped rootfs:
  ```bash
  adb shell "arduino-app-cli app stop user:<slug>; docker rm <slug>-game_runner-1; rm -rf /home/arduino/ArduinoApps/<slug>"
  ```
- Board internals, for the curious: the game runs in a Docker container wired as an App Lab
  *local brick*; the host's Mesa backport is shadow-mounted because stock Debian trixie Mesa
  doesn't know the Adreno 702; `${APP_HOME}` interpolation in brick compose files is
  unreliable, so the installer writes absolute paths.
