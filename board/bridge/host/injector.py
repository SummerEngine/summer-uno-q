#!/usr/bin/env python3
"""
UNOQ Injector (generic): virtual mouse + keyboard via /dev/uinput.
Understands:
  - {"type":"mouse_move","dx":int,"dy":int}           # relative motion
  - {"type":"mouse_click","button":"left|right|middle","action":"tap|down|up"}
  - {"type":"key","key":"A|CTRL|...","action":"tap|down|up"}
  - {"type":"mouse_abs","x":int,"y":int}              # absolute warp (X11 via xdotool)
  - {"type":"get_geom"}  -> replies {"type":"geom","w":int,"h":int}
"""

import json
import os
import signal
import socket
import subprocess
from evdev import UInput, ecodes as E

HOST = '0.0.0.0'
PORT = 5555
RUNNING = True

# Ensure we're pointing at the local X server if launched from a TTY
os.environ.setdefault("DISPLAY", ":0")

def _stop(signum=None, frame=None):
    global RUNNING
    RUNNING = False

signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)

# ---- uinput capabilities ----
MOUSE_CAP = {
    E.EV_KEY:  [E.BTN_LEFT, E.BTN_RIGHT, E.BTN_MIDDLE],
    E.EV_REL:  [E.REL_X, E.REL_Y, E.REL_WHEEL],
}
KEYBOARD_KEYS = [
    E.KEY_LEFTCTRL, E.KEY_RIGHTCTRL, E.KEY_LEFTSHIFT, E.KEY_RIGHTSHIFT,
    E.KEY_LEFTALT,  E.KEY_RIGHTALT,
    E.KEY_ENTER, E.KEY_SPACE, E.KEY_ESC, E.KEY_TAB, E.KEY_BACKSPACE,
    E.KEY_UP, E.KEY_DOWN, E.KEY_LEFT, E.KEY_RIGHT,
    *[getattr(E, f'KEY_{ch}') for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789']
]
KEYB_CAP = {E.EV_KEY: KEYBOARD_KEYS}
MOUSE_BUTTONS = {'left':E.BTN_LEFT,'right':E.BTN_RIGHT,'middle':E.BTN_MIDDLE}

def keycode(name: str) -> int:
    n = (name or '').upper()
    table = {
        "CTRL":"KEY_LEFTCTRL","SHIFT":"KEY_LEFTSHIFT","ALT":"KEY_LEFTALT",
        "ENTER":"KEY_ENTER","SPACE":"KEY_SPACE","ESC":"KEY_ESC","TAB":"KEY_TAB",
        "UP":"KEY_UP","DOWN":"KEY_DOWN","LEFT":"KEY_LEFT","RIGHT":"KEY_RIGHT",
    }
    if len(n) == 1 and n.isalnum():
        return getattr(E, f"KEY_{n}")
    return getattr(E, table.get(n, n))

def xdotool_get_geom():
    geo = subprocess.check_output(["xdotool","getdisplaygeometry"], text=True).strip()
    w, h = [int(v) for v in geo.split()]
    return w, h

def xdotool_move_abs(x: int, y: int):
    subprocess.run(["xdotool","mousemove",str(int(x)),str(int(y))], check=False)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    sock.settimeout(0.25)
    print(f"[injector] Listening on udp://{HOST}:{PORT}")

    try:
        with UInput(
            MOUSE_CAP, name="UNOQ Mouse", bustype=0x03, input_props=[E.INPUT_PROP_POINTER]
        ) as mu, UInput(
            KEYB_CAP, name="UNOQ Keyboard", bustype=0x03
        ) as ku:

            print("[injector] uinput devices ready (mouse + keyboard)")

            while RUNNING:
                try:
                    data, addr = sock.recvfrom(8192)
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    break

                try:
                    msg = json.loads(data.decode('utf-8'))
                except Exception:
                    continue

                t = msg.get("type")

                if t == "mouse_move":
                    dx = int(msg.get("dx",0)); dy = int(msg.get("dy",0))
                    if dx: mu.write(E.EV_REL, E.REL_X, dx)
                    if dy: mu.write(E.EV_REL, E.REL_Y, dy)
                    if dx or dy: mu.syn()

                elif t == "scroll":
                    clicks = int(msg.get("clicks", 1))
                    delta  = clicks if msg.get("direction", "up") == "up" else -clicks
                    mu.write(E.EV_REL, E.REL_WHEEL, delta)
                    mu.syn()

                elif t == "mouse_click":
                    btn = MOUSE_BUTTONS.get(msg.get("button","left"), E.BTN_LEFT)
                    action = msg.get("action","tap")
                    if action == "tap":
                        mu.write(E.EV_KEY, btn, 1); mu.syn()
                        mu.write(E.EV_KEY, btn, 0); mu.syn()
                    elif action == "down":
                        mu.write(E.EV_KEY, btn, 1); mu.syn()
                    elif action == "up":
                        mu.write(E.EV_KEY, btn, 0); mu.syn()

                elif t == "key":
                    kc = keycode(msg.get("key","A"))
                    act = msg.get("action","tap")
                    if kc not in KEYBOARD_KEYS: continue
                    if act in ("tap", "repeat"):
                        ku.write(E.EV_KEY, kc, 1); ku.syn()
                        ku.write(E.EV_KEY, kc, 0); ku.syn()
                    elif act == "down":
                        ku.write(E.EV_KEY, kc, 1); ku.syn()
                    elif act == "up":
                        ku.write(E.EV_KEY, kc, 0); ku.syn()

                elif t == "mouse_abs":
                    # absolute warp via X11
                    try:
                        x = int(msg.get("x",0)); y = int(msg.get("y",0))
                        xdotool_move_abs(x,y)
                    except Exception as e:
                        print(f"[injector] mouse_abs failed: {e}")

                elif t == "get_geom":
                    # Reply with current display geometry to sender (UDP)
                    try:
                        w,h = xdotool_get_geom()
                        sock.sendto(json.dumps({"type":"geom","w":w,"h":h}).encode("utf-8"), addr)
                    except Exception as e:
                        sock.sendto(json.dumps({"type":"geom","error":str(e)}).encode("utf-8"), addr)

                else:
                    # ignore unknown types
                    continue

    finally:
        try: sock.close()
        except Exception: pass
        print("[injector] Stopped cleanly.")

if __name__ == "__main__":
    main()