# Uno Q game startup performance

This note records the cold-boot delay observed with a Summer game installed as the
Arduino App CLI default app, identifies the dominant operation, and documents the
deployed optimization and its board measurements.

## Baseline

Grid Hop was installed with the Modulino bridge and selected as the default app. On
the 2026-09-04 cold boot, the relevant timestamps were:

| Event | Board time | Delta from app-cli |
|---|---:|---:|
| LightDM started | 11:51:58 | -2 s |
| `arduino-app-cli.service` started | 11:52:00 | 0 s |
| `grid-hop-game_runner-1` started | 11:53:36 | 96 s |
| Python main reported `App started` | 11:53:45 | 105 s |

The game runner itself reached the renderer about one second after its container
started. Roughly 96 of the 105 seconds therefore happened before the game container,
not in LightDM, XFCE, or the Summer/Godot executable.

The App Lab editor appearing first is a separate cosmetic issue. Its Debian package
installs an XDG autostart entry; suppressing that window does not remove the 96-second
backend delay.

## Root cause

`board/install-game.sh` copies `board/bridge/sketch` into every installed game app.
At daemon startup, Arduino App CLI immediately calls `StartDefaultApp`. `StartApp`
then calls `compileUploadSketch` whenever the app has a `sketch/` directory. That path
runs Arduino initialization, a complete compile, and an MCU upload on every cold boot,
even though the same firmware was already flashed during deployment.

Source evidence, pinned to the revisions inspected:

- [`arduino-app-cli` v0.13.0 daemon starts the default app immediately](https://github.com/arduino/arduino-app-cli/blob/1df36867f7a1a09876b1e9e8be28d7fc15fddc72/cmd/arduino-app-cli/daemon/daemon.go#L56-L75)
- [`StartApp` compiles and uploads whenever a sketch path exists](https://github.com/arduino/arduino-app-cli/blob/1df36867f7a1a09876b1e9e8be28d7fc15fddc72/internal/orchestrator/orchestrator.go#L181-L197)
- [`app.Load` treats the `sketch/` directory as the sketch-bearing signal](https://github.com/arduino/arduino-app-cli/blob/1df36867f7a1a09876b1e9e8be28d7fc15fddc72/internal/orchestrator/app/app.go#L91-L102)
- [App Lab's Debian build copies its desktop file into XDG autostart](https://github.com/arduino/arduino-app-lab/blob/8947b90ec81c4455ad28ef14d215bacb89837623/standalone-apps/app-lab-desktop/build/debian/Dockerfile#L70-L81)

## Implemented optimization

Treat the Modulino bridge as board firmware rather than a component recompiled with
every game boot:

1. during redeploy, compile and upload the canonical bridge once with Arduino
   CLI using `arduino:zephyr:unoq:wait_linux_boot=yes` (`Wait for Linux`);
2. install the Summer game app without a `sketch/` directory;
3. retain `/home/arduino/.summer/bridge/sketch` as the canonical source for the next
   explicit redeploy.

The boot mode is essential. Arduino App CLI currently forces app-owned sketches to
`wait_linux_boot=app`. The UNO Q loader clears its `wait_for_app_magic` value on every
MCU boot and blocks until App CLI signals it. Simply stripping `sketch/` after a normal
App CLI flash could therefore leave the bridge waiting forever after the next cold boot.

Source evidence:

- [App CLI v0.13.0 forces `wait_linux_boot=app` when that menu exists](https://github.com/arduino/arduino-app-cli/blob/1df36867f7a1a09876b1e9e8be28d7fc15fddc72/internal/orchestrator/orchestrator.go#L1111-L1119)
- [UNO Q defines `Wait for Linux`, `Immediate`, and `Wait for App` modes](https://github.com/arduino/ArduinoCore-zephyr/blob/79b3f1afdad455f55e4a25030953617152c0227c/boards.txt#L579-L583)
- [the loader resets and then waits on the per-boot app signal](https://github.com/arduino/ArduinoCore-zephyr/blob/79b3f1afdad455f55e4a25030953617152c0227c/loader/main.c#L225-L278)

`board/install-game.sh` implements this flow. With a non-app-gated firmware image,
`StartDefaultApp` skips `compileUploadSketch` and proceeds directly to Python
provisioning and `docker compose up`.

Two consecutive physical-board reboots on 2026-09-04 produced the following host-clock
measurements. Times start when the reboot command is issued, so the approximately
30-second bootloader/Linux interval is included:

| Event | Reboot 1 | Reboot 2 |
|---|---:|---:|
| USB ADB available / LightDM active | 31 s | 30 s |
| `arduino-app-cli.service` active | 33 s | 32 s |
| Game runner container and fullscreen game process started | 36 s | 35 s |
| Python bridge API answered `/api/state` | 48 s | 47 s |

The app-cli-to-game portion fell from 96 seconds to 3 seconds. The total measured
reboot-to-game-process time is now 35–36 seconds. Both boots reported `Grid Hop` as
`running`, retained an app directory without `sketch/`, kept
`summer-hid-injector.service` active.

After the second reboot, a test injected `W/A/S/D`, `Space`, `Tab`, and `R` into the
same UDP endpoint used by the Modulino bridge and read the exact key-down/key-up
sequence back from `UNOQ Keyboard`. This verifies the post-bridge software input path;
the physical Qwiic/I2C modules still require the planned hardware test.

## Ownership and self-repair

The STM32 firmware persists across a normal reboot, which makes a one-shot flash viable.
However, any other App Lab app with a `sketch/` overwrites that firmware when it starts.
A Summer game returning to the MCU afterwards would start fast with no working controls,
so every game start verifies the bridge and repairs it when needed:

1. `python/summer_bridge_check.py` (written into the app by `install-game.sh`, started
   from `main.py` right before `App.run()`) calls the bridge's own `apply_settings` RPC.
   The bridge answers within milliseconds; that is the whole cost on a healthy boot.
2. Silence is retried for 15 s, because on a cold boot the MCU may still be starting.
   An answer of `method apply_settings not available` means a foreign sketch is running
   and skips the wait.
3. On failure the check drops `.reflash-bridge` in the app folder (bind-mounted at
   `/app`). The host service `summer-bridge-flash` (installed by `setup-board.sh`, polls
   every 2 s) uploads the prebuilt image from `/home/arduino/.summer/bridge-build` with
   `arduino-cli upload`; no compile is involved.
4. The check keeps probing and logs `bridge check: bridge restored after N s`. Settings
   are pushed by the probe itself, so the dead zone is applied on every start. A
   `rescan` follows every pass: the bridge announces its Modulinos only when it boots,
   which on a cold boot is before the Python side exists.

Measured on the board on 2026-09-04 with the stock `examples:blink` app as the intruder:

| Event | Time |
|---|---:|
| Probe on a healthy MCU | < 1 s |
| Foreign sketch detected → flag written | 1 s after Python start |
| Flag picked up by host service | ≤ 2 s |
| `arduino-cli upload` of the prebuilt image | 14 s |
| `bridge restored` logged | 14 s after Python start, 22 s after `app start` |

Contract that still holds:

- every Summer redeploy compiles and flashes the canonical bridge in the non-app-gated
  boot mode and installs the game without `sketch/`;
- changing the bridge always requires a redeploy (the reflash uses the last deploy's
  build);
- a mismatched *Summer* bridge version is not detected: only absence or a foreign sketch.

A systemd path unit with `PathExistsGlob=` does not work for the flag: its inotify watch
sits on `ArduinoApps/` and never sees a file created inside an app folder. Hence the
polling service.

A deeper Arduino App CLI improvement would cache a sketch-content hash plus a receipt for
the firmware currently on the MCU and skip compile/upload only when both match. That
belongs in the upstream orchestrator rather than this deployment script.

## Validation status

The fast boot path, default-app recovery, game process, bridge API,
virtual input device, and software key path were verified on the connected board across
two reboots. The bridge self-repair was verified twice with `examples:blink` as the
intruder, and a third cold boot confirmed the probe reports `ok` without triggering a
reflash. A person still needs to confirm two things that automation cannot establish
without the missing modules/display observation:

1. connect the physical Modulino joystick and three buttons and confirm their configured
   actions reach the game;
2. confirm the expected first frame is visible on the attached display at roughly the
   measured 35–36 second process-start point.
