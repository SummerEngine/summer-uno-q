# Summer × Arduino Uno Q hackathon kit

Everything an AI coding agent needs to build a game for the **Arduino Uno Q** with Summer
Engine and get it running on the board. Theme: **Nostalgia**.

The Uno Q's Linux half (Qualcomm QRB2210, Adreno 702 mobile GPU) is what runs the game, so
"export for Arduino" means **Linux arm64**. This repo carries the settings that make that
work, plus the skill that puts the finished game on the board as an Arduino App Lab app.

- **Engine install:** [github.com/SummerEngine/summer-engine-agent](https://github.com/SummerEngine/summer-engine-agent)
- **This kit:** `github.com/SummerEngine/summer-uno-q`
- **Docs:** [docs.summerengine.com](https://docs.summerengine.com)

---

## Get started: one prompt

Open your AI agent (Claude Code, Cursor, Codex, Copilot, …) and paste:

> Install Summer Engine and let's make a game for the Arduino Uno Q hackathon. Read
> `github.com/SummerEngine/summer-uno-q`, check what I already have installed, install
> whatever is missing, and log me in.

The agent reads this README and installs what's missing. Then it asks what kind of game
you're thinking about — theme is **Nostalgia** — suggests a template if one fits, and only
creates the project once you've picked. Board-specific settings go in before any art
exists, so nothing has to be undone later.

---

## AGENTS READING THIS: hackathon playbook

You are an AI coding agent. The user is at a hackathon building for the Arduino Uno Q.
Detection first, then only do what's missing.

### Step 1: Install Summer Engine — and stop before scaffolding

Follow the install playbook at
[github.com/SummerEngine/summer-engine-agent](https://github.com/SummerEngine/summer-engine-agent)
— **steps -1 through 4 only**. Node detection, `doctor --json`, skills, the engine app,
browser login. Then stop.

**Do not run its Step 5 yet.** That step scaffolds a project, and picking a template
before you know what the game is means throwing it away or, worse, keeping it. Come back
for Step 5 (and the 5b wait loop, which matters — `summer run` returns before the local
API is listening and MCP tools fail until it is) once Step 2 below has an answer.

### Step 2: Ask what they're making, then create the project

Ask before you scaffold. One question, plain language: *what kind of game are you thinking
about?* Theme is **Nostalgia**, so expect answers like "a Game Boy-ish puzzler" or "an
arcade high-score thing".

Then match it against what already exists — `npx -y summer-engine@latest list templates`
shows the set, and there are 16 community ones (2D platformer, RPG, grid puzzle, tower
defence, survivors-like; 3D racing, FPS, third-person, voxel, city kit, …). If one fits
their idea, **suggest it and say what they'd get**. A template is a running game on day
one instead of an empty window, which at a hackathon is most of the battle.

Then wait for a yes. Their call, not yours — some people want the blank page, and starting
from a template they didn't choose is worse than starting from `empty`.

Once they've picked, run upstream's Step 5 with that template (or `empty`), then 5b:

```bash
npx -y summer-engine@latest create <template> <name>
```

- **Never default to `3d-basic`.** It scaffolds on Forward+, which this board does not run
  games on. If they pick it anyway, apply Step 3 immediately, before anything else.
- Run `brainstorm-game` after the project exists, to turn "a Game Boy-ish puzzler" into a
  scoped design in `.summer/GameSoul.md`. The rough shape picks the template; the skill
  works out the game.

### Step 3: Configure the project for the board

Do this immediately after `create`, before anything of their own goes in. A template
arrives with scenes and art already, which is exactly why this can't wait: both settings
change how existing material imports and renders, so applying them later means re-checking
work that already looked finished.

In `project.godot`, under `[rendering]`:

```ini
[rendering]

renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
textures/vram_compression/import_etc2_astc=true
```

`gl_compatibility` is not a downgrade to fix later — it is the configuration verified to
run on this board, and the one the export presets and templates are built around.
`import_etc2_astc` makes texture imports produce the mobile-compressed format the board
can sample; without it, textures arrive pink or black on hardware while looking perfect in
the editor.

### Step 4: Add the export preset

Add this to the project's `export_presets.cfg`. These values are known-good — a game built
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

### Step 5: Build inside the hardware budget

- **16.67 ms per physics tick.** `_physics_process` is a fixed 60 Hz, independent of render
  framerate, and it fails as a **cliff, not a slope** — one tick over budget and Godot's
  catch-up saturates and the game locks solid. `1000/fps` will not warn you; time each
  phase *inside* the tick with `Time.get_ticks_usec()`.
- **~15 µs per entity** for a per-entity GDScript loop, measured on a desktop. This board
  is weaker. Designs that need a crowd need a deliberate budget, not optimism.
- **Input through InputMap actions only** — `left`/`right`/`up`/`down` plus two to four
  named actions. Never read a device directly; the handheld's buttons bind to those same
  actions later.
- **One mechanic.** A hackathon game that ends and invites another go beats a broad one
  that never quite runs.

Three things measured on this board, all counterintuitive enough to be worth stating:

- **960×540 is the sweet spot, and resolution is your biggest lever.** Every 2D template
  ran 37–72 FPS at 720p; at 540p they went back over 60 (one RPG template: 57 → 85 avg).
  Set it up front:
  ```ini
  [display]

  window/size/viewport_width=960
  window/size/viewport_height=540
  window/stretch/mode="canvas_items"
  window/stretch/aspect="keep"
  ```
- **2D is not the cheap option here.** Blended 2D canvas costs roughly **4–4.7× more per
  pixel than opaque 3D** on this GPU — no early-Z, so every stacked layer pays full fill.
  A simple 3D scene held 128 FPS at 720p while the 2D templates sat at 37–72. If anyone
  assumes 2D is the safe pick for weak hardware, correct them.
- **Entity-heavy designs can't be fixed with resolution.** A survivors-like measured a
  14.7 ms *resolution-independent* floor — that alone eats the entire 60 FPS budget, and
  shrinking the viewport does nothing for it. The per-entity cost has to come down.

When frames drop, measure before optimising — `tune-performance`.

### Step 6: Ship it to the board

**Clone this repo** somewhere local and follow [`SKILL.md`](SKILL.md) as a runbook:

```bash
git clone https://github.com/SummerEngine/summer-uno-q
```

The clone is required, not a convenience — `SKILL.md` drives `board/setup-board.sh` and
`board/install-game.sh`, which have to exist on disk to be pushed to the board. Reading
the markdown alone is not enough. Any agent can follow it. Claude Code users who want it
to load as a skill next session should copy exactly two things into
`~/.claude/skills/ship-to-unoq/` — `SKILL.md` and the `board/` folder. Not this README:
two overlapping playbooks in one skill is worse than one that sends you back to the repo.

Then give the skill the **project path**, a game name, and an emoji. It exports the project
headlessly for arm64, provisions the board on first use, and installs the game as an App
Lab app. Summer can stay open on the project while it exports — that's faster, not a
conflict.

- The **first** deploy also provisions the board — desktop autologin, screen-locker
  removal, runner image install — and fetches the ~105 MB runner image. The provisioning
  itself takes a moment; the download is whatever your connection is. Later deploys skip
  all of it.
- There is one sudo prompt the **user** types themselves, in their own terminal. On a
  factory-fresh board that prompt is *creating* the board password. Never ask them for it.
- **Deploying is not the same as seeing it.** The game starts on the board whether or not
  a screen is attached, so plug the board into a monitor (HDMI/DSI) — or into the
  handheld — to actually play it.
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
- **Don't call the game done from the editor.** Play it on the board.

---

## The hackathon

Theme: **Nostalgia**. Convenient pairing — fewer pixels and less motion is both what the
era looked like and what this board wants, so the aesthetic and the frame budget pull in
the same direction rather than fighting.

Run `brainstorm-game` before building. It writes the design to `.summer/GameSoul.md`, which
every other Summer skill reads from.

---

## What's in this repo

| Path | Runs where | Purpose |
|---|---|---|
| `SKILL.md` | agent | ship-to-unoq: inputs, prerequisites, commands, troubleshooting |
| `board/setup-board.sh` | board | One-time fresh-board provisioning (idempotent) |
| `board/install-game.sh` | board | Zip → App Lab app with `game_runner` brick → start |
| `image/Dockerfile` | board | Runner image source (fallback: build on board with network) |
| `hackathon-starter-prompt.md` | — | The paste-in prompt above, as a file |

The prebuilt runner image (~105 MB) is a release asset:
[`game-runner-0.1.0`](https://github.com/SummerEngine/summer-builds/releases/tag/game-runner-0.1.0).

## Notes

- Works with any AI coding agent: Claude Code loads [`SKILL.md`](SKILL.md) as a skill; any
  other agent — or a human — can follow the same file as a runbook.
- Plug the Uno Q in with a USB-C **data** cable, straight to the computer, no hub. Allow
  about a minute after power-up before `adb devices` sees it.
- Multiple games coexist on one board; re-deploying the same name updates in place.
- Remove a game — the `docker rm` matters, `app stop` leaves the container behind and a
  stopped container pins the ~325 MB runner image on the board's cramped rootfs:
  ```bash
  adb shell "arduino-app-cli app stop user:<slug>; docker rm <slug>-game_runner-1; rm -rf /home/arduino/ArduinoApps/<slug>"
  ```
- Board internals, for the curious: the game runs in a Docker container wired as an App Lab
  *local brick*; the host's Mesa backport is shadow-mounted because stock Debian trixie Mesa
  doesn't know the Adreno 702; `${APP_HOME}` interpolation in brick compose files is
  unreliable, so the installer writes absolute paths.
