# Passwordless Uno Q provisioning over USB

This documents the factory-board path used on 2026-09-04 to provision an Arduino
UNO Q for Summer Engine games without App Lab onboarding, Wi-Fi, SSH, or creating a
password on the board.

The result is a board that:

- logs the `arduino` user into XFCE automatically;
- runs the Modulino-to-HID bridge as a system service;
- keeps the Summer game runner available offline;
- starts the last deployed game after boot through `arduino-app-cli`;
- needs interaction only on the laptop that is connected over USB ADB.

## Verified environment

- Arduino UNO Q Debian 13.5 factory image `20260528-558`
- `arduino-app-cli` 0.13.0
- board user `arduino`, UID 1000
- factory-cached root-helper image
  `ghcr.io/arduino/app-bricks/python-apps-base:0.10.1`
- Summer runner image `summer-game-runner:0.1.0`
- USB ADB; the board was deliberately left offline

Re-check these assumptions on a newer image. In particular, the helper image tag is
part of the contract: the setup remains offline only while that image is present in
the factory image.

## Why this works without a password

The factory `arduino` user is a member of the `docker` group. Docker-group access is
already root-equivalent: a container running as UID 0 can enter the host namespaces.
The setup script uses that existing authority for a small, explicit list of host
operations instead of invoking interactive `sudo`.

The helper used by `board/setup-board.sh` is:

```bash
docker run --rm --user 0 --privileged --pid=host \
  --entrypoint /usr/bin/nsenter \
  ghcr.io/arduino/app-bricks/python-apps-base:0.10.1 \
  -t 1 -m -u -i -n -p -- <host-command> <arguments...>
```

`nsenter` joins PID 1's mount, UTS, IPC, network, and PID namespaces, so the command
acts on the board host rather than the container filesystem. `root_exec` first tries
non-interactive `sudo -n`; it uses the Docker helper only when passwordless sudo is
not available.

This is a provisioning mechanism, not a privilege reduction. Anyone who can access
the Docker socket on this image already has equivalent host control. A production
pipeline should make that boundary explicit and should pin and verify the helper
image rather than accept an arbitrary image name.

## Factory-image autologin detail

Writing a LightDM autologin file alone is insufficient on this image. The factory
`arduino` account has a blank password whose last-change day is `0`, so PAM rejects
the autologin account phase as an expired password.

The setup fixes the account state without creating a password:

```bash
chage -d "$(date +%F)" arduino
```

It then installs:

```ini
# /etc/lightdm/lightdm.conf.d/60-autologin.conf
[Seat:*]
autologin-user=arduino
autologin-user-timeout=0
```

This leaves password-based login unset while allowing LightDM's dedicated autologin
path. On the verified board, the journal changed from:

```text
pam_unix(lightdm-autologin:account): expired password for user arduino
```

to a real UID-1000 session with `xfce4-session` running.

## Laptop-driven installation

The repository scripts remain the source of truth. From a laptop with `adb`:

```bash
adb devices -l
adb shell 'mkdir -p /home/arduino/.summer'
adb push board/bridge /home/arduino/.summer/
adb push kit/python3-evdev.deb /home/arduino/
adb push kit/arduino15-libs.tar.gz /home/arduino/
adb push board/setup-board.sh /home/arduino/setup-board.sh
adb push summer-game-runner-0.1.0.tar.gz /home/arduino/
adb shell 'bash /home/arduino/setup-board.sh /home/arduino/summer-game-runner-0.1.0.tar.gz'
```

No pseudo-terminal is required because there is no password prompt. The runner archive
is downloaded and checksum-verified on the laptop, then pushed over USB; the board does
not need network access.

`setup-board.sh` performs five idempotent operations:

1. disables the XFCE screen locker, App Lab editor window, and display blanking
   for the `arduino` session while leaving `arduino-app-cli.service` enabled;
2. repairs the factory password-age state and enables LightDM autologin;
3. loads `summer-game-runner:0.1.0` from the offline archive;
4. checks root filesystem headroom;
5. installs `python3-evdev` and enables the root-owned
   `summer-hid-injector.service` required for `/dev/uinput`.

It writes `/home/arduino/.summer-hackathon-setup` only after the runner, service, and
virtual `UNOQ Keyboard` have all been verified.

## Deploying and selecting the boot game

`board/install-game.sh` validates the export as an ARM64 ELF with a separate PCK,
assembles the Arduino app, starts it, and writes its absolute app directory to:

```text
/var/lib/arduino-app-cli/default.app
```

The Arduino app-cli daemon reads that file during boot. The last deployed Summer game
therefore becomes the boot target without requiring App Lab's Run button.

Example:

```bash
adb push build/game-linux-arm64.zip /home/arduino/game-linux-arm64.zip
adb push board/install-game.sh /home/arduino/install-game.sh
adb shell 'bash /home/arduino/install-game.sh /home/arduino/game-linux-arm64.zip "Grid Hop" "🧩"'
```

The first install compiles and uploads the Modulino sketch and can take several
minutes. Its cache is retained inside the app so redeploys of the unchanged bridge are
faster.

## Verification gates

Do not treat a marker file or `app start` exit code as sufficient. Verify each layer:

```bash
# Desktop session
adb shell 'loginctl list-sessions --no-legend; pgrep -a xfce4-session'

# HID service and virtual keyboard
adb shell 'systemctl is-active summer-hid-injector.service'
adb shell 'grep -A8 -B2 "UNOQ Keyboard" /proc/bus/input/devices'

# Boot target, app, containers, and game process
adb shell 'cat /var/lib/arduino-app-cli/default.app'
adb shell 'arduino-app-cli app list'
adb shell 'docker ps --format "{{.Names}} {{.Status}}"'
adb shell 'docker top <game>-game_runner-1 -eo pid,comm,args'
```

Finally reboot the board and repeat the checks. On a board without passwordless reboot,
the same pinned helper can run `systemctl reboot` in the host namespaces.

The 2026-09-04 test additionally injected `W/A/S/D` and the three game-button keys into
UDP port 5555, read the resulting Linux input events from `UNOQ Keyboard`, and received
the exact key-down/key-up sequence. Physical Modulino modules were not available, so
the Qwiic/I2C discovery and electrical leg remain a required hardware test.

## Current limitations and pipeline follow-ups

- The Arduino SBC package installs `/etc/xdg/autostart/ArduinoAppLab.desktop`.
  `setup-board.sh` now shadows it with a per-user entry containing `Hidden=true`; this
  suppresses only the editor window and preserves `arduino-app-cli.service`. The override
  is source-verified but still needs a physical reboot check on the board.
- On the observed cold boot, App Lab appeared first and the game became visible roughly
  two minutes later. The measured breakdown and proposed one-shot bridge-flash fast path
  are in [`startup-performance.md`](startup-performance.md).
- `arduino-app-cli app list` can briefly report `failed` while boot recovery is still
  creating the containers. Confirm container state and re-read the status before calling
  it a persistent failure.
- The board clock was stale while offline. It produced harmless future-timestamp warnings
  when extracting the offline Arduino library cache. A production host-side provisioner
  should set the board clock from the laptop before extraction.

For the main pipeline, the clean boundary is a host-side provision command that verifies
ADB identity and release digests, pushes the pinned artifacts, invokes the idempotent board
script, then performs the reboot verification gates above. Keep all root operations inside
the reviewed `root_exec` helper so passwordless provisioning does not become arbitrary
shell execution spread throughout the installer.
