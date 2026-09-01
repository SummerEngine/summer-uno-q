#!/bin/bash
# Summer Engine → Arduino Uno Q game installer. Runs ON the board (Debian side).
# Installs a Summer/Godot Linux arm64 export as an Arduino App Lab app that runs
# GPU-accelerated in a container (game_runner brick) and starts it.
#
# Usage:  install-game.sh <export-zip> <game name> [icon-emoji]
# Update: run again with the same name — replaces the game in place.
# Env:    FORCE=1 to overwrite a folder that was not created by this installer.
#         SUMMER_NO_BRIDGE=1 to assemble without the Modulino bridge.
set -euo pipefail

ZIP=${1:?usage: install-game.sh <export-zip> <game name> [icon-emoji]}
NAME=${2:?usage: install-game.sh <export-zip> <game name> [icon-emoji]}
EMOJI=${3:-🎮}
APPS=/home/arduino/ArduinoApps
IMAGE=summer-game-runner:0.1.0
BRIDGE=/home/arduino/.summer/bridge
NO_BRIDGE=${SUMMER_NO_BRIDGE:-0}

NAME=${NAME//\"/}
SLUG=$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')
[ -n "$SLUG" ] || { echo "ERROR: game name produced an empty slug"; exit 1; }
APP="$APPS/$SLUG"

[ -f "$ZIP" ] || { echo "ERROR: zip not found: $ZIP"; exit 1; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || {
    echo "ERROR: runner image $IMAGE missing — run setup-board.sh first"; exit 1; }

if [ "$NO_BRIDGE" != "1" ] && [ ! -f "$BRIDGE/python/main.py" ]; then
    echo "ERROR: Modulino bridge files missing at $BRIDGE — re-run setup-board.sh"
    echo "       (or set SUMMER_NO_BRIDGE=1 to install without Modulino support)"
    exit 1
fi

if [ -d "$APP" ] && [ ! -f "$APP/.summer-game" ] && [ "${FORCE:-0}" != "1" ]; then
    echo "ERROR: $APP exists and was not created by this installer. FORCE=1 to overwrite."
    exit 1
fi

# Stage on the SAME partition as $APPS. /home/arduino is its own mount (18G) while /
# is a cramped 9.8G shared with docker images — staging in /tmp means unzipping ~100MB
# onto the tight partition and then a cross-device copy that needs the space twice.
# Same-partition staging makes the final mv an atomic rename instead.
T=$(mktemp -d -p /home/arduino .summer-stage.XXXXXX)
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
ls ./*.pck >/dev/null 2>&1 || {
    echo "ERROR: no .pck next to the binary."
    echo "  Most likely binary_format/embed_pck=true in the export preset — this pipeline"
    echo "  needs the pck as a separate file. Set embed_pck=false and re-export."
    exit 1; }
chmod +x "$BIN"
cd - >/dev/null

# --- App Lab app skeleton ---------------------------------------------------
touch "$T/app/.summer-game"

if [ "$NO_BRIDGE" = "1" ]; then
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
else
    cat > "$T/app/app.yaml" <<EOF
name: "$NAME"
icon: $EMOJI
description: "$NAME — built with Summer Engine"
bricks:
  - game_runner:
  - arduino:web_ui: {}
EOF
    # Bridge rides inside the game app (App Lab runs one app at a time, so it
    # cannot be its own app). Files are Arduino's, verbatim — see bridge/ATTRIBUTION.md.
    cp -rp "$BRIDGE/python" "$T/app/python"
    cp -rp "$BRIDGE/sketch" "$T/app/sketch"
    cp -rp "$BRIDGE/ui" "$T/app/ui"
    # Our default button map is J/K/L, not the bridge's shipped A/S/ENTER — A and S
    # collide with WASD movement on a PC keyboard. Patched in the staged copy so the
    # vendored bridge/ stays verbatim.
    python3 - "$T/app/python/config.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
c = json.load(open(p))
for slot, key in (("3e:b0", "J"), ("3e:b1", "K"), ("3e:b2", "L")):
    c["keymap"][slot] = {"type": "key", "key": key, "modifiers": [], "mode": "hold"}
json.dump(c, open(p, "w"), indent=2)
PYEOF
    # A team's saved key map survives redeploys: keep the old app's config.json.
    if [ -f "$APP/python/config.json" ]; then
        cp "$APP/python/config.json" "$T/app/python/config.json"
    fi
fi

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
      GAME_FLAGS: "--fullscreen"
    entrypoint: ["/bin/sh", "/game/run-game.sh"]
EOF

# Carry the old app's build cache (sketch artifacts + python venv) into the new
# assembly - without it every redeploy recompiles the unchanged bridge sketch,
# ~4.5 min instead of ~1. -p above keeps sketch mtimes stable for the same reason.
if [ -d "$APP/.cache" ]; then
    cp -a "$APP/.cache" "$T/app/.cache"
fi

# --- Install & start ---------------------------------------------------------
arduino-app-cli app stop "user:$SLUG" >/dev/null 2>&1 || true
mkdir -p "$APPS"
rm -rf "$APP"
mv "$T/app" "$APP"   # same partition as $T, so this is an atomic rename

echo ">> installed $APP — starting..."
arduino-app-cli app start "user:$SLUG"

sleep 6
STATUS=$(arduino-app-cli app list 2>/dev/null | grep "user:$SLUG" | awk '{print $(NF-1)}' || true)
if [ "$STATUS" = "running" ]; then
    echo "OK: \"$NAME\" ($EMOJI) is installed and running."
    echo "    Appears in App Lab as My Apps > $NAME once a display is attached to the board."
else
    echo "FAILED: app status is '$STATUS'. Last logs:"
    arduino-app-cli app logs "user:$SLUG" --all 2>&1 | tail -20
    exit 1
fi
