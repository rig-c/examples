import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';
import { createSceneLoader } from './load-lifecycle.mjs';
import { createWindControls, BASE_WIND_LIMIT, MAX_GUST_PEAK, MIN_GUST_DURATION, MAX_GUST_DURATION } from './wind-controls.mjs';
import { readViewState, writeViewState, defaultViewState } from './view-state.mjs';
import { fitCamera, cameraScale, worldToPanel, zoomAt, referenceFrame } from './viewport.mjs';
import { drawOverlay } from './debug-overlay.mjs';

class Element {
  constructor() {
    this.children = [];
    this.style = {};
    this.clientWidth = 1200;
    this.clientHeight = 800;
    this.listeners = {};
    this.classList = { add() {}, remove() {}, toggle() {}, contains() { return false; } };
  }
  appendChild(child) { this.children.push(child); child.parent = this; return child; }
  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this);
    this.parent = null;
  }
  getContext() { return null; }
  setAttribute() {}
  addEventListener(name, listener) { this.listeners[name] = listener; }
}

function harness() {
  const nodes = new Map();
  const requests = [];
  const created = [];
  const events = [];
  const errors = [];
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, new Element());
    return nodes.get(id);
  };
  const loadModel = ({ modelUrl }) => new Promise((resolve, reject) => {
    const key = modelUrl.split('/')[1];
    const assets = {
      key, animations: [{ name: 'idle' }],
      stage: { x: -400, y: 0, width: 800 + requests.length, height: 2284 },
      disposed: 0,
      dispose() { this.disposed++; events.push(`${key}:assets`); },
    };
    requests.push({ key, assets, resolve: () => resolve(assets), reject });
  });
  class Player {
    constructor(sub, assets) {
      this.assets = assets;
      this.disposed = 0;
      this.fit = 0;
      this.renderer = { syncPixelRatio: () => this.fit++ };
      created.push(this);
    }
    play() { if (this.assets.rejectPlayer) throw new Error('player initialization failed'); }
    frame() {}
    environment() {}
    bounds() { return this.assets.stage; }
    dispose() { this.disposed++; events.push(`${this.assets.key}:player`); }
  }
  const html = readFileSync(process.env.FAMILY_VIEWER_HTML ?? new URL('./index.html', import.meta.url), 'utf8');
  let source = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
  // Execute the actual viewer script, replacing only its browser dependencies
  // and automatic initial navigation. The lifecycle implementation is imported.
  source = source.replace(/^\s*import .*;$/gm, '');
  source = source.replace(/\n    openCharacter\((?:'all5'|ui\.character)\)(?:\.catch\(err => \{[\s\S]*?\n    \}\))?;/, '');
  source += '\nglobalThis.viewer = { openCharacter, state: () => ({ players, container, box, stats: stats.textContent, ref: refImg.src }), dispose: () => { if (typeof sceneLoader !== "undefined") sceneLoader.dispose(); } };';
  const context = {
    loadModel, RigPlayer: Player, createSceneLoader, createWindControls,
    BASE_WIND_LIMIT, MAX_GUST_PEAK, MIN_GUST_DURATION, MAX_GUST_DURATION,
    readViewState, writeViewState, defaultViewState, fitCamera, cameraScale, worldToPanel, zoomAt, referenceFrame, drawOverlay,
    document: { getElementById: node, createElement: () => new Element(), querySelectorAll: () => [] },
    requestAnimationFrame() {}, performance: { now: () => 0 },
    setTimeout, console: { error: error => errors.push(error) },
  };
  runInNewContext(source, context, { filename: 'family/viewer/index.html' });
  return { viewer: context.viewer, requests, created, events, errors, stage: node('stage') };
}

const flush = () => new Promise(resolve => setImmediate(resolve));
const keys = state => Array.from(state.players, player => player.key);

test('slow A cannot publish over B or append its player into B', async () => {
  const h = harness();
  const a = h.viewer.openCharacter('naru');
  const b = h.viewer.openCharacter('nova');
  h.requests[1].resolve();
  await b;
  const before = h.viewer.state();
  const style = before.container.style.cssText;
  h.requests[0].resolve();
  await a;
  const after = h.viewer.state();
  assert.deepEqual(keys(after), ['nova']);
  assert.equal(after.container, before.container);
  assert.equal(after.box, before.box);
  assert.equal(after.stats, before.stats);
  assert.equal(after.ref, before.ref);
  assert.equal(after.container.style.cssText, style);
  assert.equal(h.stage.children.length, 1);
  assert.equal(after.container.children.length, 1);
  assert.equal(h.created.length, 1);
  assert.equal(h.created[0].fit, 1);
  assert.equal(h.requests[0].assets.disposed, 1);
  assert.equal(h.errors.length, 0);
  h.viewer.dispose();
});

test('stale A error cannot replace B status or clean up B', async () => {
  const h = harness();
  const a = h.viewer.openCharacter('naru');
  const b = h.viewer.openCharacter('nova');
  h.requests[1].resolve();
  await b;
  const status = h.viewer.state().stats;
  h.requests[0].reject(new Error('stale failure'));
  await a;
  assert.equal(h.viewer.state().stats, status);
  assert.deepEqual(keys(h.viewer.state()), ['nova']);
  assert.equal(h.created[0].disposed, 0);
  assert.equal(h.errors.length, 0);
  h.viewer.dispose();
});

test('partial batch failure releases ready players and every late sibling asset', async () => {
  const h = harness();
  const batch = h.viewer.openCharacter('all5');
  h.requests[0].resolve();
  await flush();
  assert.equal(h.created.length, 1);
  h.requests[1].reject(new Error('current load failed'));
  await flush();
  assert.equal(h.created[0].disposed, 1);
  assert.equal(h.requests[0].assets.disposed, 1);
  assert.deepEqual(keys(h.viewer.state()), []);
  assert.equal(h.viewer.state().box, null);
  assert.match(h.viewer.state().stats, /current load failed/);
  assert.equal(h.stage.children.length, 0);
  for (const request of h.requests.slice(2)) request.resolve();
  await batch;
  assert.equal(h.created.length, 1);
  for (const request of [h.requests[0], ...h.requests.slice(2)]) assert.equal(request.assets.disposed, 1);
  assert.equal(h.errors.length, 1);
  assert.deepEqual(h.events.slice(0, 2), ['roa:player', 'roa:assets']);
  h.viewer.dispose();
});

test('switching releases active and already-ready pending resources exactly once', async () => {
  const h = harness();
  const first = h.viewer.openCharacter('nova');
  h.requests[0].resolve();
  await first;
  const pending = h.viewer.openCharacter('composed');
  assert.deepEqual(h.events, ['nova:player', 'nova:assets']);
  h.requests[1].resolve();
  await flush();
  const last = h.viewer.openCharacter('naru');
  assert.deepEqual(h.events.slice(2), ['roa:player', 'roa:assets']);
  h.requests[3].resolve();
  await last;
  h.requests[2].resolve();
  await pending;
  assert.deepEqual(keys(h.viewer.state()), ['naru']);
  assert.equal(h.requests[2].assets.disposed, 1);
  assert.equal(h.stage.children.length, 1);
  h.viewer.dispose();
  for (const player of h.created) assert.equal(player.disposed, 1);
  for (const request of h.requests) assert.equal(request.assets.disposed, 1);
});

test('composed result order follows the requested lineup, not completion order', async () => {
  const h = harness();
  const batch = h.viewer.openCharacter('composed');
  h.requests[1].resolve();
  h.requests[0].resolve();
  await batch;
  assert.deepEqual(keys(h.viewer.state()), ['roa', 'luna']);
  assert.equal(h.viewer.state().box.width, 435 + h.requests[1].assets.stage.width);
  assert.equal(h.stage.children.length, 1);
  h.viewer.dispose();
});

test('player initialization failure releases player and model without publishing', async () => {
  const h = harness();
  const batch = h.viewer.openCharacter('nova');
  h.requests[0].assets.rejectPlayer = true;
  h.requests[0].resolve();
  await batch;
  assert.equal(h.created[0].disposed, 1);
  assert.equal(h.requests[0].assets.disposed, 1);
  assert.equal(h.stage.children.length, 0);
  assert.equal(h.viewer.state().box, null);
  assert.equal(h.errors.length, 1);
  h.viewer.dispose();
});
