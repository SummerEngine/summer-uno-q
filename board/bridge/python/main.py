# python/main.py
# UNO Q — Modulino HID Bridge (Arcade Emulator)
#
# Handles dynamic device discovery from the MCU, routes every input event
# to HID actions, and exposes a Web UI for full configuration.
#
# Device types: buttons, joystick, knob, distance, movement
# Keymap keys:  "{addr_hex}:{input}"  e.g. "3e:b0", "2c:jp", "3b:cw"
#
# Action types in keymap:
#   {"type":"mouse",  "button":"left|right|middle", "mode":"tap|hold"}
#   {"type":"key",    "key":"A|F1|CTRL|...", "modifiers":["CTRL","SHIFT","ALT"], "mode":"tap|hold"}
#   {"type":"scroll", "direction":"up|down", "clicks":1}
#   {"type":"none"}
#
# Endpoints:
#   GET/POST /api/settings
#   GET/POST /api/keymap
#   GET      /api/state
#   GET      /api/devices
#   POST     /api/devices          body: {addr, type, label?, device_settings?}
#   POST     /api/detect_geom
#   POST     /api/nudge

from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI
import json, os, socket, threading, time, select

# -----------------------------------------------------------------------
# UDP → injector
# -----------------------------------------------------------------------
INJECTOR_ADDR = ("172.17.0.1", 5555)
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.setblocking(False)

def _send(msg: dict):
    udp.sendto(json.dumps(msg).encode(), INJECTOR_ADDR)

def send_hid(msg: dict):
    if settings.get("hidEnabled", True):
        _send(msg)

def request_geom(timeout: float = 0.7):
    try:
        while True:
            r, _, _ = select.select([udp], [], [], 0)
            if not r: break
            udp.recvfrom(65535)
        _send({"type": "get_geom"})
        t0 = time.time()
        while time.time() - t0 < timeout:
            r, _, _ = select.select([udp], [], [], 0.05)
            if not r: continue
            data, _ = udp.recvfrom(65535)
            try:
                msg = json.loads(data.decode())
            except Exception:
                continue
            if msg.get("type") == "geom" and "w" in msg:
                return int(msg["w"]), int(msg["h"])
    except Exception:
        pass
    return None

# -----------------------------------------------------------------------
# Global settings (joystick / HID / dpad)
# -----------------------------------------------------------------------
settings = {
    "hidEnabled": True,
    "sensX": 10.0, "sensY": 10.0,
    "accel": 0.05,  "dead":  0.04,
    "invertY": True,
    "mode": "dpad",
    "dpadThreshold": 0.35,
    "dpadDiagonal": "both",
    "dpadRepeat": True,
    "dpadInitialDelayMs": 200,
    "dpadRepeatMs": 70,
    "dpadReleaseFactor": 0.70,
}

# -----------------------------------------------------------------------
# Device registry
# -----------------------------------------------------------------------
devices = {}        # addr(int) -> {type, label, addr}
device_settings = {}  # addr(int) -> device-specific config dict
vibro_addr = None   # address of connected Modulino Vibro, or None if absent
VIBRO_DURATION_MS = 50  # haptic pulse length in ms

def _default_device_settings(device_type: str) -> dict:
    if device_type == "knob":
        return {"knob_invert": False}
    if device_type == "distance":
        return {
            "dist_near_mm":    150.0,   # trigger :near when mm < this
            "dist_far_mm":     400.0,   # trigger :far  when mm > this
            "dist_cooldown_ms": 500,
        }
    if device_type == "movement":
        return {
            "imu_mode":      "relative",  # "relative" | "dpad" | "disabled"
            "imu_sensX":     5.0,
            "imu_sensY":     5.0,
            "imu_invert_x":  False,
            "imu_invert_y":  False,
            "imu_threshold": 0.30,        # tilt threshold for dpad mode
            "imu_rotation":  0,           # 0 | 90 | -90 — corrects mounting orientation
        }
    return {}

# -----------------------------------------------------------------------
# Keymap
# -----------------------------------------------------------------------
keymap = {}   # "{addr_hex}:{input}" -> action dict

# -----------------------------------------------------------------------
# Config persistence
# -----------------------------------------------------------------------
_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def _load_config():
    try:
        with open(_CONFIG_FILE) as f:
            data = json.load(f)
        if "settings" in data:
            settings.update({k: v for k, v in data["settings"].items() if k in settings})
        if "keymap" in data:
            keymap.update(data["keymap"])
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[config] load error: {e}")

def _save_config():
    try:
        with open(_CONFIG_FILE, "w") as f:
            json.dump({"settings": settings, "keymap": keymap}, f, indent=2)
    except Exception as e:
        print(f"[config] save error: {e}")

_load_config()

def _default_keymap_entries(addr: int, device_type: str) -> dict:
    k = f"{addr:02x}"
    if device_type == "buttons":
        return {
            f"{k}:b0": {"type": "mouse",  "button": "left",  "mode": "tap"},
            f"{k}:b1": {"type": "mouse",  "button": "right", "mode": "tap"},
            f"{k}:b2": {"type": "key",    "key": "CTRL",     "modifiers": [], "mode": "hold"},
        }
    if device_type == "joystick":
        return {
            f"{k}:jp": {"type": "mouse", "button": "left", "mode": "tap"},
        }
    if device_type == "knob":
        return {
            f"{k}:cw":  {"type": "scroll", "direction": "up",   "clicks": 1},
            f"{k}:ccw": {"type": "scroll", "direction": "down", "clicks": 1},
            f"{k}:btn": {"type": "none"},
        }
    if device_type == "distance":
        return {
            f"{k}:near": {"type": "mouse", "button": "left", "mode": "tap"},
            f"{k}:far":  {"type": "none"},
        }
    return {}

# -----------------------------------------------------------------------
# Haptic feedback
# -----------------------------------------------------------------------
def trigger_vibro():
    """Fire a short haptic pulse if a Modulino Vibro is connected."""
    if vibro_addr is not None:
        threading.Thread(
            target=lambda: Bridge.call("vibrate", VIBRO_DURATION_MS),
            daemon=True
        ).start()

# -----------------------------------------------------------------------
# -----------------------------------------------------------------------
# HID action dispatcher
# -----------------------------------------------------------------------
def send_hid_action(action: dict, pressed: bool):
    t = action.get("type", "none")
    if t == "none":
        return
    if t == "mouse":
        btn  = action.get("button", "left")
        mode = action.get("mode", "tap")
        if mode == "hold":
            send_hid({"type": "mouse_click", "button": btn,
                      "action": "down" if pressed else "up"})
            if pressed:
                trigger_vibro()
        elif mode == "tap" and pressed:
            send_hid({"type": "mouse_click", "button": btn, "action": "tap"})
            trigger_vibro()
    elif t == "key":
        key  = action.get("key", "A")
        mods = action.get("modifiers", [])
        mode = action.get("mode", "tap")
        if mode == "hold":
            send_hid({"type": "key", "key": key, "modifiers": mods,
                      "action": "down" if pressed else "up"})
            if pressed:
                trigger_vibro()
        elif mode == "tap" and pressed:
            send_hid({"type": "key", "key": key, "modifiers": mods, "action": "tap"})
            trigger_vibro()
    elif t == "scroll" and pressed:
        send_hid({"type": "scroll",
                  "direction": action.get("direction", "up"),
                  "clicks":    action.get("clicks", 1)})

# -----------------------------------------------------------------------
# Per-device runtime state
# -----------------------------------------------------------------------
_btn_prev        = {}   # addr|str -> dict of bool states
_dist_near       = {}   # addr     -> bool
_dist_far        = {}   # addr     -> bool
_dist_near_last_t= {}   # addr     -> float timestamp
_dist_far_last_t = {}   # addr     -> float timestamp
_frac        = {}   # addr     -> (float, float) sub-pixel accumulator
_imu_frac    = {}   # addr     -> (float, float)
_joy_mode    = {}   # addr     -> str  last mode (for transition handling)

# -----------------------------------------------------------------------
# D-Pad engine (per joystick or IMU, keyed by addr)
# -----------------------------------------------------------------------
_dpad = {}  # addr -> {down, last_press, last_repeat}

def _dpad_st(addr):
    if addr not in _dpad:
        _dpad[addr] = {
            "down":        {k: False for k in ("UP","DOWN","LEFT","RIGHT")},
            "last_press":  {k: 0.0   for k in ("UP","DOWN","LEFT","RIGHT")},
            "last_repeat": {k: 0.0   for k in ("UP","DOWN","LEFT","RIGHT")},
        }
    return _dpad[addr]

def _kd(k, force=False): (_send if force else send_hid)({"type":"key","key":k,"modifiers":[],"action":"down"})
def _ku(k, force=False): (_send if force else send_hid)({"type":"key","key":k,"modifiers":[],"action":"up"})
def _kt(k):              send_hid({"type":"key","key":k,"modifiers":[],"action":"tap"})
def _kr(k):              send_hid({"type":"key","key":k,"modifiers":[],"action":"down"})

def _dpad_release_all(addr, force=False):
    st = _dpad_st(addr)
    for k in ("UP","DOWN","LEFT","RIGHT"):
        if st["down"][k]:
            _ku(k, force=force)
            st["down"][k] = False
            st["last_press"][k] = 0.0
            st["last_repeat"][k] = 0.0

def _dpad_update(addr, nx, ny, press_thr=None):
    if press_thr is None:
        press_thr = float(settings.get("dpadThreshold", 0.35))
    st = _dpad_st(addr)
    rel_thr     = max(0.0, press_thr * float(settings.get("dpadReleaseFactor", 0.70)))
    policy      = settings.get("dpadDiagonal", "stronger")
    do_rep      = bool(settings.get("dpadRepeat", True))
    delay_ms    = int(settings.get("dpadInitialDelayMs", 350))
    rep_ms      = int(settings.get("dpadRepeatMs", 70))
    now         = time.time()
    vals = {"UP": max(0.0,-ny), "DOWN": max(0.0,ny),
            "LEFT": max(0.0,-nx), "RIGHT": max(0.0,nx)}

    def press(k):
        if not st["down"][k]:
            st["down"][k] = True; st["last_press"][k] = now; st["last_repeat"][k] = 0.0
            _kd(k)

    def release(k):
        if st["down"][k]:
            st["down"][k] = False; st["last_press"][k] = 0.0; st["last_repeat"][k] = 0.0
            _ku(k)

    def maybe_repeat(k):
        if do_rep:
            since = (now - st["last_press"][k]) * 1000.0
            last_r = ((now - st["last_repeat"][k]) * 1000.0) if st["last_repeat"][k] else None
            if since >= delay_ms and (last_r is None or last_r >= rep_ms):
                _kr(k); st["last_repeat"][k] = now

    if policy == "stronger":
        held = [k for k,d in st["down"].items() if d]
        if held:
            k = held[0]
            if vals[k] <= rel_thr: release(k)
            else: maybe_repeat(k)
        else:
            best = max(vals.items(), key=lambda kv: kv[1])
            if best[1] >= press_thr: press(best[0])
    else:
        for k in ("UP","DOWN","LEFT","RIGHT"):
            v = vals[k]
            if not st["down"][k]:
                if v >= press_thr: press(k)
            else:
                if v <= rel_thr: release(k)
                else: maybe_repeat(k)

# -----------------------------------------------------------------------
# Bridge event handlers
# -----------------------------------------------------------------------
latest_state = {"ts": 0.0, "hid": True, "devices": {}}

def on_device_found(addr: int, device_type: str):
    global vibro_addr
    devices[addr] = {"type": device_type, "addr": addr, "label": device_type.title()}
    if device_type == "vibro":
        vibro_addr = addr
    if addr not in device_settings:
        device_settings[addr] = _default_device_settings(device_type)
    for key, val in _default_keymap_entries(addr, device_type).items():
        if key not in keymap:
            keymap[key] = val

def on_device_unknown(addr: int):
    devices[addr] = {"type": "unknown", "addr": addr, "label": f"Unknown 0x{addr:02X}"}

def on_btn_event(addr: int, b0: bool, b1: bool, b2: bool):
    k = f"{addr:02x}"
    current = {"b0": bool(b0), "b1": bool(b1), "b2": bool(b2)}
    _btn_prev.setdefault(addr, {"b0": False, "b1": False, "b2": False})
    if settings.get("hidEnabled", True):
        for inp, pressed in current.items():
            if pressed == _btn_prev[addr].get(inp, False): continue
            action = keymap.get(f"{k}:{inp}")
            if action:
                send_hid_action(action, pressed)
    _btn_prev[addr] = current
    latest_state["devices"][str(addr)] = {
        "type": "buttons", "b0": bool(b0), "b1": bool(b1), "b2": bool(b2)}
    latest_state["ts"] = time.time()

def on_joy_event(addr: int, nx: float, ny: float, jp: bool):
    k = f"{addr:02x}"
    if settings.get("invertY", False):
        ny = -ny

    mode      = settings.get("mode", "relative")
    hid_on    = settings.get("hidEnabled", True)
    last_mode = _joy_mode.get(addr, mode)

    # Handle mode transition cleanup
    if mode != last_mode:
        if last_mode == "dpad":
            _dpad_release_all(addr, force=True)
        if last_mode == "relative":
            _frac[addr] = (0.0, 0.0)
    _joy_mode[addr] = mode

    dx = dy = 0
    if hid_on:
        if mode == "relative":
            sx  = settings["sensX"];  sy  = settings["sensY"]
            acc = settings["accel"]
            fx0, fy0 = _frac.get(addr, (0.0, 0.0))
            fx = sx * nx * (1.0 + acc * abs(nx)) + fx0
            fy = sy * ny * (1.0 + acc * abs(ny)) + fy0
            dx, dy = int(fx), int(fy)
            _frac[addr] = (fx - dx, fy - dy)
            if dx or dy:
                send_hid({"type": "mouse_move", "dx": dx, "dy": dy})
        else:  # dpad
            _dpad_update(addr, nx, ny)

    # Joystick push button (edge-triggered)
    jp_key = f"{k}_jp"
    _btn_prev.setdefault(jp_key, False)
    if hid_on and bool(jp) != _btn_prev[jp_key]:
        action = keymap.get(f"{k}:jp")
        if action:
            send_hid_action(action, bool(jp))
    _btn_prev[jp_key] = bool(jp)

    latest_state["devices"][str(addr)] = {
        "type": "joystick",
        "nx": round(float(nx), 3), "ny": round(float(ny), 3),
        "dx": dx, "dy": dy, "jp": bool(jp)}
    latest_state.update({"ts": time.time(), "hid": hid_on})

def on_knob_event(addr: int, delta: int, pressed: bool):
    k = f"{addr:02x}"
    if not settings.get("hidEnabled", True):
        return
    ds = device_settings.get(addr, {})
    if ds.get("knob_invert", False):
        delta = -delta
    # Rotation
    if delta != 0:
        action = keymap.get(f"{k}:cw" if delta > 0 else f"{k}:ccw")
        if action:
            send_hid_action(action, True)
    # Button press (edge-triggered)
    btn_key = f"{k}_knob"
    _btn_prev.setdefault(btn_key, False)
    if bool(pressed) != _btn_prev[btn_key]:
        action = keymap.get(f"{k}:btn")
        if action:
            send_hid_action(action, bool(pressed))
    _btn_prev[btn_key] = bool(pressed)
    latest_state["devices"][str(addr)] = {
        "type": "knob", "dir": int(delta), "pressed": bool(pressed)}
    latest_state["ts"] = time.time()

def on_dist_event(addr: int, mm: float):
    k   = f"{addr:02x}"
    ds  = device_settings.get(addr, {})
    near_thr    = float(ds.get("dist_near_mm",    150.0))
    far_thr     = float(ds.get("dist_far_mm",     400.0))
    cooldown_ms = float(ds.get("dist_cooldown_ms", 500))
    now  = time.time()
    near = (mm > 0 and mm < near_thr)
    far  = (mm > far_thr)

    if settings.get("hidEnabled", True):
        # :near — rising edge + cooldown
        if near and not _dist_near.get(addr, False):
            if (now - _dist_near_last_t.get(addr, 0.0)) * 1000.0 >= cooldown_ms:
                action = keymap.get(f"{k}:near")
                if action:
                    send_hid_action(action, True)
                    send_hid_action(action, False)
                _dist_near_last_t[addr] = now
        # :far — rising edge + cooldown
        if far and not _dist_far.get(addr, False):
            if (now - _dist_far_last_t.get(addr, 0.0)) * 1000.0 >= cooldown_ms:
                action = keymap.get(f"{k}:far")
                if action:
                    send_hid_action(action, True)
                    send_hid_action(action, False)
                _dist_far_last_t[addr] = now

    _dist_near[addr] = near
    _dist_far[addr]  = far
    latest_state["devices"][str(addr)] = {
        "type": "distance", "mm": round(float(mm), 1),
        "near": near, "far": far}
    latest_state["ts"] = time.time()

def _rotate_axes(ax: float, ay: float, az: float, deg: int):
    """Correct the tilt reference frame for how the Movement module is mounted.
    At 0 deg (flat), az reads gravity and ax/ay carry the left-right/front-back
    tilt. At +-90 deg the module is tipped onto its side, so the roles of ay
    (now reading a near-constant gravity component) and az (now the axis that
    actually tracks front-back tilt) swap; ax keeps tracking left-right tilt
    unchanged since it's the tipping axis."""
    deg = int(deg) % 360
    if deg == 90:
        return ax, az
    if deg == 180:
        return -ax, -ay
    if deg == 270:   # equivalent to -90
        return ax, -az
    return ax, ay

def on_imu_event(addr: int, ax: float, ay: float, az: float,
                 roll: float, pitch: float, yaw: float):
    if not settings.get("hidEnabled", True):
        return
    ds   = device_settings.get(addr, {})
    mode = ds.get("imu_mode", "relative")
    if mode == "disabled":
        return
    inv_x = bool(ds.get("imu_invert_x", False))
    inv_y = bool(ds.get("imu_invert_y", False))
    sx    = float(ds.get("imu_sensX", 5.0))
    sy    = float(ds.get("imu_sensY", 5.0))
    rax, ray = _rotate_axes(ax, ay, az, ds.get("imu_rotation", 0))
    nx    = rax * (-1 if inv_x else 1)
    ny    = ray * (-1 if inv_y else 1)

    if mode == "relative":
        fx0, fy0 = _imu_frac.get(addr, (0.0, 0.0))
        fx = sx * nx + fx0
        fy = sy * ny + fy0
        dx, dy = int(fx), int(fy)
        _imu_frac[addr] = (fx - dx, fy - dy)
        if dx or dy:
            send_hid({"type": "mouse_move", "dx": dx, "dy": dy})
    elif mode == "dpad":
        thr = float(ds.get("imu_threshold", 0.30))
        _dpad_update(addr, nx, ny, press_thr=thr)

    latest_state["devices"][str(addr)] = {
        "type": "movement",
        "ax": round(float(ax), 3), "ay": round(float(ay), 3), "az": round(float(az), 3)}
    latest_state["ts"] = time.time()

Bridge.provide("device_found",  on_device_found)
Bridge.provide("device_unknown", on_device_unknown)
Bridge.provide("btn_event",   on_btn_event)
Bridge.provide("joy_event",   on_joy_event)
Bridge.provide("knob_event",  on_knob_event)
Bridge.provide("dist_event",  on_dist_event)
Bridge.provide("imu_event",   on_imu_event)

# -----------------------------------------------------------------------
# Web UI & REST API
# -----------------------------------------------------------------------
_ui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ui")
ui = WebUI(assets_dir_path=_ui_dir)

def get_settings():
    return settings

def post_settings(body: dict):
    prev_hid = settings.get("hidEnabled", True)
    allowed  = [
        "hidEnabled", "sensX", "sensY", "accel", "dead", "invertY",
        "mode",
        "dpadThreshold", "dpadDiagonal", "dpadRepeat",
        "dpadInitialDelayMs", "dpadRepeatMs", "dpadReleaseFactor",
    ]
    for key in allowed:
        if key in body:
            settings[key] = body[key]
    if prev_hid and not settings.get("hidEnabled", True):
        for addr in list(devices.keys()):
            _dpad_release_all(addr, force=True)
    Bridge.call("apply_settings",
                settings["sensX"], settings["sensY"],
                settings["accel"], settings["dead"], settings["invertY"])
    _save_config()
    return {"ok": True, "settings": settings}

def get_keymap():
    return keymap

def post_keymap(body: dict):
    if body:
        keymap.update(body)
    _save_config()
    return {"ok": True, "keymap": keymap}

def get_state():
    latest_state["hid"] = bool(settings.get("hidEnabled", True))
    return {"ok": True, "state": latest_state, "settings": settings,
            "keymap": keymap, "devices": devices}

def get_devices():
    return {"ok": True, "devices": devices, "device_settings": device_settings}

def post_devices(body: dict):
    """Configure an unknown device, or update label / device settings."""
    addr = body.get("addr")
    if addr is None:
        return {"ok": False, "error": "addr required"}
    addr = int(addr)
    if "type" in body:
        device_type = body["type"]
        devices[addr] = {
            "type":  device_type,
            "addr":  addr,
            "label": body.get("label", device_type.title()),
        }
        if addr not in device_settings:
            device_settings[addr] = _default_device_settings(device_type)
        for key, val in _default_keymap_entries(addr, device_type).items():
            if key not in keymap:
                keymap[key] = val
        # Tell MCU to initialize the device at that address
        Bridge.call("configure_device", addr, device_type)
    if "label" in body and addr in devices:
        devices[addr]["label"] = body["label"]
    if "device_settings" in body and addr in device_settings:
        device_settings[addr].update(body["device_settings"])
    return {"ok": True, "device": devices.get(addr),
            "device_settings": device_settings.get(addr)}

def detect_geom():
    g = request_geom()
    if g:
        settings["screenW"], settings["screenH"] = g
        return {"ok": True, "w": g[0], "h": g[1]}
    return {"ok": False, "error": "No reply from injector"}

def nudge():
    send_hid({"type": "mouse_move", "dx": 120, "dy": 60})
    return {"ok": True}

def rescan():
    """Ask the MCU to re-run the I2C scan and re-emit device_found events."""
    global vibro_addr
    devices.clear()
    latest_state["devices"].clear()
    vibro_addr = None
    Bridge.call("rescan")
    return {"ok": True}

ui.expose_api("GET",  "/api/settings",    get_settings)
ui.expose_api("POST", "/api/settings",    post_settings)
ui.expose_api("GET",  "/api/keymap",      get_keymap)
ui.expose_api("POST", "/api/keymap",      post_keymap)
ui.expose_api("GET",  "/api/state",       get_state)
ui.expose_api("GET",  "/api/devices",     get_devices)
ui.expose_api("POST", "/api/devices",     post_devices)
ui.expose_api("POST", "/api/detect_geom", detect_geom)
ui.expose_api("POST", "/api/nudge",       nudge)
ui.expose_api("POST", "/api/rescan",      rescan)

App.run()
