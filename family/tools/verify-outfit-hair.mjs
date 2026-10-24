/** Reproduce the #63 exact shared-pose bar through the pinned viewer's readers. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { assertSharedDrawsEqual } from './uniform-hair-contract.mjs';
import { officeModelBaselineForOutfits } from './verify-reproducibility.mjs';

const family = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const lineup = [['roa', 0], ['luna', .06], ['jinni', .45], ['naru', .85], ['nova', 1.25]];

export function measureOutfitHair(root = family, { frames = false, modelText } = {}) {
  const player = readFileSync(join(root, 'viewer/assets/player.js'), 'utf8');
  const accepted = JSON.parse(readFileSync(join(root, 'accepted-inputs.json'), 'utf8'));
  assert.equal(sha(player), accepted.files['viewer/assets/player.js'].sha256, 'OUTFIT_PLAYER_PIN');
  assert.match(player, /export\{[^}]*\};?\s*$/);
  // This adapter is tied to the accepted viewer bundle. It exposes its actual
  // parser/track/posed-frame functions; no copied physics or model reader is used.
  const source = player.replace(/export\{[^}]*\};?\s*$/, 'return {read:gc,view:Un,open:Hn,clock:oe,source:hs,frame:fs};');
  const api = new Function('document', source)({ createElement: () => ({ relList: { supports: () => true } }) });
  const sources = { 'viewer/assets/player.js': sha(player) }, rows = [], snapshots = [];
  const inventory = JSON.parse(readFileSync(join(root, 'docs/outfit-hair-inventory.json'), 'utf8'));
  const cloth = new Set(['topwear','bottomwear','legwear','shoes','sleeves','handwear_l','handwear_r','neckwear','neck']);
  let tick = 0;
  function closed(index) {
    const u = (((tick % 200) / 60 - (.3 + index * .55) + 10 / 3) % (10 / 3)) / .24;
    if (u >= 1) return 0;
    if (u < .30) { const t = u / .30; return t * t * (3 - 2 * t); }
    if (u < .46) return 1;
    const t = (u - .46) / .54; return 1 - t * t * (3 - 2 * t);
  }
  function open(relative, index, phase) {
    const text = modelText ? modelText(relative) : officeModelBaselineForOutfits(root, relative); sources[relative] = sha(text);
    const read = api.read(text, relative), view = api.view(read.doc);
    const track = api.open(view, 'idle', { loop: true, reset: 'animation', clock: api.clock, adjust(pose) {
      if (!pose.names.includes('eye_r') || !pose.names.includes('eye_l')) return;
      const c = closed(index);
      for (const name of ['eye_r', 'eye_l']) { const b = pose.bone(name); b.scaleY = (b.setup.scaleY ?? 1) * (1 - c * .88); }
      for (const name of ['brow_r', 'brow_l']) if (pose.names.includes(name)) { const b = pose.bone(name); b.y = (b.setup.y ?? 0) - c * 1.2; }
    } });
    let pose = track.first;
    if (phase) pose = track.step(phase);
    return { read, view, track, pose };
  }
  for (const outfit of ['homewear', 'swimwear']) for (const [index, [character, phase]] of lineup.entries()) {
    tick = 0;
    const office = open(`${character}/out/check/build/skeleton.model.json`, index, phase);
    const control = open(`${character}/out/check/build/skeleton.model.json`, index, phase);
    const candidate = open(`outfits/${outfit}/${character}/out/check/build/skeleton.model.json`, index, phase);
    for (let step = 0; step < 1200; step++) {
      tick++;
      for (const entry of [office, candidate, control]) {
        entry.track.setEnvironment({ wind: [4, 0], gravity: [0, 0] });
        entry.pose = entry.track.step(1 / 60);
      }
    }
    const frame = entry => api.frame(api.source(entry.view, entry.read.parsed), entry.pose);
    const a = frame(office), b = frame(candidate);
    const pinned = inventory.rows.find(row => row.character === character && row.outfit === outfit);
    assert.ok(pinned, 'OUTFIT_SHARED_INVENTORY_REQUIRED');
    for (const value of [a,b]) assert.deepEqual(value.order.filter(draw => !cloth.has(draw.slot)).map(draw => draw.slot), pinned.sharedDraws, 'OUTFIT_SHARED_INVENTORY_DRIFT');
    if (frames) snapshots.push({character,outfit,index,phase,office:a,candidate:b});
    const normal = assertSharedDrawsEqual(a, frame(control));
    rows.push({ character, outfit, ...assertSharedDrawsEqual(a, b), normal });
  }
  assert.equal(rows.reduce((sum,row) => sum+row.draws,0), inventory.rows.reduce((sum,row) => sum+row.drawCount,0), 'OUTFIT_COMPLETE_INVENTORY');
  return { spec: 'family-outfit-shared-pose/1', recipe: { lineup, steps: 1200, dt: 1 / 60, wind: [4, 0], gravity: [0, 0], blink: 'accepted deterministic viewer schedule', excludedSlots: ['clothing slots', 'neck'], tolerance: 0 }, rows, sources, ...(frames ? {snapshots} : {}), totalDraws: rows.reduce((sum,row) => sum+row.draws,0), PASS: true, pixelZeroClaimed: false };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  if (process.argv.slice(2).join(' ') === '--help') {
    console.log('Usage: node family/tools/verify-outfit-hair.mjs --out <new-receipt.json>');
  } else {
    assert.equal(process.argv.length, 4, 'Usage: node family/tools/verify-outfit-hair.mjs --out <new-receipt.json>');
    assert.equal(process.argv[2], '--out');
    const output = resolve(process.argv[3]); assert.ok(!existsSync(output), 'OUTFIT_FRESH_RECEIPT_REQUIRED');
    writeFileSync(output, JSON.stringify(measureOutfitHair(), null, 2) + '\n');
    console.log('OUTFIT_SHARED_POSE_PASS complete pinned inventories; pixel zero not claimed');
  }
}
