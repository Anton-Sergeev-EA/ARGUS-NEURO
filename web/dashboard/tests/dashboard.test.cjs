const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function harness() {
  class Element {
    constructor() { this.textContent = ''; this.children = []; this.nodes = new Map(); this.style = {}; this.dataset = {}; this.handlers = {}; this.classList = { toggle() {} }; }
    addEventListener(name, fn) { this.handlers[name] = fn; }
    querySelector(selector) { if (!this.nodes.has(selector)) this.nodes.set(selector, new Element()); return this.nodes.get(selector); }
    querySelectorAll() { return []; }
    appendChild(child) { this.children.push(child); }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    remove() {}
    getContext() { return null; }
  }
  const ids = new Map();
  const timers = new Map();
  let timerId = 0;
  class Socket {
    static OPEN = 1;
    constructor() { this.handlers = {}; this.readyState = 0; }
    addEventListener(name, fn) { this.handlers[name] = fn; }
    close() { this.handlers.close?.(); }
    emit(name, event = {}) { if (name === 'open') this.readyState = 1; this.handlers[name]?.(event); }
  }
  const context = vm.createContext({
    console, Date, Map, Set, JSON, Math, Number, String, Array,
    WebSocket: Socket, location: { protocol: 'http:', host: 'localhost' },
    window: { devicePixelRatio: 1 },
    getComputedStyle: () => ({ getPropertyValue: () => '#aaa' }),
    setTimeout: fn => { const id = ++timerId; timers.set(id, fn); return id; },
    clearTimeout: id => timers.delete(id),
    setInterval: fn => { const id = ++timerId; timers.set(id, fn); return id; },
    clearInterval: id => timers.delete(id),
    document: { documentElement: new Element(), querySelectorAll: () => [], createElement: () => new Element(), getElementById: id => { if (!ids.has(id)) ids.set(id, new Element()); return ids.get(id); } },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8'), context);
  return { run: code => vm.runInContext(code, context), ids };
}

test('connection failure never silently starts artificial telemetry', () => {
  const h = harness();
  h.run("socket.emit('open'); socket.emit('close')");
  assert.equal(h.run('state.mode'), 'disconnected');
  assert.equal(h.run('offlineTimer'), null);
  assert.equal(h.run('state.assets.size'), 0);
  assert.equal(h.run('reconnectTimer !== null'), true);
});

test('demo is explicit and its data is cleared on reconnect', () => {
  const h = harness();
  h.ids.get('demoBtn').handlers.click();
  assert.equal(h.run('state.mode'), 'demo');
  assert.equal(h.run('state.source'), 'browser_demo');
  assert.equal(h.run('state.assets.size'), 3);
  h.ids.get('reconnectBtn').handlers.click();
  assert.equal(h.run('state.assets.size'), 0);
  assert.equal(h.run('offlineTimer'), null);
});

test('warmup nulls, stale feed and untrusted labels render safely', () => {
  const h = harness();
  h.run(`socket.emit('open'); ingestTick({type:'tick', source:'simulation', assets:[{asset_id:'<img src=x onerror=alert(1)>', asset_type:'UAV_PDU', sensors:{temperature_c:42}, assessment:{health_index:null, is_anomaly:null, rul_hours:null, status:'warming_up', data_quality:{samples_collected:1,samples_required:24,issues:[]}, evidence:[], explanation:[]}}]})`);
  assert.equal(h.run("[...state.cards.values()][0].querySelector('.asset-id').textContent"), '<img src=x onerror=alert(1)>');
  assert.equal(h.run("[...state.cards.values()][0].querySelector('.m-rul').textContent"), '—');
  h.run('state.lastReceived = Date.now() - 20000; render()');
  assert.equal(h.run('isStale()'), true);
  assert.equal(h.run('offlineTimer'), null);
});
