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

class Element {
  constructor() {
    this.children = [];
    this.style = {};
    this.clientWidth = 1200;
    this.clientHeight = 800;
    this.listeners = {};
    this.classList = { add() {}, remove() {}, toggle() {}, contains() { return false; } };
  }
  appendChild(child) { child.remove(); this.children.push(child); child.parent = this; return child; }
  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this);
    this.parent = null;
  }
  getContext() { return null; }
  setAttribute() {}
  addEventListener(name, listener) {
    const previous = this.listeners[name];
    this.listeners[name] = event => { previous?.(event); listener(event); };
  }
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
    const key = modelUrl.startsWith('/outfits/') ? 'naru' : modelUrl.split('/')[1];
    const assets = {
      key, animations: [{ name: 'idle' }],
      stage: { x: -400, y: 0, width: 800, height: 2284 },
      disposed: 0,
      dispose() { this.disposed++; events.push(`${key}:assets`); },
    };
    requests.push({ key, modelUrl, assets, resolve: () => resolve(assets), reject });
  });
  class Player {
    constructor(sub, assets) {
      this.assets = assets;
      this.disposed = 0;
      this.fit = 0;
      this.sub = sub;
      this.frames = [];
      this.renderer = { syncPixelRatio: () => {
        this.fit++;
        this.syncParent = sub.parent;
        this.syncStyle = sub.parent?.style.cssText;
        if (this.assets.rejectSync) throw new Error('pixel ratio sync failed');
      } };
      created.push(this);
    }
    play(name, options = {}) { if (this.assets.rejectPlayer) throw new Error('player initialization failed'); this.animation = name; this.loop = options.loop ?? true; this.phase = 0; }
    frame(dt) {
      this.frames.push({ dt, fit: this.fit, parent: this.sub.parent, style: this.sub.parent?.style.cssText });
      if (this.assets.rejectAttachedFrame && this.sub.parent?.id === 'rig-root') throw new Error('attached frame failed');
      this.phase += dt;
    }
    entry() { return { animation: this.animation, loop: this.loop, animationTime: this.phase }; }
    seek(time) { if (this.assets.rejectSeek) throw new Error('seek failed'); this.phase = time; }
    environment(value) { this.env = value; }
    bounds() { return this.assets.stage; }
    dispose() { this.disposed++; events.push(`${this.assets.key}:player`); }
  }
  const html = readFileSync(process.env.FAMILY_VIEWER_HTML ?? new URL('./index.html', import.meta.url), 'utf8');
  let source = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
  // Execute the actual viewer script, replacing only its browser dependencies
  // and automatic initial navigation. The lifecycle implementation is imported.
  source = source.replace(/^\s*import .*;$/gm, '');
  source = source.replace(/\n    openCharacter\((?:'all5'|ui\.character)\)(?:\.catch\(err => \{[\s\S]*?\n    \}\))?;/, '');
  source += '\nglobalThis.viewer = { openCharacter, openOutfit, updateViewport, state: () => ({ players, container, box, camera, ui, stats: stats.textContent, ref: refImg.src, caption: refCaption.textContent }), dispose: () => { outfitTransaction.invalidate(); sceneLoader.dispose(); } };';
  const context = {
    loadModel, RigPlayer: Player, createSceneLoader, createWindControls,
    BASE_WIND_LIMIT, MAX_GUST_PEAK, MIN_GUST_DURATION, MAX_GUST_DURATION,
    readViewState, writeViewState, defaultViewState, fitCamera, cameraScale, worldToPanel, zoomAt, referenceFrame, drawOverlay, outfitAssets, ownAssets, createOutfitTransaction,
    document: { getElementById: node, createElement: () => new Element(), querySelectorAll: () => [] },
    requestAnimationFrame() {}, performance: { now: () => 0 },
    setTimeout, console: { error: error => errors.push(error) },
  };
  runInNewContext(source, context, { filename: 'family/viewer/index.html' });
  return { viewer: context.viewer, requests, created, events, errors, stage: node('stage'), node };
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

async function family(h) {
  const opened = h.viewer.openCharacter('all5');
  for (const request of h.requests) request.resolve();
  await opened;
  return h.viewer.state();
}

test('outfit transaction replaces only Naru, keeps live camera/controls and forwards scene cleanup', async () => {
  const h = harness(), before = await family(h);
  h.node('pauseBtn').listeners.click();
  h.node('speed').value = '1.8'; h.node('speed').listeners.input();
  h.node('bonesBtn').listeners.click(); h.node('meshBtn').listeners.click();
  h.node('wind').value = '24'; h.node('wind').listeners.input();
  h.node('gravity').value = '1.2'; h.node('gravity').listeners.input();
  before.camera.zoom = 3.2;
  h.viewer.updateViewport();
  const previousSyncs = before.players.map(p => p.player.fit);
  const displayStyle = before.container.style.cssText;
  const entry = before.players[3], original = entry.player;
  original.phase = 1.25;
  const opening = h.viewer.openOutfit('homewear');
  assert.equal(h.viewer.state().container, before.container); assert.equal(original.disposed, 0);
  original.phase = 2.75;
  h.requests[5].resolve(); assert.equal(await opening, true);
  const after = h.viewer.state();
  assert.equal(after.players[3], entry); assert.notEqual(entry.player, original); assert.equal(entry.player.phase, 2.75);
  assert.equal(after.camera, before.camera); assert.equal(after.box, before.box); assert.equal(after.container, before.container);
  assert.equal(entry.player.fit, 1); assert.equal(entry.player.syncParent, after.container); assert.equal(entry.player.syncStyle, displayStyle);
  assert.deepEqual(entry.player.frames.at(-1), { dt: 0, fit: 1, parent: after.container, style: displayStyle });
  assert.equal(after.ui.paused, true); assert.equal(after.ui.speed, 1.8); assert.equal(after.ui.bones, true); assert.equal(after.ui.mesh, true);
  assert.equal(after.ui.outfits.naru, 'homewear'); assert.match(after.caption, /오피스 원화 기준/);
  assert.deepEqual(Array.from(entry.player.env.wind), [24, 0]); assert.deepEqual(Array.from(entry.player.env.gravity), [0, 1.2]);
  assert.equal(h.created.length, 6); assert.equal(original.disposed, 1); assert.equal(h.requests[3].assets.disposed, 1);
  for (const i of [0, 1, 2, 4]) { assert.equal(after.players[i], before.players[i]); assert.equal(after.players[i].player.disposed, 0); assert.equal(after.players[i].player.fit, previousSyncs[i]); }
  assert.equal(after.container.children.length, 5);
  h.viewer.dispose();
  for (const player of h.created) assert.equal(player.disposed, 1);
  for (const request of h.requests) assert.equal(request.assets.disposed, 1);
});

test('missing homewear and invalid stage or seek retain office and roll back the selector', async () => {
  const h = harness(), before = await family(h), original = before.players[3].player;
  let opening = h.viewer.openOutfit('homewear'); h.requests[5].reject(Error('404')); assert.equal(await opening, false);
  assert.equal(h.viewer.state().players[3].player, original); assert.equal(h.node('outfitSelect').value, 'office');
  opening = h.viewer.openOutfit('homewear'); h.requests[6].assets.stage.width = 801; h.requests[6].resolve(); assert.equal(await opening, false);
  assert.equal(h.requests[6].assets.disposed, 1);
  opening = h.viewer.openOutfit('homewear'); h.requests[7].assets.rejectSeek = true; h.requests[7].resolve(); assert.equal(await opening, false);
  assert.equal(h.viewer.state().players[3].player, original); assert.equal(h.viewer.state().ui.outfits.naru, 'office');
  assert.equal(original.disposed, 0); assert.equal(h.requests[7].assets.disposed, 1);
  h.viewer.dispose();
});

test('attached renderer sync or first displayed frame failure rolls back before ownership transfer', async () => {
  for (const field of ['rejectSync', 'rejectAttachedFrame']) {
    const h = harness(), before = await family(h), original = before.players[3].player, originalAssets = h.requests[3].assets;
    const opening = h.viewer.openOutfit('homewear');
    h.requests[5].assets[field] = true; h.requests[5].resolve(); assert.equal(await opening, false);
    assert.equal(h.viewer.state().players[3].player, original); assert.equal(original.disposed, 0); assert.equal(originalAssets.disposed, 0);
    assert.equal(h.created[5].disposed, 1); assert.equal(h.requests[5].assets.disposed, 1);
    assert.equal(h.created[5].sub.parent, null); assert.equal(before.container.children.length, 5);
    assert.equal(h.node('outfitSelect').value, 'office'); assert.equal(h.viewer.state().ui.outfits.naru, 'office');
    h.viewer.dispose(); assert.equal(original.disposed, 1); assert.equal(originalAssets.disposed, 1);
  }
});

test('returning to current office cancels pending homewear, and scene navigation invalidates candidates', async () => {
  const h = harness(), before = await family(h), original = before.players[3].player;
  const homewear = h.viewer.openOutfit('homewear'); await h.viewer.openOutfit('office');
  h.requests[5].resolve(); assert.equal(await homewear, false);
  assert.equal(h.viewer.state().players[3].player, original); assert.equal(h.requests[5].assets.disposed, 1);
  const late = h.viewer.openOutfit('homewear'), scene = h.viewer.openCharacter('nova');
  h.requests[7].resolve(); await scene; const current = h.viewer.state();
  h.requests[6].resolve(); assert.equal(await late, false);
  assert.equal(h.viewer.state().container, current.container); assert.deepEqual(keys(h.viewer.state()), ['nova']);
  assert.equal(h.requests[6].assets.disposed, 1); assert.equal(h.viewer.state().ui.outfits.naru, 'office');
  h.viewer.dispose();
});

test('persisted homewear failing on scene reload falls back to the unchanged office URL', async () => {
  const h = harness(); h.viewer.state().ui.outfits.naru = 'homewear';
  const opening = h.viewer.openCharacter('naru');
  assert.match(h.requests[0].modelUrl, /^\/outfits\/homewear\/naru\//);
  h.requests[0].reject(Error('404')); await flush();
  assert.match(h.requests[1].modelUrl, /^\/naru\/out\/check\/build\/skeleton\.model\.json/);
  h.requests[1].resolve(); await opening;
  assert.equal(h.viewer.state().ui.outfits.naru, 'office'); assert.match(h.viewer.state().stats, /오피스 유지/);
  assert.equal(h.node('outfitSelect').value, 'office'); h.viewer.dispose();
});

test('homewear-office-homewear cycles preserve cleanup ownership and individual reference', async () => {
  const h = harness(); h.node('charSelect').value = 'naru'; h.viewer.state().ui.character = 'naru';
  const opened = h.viewer.openCharacter('naru'); h.requests[0].resolve(); await opened;
  const stable = h.viewer.state().players[0];
  for (const outfit of ['homewear', 'office', 'homewear']) {
    const opened = h.viewer.openOutfit(outfit); h.requests.at(-1).resolve(); assert.equal(await opened, true);
    assert.equal(h.viewer.state().players[0], stable); assert.equal(h.viewer.state().ui.outfits.naru, outfit);
    assert.match(h.viewer.state().ref, outfit === 'homewear' ? /^\/outfits\/homewear\/naru\/inputs\/painting.png/ : /^\/naru\/inputs\/painting.png/);
  }
  h.viewer.dispose();
  for (const player of h.created) assert.equal(player.disposed, 1);
  for (const request of h.requests) assert.equal(request.assets.disposed, 1);
});
