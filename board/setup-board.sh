#!/bin/bash
# One-time Arduino Uno Q setup for running Summer Engine games. Runs ON the board.
# Safe to re-run (idempotent). Needs sudo ONLY for the autologin step, and only the
# first time. The password is the one set during the board's own App Lab setup.
#
# Usage: setup-board.sh [path-to-summer-game-runner-0.1.0.tar.gz]
set -uo pipefail

IMAGE=summer-game-runner:0.1.0
MARKER=/home/arduino/.summer-hackathon-setup
TARBALL=${1:-}
IMAGE_OK=1

echo "==> Summer Uno Q board setup"

# 1. Screen locker + blanking off (user-level, no sudo). A locked/blanked session
#    freezes every game on the board — this is mandatory, not cosmetic.
pkill -u arduino light-locker 2>/dev/null || true
mkdir -p /home/arduino/.config/autostart
printf '[Desktop Entry]\nType=Application\nName=Screen Locker\nHidden=true\n' \
    > /home/arduino/.config/autostart/light-locker.desktop
printf '[Desktop Entry]\nType=Application\nName=Summer no-blank\nExec=xset s off -dpms\n' \
    > /home/arduino/.config/autostart/summer-noblank.desktop
if [ -f /home/arduino/.Xauthority ]; then
    DISPLAY=:0 XAUTHORITY=/home/arduino/.Xauthority xset s off -dpms 2>/dev/null || true
fi
echo "1/5 screen locker + blanking disabled"

# 2. Desktop autologin (needs sudo, once). Without it the board boots to a login
#    screen and no game can reach the display.
if [ -f /etc/lightdm/lightdm.conf.d/60-autologin.conf ]; then
    echo "2/5 autologin already configured"
else
    echo "2/5 enabling autologin (needs the board password)..."
    printf '[Seat:*]\nautologin-user=arduino\nautologin-user-timeout=0\n' > /tmp/60-autologin.conf
    sudo sh -c 'mkdir -p /etc/lightdm/lightdm.conf.d && cp /tmp/60-autologin.conf /etc/lightdm/lightdm.conf.d/60-autologin.conf' \
        || { echo "ERROR: autologin needs sudo"; exit 1; }
    if ! loginctl list-sessions --no-legend 2>/dev/null | grep -q " arduino "; then
        echo "    no active session — restarting login manager to log in now"
        sudo systemctl restart lightdm
    else
        echo "    active session kept; autologin applies from next boot"
    fi
fi

# 3. Runner image.
if docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "3/5 runner image $IMAGE present"
elif [ -n "$TARBALL" ] && [ -f "$TARBALL" ]; then
    echo "3/5 loading runner image from $TARBALL ..."
    if docker load < "$TARBALL" && docker image inspect "$IMAGE" >/dev/null 2>&1; then
        echo "    loaded"
    else
        echo "    ERROR: docker load failed or did not produce $IMAGE (out of disk on / ?)"
        IMAGE_OK=0
    fi
else
    echo "3/5 ERROR: runner image $IMAGE missing and no tarball given."
    echo "    Download it from the summer-builds release and re-run:"
    echo "    setup-board.sh /home/arduino/summer-game-runner-0.1.0.tar.gz"
    IMAGE_OK=0
fi

# 4. Disk headroom.
AVAIL_KB=$(df --output=avail / | tail -1 | tr -d ' ')
echo "4/5 rootfs free: $((AVAIL_KB / 1024)) MB"
if [ "$AVAIL_KB" -lt 512000 ]; then
    echo "    WARNING: low disk space. Unused stock images can be removed to free ~1.6 GB:"
    echo "    docker image rm ghcr.io/arduino/app-bricks/ei-models-runner:<tag> \\"
    echo "        ghcr.io/arduino/app-bricks/llamacpp-runner:<tag> \\"
    echo "        ghcr.io/arduino/app-bricks/models-downloader:<tag> influxdb:<tag>"
    echo "    (they re-download automatically if an App Lab example needs them)"
fi

# 5. Modulino HID injector (Arduino's, verbatim — bridge/ATTRIBUTION.md). Games get
#    Modulino input as ordinary keyboard/mouse events via /dev/uinput. /dev/uinput is
#    root-only (0600), so this must be a SYSTEM unit — the official guide's user unit
#    fails with "cannot be opened for writing".
BRIDGE=/home/arduino/.summer/bridge
if [ ! -f "$BRIDGE/host/injector.py" ]; then
    echo "    ERROR: bridge files missing at $BRIDGE — push them first (see SKILL.md)"
    exit 1
fi

if ! dpkg -s python3-evdev >/dev/null 2>&1; then
    if [ -f /home/arduino/python3-evdev.deb ]; then
        sudo dpkg -i /home/arduino/python3-evdev.deb
    else
        sudo apt-get install -y python3-evdev   # online fallback
    fi
fi
python3 -c 'import evdev' || { echo "    ERROR: python3-evdev unusable"; exit 1; }

# Sketch-library cache so the first game deploy builds offline. Always extract:
# it is 3 MB and idempotent, and any presence check here invites version drift —
# factory boards ship Arduino_Modulino 0.7.0 while the sketch pins 0.8.0, so
# "a Modulino lib exists" is not "the right one exists".
if [ -f /home/arduino/arduino15-libs.tar.gz ]; then
    tar -xzf /home/arduino/arduino15-libs.tar.gz -C /home/arduino/ \
        || echo "    WARNING: lib cache extraction failed — first game deploy will need the board online"
fi

sudo tee /etc/systemd/system/summer-hid-injector.service >/dev/null <<UNIT
[Unit]
Description=Summer HID injector (Modulino bridge -> uinput)
StartLimitIntervalSec=0

[Service]
ExecStart=/usr/bin/python3 $BRIDGE/host/injector.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now summer-hid-injector.service
echo "5/5 HID injector service installed"

# Only claim completion if the board can actually run a game. Marking a half-set-up
# board "done" is worse than failing: the deploy flow checks this marker, skips setup,
# then fails on the missing image — and the fix it points at is the setup it just skipped.
if [ "$IMAGE_OK" != "1" ]; then
    echo "!!! Setup incomplete: runner image not installed"
    echo "   Not marking this board as set up. Re-run with the tarball path:"
    echo "   setup-board.sh /home/arduino/summer-game-runner-0.1.0.tar.gz"
    exit 1
fi

systemctl is-active --quiet summer-hid-injector.service || {
    echo "ERROR: injector service not running"; exit 1; }
sleep 1
grep -q "UNOQ Keyboard" /proc/bus/input/devices || {
    echo "ERROR: injector's virtual keyboard did not appear"; exit 1; }

touch "$MARKER"
echo "==> Setup complete, board is ready"
