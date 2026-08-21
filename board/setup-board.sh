#!/bin/bash
# One-time Arduino Uno Q setup for running Summer Engine games. Runs ON the board.
# Safe to re-run (idempotent). Needs sudo ONLY for the autologin step, and only
# the first time; on a factory-fresh board the first sudo asks you to CREATE a
# password — pick one and remember it, it becomes the board's password.
#
# Usage: setup-board.sh [path-to-summer-game-runner-0.1.0.tar.gz]
set -uo pipefail

IMAGE=summer-game-runner:0.1.0
MARKER=/home/arduino/.summer-hackathon-setup
TARBALL=${1:-}
IMAGE_OK=1

echo "== Summer Uno Q board setup =="

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
echo "1/4 screen locker + blanking disabled"

# 2. Desktop autologin (needs sudo, once). Without it the board boots to a login
#    screen and no game can reach the display.
if [ -f /etc/lightdm/lightdm.conf.d/60-autologin.conf ]; then
    echo "2/4 autologin already configured"
else
    echo "2/4 enabling autologin (sudo — on a fresh board this CREATES the password)..."
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
    echo "3/4 runner image $IMAGE present"
elif [ -n "$TARBALL" ] && [ -f "$TARBALL" ]; then
    echo "3/4 loading runner image from $TARBALL ..."
    if docker load < "$TARBALL" && docker image inspect "$IMAGE" >/dev/null 2>&1; then
        echo "    loaded"
    else
        echo "    ERROR: docker load failed or did not produce $IMAGE (out of disk on / ?)"
        IMAGE_OK=0
    fi
else
    echo "3/4 ERROR: runner image $IMAGE missing and no tarball given."
    echo "    Download it from the summer-builds release and re-run:"
    echo "    setup-board.sh /home/arduino/summer-game-runner-0.1.0.tar.gz"
    IMAGE_OK=0
fi

# 4. Disk headroom.
AVAIL_KB=$(df --output=avail / | tail -1 | tr -d ' ')
echo "4/4 rootfs free: $((AVAIL_KB / 1024)) MB"
if [ "$AVAIL_KB" -lt 512000 ]; then
    echo "    WARNING: low disk space. Unused stock images can be removed to free ~1.6 GB:"
    echo "    docker image rm ghcr.io/arduino/app-bricks/ei-models-runner:<tag> \\"
    echo "        ghcr.io/arduino/app-bricks/llamacpp-runner:<tag> \\"
    echo "        ghcr.io/arduino/app-bricks/models-downloader:<tag> influxdb:<tag>"
    echo "    (they re-download automatically if an App Lab example needs them)"
fi

# Only claim completion if the board can actually run a game. Marking a half-set-up
# board "done" is worse than failing: the deploy flow checks this marker, skips setup,
# then fails on the missing image — and the fix it points at is the setup it just skipped.
if [ "$IMAGE_OK" != "1" ]; then
    echo "== setup INCOMPLETE — runner image not installed =="
    echo "   Not marking this board as set up. Re-run with the tarball path:"
    echo "   setup-board.sh /home/arduino/summer-game-runner-0.1.0.tar.gz"
    exit 1
fi

touch "$MARKER"
echo "== setup complete == ☀️"
