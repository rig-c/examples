import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';
import { createSceneLoader } from './load-lifecycle.mjs';
import { createWindControls } from './wind-controls.mjs';

const near = (actual, expected, tolerance = 1e-9) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);

test('still air, extended signed range and invalid inputs', () => {
  const wind = createWindControls();
  assert.equal(wind.read().wind, 0);
  for (const value of [-6, -4, 0, 4, 6]) {
    wind.setBase(value);
    assert.equal(wind.advance(0.25).wind, value);
  }
  wind.setBase(100);
  assert.equal(wind.read().wind, 6);
  wind.setBase(-100);
  assert.equal(wind.read().wind, -6);
  for (const bad of [NaN, Infinity, -Infinity]) assert.throws(() => wind.setBase(bad), /base wind/);
  for (const bad of [NaN, Infinity, -0.1]) assert.throws(() => wind.advance(bad), /wind dt/);
});

test('one smooth 2.4-second gust adds 6, follows the starting base sign and returns to base', () => {
  for (const base of [-3, 0, 3]) {
    const wind = createWindControls();
    wind.setBase(base);
    wind.triggerGust();
    assert.equal(wind.read().wind, base);
    // Flat start/end slopes prevent an impulse when the pulse begins or ends.
    assert.ok(Math.abs(wind.advance(0.0001).wind - base) < 0.000001);
    near(wind.advance(1.2 - 0.0001).wind, base + (base < 0 ? -6 : 6));
    near(wind.advance(1.2).wind, base);
    assert.equal(wind.read().gusting, false);
  }
  const wind = createWindControls();
  wind.setBase(-2);
  wind.triggerGust();
  wind.setBase(2);
  near(wind.advance(1.2).wind, -4, 1e-8); // Direction belongs to this pulse's start.
});

test('repeated clicks keep one continuous pulse; repeat uses a six-second start interval and finishes when disabled', () => {
  const wind = createWindControls();
  wind.setRepeat(true);
  near(wind.advance(1.2).wind, 6);
  wind.triggerGust();
  near(wind.read().wind, 6);
  near(wind.advance(1.2).wind, 0);
  near(wind.advance(3.6).wind, 0);
  near(wind.advance(1.2).wind, 6);
  wind.setRepeat(false);
  near(wind.read().wind, 6);
  near(wind.advance(1.2).wind, 0);
  near(wind.advance(6).wind, 0);
  // A large elapsed step retains the pulse phase rather than accumulating pulses.
  wind.setRepeat(true);
  near(wind.advance(13.2).wind, 6, 1e-8);
});

test('base reversal plus clicks and enabling repeat preserve the current pulse, then use the new direction', () => {
  const wind = createWindControls();
  wind.setBase(6);
  wind.triggerGust();
  near(wind.advance(1.2).wind, 12);
  wind.setBase(-6);
  near(wind.read().wind, 0);
  wind.triggerGust();
  near(wind.read().wind, 0);
  wind.setRepeat(true);
  near(wind.read().wind, 0);
  near(wind.read().gust, 6);
  near(wind.advance(1.2).wind, -6);
  near(wind.advance(3.6).wind, -6);
  near(wind.advance(1.2).wind, -12);
});

test('breeze preserves its original waveform, composes with gust/base, and clamps both extremes', () => {
  const wind = createWindControls();
  wind.setBase(2);
  wind.setBreeze(true);
  near(wind.advance(1).wind, 2.8763410617769942);
  wind.setBreeze(false);
  assert.equal(wind.read().wind, 2);
  // At the slider's extremes a gust must still change the actual wind.
  for (const base of [-6, 6]) {
    wind.setBase(base);
    wind.triggerGust();
    const peak = wind.advance(1.2).wind;
    assert.equal(peak, base < 0 ? -12 : 12);
    assert.equal(peak - base, base < 0 ? -6 : 6);
    near(wind.advance(1.2).wind, base);
  }
  for (const base of [-6, 6]) {
    wind.setBase(base);
    wind.setBreeze(true);
    wind.triggerGust();
    for (let i = 0; i < 720; i++) {
      const current = wind.advance(1 / 60);
      assert.ok(Number.isFinite(current.wind) && Math.abs(current.wind) <= 12);
      assert.equal(current.base, base);
    }
  }
});

class Element {
  constructor() {
    this.children = [];
    this.style = {};
    this.clientWidth = 1200;
    this.clientHeight = 800;
    this.value = '';
    this.listeners = {};
    this.attributes = new Map();
    const classes = new Set();
    this.classList = {
      add: name => classes.add(name),
      remove: name => classes.delete(name),
      contains: name => classes.has(name),
      toggle(name, force = !classes.has(name)) { if (force) classes.add(name); else classes.delete(name); return force; },
    };
  }
  appendChild(child) { this.children.push(child); child.parent = this; return child; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
  addEventListener(name, listener) { this.listeners[name] = listener; }
  setAttribute(name, value) { this.attributes.set(name, value); }
}

async function viewerHarness() {
  const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
  const nodes = new Map();
  const node = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  // Read actual input defaults; the VM must not silently supply different UI values.
  for (const match of html.matchAll(/<input\b[^>]*id="([^"]+)"[^>]*>/g)) {
    node(match[1]).value = match[0].match(/value="([^"]*)"/)?.[1] ?? '';
  }
  const created = [];
  const pendingFrames = [];
  let now = 0;
  let pendingLoad = null;
  class Player {
    constructor(sub, assets) {
      this.key = assets.key;
      this.environments = [];
      this.frames = [];
      this.renderer = { syncPixelRatio() {} };
      created.push(this);
    }
    play() {}
    frame(dt) { this.frames.push({ dt, wind: this.env?.wind[0] }); }
    environment(env) {
      assert.ok(env.wind.every(Number.isFinite));
      assert.ok(env.gravity.every(Number.isFinite));
      this.env = env;
      this.environments.push(env);
    }
    dispose() { this.disposed = true; }
  }
  const assets = key => ({ key, animations: [{ name: 'idle' }], stage: { x: -400, y: 0, width: 800, height: 2284 }, dispose() {} });
  const context = {
    createSceneLoader, createWindControls, RigPlayer: Player,
    loadModel({ modelUrl }) {
      const key = modelUrl.split('/')[1];
      if (pendingLoad) return new Promise(resolve => { pendingLoad.resolve = () => resolve(assets(key)); });
      return Promise.resolve(assets(key));
    },
    document: { getElementById: node, createElement: () => new Element(), querySelectorAll: () => [] },
    requestAnimationFrame: fn => pendingFrames.push(fn), performance: { now: () => now }, setTimeout,
    console: { error(error) { throw error; } },
  };
  const source = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1].replace(/^\s*import .*;$/gm, '');
  runInNewContext(source + '\nglobalThis.viewer = { openCharacter, state: () => windControls.read(), players: () => players, dispose: () => sceneLoader.dispose() };', context);
  await new Promise(resolve => setImmediate(resolve));
  return {
    html, node, viewer: context.viewer, created,
    input(id, value) { node(id).value = String(value); node(id).listeners.input(); },
    click(id) { if (!node(id).disabled) node(id).listeners.click(); },
    step(seconds, frames = Math.round(seconds * 60)) {
      for (let i = 0; i < frames; i++) {
        now += seconds * 1000 / frames;
        assert.equal(pendingFrames.length, 1);
        pendingFrames.shift()(now);
      }
    },
    blockLoad() { pendingLoad = {}; },
    releaseLoad() { pendingLoad.resolve(); pendingLoad = null; },
  };
}

test('actual HTML controls preserve selected base, apply one composed environment per frame, and retain gravity', async () => {
  const h = await viewerHarness();
  assert.match(h.html, /id="wind"[^>]*min="-6"[^>]*max="6"[^>]*step="0.1"[^>]*value="0"/);
  assert.equal(h.viewer.players().length, 5);
  for (const entry of h.viewer.players()) assert.equal(entry.player.env.wind[0], 0);
  h.input('wind', 3);
  h.input('gravity', -1.5);
  h.click('gustBtn');
  h.click('pulseBtn');
  const counts = h.viewer.players().map(entry => entry.player.environments.length);
  h.step(1.2);
  assert.equal(h.node('wind').value, '3');
  assert.equal(h.node('windVal').textContent, '3.0');
  assert.equal(h.node('gustBtn').attributes.get('aria-pressed'), 'true');
  const expected = h.viewer.state().wind;
  assert.equal(h.node('windCurrent').textContent, expected.toFixed(1));
  for (const [i, entry] of h.viewer.players().entries()) {
    near(entry.player.env.wind[0], expected);
    assert.equal(entry.player.env.gravity[1], -1.5);
    assert.equal(entry.player.environments.length - counts[i], 72);
    near(entry.player.frames.at(-1).wind, expected);
  }
  h.click('gustBtn');
  h.step(1.2);
  near(h.viewer.state().wind, 3);
  assert.equal(h.node('wind').value, '3');
  h.input('wind', -6);
  h.click('pulseBtn');
  h.step(1.2);
  assert.equal(h.node('windCurrent').textContent, '-12.0');
  h.input('wind', 6);
  // Changing the base mid-pulse does not silently reverse the active gust.
  assert.equal(h.node('windCurrent').textContent, '0.0');
  assert.equal(h.node('pulseBtn').disabled, true);
  assert.equal(h.node('pulseBtn').textContent, '돌풍 진행 중');
  h.click('pulseBtn');
  assert.equal(h.node('windCurrent').textContent, '0.0');
  h.click('repeatGustBtn');
  assert.equal(h.node('windCurrent').textContent, '0.0');
  h.step(1.2 + 1 / 60); // Check after the end frame, independent of float accumulation.
  assert.equal(h.node('pulseBtn').disabled, false);
  assert.equal(h.node('pulseBtn').textContent, '돌풍');
  h.click('pulseBtn');
  h.step(1.2);
  assert.equal(h.node('windCurrent').textContent, '12.0');
  assert.equal(h.node('wind').value, '6');
  h.viewer.dispose();
});

test('actual HTML pause freezes wind and repeat clocks; speed applies to wind and player together', async () => {
  const h = await viewerHarness();
  h.click('repeatGustBtn');
  h.step(0.6);
  near(h.viewer.state().wind, 3);
  h.click('pauseBtn');
  const frozen = h.viewer.state();
  const frameCount = h.viewer.players()[0].player.frames.length;
  h.step(3);
  assert.deepEqual(h.viewer.state(), frozen);
  assert.equal(h.viewer.players()[0].player.frames.length, frameCount);
  h.input('gravity', 2);
  near(h.viewer.players()[0].player.env.wind[0], 3);
  h.input('speed', 2);
  h.click('pauseBtn');
  h.step(0.3);
  near(h.viewer.state().wind, 6);
  near(h.viewer.players()[0].player.frames.at(-1).dt, 1 / 30);
  h.click('repeatGustBtn');
  assert.equal(h.node('repeatGustBtn').attributes.get('aria-pressed'), 'false');
  h.step(0.6);
  near(h.viewer.state().wind, 0);
  h.viewer.dispose();
});

test('actual HTML character load freezes pulse and new players inherit current wind instead of slider base', async () => {
  const h = await viewerHarness();
  h.input('wind', -2);
  h.click('pulseBtn');
  h.step(1.2);
  near(h.viewer.state().wind, -8);
  h.blockLoad();
  const loading = h.viewer.openCharacter('nova');
  const time = h.viewer.state().time;
  h.step(2);
  near(h.viewer.state().time, time);
  h.releaseLoad();
  await loading;
  assert.equal(h.viewer.players().length, 1);
  near(h.viewer.players()[0].player.env.wind[0], -8);
  assert.equal(h.node('wind').value, '-2');
  h.step(1.2);
  near(h.viewer.players()[0].player.env.wind[0], -2);
  h.viewer.dispose();
});
