FROM debian:trixie-slim

# GL/EGL via Mesa (freedreno is upstream Mesa; trixie matches the board's host libs so
# the HOST_GL=1 bind-mount fallback stays ABI-compatible), Wayland + X11 client libs for
# whichever display server the desktop runs, pulse for audio via pipewire-pulse.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libegl1 libgles2 libgl1-mesa-dri mesa-utils-extra \
        libwayland-client0 libwayland-cursor0 libwayland-egl1 libxkbcommon0 libdecor-0-0 \
        libx11-6 libxcursor1 libxinerama1 libxrandr2 libxi6 libxext6 libxfixes3 libxrender1 \
        libpulse0 libudev1 fontconfig ca-certificates \
    && (apt-get install -y --no-install-recommends glmark2-es2-wayland || true) \
    && (apt-get install -y --no-install-recommends libasound2 || \
        apt-get install -y --no-install-recommends libasound2t64 || true) \
    && rm -rf /var/lib/apt/lists/*

# Game and entrypoint are bind-mounted at /game by the brick compose / test scripts.
CMD ["/bin/sh", "/game/run-game.sh"]
