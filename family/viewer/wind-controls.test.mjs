import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';
import { createSceneLoader } from './load-lifecycle.mjs';
import { createWindControls, BASE_WIND_LIMIT, MAX_GUST_PEAK, MIN_GUST_DURATION, MAX_GUST_DURATION } from './wind-controls.mjs';
import { readViewState, writeViewState, defaultViewState } from './view-state.mjs';
import { fitCamera, cameraScale, worldToPanel, zoomAt, referenceFrame } from './viewport.mjs';
import { drawOverlay } from './debug-overlay.mjs';
import { outfitAssets, ownAssets } from './outfits.mjs';
import { createOutfitTransaction } from './outfit-transaction.mjs';

const near = (actual, expected, tolerance = 1e-8) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);

test('diagnostic peak defaults to 48 and combines with the broad base without a hidden total cap', () => {
  const wind = createWindControls();
  wind.triggerGust();
  near(wind.advance(1.2).wind, 48);
  for (const sign of [-1, 1]) {
    wind.restore(null);
    wind.setBase(sign * 100);
    wind.setGustPeak(200);
    wind.triggerGust();
    near(wind.advance(1.2).wind, sign * 300);
    near(wind.advance(1.2).wind, sign * 100);
  }
});

test('invalid settings refuse atomically instead of silently clipping the requested test', () => {
  const wind = createWindControls();
  wind.setBase(75);
  const invalidSettings = [
    ['setBase', 101], ['setBase', -101],
    ['setGustPeak', 201], ['setGustPeak', -1],
    ['setGustDuration', 0], ['setGustDuration', 21],
  ];
  for (const [method, bad] of invalidSettings) {
    const before = wind.snapshot();
    assert.throws(() => wind[method](bad), RangeError);
    assert.deepEqual(wind.snapshot(), before);
  }
  for (const bad of [NaN, Infinity, -Infinity]) {
    for (const method of ['setBase', 'setGustPeak', 'setGustDuration']) {
      assert.throws(() => wind[method](bad), RangeError);
    }
  }
  for (const bad of [-1, NaN, Infinity]) assert.throws(() => wind.advance(bad), RangeError);
});

test('pulse settings and direction remain continuous during a pulse and apply on the next one', () => {
  const wind = createWindControls();
  wind.setBase(10);
  wind.triggerGust();
  near(wind.advance(1.2).wind, 58);

  wind.setGustPeak(200);
  wind.setGustDuration(6);
  wind.setBase(-10);
  near(wind.read().wind, 38);
  wind.triggerGust();
  near(wind.read().wind, 38);
  assert.equal(wind.read().activeGustDuration, 2.4);

  near(wind.advance(1.2).wind, -10);
  wind.triggerGust();
  near(wind.advance(3).wind, -210);
});

test('both extreme durations, directions, repeat and opposite base remain finite without a hidden envelope', () => {
  for (const duration of [0.1, 20]) {
    for (const sign of [-1, 1]) {
      const wind = createWindControls();
      wind.setBase(sign * 100);
      wind.setGustPeak(200);
      wind.setGustDuration(duration);
      wind.setRepeat(true);
      near(wind.advance(duration / 2).wind, sign * 300);

      wind.setBase(-sign * 100);
      near(wind.read().wind, sign * 100);
      wind.triggerGust();
      near(wind.read().wind, sign * 100);
      near(wind.advance(duration / 2).wind, -sign * 100);

      const gap = Math.max(6, duration + 0.6) - duration;
      wind.advance(gap + duration / 2);
      near(wind.read().wind, -sign * 300, 1e-7);
      wind.setBreeze(true);
      for (let i = 0; i < 200; i++) assert.ok(Number.isFinite(wind.advance(0.13).wind));
    }
  }
});

test('repeat uses six-second starts for short pulses and leaves a gap after long pulses', () => {
  const wind = createWindControls();
  wind.setRepeat(true);
  near(wind.advance(1.2).wind, 48);
  wind.setRepeat(false);
  near(wind.advance(1.2).wind, 0);
  near(wind.advance(10).wind, 0);

  wind.restore(null);
  wind.setGustDuration(20);
  wind.setRepeat(true);
  assert.equal(wind.advance(20.1).gusting, false);
  assert.equal(wind.advance(0.6).gusting, true);
  assert.ok(wind.read().gust > 0);
  assert.ok(Number.isFinite(wind.advance(1e6).wind));
});

test('breeze retains its numeric waveform and composes with the diagnostic pulse without total clipping', () => {
  const wind = createWindControls();
  wind.setBase(2);
  wind.setBreeze(true);
  near(wind.advance(1).wind, 2.8763410617769942);
  wind.setBreeze(false);
  assert.equal(wind.read().wind, 2);

  wind.restore(null);
  wind.setBase(100);
  wind.setBreeze(true);
  wind.setGustPeak(200);
  wind.setGustDuration(2);
  wind.triggerGust();
  near(wind.advance(1).wind, 300.876341061777);
  wind.setBreeze(false);
  near(wind.read().wind, 300);
  near(wind.advance(1).wind, 100);
});

test('snapshot retains stable configuration and restore begins a fresh test; corrupt restore is atomic', () => {
  const wind = createWindControls();
  wind.setBase(-80);
  wind.setGustPeak(180);
  wind.setGustDuration(0.4);
  wind.setBreeze(true);
  wind.setRepeat(true);
  wind.advance(0.2);

  const saved = wind.snapshot();
  const copy = createWindControls();
  copy.restore(JSON.parse(JSON.stringify(saved)));
  assert.deepEqual(copy.snapshot(), saved);
  assert.equal(copy.read().time, 0);
  near(copy.read().gust, 0);
  assert.equal(copy.read().gusting, true);

  const invalidSnapshots = [
    { ...saved, version: 2 }, { ...saved, gustPeak: Infinity },
    { ...saved, repeat: 'yes' }, [], undefined,
  ];
  for (const value of invalidSnapshots) {
    const before = copy.read();
    assert.throws(() => copy.restore(value), RangeError);
    assert.deepEqual(copy.read(), before);
  }
  copy.restore(null);
  assert.deepEqual(copy.snapshot(), createWindControls().snapshot());
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
      toggle(name, force = !classes.has(name)) {
        if (force) classes.add(name); else classes.delete(name);
        return force;
      },
    };
  }
  appendChild(child) {
    this.children.push(child);
    child.parent = this;
    return child;
  }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
  addEventListener(name, listener) { (this.listeners[name] ??= []).push(listener); }
  getContext() { return null; }
  fire(name) { for (const listener of this.listeners[name] ?? []) listener(); }
  setAttribute(name, value) { this.attributes.set(name, value); }
}

async function viewerHarness(storage = { getItem() { return null; }, setItem() {} }) {
  const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, new Element());
    return nodes.get(id);
  };
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
    createSceneLoader, createWindControls, BASE_WIND_LIMIT, MAX_GUST_PEAK, MIN_GUST_DURATION, MAX_GUST_DURATION,
    readViewState, writeViewState, defaultViewState, fitCamera, cameraScale, worldToPanel, zoomAt, referenceFrame, drawOverlay, outfitAssets, ownAssets, createOutfitTransaction,
    localStorage: storage, RigPlayer: Player,
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
    html, node, viewer: context.viewer, created, storage,
    change(id, value) {
      node(id).value = String(value);
      node(id).fire('change');
    },
    input(id, value) {
      node(id).value = String(value);
      node(id).fire('input');
    },
    click(id) { if (!node(id).disabled) node(id).fire('click'); },
    step(seconds, frames = Math.round(seconds * 60)) {
      for (let i = 0; i < frames; i++) {
        now += seconds * 1000 / frames;
        assert.equal(pendingFrames.length, 1);
        pendingFrames.shift()(now);
      }
    },
    blockLoad() { pendingLoad = {}; },
    releaseLoad() {
      pendingLoad.resolve();
      pendingLoad = null;
    },
  };
}

test('actual HTML default gust delivers peak 48 to every player with the base slider left at zero', async () => {
  const h = await viewerHarness();
  assert.equal(h.node('wind').value, '0');
  h.click('pulseBtn');
  h.step(1.2);
  near(h.viewer.state().wind, 48);
  assert.equal(h.node('windCurrent').textContent, '48.0');
  assert.equal(h.node('wind').value, '0');
  assert.equal(h.node('pulseBtn').disabled, true);
  for (const entry of h.viewer.players()) {
    near(entry.player.env.wind[0], 48);
    near(entry.player.frames.at(-1).wind, 48);
  }
  h.click('pulseBtn');
  near(h.viewer.state().wind, 48);
  h.step(1.2 + 1 / 60);
  near(h.viewer.state().wind, 0);
  assert.equal(h.node('pulseBtn').disabled, false);
  h.viewer.dispose();
});

test('actual HTML diagnostic inputs send the requested stress to every player', async () => {
  const h = await viewerHarness();
  assert.equal(h.viewer.players().length, 5);
  h.input('wind', 100);
  h.change('gustPeak', 200);
  h.change('gustDuration', 0.4);
  h.click('pulseBtn');
  h.step(0.2);
  near(h.viewer.state().wind, 300);
  assert.equal(h.node('windCurrent').textContent, '300.0');
  for (const entry of h.viewer.players()) near(entry.player.frames.at(-1).wind, 300);
  h.step(0.2 + 1 / 60);
  near(h.viewer.state().wind, 100);
  assert.equal(h.node('pulseBtn').disabled, false);
  h.viewer.dispose();
});

test('actual HTML retains gravity and applies exactly one composed environment to each player per frame', async () => {
  const h = await viewerHarness();
  h.input('wind', 75);
  h.input('gravity', -1.5);
  h.change('gustPeak', 120);
  h.change('gustDuration', 2);
  h.click('gustBtn');
  h.click('pulseBtn');
  const counts = h.viewer.players().map(entry => entry.player.environments.length);
  h.step(0.5);
  const expected = h.viewer.state().wind;

  assert.equal(h.node('wind').value, '75');
  assert.equal(h.node('windVal').textContent, '75.0');
  assert.equal(h.node('gustBtn').attributes.get('aria-pressed'), 'true');
  assert.equal(h.node('windCurrent').textContent, expected.toFixed(1));
  for (const [index, entry] of h.viewer.players().entries()) {
    assert.equal(entry.player.environments.length - counts[index], 30);
    near(entry.player.env.wind[0], expected);
    assert.equal(entry.player.env.gravity[1], -1.5);
    near(entry.player.frames.at(-1).wind, expected);
  }

  // A gravity-only input must retain the current base/breeze/pulse composition.
  h.input('gravity', 2.5);
  near(h.viewer.state().wind, expected);
  for (const entry of h.viewer.players()) {
    near(entry.player.env.wind[0], expected);
    assert.equal(entry.player.env.gravity[1], 2.5);
  }
  h.click('gustBtn');
  h.step(1.5 + 1 / 60);
  near(h.viewer.state().wind, 75);
  h.viewer.dispose();
});

test('actual HTML pause, speed and loading keep the diagnostic clock and players together', async () => {
  const h = await viewerHarness();
  h.click('pulseBtn');
  h.step(0.6);
  near(h.viewer.state().wind, 24);

  h.click('pauseBtn');
  const state = h.viewer.state();
  const count = h.viewer.players()[0].player.frames.length;
  h.step(3);
  assert.deepEqual(h.viewer.state(), state);
  assert.equal(h.viewer.players()[0].player.frames.length, count);

  h.input('speed', 2);
  h.click('pauseBtn');
  h.step(0.3);
  near(h.viewer.state().wind, 48);
  h.blockLoad();
  const loading = h.viewer.openCharacter('nova');
  const time = h.viewer.state().time;
  h.step(2);
  near(h.viewer.state().time, time);

  h.releaseLoad();
  await loading;
  assert.equal(h.viewer.players().length, 1);
  near(h.viewer.players()[0].player.env.wind[0], 48);
  h.step(0.6 + 1 / 60);
  near(h.viewer.state().wind, 0);
  h.viewer.dispose();
});

test('actual HTML stores stress configuration and resets the diagnostic on reload', async () => {
  let saved = null;
  const storage = {
    getItem() { return saved; },
    setItem(key, value) { saved = value; },
  };
  const h = await viewerHarness(storage);
  h.input('wind', -100);
  h.change('gustPeak', 190);
  h.change('gustDuration', 20);
  h.click('gustBtn');
  h.click('repeatGustBtn');
  h.step(0.5);

  const next = await viewerHarness(storage);
  assert.equal(next.viewer.state().base, -100);
  assert.equal(next.viewer.state().gustPeak, 190);
  assert.equal(next.viewer.state().gustDuration, 20);
  assert.equal(next.viewer.state().breeze, true);
  assert.equal(next.viewer.state().repeat, true);
  assert.equal(next.viewer.state().time, 0);
  h.viewer.dispose();
  next.viewer.dispose();
});


test('actual HTML numeric inputs survive UI synchronization and reload before a change event', async () => {
  let saved = null;
  const storage = {
    getItem() { return saved; },
    setItem(key, value) { saved = value; },
  };
  const h = await viewerHarness(storage);
  // Typing/filling dispatches input before blur/change. An unrelated UI action
  // must not replace these valid edits with the previous controller settings.
  h.input('gustPeak', 96);
  h.input('gustDuration', 4);
  h.click('bonesBtn');
  assert.equal(h.node('gustPeak').value, '96');
  assert.equal(h.node('gustDuration').value, '4');
  assert.equal(h.viewer.state().gustPeak, 96);
  assert.equal(h.viewer.state().gustDuration, 4);

  const next = await viewerHarness(storage);
  assert.equal(next.node('gustPeak').value, '96');
  assert.equal(next.node('gustDuration').value, '4');
  assert.equal(next.viewer.state().gustPeak, 96);
  assert.equal(next.viewer.state().gustDuration, 4);

  // An incomplete or out-of-range draft remains editable until change, while
  // the last valid diagnostic configuration remains standing and persisted.
  h.input('gustPeak', '');
  h.input('gustDuration', 0);
  assert.equal(h.node('gustPeak').value, '');
  assert.equal(h.node('gustDuration').value, '0');
  assert.equal(h.viewer.state().gustPeak, 96);
  assert.equal(h.viewer.state().gustDuration, 4);
  h.change('gustPeak', '');
  h.change('gustDuration', 0);
  assert.equal(h.node('gustPeak').value, '96');
  assert.equal(h.node('gustDuration').value, '4');
  h.viewer.dispose();
  next.viewer.dispose();
});
