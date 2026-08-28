// sketch/sketch.ino
// UNO Q — Multi-Modulino HID Bridge
// Scans the Qwiic/I2C bus on startup, discovers every connected Modulino,
// notifies Python of what was found, then polls each device every 16 ms.
//
// Supported devices:
//   buttons  (0x3E  fw:0x7C) — 3 push buttons
//   joystick (0x2C  fw:0x58) — X/Y axes + push
//   knob     (0x3A/0x3B) — rotary encoder + push
//   distance (0x29  fixed)   — VL53L4CD ToF, mm
//   movement (0x6A  fixed)   — LSM6DSOX IMU
//   vibro    (0x38  default) — haptic feedback motor
//
// Events sent to Python:
//   device_found  (addr:int, type:str)
//   device_unknown(addr:int)
//   btn_event     (addr:int, b0:bool, b1:bool, b2:bool)
//   joy_event     (addr:int, nx:float, ny:float, push:bool)
//   knob_event    (addr:int, dir:int, pressed:bool)  dir=-1/0/+1
//   dist_event    (addr:int, mm:float)
//   imu_event     (addr:int, ax,ay,az,roll,pitch,yaw:float)
//
// RPCs received from Python:
//   apply_settings(sensX,sensY,accel,dead,invertY)
//   configure_device(addr:int, type:str)  — assign type to unknown addr
//   vibrate(ms:int)                       — trigger haptic pulse

#include <Arduino_RouterBridge.h>
#include <Arduino_Modulino.h>
#include <Arduino_LED_Matrix.h>

static ArduinoLEDMatrix matrix;

// ---------------------------------------------------------------------------
// Known I2C Wire-layer addresses (7-bit, what Wire.beginTransmission uses)
// The Modulino library stores "fw" addresses (doubled); we derive Wire addrs
// by dividing by 2 in scan().  Distance/Movement use the real address directly.
// ---------------------------------------------------------------------------
struct KnownAddr { uint8_t addr; const char* type; };
static const KnownAddr KNOWN[] = {
  { 0x3E, "buttons"  },   // fw 0x7C / 2
  { 0x2C, "joystick" },   // fw 0x58 / 2
  { 0x3A, "knob"     },   // fw 0x74 / 2
  { 0x3B, "knob"     },   // fw 0x76 / 2
  { 0x29, "distance" },   // fixed
  { 0x6A, "movement" },   // fixed (LSM6DSOX default)
  { 0x38, "vibro"    },   // default
};
static const int N_KNOWN = (int)(sizeof(KNOWN) / sizeof(KNOWN[0]));

static const char* classifyAddr(uint8_t addr) {
  for (int i = 0; i < N_KNOWN; i++)
    if (KNOWN[i].addr == addr) return KNOWN[i].type;
  return nullptr;
}

// ---------------------------------------------------------------------------
// Device pools
// ---------------------------------------------------------------------------
#define MAX_BUTTONS  4
#define MAX_JOYSTICK 2
#define MAX_KNOB     2

static ModulinoButtons  btnDev[MAX_BUTTONS];
static uint8_t          btnAddr[MAX_BUTTONS];
static int              nBtn = 0;

static ModulinoJoystick joyDev[MAX_JOYSTICK];
static uint8_t          joyAddr[MAX_JOYSTICK];
static int              nJoy = 0;

static ModulinoKnob     knobDev[MAX_KNOB];
static uint8_t          knobAddr[MAX_KNOB];
static int              nKnob = 0;

// Distance and Movement have no address arg — singletons
static ModulinoDistance distDev;
static bool             hasDist = false;

static ModulinoMovement movDev;
static bool             hasMov  = false;

static ModulinoVibro    vibroDev;
static bool             hasVibro = false;

// ---------------------------------------------------------------------------
// Peak auto-calibration — adapts to the joystick's actual mechanical range.
// getX()/getY() return int8_t centred at 0, but the physical throw may only
// reach ±40..80 out of the theoretical ±127.  Tracking the observed peak and
// normalising to it ensures full [-1..+1] output regardless of hardware.
// ---------------------------------------------------------------------------
struct PeakCal {
  float peak = 8.0f;           // start small so first real movement calibrates fast
  void update(float v) {
    float a = fabsf(v);
    if (a > peak) peak = a;
  }
  float norm(float v) const {
    float n = v / peak;
    if (n >  1.0f) return  1.0f;
    if (n < -1.0f) return -1.0f;
    return n;
  }
};
static PeakCal calX[MAX_JOYSTICK], calY[MAX_JOYSTICK];

// ---------------------------------------------------------------------------
// Settings (subset forwarded from Python)
// ---------------------------------------------------------------------------
static float gDead = 0.06f;

String apply_settings(float sensX, float sensY, float accel, float dead, bool invertY) {
  gDead = dead;
  return "{\"ok\":true}";
}

static inline float applyDead(float v, float d) {
  float a = fabsf(v);
  if (a < d) return 0.0f;
  return copysignf((a - d) / (1.0f - d), v);
}

// ---------------------------------------------------------------------------
// Device initializer — called from scan and from configure_device RPC
// ---------------------------------------------------------------------------
static void initDevice(uint8_t addr, const char* type) {
  String t = type;
  if (t == "buttons" && nBtn < MAX_BUTTONS) {
    btnDev[nBtn] = ModulinoButtons(addr);
    if (btnDev[nBtn].begin()) { btnAddr[nBtn++] = addr; }

  } else if (t == "joystick" && nJoy < MAX_JOYSTICK) {
    joyDev[nJoy] = ModulinoJoystick(addr);
    if (joyDev[nJoy].begin()) { joyAddr[nJoy++] = addr; }

  } else if (t == "knob" && nKnob < MAX_KNOB) {
    knobDev[nKnob] = ModulinoKnob(addr);
    if (knobDev[nKnob].begin()) { knobAddr[nKnob++] = addr; }

  } else if (t == "distance" && !hasDist) {
    hasDist = distDev.begin();

  } else if (t == "movement" && !hasMov) {
    hasMov = movDev.begin();

  } else if (t == "vibro" && !hasVibro) {
    vibroDev = ModulinoVibro(addr);
    hasVibro = vibroDev.begin();
  }
}

// ---------------------------------------------------------------------------
// configure_device RPC — Python assigns a type to an unknown address
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// vibrate RPC — Python requests a haptic pulse (duration in ms)
// ---------------------------------------------------------------------------
String vibrate(int ms) {
  if (hasVibro) vibroDev.on((size_t)ms);
  return "{\"ok\":true}";
}

String configure_device(int addr, String type) {
  initDevice((uint8_t)addr, type.c_str());
  Bridge.notify("device_found", addr, type);
  return "{\"ok\":true}";
}

// ---------------------------------------------------------------------------
// rescan RPC — Python requests a fresh I2C discovery (e.g. from UI button)
// ---------------------------------------------------------------------------
String rescan() {
  nBtn = 0; nJoy = 0; nKnob = 0;
  hasDist = false; hasMov = false; hasVibro = false;
  scanAndDiscover();
  return "{\"ok\":true}";
}

// ---------------------------------------------------------------------------
// I2C bus scan
// ---------------------------------------------------------------------------
static void scanAndDiscover() {
  auto* wire = Module::getWire();
  if (!wire) return;
  for (uint8_t addr = 0x08; addr < 0x78; addr++) {
    wire->beginTransmission(addr);
    if (wire->endTransmission() != 0) continue;
    const char* t = classifyAddr(addr);
    if (t) {
      Bridge.notify("device_found", (int)addr, t);
      initDevice(addr, t);
    } else {
      Bridge.notify("device_unknown", (int)addr);
    }
  }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);
  static const uint8_t frame_1[] = {
    0, 0, 0, 0, 0, 7, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 7, 0, 0, 0, 0, 0, 0,
    0, 0, 7, 7, 7, 7, 7, 7, 7, 7, 7, 0, 0,
    0, 7, 7, 0, 7, 7, 7, 7, 7, 7, 7, 7, 0,
    0, 7, 0, 0, 0, 7, 7, 7, 0, 7, 0, 7, 0,
    0, 7, 7, 0, 7, 7, 7, 7, 7, 7, 7, 7, 0,
    0, 0, 7, 7, 7, 7, 7, 7, 7, 7, 7, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  };
  matrix.draw(frame_1);
  Bridge.begin();
  Modulino.begin();
  Bridge.provide("apply_settings",   apply_settings);
  Bridge.provide("configure_device", configure_device);
  Bridge.provide("rescan",           rescan);
  Bridge.provide("vibrate",          vibrate);
  delay(500);       // give Python time to register Bridge handlers before scanning
  scanAndDiscover();
}

// ---------------------------------------------------------------------------
// Loop 
// ---------------------------------------------------------------------------
// Previous button states for edge detection — avoids flooding Bridge every 16 ms
static bool btnPrev[MAX_BUTTONS][3];

void loop() {
  static unsigned long last = 0;
  const unsigned long  now  = millis();
  if (now - last < 16) return;
  last = now;

  // ---- Buttons ----
  for (int i = 0; i < nBtn; i++) {
    btnDev[i].update();
    bool b0 = btnDev[i].isPressed(0);
    bool b1 = btnDev[i].isPressed(1);
    bool b2 = btnDev[i].isPressed(2);
    if (b0 != btnPrev[i][0] || b1 != btnPrev[i][1] || b2 != btnPrev[i][2]) {
      Bridge.notify("btn_event", (int)btnAddr[i], (int)b0, (int)b1, (int)b2);
      btnPrev[i][0] = b0; btnPrev[i][1] = b1; btnPrev[i][2] = b2;
    }
  }

  // ---- Joystick ----
  // getX/Y() returns int8_t centred at 0 but physical throw varies per unit.
  // PeakCal self-calibrates to the observed range so full deflection = ±1.
  for (int i = 0; i < nJoy; i++) {
    joyDev[i].update();
    float rx = (float)joyDev[i].getX();
    float ry = (float)joyDev[i].getY();
    calX[i].update(rx);
    calY[i].update(ry);
    float nx = applyDead(calX[i].norm(rx), gDead);
    float ny = applyDead(calY[i].norm(ry), gDead);
    bool  jp = joyDev[i].isPressed();
    Bridge.notify("joy_event", (int)joyAddr[i], nx, ny, jp);
  }

  // ---- Knob ----
  // getDirection() returns debounced -1/0/+1 and internally batches I2C reads
  for (int i = 0; i < nKnob; i++) {
    int8_t dir     = knobDev[i].getDirection();
    bool   pressed = knobDev[i].isPressed();
    if (dir != 0 || pressed)
      Bridge.notify("knob_event", (int)knobAddr[i], (int)dir, pressed);
  }

  // ---- Distance ----
  if (hasDist && distDev.available()) {
    Bridge.notify("dist_event", (int)0x29, distDev.get());
  }

  // ---- Movement / IMU ----
  if (hasMov && movDev.available() && movDev.update()) {
    float ax = applyDead(movDev.getX(),     gDead);
    float ay = applyDead(movDev.getY(),     gDead);
    float az = movDev.getZ();
    float rl = movDev.getRoll();
    float pt = movDev.getPitch();
    float yw = movDev.getYaw();
    Bridge.notify("imu_event", (int)0x6A, ax, ay, az, rl, pt, yw);
  }
}
