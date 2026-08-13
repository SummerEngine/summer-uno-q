#!/bin/bash
# Summer Engine → Arduino Uno Q game installer. Runs ON the board (Debian side).
# Installs a Summer/Godot Linux arm64 export as an Arduino App Lab app that runs
# GPU-accelerated in a container (game_runner brick) and starts it.
#
# Usage:  install-game.sh <export-zip> <game name> [icon-emoji]
# Update: run again with the same name — replaces the game in place.
# Env:    FORCE=1 to overwrite a folder that was not created by this installer.
set -euo pipefail

ZIP=${1:?usage: install-game.sh <export-zip> <game name> [icon-emoji]}
NAME=${2:?usage: install-game.sh <export-zip> <game name> [icon-emoji]}
EMOJI=${3:-🎮}
APPS=/home/arduino/ArduinoApps
IMAGE=summer-game-runner:0.1.0

NAME=${NAME//\"/}
SLUG=$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')
[ -n "$SLUG" ] || { echo "ERROR: game name produced an empty slug"; exit 1; }
APP="$APPS/$SLUG"

[ -f "$ZIP" ] || { echo "ERROR: zip not found: $ZIP"; exit 1; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || {
    echo "ERROR: runner image $IMAGE missing — run setup-board.sh first"; exit 1; }

if [ -d "$APP" ] && [ ! -f "$APP/.summer-game" ] && [ "${FORCE:-0}" != "1" ]; then
    echo "ERROR: $APP exists and was not created by this installer. FORCE=1 to overwrite."
    exit 1
fi

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/app/game"
unzip -oq "$ZIP" -d "$T/app/game"

# Identify the game binary (largest non-.pck file) and sanity-check it: ELF, aarch64.
cd "$T/app/game"
BIN=$(ls -Sp . | grep -v '/$' | grep -v '\.pck$' | head -1)
[ -n "$BIN" ] || { echo "ERROR: no binary found in zip"; exit 1; }
head -c 4 "$BIN" | grep -q ELF || { echo "ERROR: $BIN is not an ELF executable — wrong export?"; exit 1; }
MACHINE=$(dd if="$BIN" bs=1 skip=18 count=2 2>/dev/null | od -An -tx1 | tr -d ' \n')
[ "$MACHINE" = "b700" ] || {
    echo "ERROR: $BIN is not arm64 (e_machine=$MACHINE). Export with the 'Linux arm64 (Uno Q)' preset."; exit 1; }
ls ./*.pck >/dev/null 2>&1 || { echo "ERROR: no .pck in zip — incomplete export?"; exit 1; }
chmod +x "$BIN"
cd - >/dev/null

# --- App Lab app skeleton ---------------------------------------------------
touch "$T/app/.summer-game"

cat > "$T/app/app.yaml" <<EOF
name: "$NAME"
icon: $EMOJI
description: "$NAME — built with Summer Engine"
bricks:
  - game_runner:
EOF

mkdir -p "$T/app/python"
cat > "$T/app/python/main.py" <<'EOF'
# The game runs in the game_runner brick container; this mandatory entry point
# keeps the App alive so App Lab shows it as running until the user stops it.
import signal
import sys
import time

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
print("game runs in the game_runner brick; python side idling.")
while True:
    time.sleep(60)
EOF

cat > "$T/app/run-game.sh" <<'EOF'
#!/bin/sh
# Entrypoint of the game_runner brick container. App folder is mounted at /game.
set -e
cd /game/game
BIN=$(ls -Sp . | grep -v '/$' | grep -v '\.pck$' | head -1)
chmod +x "$BIN" 2>/dev/null || true
echo "game_runner: launching $BIN ${GAME_FLAGS:-}"
exec "./$BIN" ${GAME_FLAGS:-}
EOF
chmod +x "$T/app/run-game.sh"

mkdir -p "$T/app/bricks/game_runner"
cat > "$T/app/bricks/game_runner/brick_config.yaml" <<'EOF'
id: game_runner
name: Summer Game Runner
description: Runs a Summer Engine (Godot) game on the board's display with GPU acceleration
mount_devices_into_container: true
EOF

# Absolute app path on purpose: ${APP_HOME} interpolation and relative paths are
# unreliable in included brick compose files (verified on app-cli 0.13.0).
# Host libdir is shadow-mounted because the host Mesa backport (26.x) supports the
# Adreno 702 while stock trixie Mesa (25.x) does not.
cat > "$T/app/bricks/game_runner/brick_compose.yaml" <<EOF
services:
  game_runner:
    image: $IMAGE
    restart: "no"
    volumes:
      - $APP:/game
      - /tmp/.X11-unix:/tmp/.X11-unix
      - /home/arduino/.Xauthority:/tmp/.Xauthority:ro
      - /run/user/1000:/run/user/1000
      - /usr/lib/aarch64-linux-gnu:/usr/lib/aarch64-linux-gnu:ro
    environment:
      DISPLAY: ":0"
      XAUTHORITY: /tmp/.Xauthority
      XDG_RUNTIME_DIR: /run/user/1000
      HOME: /tmp
    entrypoint: ["/bin/sh", "/game/run-game.sh"]
EOF

# --- Install & start ---------------------------------------------------------
arduino-app-cli app stop "user:$SLUG" >/dev/null 2>&1 || true
rm -rf "$APP"
mkdir -p "$APPS"
mv "$T/app" "$APP"

echo ">> installed $APP — starting..."
arduino-app-cli app start "user:$SLUG"

sleep 6
STATUS=$(arduino-app-cli app list 2>/dev/null | grep "user:$SLUG" | awk '{print $(NF-1)}' || true)
if [ "$STATUS" = "running" ]; then
    echo "OK: \"$NAME\" ($EMOJI) is running — manage it in App Lab under My Apps."
else
    echo "FAILED: app status is '$STATUS'. Last logs:"
    arduino-app-cli app logs "user:$SLUG" --all 2>&1 | tail -20
    exit 1
fi
