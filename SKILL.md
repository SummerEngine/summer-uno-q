---
name: ship-to-unoq
description: Deploy a Summer Engine game to an Arduino Uno Q handheld over USB. Use when the user wants to put their game on the Arduino/Uno Q/handheld, deploy to the board, or update a game already on it. Input is the path to their Linux arm64 export zip; the skill provisions a fresh board on first use, installs the game as an Arduino App Lab app, and starts it.
---

# Ship a Summer Engine game to the Arduino Uno Q

You are deploying a Godot/Summer **Linux arm64 export zip** to an Arduino Uno Q
plugged into this computer via USB-C. The game becomes an **Arduino App Lab app**
(visible in App Lab's "My Apps" with a name and emoji icon, start/stoppable there)
running GPU-accelerated in a container on the board.

Everything board-side is done by two scripts in this skill's `board/` folder.
Your job is orchestration: get three inputs, check prerequisites, push, run, and
translate errors. Do not improvise the packaging — the scripts are the product.

## Inputs to collect from the user

1. **Path to the export zip** (they exported with the "Linux arm64 (Uno Q)" preset
   and noted where they saved it). If they only have a project, tell them to export
   first: preset must target arm64 with `textures/etc2_astc=true`,
   `s3tc_bptc=false`, and the project must use the **Compatibility** renderer.
2. **Game name** (shown in App Lab; also becomes the install slug).
3. **Icon emoji** (optional, default 🎮).

## Prerequisites (once per computer)

- `adb` (Android platform-tools): `winget install Google.PlatformTools` (Windows),
  `brew install android-platform-tools` (macOS), `sudo apt install android-sdk-platform-tools` (Linux).
- Board plugged in with a **data** USB-C cable, straight to the computer (not
  through a hub). After power-up the board takes **up to a minute** to appear —
  poll `adb devices` before concluding failure.

## First deploy on a fresh board (one-time, ~10 min)

Detect: `adb shell test -f /home/arduino/.summer-jam-setup && echo done` — if
"done", skip to Deploy.

1. Download the runner image (~130 MB) from
   `https://github.com/SummerEngine/summer-builds/releases/download/game-runner-0.1.0/summer-game-runner-0.1.0.tar.gz`
2. Push it and the setup script:
   ```
   adb push summer-game-runner-0.1.0.tar.gz /home/arduino/
   adb push board/setup-board.sh /home/arduino/
   adb shell "sed -i 's/\r$//' /home/arduino/setup-board.sh"
   ```
3. Run setup **interactively** (sudo will prompt; on a factory-fresh board it asks
   the user to CREATE the board password — have the user type it, never ask them
   to tell it to you):
   ```
   adb shell -t "bash /home/arduino/setup-board.sh /home/arduino/summer-game-runner-0.1.0.tar.gz"
   ```
4. Re-run until it prints `== setup complete ==`. It is idempotent.

## Deploy (every time)

```
adb push <their-export.zip> /home/arduino/game-upload.zip
adb push board/install-game.sh /home/arduino/
adb shell "sed -i 's/\r$//' /home/arduino/install-game.sh"
adb shell "bash /home/arduino/install-game.sh /home/arduino/game-upload.zip '<Game Name>' '<emoji>'"
```

Success is the line `OK: "<name>" (<emoji>) is running`. Updating an existing
game is the same command with the same name. On failure the installer prints the
app logs — read them before retrying.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `adb devices` empty | Charge-only cable, hub in the path, or board still booting — direct data cable, wait 60 s |
| installer: "not arm64" | Wrong export preset — re-export with Linux **arm64** (Uno Q) preset |
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
- To remove a game: `adb shell "arduino-app-cli app stop user:<slug>; rm -rf /home/arduino/ArduinoApps/<slug>"`
