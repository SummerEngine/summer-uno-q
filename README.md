# ship-to-unoq — deploy Summer Engine games to the Arduino Uno Q

Ships a Summer Engine (Godot 4.6) **Linux arm64 export zip** to an Arduino Uno Q
over USB, as an **Arduino App Lab app**: your game shows up in App Lab's "My Apps"
with a name and emoji icon, and runs GPU-accelerated on the board's display.

Works with any AI coding agent: Claude Code loads [SKILL.md](SKILL.md) as a skill;
any other agent (or a human) can follow the same file as a runbook.

## Quickstart

1. Export your game in Summer with the **Linux arm64 (Uno Q)** preset
   (`etc2_astc=true`, `s3tc_bptc=false`, Compatibility renderer) and note the zip path.
2. Plug the Uno Q into your computer (USB-C **data** cable, no hub; allow ~1 min to boot).
3. Tell your agent: *"ship my game to the Uno Q — the export is at `<path>`,
   call it `<Name>` with icon `<emoji>`"* and point it at this folder.

The agent handles the rest, including one-time setup of a factory-fresh board
(~10 min: desktop autologin, screen-locker removal, runner image install — you'll
be asked to create the board's password at the sudo prompt).

## Contents

| File | Runs where | Purpose |
|---|---|---|
| `SKILL.md` | agent | Orchestration: inputs, prerequisites, commands, troubleshooting |
| `board/setup-board.sh` | board | One-time fresh-board provisioning (idempotent) |
| `board/install-game.sh` | board | Zip → App Lab app with `game_runner` brick → start |
| `image/Dockerfile` | board | Runner image source (fallback: build on board with network) |

The prebuilt runner image (~100 MB) is a release asset:
[`game-runner-0.1.0`](https://github.com/SummerEngine/summer-builds/releases/tag/game-runner-0.1.0).

## Notes

- Multiple games coexist on one board; re-deploying the same name updates in place.
- Remove a game: `adb shell "arduino-app-cli app stop user:<slug>; rm -rf /home/arduino/ArduinoApps/<slug>"`
- Board internals (why the container setup looks the way it does): the game runs in
  a Docker container wired as an App Lab *local brick*; the host's Mesa backport is
  shadow-mounted because stock Debian trixie Mesa doesn't support the Adreno 702;
  `${APP_HOME}` interpolation in brick compose files is unreliable, so the installer
  writes absolute paths.
