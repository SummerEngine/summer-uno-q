---
name: ship-to-unoq
description: Export a Summer Engine game for Linux arm64 and deploy it to an Arduino Uno Q over USB. Use when the user wants to put their game on the Arduino/Uno Q/handheld, deploy to the board, or update a game already on it. Input is the path to their project; the skill exports it headlessly, provisions a fresh board on first use, installs the game as an Arduino App Lab app, and starts it.
---

# Ship a Summer Engine game to the Arduino Uno Q

You are taking a Summer Engine project, exporting it for **Linux arm64**, and
deploying it to an Arduino Uno Q plugged into this computer via USB-C. The game
becomes an **Arduino App Lab app** (visible in App Lab's "My Apps" with a name and
emoji icon, start/stoppable there) running GPU-accelerated in a container on the
board.

You export on the host; everything board-side is done by two scripts in this skill's
`board/` folder. Your job is orchestration: get the inputs, export, check
prerequisites, push, run, and translate errors. **Board-side, do not improvise —
never hand-assemble the app folder, brick files, or container config; the scripts
are the product.** The host-side export below is yours to run.

**Paths:** `board/...` in the commands below refers to this skill's own directory
(where this SKILL.md lives) — resolve it to an absolute path before running, since
your working directory is the user's project.

## Before anything: has the board had its own first-time setup?

The Uno Q ships with its own out-of-box setup — board name, password, Wi-Fi — and it is
the person's to do, not yours. It happens in **Arduino App Lab on their laptop**, with the
board plugged in over USB-C. Nothing here works until it is done.

**Check it yourself, then ask only if something is missing.** Two commands, and they are
worth running before every first deploy rather than trusting anyone's memory:

```
adb shell "test -f /home/arduino/.summer-hackathon-setup && echo provisioned"
adb shell "ip -4 addr show wlan0" | grep inet
```

Keep the quotes exactly as written. Unquoted, a Git Bash / MSYS shell on Windows rewrites
the path and answers `test: C:/Program: binary operator expected`, which reads like a
board problem and is not one.

- **Marker present** — this board has been through everything already; skip to Deploy.
- **`wlan0` has an address** (e.g. `inet 10.20.10.8/24`) — the wizard was completed. Carry
  on with the rest of this skill.
- **No address** — the board is not on Wi-Fi, whatever the person believes. Stop and ask;
  do not push files or run setup first.

Wi-Fi is not optional here. A board that is not connected keeps showing its own setup
prompt on screen, over whatever else is running, and a game set to launch at boot does not
come up. It is also the one part of this you cannot do for them.

**Send this list exactly as written.** The numbering matches the order App Lab's wizard
asks in, and the Wi-Fi line carries the warning people most need. Do not summarise it,
reorder it, or add steps of your own:

> Before I can put anything on the board, it needs its own one-time setup — a couple of
> minutes in Arduino App Lab on your laptop ☀️
>
> 1. Install and open **Arduino App Lab**, then plug the board in over USB-C.
> 2. Give the board a name.
> 3. **Connect it to Wi-Fi.** Don't skip this one: without it the board keeps its setup
>    prompt on screen and your game won't start on its own.
> 4. Set a password — **remember it**, you'll type it once more later.
>
> Say when it's done and I'll take it from there.

Then wait, and when they say it is done, run the `wlan0` check again rather than taking
their word for it. Still no address means the Wi-Fi step specifically was skipped or did
not take — say that, rather than pressing on into a setup that will fail. If the check
passes but `adb shell hostname` still answers `uno-q`, the wizard was closed early;
everything else works, so mention it once and continue.

The same check is worth a second look if a board that used to boot straight into its game
stops doing so: Wi-Fi it has lost has the same effect as Wi-Fi it never had.

## Inputs to collect from the user

1. **Path to the project** (the folder containing `project.godot`). **Always export it
   fresh** — see Export below. The only exception is the user explicitly saying they
   already exported and want that zip used; then take their zip path and skip Export.

   **Never decide for yourself that an existing zip is current.** Not from timestamps,
   not from "the zip is newer than the source files", not from a `build/` folder that
   looks recent. Whatever you glob as "source" will miss something — a changed PNG, a new
   audio file, an edited `project.godot` — and the failure lands as "my fix didn't do
   anything" on the board, which sends someone debugging game code that never left their
   laptop. A full export takes 10–20 seconds. Just run it.
2. **Game name** — **always ask, every deploy.** Never infer it from the folder name or
   `application/config/name`; "unoq-jam" is a directory, not what someone wants their
   game called in App Lab. The name also becomes the install slug, so a guessed one
   sticks: deploying again under the real name creates a *second* app rather than
   updating the first, and the wrong one has to be removed by hand.
3. **Icon emoji** — ask in the same breath. Offer 🎮 as the default and suggest one that
   fits the game if you have a feel for it (👾 shooter, 🏎️ racer, 🧩 puzzle, 👻 spooky,
   ⚔️ action, 🌞 sunny), but let them pick. It shows next to the name in App Lab.

Ask for both in **one** short message, before you export, so the deploy doesn't stall
halfway waiting on a name. If setup also needs their terminal, fold the question into
that same message rather than sending two.

## Export (host side)

Do this before touching the board — a failed export is cheaper to diagnose than a
failed deploy.

**1. Check the project is configured for the board.** Read `project.godot` and
confirm, under `[rendering]`:

- `renderer/rendering_method="gl_compatibility"` — if this says `forward_plus`, stop.
  Compatibility is the configuration verified to run on this board, and switching a
  project that already has content can change how existing materials look. Tell the
  user, fix it, and have them look at the game in the editor before shipping.
- `textures/vram_compression/import_etc2_astc=true` — if missing, add it, then force a
  reimport before exporting:

  ```
  "<engine>" --headless --path "<project>" --import
  ```

  Existing `.import` files were written under the old compression setting. Adding the
  setting and exporting straight away can ship textures in the desktop format while
  `project.godot` visibly says otherwise — the board shows pink or black and the one
  setting you would think to check looks correct. If the user has the editor open, they
  can reimport there instead; either way confirm it happened before exporting.

Also confirm, under `[display]`: `window/stretch/mode="viewport"` and
`window/size/viewport_width` no larger than 960. Anything else renders at screen
resolution — ~38 fps at 1080p on this board vs 60+ at 960x540. If the settings are
missing or larger, fix them and say so in one line (repo README, Step 3): it is a
two-line change plus a look at the game in the editor, and shipping without it means
"the game is slow on the board" reports that are really a resolution bug. The one
exception: the user explicitly choosing a different resolution — their call, ship it;
just make sure they said it, rather than a template or a default having said it for
them.

**If the project is 3D, confirm the board profile is present — add it if not.** A 2D game
needs none of it. The reasoning behind each line, and what to tune when a 3D game is still
slow, lives in the repo README (Step 3 and Step 5); this is the check:

```ini
lights_and_shadows/directional_shadow/size=1024
lights_and_shadows/directional_shadow/soft_shadow_filter_quality=0
scaling_3d/mode=0
scaling_3d/scale=0.7
shading/overrides/force_vertex_shading=true
```

If you had to add them, say so in one line — no list of settings, just what you did and
an invitation to try it:

> Tuned the 3D settings a bit so the game runs well on the Arduino. Give it a play
> and let me know if you want anything changed.

Two more checks while you are in there: `anti_aliasing/quality/msaa_3d` must be off (it is
by default — MSAA is catastrophic on this GPU, not merely expensive), and the preset's
`custom_features` must not contain `mobile` (the tag flips `OS.has_feature("mobile")`, and
a game that checks it switches to touchscreen controls on a handheld with physical
buttons). As with resolution, an attendee who chose their own values has made a decision:
ship what they ask for.

**2. Find the arm64 preset.** Read `export_presets.cfg` and find the preset whose
options include `binary_format/architecture="arm64"`. Use its `name=` value verbatim —
do not assume it is called "Linux arm64 (Uno Q)", teams rename things. That preset
must also have `texture_format/etc2_astc=true`, `texture_format/s3tc_bptc=false` and
`binary_format/embed_pck=false`. The installer needs the `.pck` as a separate file beside
the binary and refuses an embedded one — and that refusal lands on the board, after an
export that looked entirely successful.

If there is no arm64 preset, the project was not set up for the board. Point the user
at the repo README's "Add the export preset" step rather than authoring one here —
one copy of those values, in one place.

**3. Find the engine binary.** Read it from the `engine-install` check:

```
npx -y summer-engine@latest doctor --json
```

Do not guess the path; it differs per platform and install.

**4. Export release.** Create the output directory first — this is not optional:

```
mkdir -p "<project>/build"                                          # macOS / Linux
New-Item -ItemType Directory -Force "<project>\build" | Out-Null    # Windows PowerShell
```

PowerShell's `mkdir` does not accept `-p`; use the `New-Item` form there. Then:

```
"<engine>" --headless --path "<project>" --export-release "<preset name>" "<project>/build/game-linux-arm64.zip"
```

If the output directory does not exist, the export prints a complete, successful-looking
`savepack` run, reports `[ DONE ]`, **exits 0 — and writes no file at all.** A fresh
project has no `build/`, so skipping the `mkdir` fails silently every single time. If a
zip from an earlier export is already sitting there, you will deploy that stale build
and nothing in the output will tell you.

So: **exit code 0 is not success.** Success is exit 0 **and** a `.zip` whose modified
time is from this run. Check all three.

Release, never debug — debug builds are bigger and slower and this board has no
headroom. A small game lands around 28 MB. Normal noise on headless shutdown, not
failures: `WARNING: ... RIDs ... were leaked`, `ObjectDB instances leaked at exit`, and
on Windows `[WebView2] Failed to get parent window`.

`build/` is a build artifact — if the project is under version control, add it to
`.gitignore`. The filename is fixed, so each export overwrites the last rather than
piling up.

The user can keep Summer open on the same project while you do this — a headless
export alongside a running editor is fine, and is in fact faster, since the import
caches are warm.

**If the export fails for missing export templates, install them from the public
`summer-builds` release** — the app does not ship Linux templates; this is the normal
path, not an error:

1. `"<engine>" --version` prints e.g. `4.7.2.stable.mono.custom_build.a8e5ca520`.
   The part before `.custom_build` is the **version folder** (`4.7.2.stable.mono`);
   the part after it is the **build hash**.
2. List `https://api.github.com/repos/SummerEngine/summer-builds/releases/tags/templates`
   and pick the `.tpz` asset that matches your build — assets are named either by
   version config (`summer-linux-templates-<version folder>.tpz`, e.g.
   `...-4.7.2.stable.mono.tpz`) or by engine commit
   (`summer-linux-templates-<full-hash>.tpz`, where the full hash starts with your
   build hash). Prefer the version-config name when both exist. Download it
   (~115 MB, no auth — the repo is public).
3. A `.tpz` is a zip with everything under a `templates/` folder. Extract it and move
   the **contents** of `templates/` (not the folder itself) into:
   - Windows: `%APPDATA%\Godot\export_templates\<version folder>\`
   - macOS: `~/Library/Application Support/Godot/export_templates/<version folder>/`
   Create the version folder if it doesn't exist. Result:
   `.../export_templates/4.7.2.stable.mono/linux_release.arm64` (plus its siblings).
4. Re-run the export.

If no asset matches the build hash, templates for this engine build have not been
published — that IS an organizer problem: they must run the `summer_linux_templates`
workflow in the engine repo for this commit. Don't work around it with a
different-version tpz; templates are keyed to the exact build for a reason.

## Prerequisites (once per computer)

- `adb` (Android platform-tools): `winget install Google.PlatformTools` (Windows),
  `brew install android-platform-tools` (macOS), `sudo apt install adb` (Debian) or
  `sudo apt install android-sdk-platform-tools` (Ubuntu — the package is named
  differently per distro; if the first one 404s, try the other).
- Board plugged in with a **data** USB-C cable, straight to the computer (not
  through a hub). After power-up the board takes **up to a minute** to appear —
  poll `adb devices` before concluding failure.

**On Windows, do not run `adb push` from a Git Bash / MSYS shell** without guarding
it. MSYS rewrites the *remote* path as if it were local, so
`adb push game.zip /home/arduino/x.zip` becomes
`C:/Program Files/Git/home/arduino/x.zip` and fails with
`remote secure_mkdirs failed` — after printing `1 file pushed, 0 skipped`, so it
reads like success while nothing landed. Either run adb from PowerShell, or prefix
every adb command with `MSYS_NO_PATHCONV=1`. Verify with
`adb shell ls -la <remote path>` rather than trusting the push output.

## First deploy on a fresh board (one-time)

Detect: `adb shell test -f /home/arduino/.summer-hackathon-setup && echo done` — if
"done", skip to Deploy.

1. Download the runner image (~105 MB) from
   `https://github.com/SummerEngine/summer-builds/releases/download/game-runner-0.1.0/summer-game-runner-0.1.0.tar.gz`
2. Push it, the Modulino bridge, and the setup script:
   ```
   adb push summer-game-runner-0.1.0.tar.gz /home/arduino/
   adb shell "mkdir -p /home/arduino/.summer"
   adb push board/bridge /home/arduino/.summer/
   adb push kit/python3-evdev.deb /home/arduino/python3-evdev.deb
   adb push kit/arduino15-libs.tar.gz /home/arduino/arduino15-libs.tar.gz
   adb push board/setup-board.sh /home/arduino/
   adb shell "sed -i 's/\r$//' /home/arduino/setup-board.sh"
   ```
   The bridge directory is **mandatory**: `setup-board.sh` installs the system-wide
   HID injector service and refuses to run without it. (`SUMMER_NO_BRIDGE=1` is a
   separate, deploy-time flag — see "Modulino input" below — that skips bundling
   the bridge into one game's app; it does not change what setup needs.) The two
   `kit/` files are committed in this repo — push both, always. They are what makes
   setup and the first deploy work on a board with no network; without them setup
   falls back to `apt-get`, which fails on an offline board. Do not tell the user
   the board needs internet — with the kit pushed, it doesn't.
3. The setup script needs sudo, and sudo prompts for a password — **your shell has
   no interactive stdin, so do NOT run this step yourself; it will hang.** Give the
   user this command to run in their own terminal, and wait for them to confirm:
   ```
   adb shell -t "bash /home/arduino/setup-board.sh /home/arduino/summer-game-runner-0.1.0.tar.gz"
   ```
   The prompt wants the board password they set in App Lab. (A board that somehow never
   went through that wizard is asked to *create* one at this prompt instead.) Either way
   they type it themselves; never ask them to tell it to you.
4. The script prints `Setup complete` when done; it is idempotent, so on any
   doubt have the user re-run it. If it reported the autologin step as already
   configured and the image as present, setup was already done — carry on.
   If it prints `Setup incomplete` and exits 1, the runner image did not
   install. It deliberately does **not** mark the board as set up in that case, so
   fix what it names (usually the tarball path, or disk space on `/`) and re-run.
   Do not proceed to Deploy — the install will fail on the missing image.

## Deploy (every time)

`<zip>` below is what you exported (`<project>/build/game-linux-arm64.zip`), or the
user's own zip if they supplied one and you skipped Export.

```
adb push <zip> /home/arduino/game-upload.zip
adb push board/install-game.sh /home/arduino/
adb shell "sed -i 's/\r$//' /home/arduino/install-game.sh"
adb shell "bash /home/arduino/install-game.sh /home/arduino/game-upload.zip '<Game Name>' '<emoji>'"
```

Success is a line starting `OK:`. Each deploy compiles and flashes the persistent
Modulino bridge in `Wait for Linux` mode — expect **~5 minutes** with no output during
the build; it is not hung. The installed game intentionally has no app-owned `sketch/`,
so later cold boots skip that compile/upload and proceed directly to the containers.
Updating an existing game is the same command with the same name. A **3D** game then sits on the Summer splash for another 60–100 s on
its first launch while GLES shaders compile — also not hung; later launches are quick.
On failure the installer prints the app logs — read them before retrying.

Every deploy also makes the game the **boot app**: power-cycling the board starts it
automatically, no App Lab, no keyboard, no mouse. The last deployed game owns the
boot slot.

**Push the exact zip you just exported — never glob for it.** A project that has been
exported before can hold several arm64 zips in `build/` under different names; picking
one with a wildcard silently ships a build from days ago that looks entirely correct.

## Modulino input

Every deployed game automatically includes Arduino's Modulino HID bridge. Physical
controls arrive as ordinary keyboard events — bind these in the game:

| Physical | Key |
|---|---|
| Joystick | W / A / S / D |
| Button A / B / C | J / K / L |

**Build the game to this map and no remapping is ever needed** — movement on W/A/S/D
(fixed — the installer patches the bridge's joystick output to WASD at assembly), actions
on J / K / L (also set by the installer; deliberately away from WASD so the two hands never
collide). The user never opens a config page; keymapping is your
job, not theirs.

**When the user asks for different controls, that request comes to you, the agent —
there is no config page.** Preferred route: change the GAME's own bindings (Input
Map) so it matches the pad map — the keys the pad sends are the fixed contract.
Only when the game's bindings genuinely can't match (an existing project, a key the
design demands) remap the bridge's buttons instead: edit the deployed app's
`python/config.json` on the board, then restart the app:

```
adb shell "python3 - <<'PY'
import json
p = '/home/arduino/ArduinoApps/<slug>/python/config.json'
c = json.load(open(p))
c['keymap']['3e:b0'] = {'type': 'key', 'key': 'W', 'modifiers': [], 'mode': 'hold'}
json.dump(c, open(p, 'w'), indent=2)
PY
arduino-app-cli app restart user:<slug>"
```

`3e:b0`/`3e:b1`/`3e:b2` are buttons A/B/C; `key` takes A-Z, SPACE, ENTER and arrow
names; `mode` is `hold` (key down while pressed) or `tap`. The config loads at app
start, persists, and survives normal redeploys; a `SUMMER_NO_BRIDGE=1` deploy
discards it. No Modulinos attached = nothing happens, keyboard still works.

The bridge firmware is flashed once per deploy, not on every boot. Every game start
probes it and, if another App Lab app has flashed its own sketch over it, reflashes it
(about 15 s, logged as `bridge check: bridge restored after N s`). To see the probe's
verdict on the board: `docker logs <slug>-main-1 2>&1 | grep "bridge check"`. To test the
repair, let Arduino's stock Blink example take the MCU, then start the game again:

```
adb shell "arduino-app-cli app stop user:<slug>; arduino-app-cli app start examples:blink; arduino-app-cli app stop examples:blink; arduino-app-cli app start user:<slug>"
```

Troubleshooting: `systemctl status summer-hid-injector summer-bridge-flash` on the board.
To prove the injector end of the chain, send it the same UDP packet the sketch would; the
pointer moves:

```
adb shell "python3 -c \"import socket,json; socket.socket(socket.AF_INET,socket.SOCK_DGRAM).sendto(json.dumps({'type':'mouse_move','dx':50,'dy':50}).encode(),('127.0.0.1',5555))\""
```

If a sketch build ever blocks a deploy, re-run install-game.sh with
`SUMMER_NO_BRIDGE=1` for a sketch-less install:
`adb shell "SUMMER_NO_BRIDGE=1 bash /home/arduino/install-game.sh /home/arduino/game-upload.zip '<Game Name>' '<emoji>'"`

Note: the injector accepts UDP on 0.0.0.0:5555 (Arduino's design, unmodified) — on a
shared network, anyone can inject input to the board. Acceptable for the jam; do not
put boards on hostile networks.

## What to tell the user

Report the outcome and anything they must act on. Nothing else. A deploy is a few
sentences, not a report.

- **No status recaps.** Never post a "Status so far", a list of what you verified, or an
  inventory of steps you skipped. You checked the zip and the board — good, that's your
  job, not news. At the sudo handoff the user needs the command and what to wait for; a
  progress dump above it just buries the one thing they have to do. They'll ask if they
  want detail.
- **The sudo handoff, sent exactly as written** (only the command's paths change):

  > One step needs your terminal — it sets the board up for games, one time:
  > screen-lock off, autologin, the game runtime, and the controller-input service.
  > It'll ask for the board password you set in App Lab ☀️
  >
  > ```
  > adb shell -t "bash /home/arduino/setup-board.sh /home/arduino/summer-game-runner-0.1.0.tar.gz"
  > ```
  >
  > Wait for `Setup complete` and say go.

  If you still need the name and emoji, ask for them in that same message. Everything
  else waits.

- **Say one line before a long wait, then go quiet.** A deploy that takes minutes with no
  message looks like nothing is happening, and the person is left watching a blank chat.
  Send exactly one of these the moment you start, and nothing else until it finishes:

  > Putting it on the board now. The first deploy also builds the controller sketch, so
  > give it about five minutes.

  > Updating it on the board, about thirty seconds.

  This is not a status recap: it is one sentence, sent before the wait rather than after
  it. Do not follow it with progress updates, step counts, or "still working" messages.

- **Don't narrate clean checks.** If the renderer, the import setting and the preset were
  already right, that is not news — say nothing about them. Only speak up when you had to
  change something, or when something is wrong and they need to decide.
- **Don't relay engine or container logs.** `ERROR: ... glx_context ... ERR_UNCONFIGURED`
  followed by a switch to OpenGLES is the normal path on this board: there is no
  desktop-GL driver, so Godot falls back to GLES, which is what `gl_compatibility`
  targets. `os_same_file_description ... DRM fds` is the same kind of noise. Recognise
  them, don't chase them, and don't paste them at the user — they never see the game log
  and quoting an `ERROR:` line at someone whose deploy just succeeded only worries them.
- **On success: one happy line, then the controls, then hand them the wheel.** The player
  is holding a joystick and three buttons, not a keyboard — so name those and say what
  each one does *in this game*. You wrote the bindings, so you know: translate J/K/L back
  into buttons A/B/C and their in-game action. Something like:

  > Voxel Island is on the board ☀️ — joystick to move, **A** to jump, **B** to place a
  > block, **C** to pause. Go play, and tell me what you want changed.

  Never tell them to press W/A/S/D or J/K/L, here or in any other message: those are the
  keys the controls send under the hood, and nobody holding the handheld has a keyboard.
  If a button is unused in this game, leave it out rather than listing it as idle. That's
  the whole message — no monitor/cable talk, no explanation of virtual displays, no
  `app logs` command, no App Lab click-through. Keep `app list` and `app logs` for when
  something actually failed.
- Don't tell them to open App Lab, browse My Apps, or press Run to start it — the game is
  already running.
- **If you drove the game yourself to verify it** (injected input, played it, crashed it),
  leave it running but not in your test wreckage: restart it fresh before your final
  message — `adb shell "arduino-app-cli app restart user:<slug>"`, seconds, no rebuild —
  so the player walks up to a title screen on their display, not your crashed run.
- Then say how to redeploy after edits: same command, same name, updates in place.

## Tone

Summer is sunny — write like it. Warm, light, short sentences, a ☀️ where one lands
naturally. One emoji in a message is plenty; don't decorate every line, and don't reach
for a thesaurus of enthusiasm. "Your game's on the board ☀️" beats "Deployment completed
successfully."

Precision outranks cheer. When something breaks, say so plainly and keep the fix
legible — a sunny tone never means a vague one, and never means a longer one.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `adb devices` empty | Charge-only cable, hub in the path, or board still booting — direct data cable, wait 60 s |
| installer: "not arm64" | You exported with the wrong preset — re-read `export_presets.cfg` for the one with `architecture="arm64"` and export again |
| export fails: no export template found | Normal on a fresh install — download the matching tpz from summer-builds and install it (see Export, step "missing export templates"). Only if no asset matches the build hash: get an organizer |
| installer: `[ERROR] App "<other>" Is Running` | Another game was up when this one tried to start (App Lab runs one app at a time). The installer stops other running apps itself; seeing this means an old installer copy — re-push `board/install-game.sh` and run it again |
| installer: "runner image missing" | First-deploy setup was skipped — run the fresh-board flow |
| App starts then black/frozen game, 0% CPU | Board not set up (screen locker) — run setup-board.sh |
| Game runs but textures broken/pink | Preset missing `etc2_astc=true` or project not on Compatibility renderer — fix and re-export |
| `unauthorized` in adb | Accept the prompt on the board's screen if attached, or replug |
| Disk full errors | See setup script's cleanup hint (removes re-downloadable stock images) |

## Notes

- Multiple games coexist; each name gets its own app. The installer refuses to
  overwrite non-game folders unless `FORCE=1`.
- The board plays the game on its attached screen (HDMI/DSI). No screen = the game
  still runs on a virtual display; that is not an error.
- To remove a game, stop it, remove its container, then the folder — `app stop` leaves
  the container behind, and a stopped container pins the ~325 MB runner image on the
  board's cramped rootfs:
  `adb shell "arduino-app-cli app stop user:<slug>; docker rm <slug>-game_runner-1; rm -rf /home/arduino/ArduinoApps/<slug>"`
