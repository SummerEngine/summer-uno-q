// ─────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────
const $ = s => document.querySelector(s);
const ok  = msg => $('#status').innerHTML = `<span class="ok">${msg}</span>`;
const err = msg => $('#status').innerHTML = `<span class="err">${msg}</span>`;
const api = (method, path, body) => fetch(path, {
  method, cache: 'no-store',
  headers: body ? {'Content-Type':'application/json'} : undefined,
  body:    body ? JSON.stringify(body) : undefined,
}).then(r => r.json());

function showModePanels(mode) {
  $('#rel_cfg').classList.toggle('hidden',  mode !== 'relative');
  $('#dpad_cfg').classList.toggle('hidden', mode !== 'dpad');
}
function reflectHID(on) {
  document.body.classList.toggle('hid-off', !on);
  $('#live_hid').textContent = on ? 'enabled' : 'disabled';
}

// ─────────────────────────────────────────────────────────────────────────
// Action picker
//
// An "action picker" is a set of controls grouped by data-picker attribute.
// buildPicker(parent, id, action) — inserts controls into parent element
// getPickerValue(id)              — returns the action dict
// setPickerValue(id, action)      — loads action into controls
// ─────────────────────────────────────────────────────────────────────────
const KEY_OPTIONS = [
  // Mouse (handled separately via type selector, but listed for reference)
];

const ALL_KEYS = [
  ...('ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')),
  ...('0123456789'.split('')),
  ...Array.from({length:12},(_,i)=>`F${i+1}`),
  'ENTER','ESC','TAB','BACKSPACE','DELETE','SPACE',
  'UP','DOWN','LEFT','RIGHT',
  'HOME','END','PAGEUP','PAGEDOWN',
];

function buildKeySelect(id, cls) {
  const sel = document.createElement('select');
  sel.id = id; sel.className = cls || '';
  const groups = [
    ['Letters',    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')],
    ['Numbers',    '0123456789'.split('')],
    ['Function',   Array.from({length:12},(_,i)=>`F${i+1}`)],
    ['Special',    ['ENTER','ESC','TAB','BACKSPACE','DELETE','SPACE']],
    ['Navigation', ['UP','DOWN','LEFT','RIGHT','HOME','END','PAGEUP','PAGEDOWN']],
  ];
  groups.forEach(([label, keys]) => {
    const g = document.createElement('optgroup');
    g.label = label;
    keys.forEach(k => { const o = document.createElement('option'); o.value = k; o.textContent = k; g.appendChild(o); });
    sel.appendChild(g);
  });
  return sel;
}

function buildPicker(parent, pickerId, action) {
  const wrap = document.createElement('div');
  wrap.className = 'action-picker';
  wrap.dataset.picker = pickerId;

  // Type selector
  const typeEl = document.createElement('select');
  typeEl.className = 'ap-type';
  [['none','— None —'],['mouse','Mouse button'],['key','Key / Shortcut'],['scroll','Scroll wheel']]
    .forEach(([v,l]) => { const o = document.createElement('option'); o.value=v; o.textContent=l; typeEl.appendChild(o); });
  wrap.appendChild(typeEl);

  // Mouse sub-panel
  const mouseDiv = document.createElement('span');
  mouseDiv.className = 'ap-mouse';
  const mouseBtn = document.createElement('select'); mouseBtn.className = 'ap-mouse-btn';
  [['left','Left'],['right','Right'],['middle','Middle']].forEach(([v,l])=>{
    const o=document.createElement('option');o.value=v;o.textContent=l+' click';mouseBtn.appendChild(o);});
  const mouseMode = document.createElement('select'); mouseMode.className = 'ap-mouse-mode';
  [['tap','Tap'],['hold','Hold (drag)']].forEach(([v,l])=>{
    const o=document.createElement('option');o.value=v;o.textContent=l;mouseMode.appendChild(o);});
  mouseDiv.appendChild(mouseBtn); mouseDiv.appendChild(mouseMode);
  wrap.appendChild(mouseDiv);

  // Key sub-panel
  const keyDiv = document.createElement('span');
  keyDiv.className = 'ap-key';
  const keyName = buildKeySelect(null, 'ap-key-name');
  const modsDiv = document.createElement('span'); modsDiv.className = 'modifiers';
  ['CTRL','SHIFT','ALT'].forEach(mod => {
    const lbl = document.createElement('label');
    const cb  = document.createElement('input'); cb.type='checkbox'; cb.dataset.mod=mod;
    lbl.appendChild(cb); lbl.appendChild(document.createTextNode(mod));
    modsDiv.appendChild(lbl);
  });
  const keyMode = document.createElement('select'); keyMode.className = 'ap-key-mode';
  [['tap','Tap'],['hold','Hold']].forEach(([v,l])=>{
    const o=document.createElement('option');o.value=v;o.textContent=l;keyMode.appendChild(o);});
  keyDiv.appendChild(keyName); keyDiv.appendChild(modsDiv); keyDiv.appendChild(keyMode);
  wrap.appendChild(keyDiv);

  // Scroll sub-panel
  const scrollDiv = document.createElement('span');
  scrollDiv.className = 'ap-scroll';
  const scrollDir = document.createElement('select'); scrollDir.className = 'ap-scroll-dir';
  [['up','Scroll up'],['down','Scroll down']].forEach(([v,l])=>{
    const o=document.createElement('option');o.value=v;o.textContent=l;scrollDir.appendChild(o);});
  scrollDiv.appendChild(scrollDir);
  wrap.appendChild(scrollDiv);

  parent.appendChild(wrap);

  // Show/hide sub-panels based on type selection
  function syncType() {
    const v = typeEl.value;
    mouseDiv.style.display  = v==='mouse'  ? '' : 'none';
    keyDiv.style.display    = v==='key'    ? '' : 'none';
    scrollDiv.style.display = v==='scroll' ? '' : 'none';
  }
  typeEl.addEventListener('change', syncType);

  // Load initial action
  setPickerValue(wrap, action || {type:'none'});
  syncType();
  return wrap;
}

function setPickerValue(wrap, action) {
  if (!wrap) return;
  const t = action.type || 'none';
  wrap.querySelector('.ap-type').value = t;
  if (t === 'mouse') {
    wrap.querySelector('.ap-mouse-btn').value  = action.button || 'left';
    wrap.querySelector('.ap-mouse-mode').value = action.mode   || 'tap';
  } else if (t === 'key') {
    const ksel = wrap.querySelector('.ap-key-name');
    const k = (action.key || 'A').toUpperCase();
    if ([...ksel.options].some(o=>o.value===k)) ksel.value = k;
    const mods = action.modifiers || [];
    wrap.querySelectorAll('.modifiers input').forEach(cb => {
      cb.checked = mods.includes(cb.dataset.mod);
    });
    wrap.querySelector('.ap-key-mode').value = action.mode || 'tap';
  } else if (t === 'scroll') {
    wrap.querySelector('.ap-scroll-dir').value = action.direction || 'up';
  }
  // Sync visibility
  const te = wrap.querySelector('.ap-type');
  const v = te.value;
  wrap.querySelector('.ap-mouse').style.display  = v==='mouse'  ? '' : 'none';
  wrap.querySelector('.ap-key').style.display    = v==='key'    ? '' : 'none';
  wrap.querySelector('.ap-scroll').style.display = v==='scroll' ? '' : 'none';
}

function getPickerValue(wrap) {
  if (!wrap) return {type:'none'};
  const t = wrap.querySelector('.ap-type').value;
  if (t === 'mouse') return {
    type:'mouse',
    button: wrap.querySelector('.ap-mouse-btn').value,
    mode:   wrap.querySelector('.ap-mouse-mode').value,
  };
  if (t === 'key') {
    const mods = [...wrap.querySelectorAll('.modifiers input')]
      .filter(cb=>cb.checked).map(cb=>cb.dataset.mod);
    return {
      type:'key',
      key:       wrap.querySelector('.ap-key-name').value,
      modifiers: mods,
      mode:      wrap.querySelector('.ap-key-mode').value,
    };
  }
  if (t === 'scroll') return {
    type:'scroll',
    direction: wrap.querySelector('.ap-scroll-dir').value,
    clicks: 1,
  };
  return {type:'none'};
}

// ─────────────────────────────────────────────────────────────────────────
// Devices panel
// ─────────────────────────────────────────────────────────────────────────
const DEVICE_TYPES = ['buttons','joystick','knob','distance','movement'];
const DEVICE_INPUTS = {
  buttons:  ['b0','b1','b2'],
  joystick: ['jp'],
  knob:     ['cw','ccw','btn'],
  distance: ['near','far'],
  movement: [],  // axis-based, no keymap entries
};
const INPUT_LABELS = {
  b0:'Button A', b1:'Button B', b2:'Button C',
  jp:'Push (joystick)', cw:'Rotate CW', ccw:'Rotate CCW', btn:'Push (knob)',
  near:'Object near', far:'Object far',
};

let _devices = {};
let _deviceSettings = {};
let _keymap = {};

function buildDevicePanel(addr, dev) {
  const card = document.createElement('div');
  card.className = 'device-card' + (dev.type==='unknown' ? ' unknown' : '');
  card.dataset.addr = addr;

  const badge = document.createElement('div');
  badge.className = 'device-type-badge' + (dev.type==='unknown' ? ' unknown' : '');
  badge.textContent = dev.type === 'unknown' ? `Unknown — 0x${parseInt(addr).toString(16).toUpperCase()}` : dev.label;
  card.appendChild(badge);

  const addrLine = document.createElement('small');
  addrLine.textContent = `I²C 0x${parseInt(addr).toString(16).toUpperCase().padStart(2,'0')}`;
  card.appendChild(addrLine);

  if (dev.type === 'unknown') {
    // Type selector + configure button
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:6px;margin-top:8px;align-items:center;';
    const sel = document.createElement('select'); sel.className = 'unknown-type-sel';
    DEVICE_TYPES.forEach(tp => {
      const o = document.createElement('option'); o.value=tp; o.textContent=tp.charAt(0).toUpperCase()+tp.slice(1);
      sel.appendChild(o);
    });
    const btn = document.createElement('button'); btn.textContent='Configure'; btn.className='primary';
    btn.onclick = async () => {
      const type = sel.value;
      const res = await api('POST','/api/devices',{addr:parseInt(addr),type});
      if (res.ok) { ok('Device configured.'); await loadDevicesAndMapping(); }
      else err('Configure failed.');
    };
    row.appendChild(sel); row.appendChild(btn);
    card.appendChild(row);
  }
  return card;
}

function buildDistanceSettings(addr, ds) {
  const wrap = document.createElement('div');
  wrap.style.marginTop='8px';
  wrap.innerHTML = `
    <div class="kv"><span>Near threshold (mm)</span>
      <input type="number" id="dist_near_${addr}" min="10" max="2000" step="10" value="${ds.dist_near_mm||150}">
    </div>
    <div class="kv"><span>Far threshold (mm)</span>
      <input type="number" id="dist_far_${addr}" min="10" max="5000" step="10" value="${ds.dist_far_mm||400}">
    </div>
    <div class="kv"><span>Cooldown (ms)</span>
      <input type="number" id="dist_cd_${addr}" min="100" max="5000" step="100" value="${ds.dist_cooldown_ms||500}">
    </div>`;
  const btn = document.createElement('button');
  btn.textContent='Save'; btn.style.marginTop='6px';
  btn.onclick = async () => {
    const ds2 = {
      dist_near_mm:     parseFloat(document.getElementById(`dist_near_${addr}`).value)||150,
      dist_far_mm:      parseFloat(document.getElementById(`dist_far_${addr}`).value)||400,
      dist_cooldown_ms: parseInt(document.getElementById(`dist_cd_${addr}`).value)||500,
    };
    await api('POST','/api/devices',{addr:parseInt(addr),device_settings:ds2});
    ok('Distance settings saved.');
  };
  wrap.appendChild(btn);
  return wrap;
}

function buildIMUSettings(addr, ds) {
  const modeVal = ds.imu_mode || 'relative';
  const rotVal = String(ds.imu_rotation ?? 0);
  const wrap = document.createElement('div');
  wrap.style.marginTop='8px';
  wrap.innerHTML = `
    <label>Mode
      <select id="imu_mode_${addr}">
        <option value="relative">Relative mouse</option>
        <option value="dpad">D-Pad (arrow keys)</option>
        <option value="disabled">Disabled</option>
      </select>
    </label>
    <label>Mounting rotation
      <select id="imu_rot_${addr}">
        <option value="0">0° (flat)</option>
        <option value="90">+90°</option>
        <option value="-90">-90°</option>
      </select>
    </label>
    <small>Use if the module is mounted perpendicular to the surface, to correct which way is "up".</small>
    <div class="kv"><span>Sensitivity X</span><input type="number" id="imu_sx_${addr}" min="0.1" max="50" step="0.5" value="${ds.imu_sensX||5}"></div>
    <div class="kv"><span>Sensitivity Y</span><input type="number" id="imu_sy_${addr}" min="0.1" max="50" step="0.5" value="${ds.imu_sensY||5}"></div>
    <label><input type="checkbox" id="imu_ix_${addr}" ${ds.imu_invert_x?'checked':''}> Invert X</label>
    <label><input type="checkbox" id="imu_iy_${addr}" ${ds.imu_invert_y?'checked':''}> Invert Y</label>
    <div class="kv"><span>D-Pad threshold</span><input type="number" id="imu_thr_${addr}" min="0.05" max="0.95" step="0.05" value="${ds.imu_threshold||0.30}"></div>`;
  document.createElement('option'); // trick to avoid lint; harmless
  const btn = document.createElement('button');
  btn.textContent='Save'; btn.style.marginTop='6px';
  btn.onclick = async () => {
    const ds2 = {
      imu_mode:     document.getElementById(`imu_mode_${addr}`).value,
      imu_rotation: parseInt(document.getElementById(`imu_rot_${addr}`).value, 10) || 0,
      imu_sensX:    parseFloat(document.getElementById(`imu_sx_${addr}`).value)||5,
      imu_sensY:    parseFloat(document.getElementById(`imu_sy_${addr}`).value)||5,
      imu_invert_x:  document.getElementById(`imu_ix_${addr}`).checked,
      imu_invert_y:  document.getElementById(`imu_iy_${addr}`).checked,
      imu_threshold: parseFloat(document.getElementById(`imu_thr_${addr}`).value)||0.30,
    };
    await api('POST','/api/devices',{addr:parseInt(addr),device_settings:ds2});
    ok('IMU settings saved.');
  };
  wrap.appendChild(btn);
  // Set select values after insertion
  setTimeout(()=>{
    const s=document.getElementById(`imu_mode_${addr}`); if(s) s.value=modeVal;
    const r=document.getElementById(`imu_rot_${addr}`);  if(r) r.value=rotVal;
  },0);
  return wrap;
}

// ─────────────────────────────────────────────────────────────────────────
// Input mapping panel
// ─────────────────────────────────────────────────────────────────────────
function buildMappingRows(devices, keymap) {
  const container = $('#mappingRows');
  container.innerHTML = '';
  let hasAny = false;

  Object.entries(devices).forEach(([addr, dev]) => {
    const inputs = DEVICE_INPUTS[dev.type] || [];
    const ds = _deviceSettings[addr] || {};
    const hasSettings = ['movement', 'distance', 'knob'].includes(dev.type);
    if (inputs.length === 0 && !hasSettings) return;
    hasAny = true;
    const addrHex = parseInt(addr).toString(16).padStart(2,'0');

    const col = document.createElement('div');
    col.className = 'card';
    col.style.minWidth = '280px';

    const title = document.createElement('h3');
    title.textContent = `${dev.label}  (0x${addrHex.toUpperCase()})`;
    col.appendChild(title);

    inputs.forEach(inp => {
      const mapKey = `${addrHex}:${inp}`;
      const action = keymap[mapKey] || {type:'none'};

      const row = document.createElement('div');
      row.style.cssText = 'margin:8px 0;';
      const lbl = document.createElement('label');
      lbl.textContent = INPUT_LABELS[inp] || inp;
      lbl.style.color = 'var(--muted)';
      lbl.style.fontSize = '13px';
      row.appendChild(lbl);

      buildPicker(row, mapKey, action);
      col.appendChild(row);
    });

    // Per-device settings appended below input pickers
    if (dev.type === 'knob') {
      const sep = document.createElement('hr');
      sep.style.cssText = 'margin:10px 0;opacity:0.3';
      col.appendChild(sep);
      const inv = document.createElement('label');
      inv.style.marginTop = '4px';
      const cb = document.createElement('input'); cb.type = 'checkbox'; cb.id = `knob_invert_${addr}`;
      cb.checked = !!ds.knob_invert;
      inv.appendChild(cb); inv.appendChild(document.createTextNode(' Invert direction'));
      col.appendChild(inv);
      const saveBtn = document.createElement('button');
      saveBtn.textContent = 'Save'; saveBtn.style.marginTop = '6px';
      saveBtn.onclick = async () => {
        await api('POST', '/api/devices', {addr: parseInt(addr), device_settings: {knob_invert: cb.checked}});
        ok('Knob settings saved.');
      };
      col.appendChild(saveBtn);
    }
    if (dev.type === 'distance') {
      const sep = document.createElement('hr');
      sep.style.cssText = 'margin:10px 0;opacity:0.3';
      col.appendChild(sep);
      col.appendChild(buildDistanceSettings(addr, ds));
    }
    if (dev.type === 'movement') {
      col.appendChild(buildIMUSettings(addr, ds));
    }

    container.appendChild(col);
  });

  if (!hasAny) {
    container.innerHTML = '<small>No devices with mappable inputs detected yet.</small>';
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Load / save
// ─────────────────────────────────────────────────────────────────────────
function updatePointerVisibility(devices) {
  const hasJoy = Object.values(devices).some(d => d.type === 'joystick');
  $('#pointerSettings').classList.toggle('hidden', !hasJoy);
}

async function loadDevicesAndMapping() {
  const [devRes, kmRes] = await Promise.all([
    api('GET', '/api/devices'),
    api('GET', '/api/keymap'),
  ]);
  if (!devRes.ok) return;

  _devices        = devRes.devices        || {};
  _deviceSettings = devRes.device_settings || {};
  _keymap         = kmRes || {};

  // Rebuild device panel
  const dl = $('#deviceList');
  dl.innerHTML = '';
  const devEntries = Object.entries(_devices);
  if (devEntries.length === 0) {
    dl.innerHTML = '<small>No devices found on I²C bus.</small>';
  } else {
    devEntries.forEach(([addr, dev]) => dl.appendChild(buildDevicePanel(addr, dev)));
  }

  // Rebuild mapping panel and pointer section visibility
  buildMappingRows(_devices, _keymap);
  updatePointerVisibility(_devices);
}

async function loadSettings() {
  const s = await api('GET', '/api/settings').catch(()=>null);
  if (!s) { err('Cannot reach /api/settings'); return; }

  $('#hidEnabled').checked  = !!(s.hidEnabled ?? true);
  reflectHID($('#hidEnabled').checked);
  $('#mode').value          = s.mode || 'relative';
  $('#sensX').value         = s.sensX;   $('#sensXv').textContent = s.sensX;
  $('#sensY').value         = s.sensY;   $('#sensYv').textContent = s.sensY;
  $('#accel').value         = s.accel;   $('#accelv').textContent = s.accel;
  $('#dead').value          = s.dead;    $('#deadv').textContent  = s.dead;
  $('#invertY').checked     = !!s.invertY;
  $('#dpadThreshold').value         = s.dpadThreshold    ?? 0.35;
  $('#dpadReleaseFactor').value     = s.dpadReleaseFactor ?? 0.70;
  $('#dpadDiagonal').value          = s.dpadDiagonal     ?? 'stronger';
  $('#dpadRepeat').checked          = !!(s.dpadRepeat ?? true);
  $('#dpadInitialDelayMs').value    = s.dpadInitialDelayMs ?? 350;
  $('#dpadRepeatMs').value          = s.dpadRepeatMs      ?? 70;

  showModePanels($('#mode').value);
}

async function saveSettings(opts={}) {
  const body = {
    hidEnabled: $('#hidEnabled').checked,
    mode:       $('#mode').value,
    sensX:  parseFloat($('#sensX').value),
    sensY:  parseFloat($('#sensY').value),
    accel:  parseFloat($('#accel').value),
    dead:   parseFloat($('#dead').value),
    invertY: $('#invertY').checked,
    dpadThreshold:      parseFloat($('#dpadThreshold').value),
    dpadReleaseFactor:  parseFloat($('#dpadReleaseFactor').value),
    dpadDiagonal:       $('#dpadDiagonal').value,
    dpadRepeat:         $('#dpadRepeat').checked,
    dpadInitialDelayMs: parseInt($('#dpadInitialDelayMs').value,10) || 350,
    dpadRepeatMs:       parseInt($('#dpadRepeatMs').value,10)       || 70,
  };
  try {
    await api('POST', '/api/settings', body);
    if (!opts.silent) ok('Pointer settings saved.');
  } catch(e) {
    if (!opts.silent) err('Failed to save settings.');
  }
}

async function saveKeymap() {
  const body = {};
  document.querySelectorAll('[data-picker]').forEach(wrap => {
    body[wrap.dataset.picker] = getPickerValue(wrap);
  });
  try {
    await api('POST', '/api/keymap', body);
    ok('Input mapping saved.');
  } catch(e) {
    err('Failed to save mapping.');
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Live polling
// ─────────────────────────────────────────────────────────────────────────
function renderLiveDevices(devicesState) {
  const container = $('#liveDevices');
  if (!devicesState || Object.keys(devicesState).length === 0) {
    container.innerHTML = '<small>Waiting for data…</small>';
    return;
  }
  // Build one mini-card per device
  const html = Object.entries(devicesState).map(([addr, d]) => {
    const addrHex = parseInt(addr).toString(16).toUpperCase().padStart(2,'0');
    const dev = _devices[addr] || {};
    const label = dev.label || dev.type || '?';
    const rows = Object.entries(d).map(([k,v]) => {
      const val = typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(3)) : String(v);
      return `<div class="kv"><span>${k}</span><code>${val}</code></div>`;
    }).join('');
    return `<div class="card" style="min-width:180px">
      <div style="font-weight:600;margin-bottom:4px">${label} <small>0x${addrHex}</small></div>
      ${rows || '<small>—</small>'}
    </div>`;
  }).join('');
  container.innerHTML = html;
}

async function pollState() {
  try {
    const data = await api('GET', '/api/state');
    if (!data || !data.ok) return;
    const s   = data.state    || {};
    const cfg = data.settings || {};
    const devs= data.devices  || {};
    const ts  = s.ts ? new Date(s.ts*1000).toLocaleTimeString() : '—';

    $('#live_ts').textContent = ts;
    reflectHID(!!(s.hid ?? cfg.hidEnabled));
    renderLiveDevices(s.devices || {});

    // Refresh device list if new devices appeared
    const devCount = Object.keys(devs).length;
    const knownCount = Object.keys(_devices).length;
    if (devCount !== knownCount) {
      await loadDevicesAndMapping();
    }
  } catch(e) { /* no-op */ }
}

// ─────────────────────────────────────────────────────────────────────────
// Event bindings
// ─────────────────────────────────────────────────────────────────────────
function bindUI() {
  const upd = (id, vid) => $(id).addEventListener('input', () => $(vid).textContent = $(id).value);
  upd('#sensX','#sensXv'); upd('#sensY','#sensYv');
  upd('#accel','#accelv'); upd('#dead','#deadv');

  $('#mode').addEventListener('change', () => showModePanels($('#mode').value));

  $('#hidEnabled').addEventListener('change', async () => {
    await saveSettings({silent:true});
    reflectHID($('#hidEnabled').checked);
  });
  $('#saveSettings').addEventListener('click', saveSettings);
  $('#saveKeymap').addEventListener('click', saveKeymap);

  $('#nudge').addEventListener('click', async () => {
    try { await api('POST','/api/nudge'); ok('Nudged cursor.'); }
    catch(e) { err('Nudge failed.'); }
  });

  $('#rescan').addEventListener('click', async () => {
    ok('Rescanning I²C bus…');
    try {
      await api('POST', '/api/rescan');
      // wait briefly for MCU to scan and send device_found events back
      setTimeout(async () => { await loadDevicesAndMapping(); ok('Rescan complete.'); }, 1200);
    } catch(e) { err('Rescan failed.'); }
  });
}

// ─────────────────────────────────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────────────────────────────────
(async function init() {
  bindUI();
  await loadSettings();
  await loadDevicesAndMapping();
  // Auto-scan if no devices came in via startup events yet
  if (Object.keys(_devices).length === 0) {
    ok('No devices yet — triggering I²C scan…');
    try {
      await api('POST', '/api/rescan');
      await new Promise(r => setTimeout(r, 1400));
      await loadDevicesAndMapping();
    } catch(e) { /* best effort */ }
  }
  ok('Ready. Devices will appear as they are discovered.');
  setInterval(pollState, 200);
  pollState();
})();