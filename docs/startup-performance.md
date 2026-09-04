# Uno Q game startup performance

This note records the cold-boot delay observed with a Summer game installed as the
Arduino App CLI default app, identifies the dominant operation, and proposes one
focused optimization.

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

## One focused optimization

Treat the Modulino bridge as board firmware rather than a component recompiled with
every game boot:

1. during setup or redeploy, compile and upload the canonical bridge once with Arduino
   CLI using `arduino:zephyr:unoq:wait_linux_boot=yes` (`Wait for Linux`) or the
   `wait_linux_boot=no` immediate mode;
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

With a non-app-gated firmware image, `StartDefaultApp` can skip
`compileUploadSketch` and proceed to cached Python provisioning and
`docker compose up`. Based on the baseline, the expected improvement is approximately
80–95 seconds, bringing LightDM-to-game time from about 107 seconds to roughly 10–25
seconds. This remains an estimate until the same cold-boot measurement is repeated with
the candidate change.

## Ownership and recovery risk

The STM32 firmware persists across a normal reboot, which makes a one-shot flash viable.
However, another App Lab app can overwrite that firmware. Returning to a Summer game
without an app-owned sketch would then start quickly but its Modulino input bridge would
be absent or wrong.

The minimum recovery contract is:

- every Summer redeploy flashes the canonical bridge in the non-app-gated boot mode,
  verifies it, and installs the game without `sketch/`;
- changing the bridge always requires redeploy;
- if another app owned the MCU since the last Summer deploy, redeploy the Summer game
  before relying on its controls.

A deeper Arduino App CLI improvement would cache a sketch-content hash plus a receipt for
the firmware currently on the MCU and skip compile/upload only when both match. That avoids
the ownership caveat but belongs in the upstream orchestrator rather than this deployment
script.

## Required validation before merging

Run the same experiment on a connected board:

1. deploy normally and confirm joystick/button input;
2. compile/upload the same bridge with `wait_linux_boot=yes`, then install the app
   without `sketch/`;
3. cold reboot;
4. capture `journalctl -b -o short-iso -u lightdm -u arduino-app-cli`;
5. capture Docker `Created` and `StartedAt` timestamps;
6. confirm the game reaches fullscreen and app status becomes `running`;
7. confirm physical Modulino input still reaches the game;
8. repeat one more cold boot to rule out a one-run cache effect.

Do not merge the optimization from source inspection alone. The current evidence proves
where the time goes; it does not yet prove that the bridge firmware resumes correctly
after a cold boot without App CLI's sketch path.
