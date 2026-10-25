import test from 'node:test';
import assert from 'node:assert/strict';
import { compareInventories } from './verify-producer.mjs';

test('producer inventory admits identity and refuses byte, pixel, missing and empty plants', () => {
  const row = { 'rig/images/part.png': { bytes: 4, sha256: 'original-file', rgba: { width: 1, height: 1, sha256: 'original-pixels' } } };
  assert.equal(compareInventories(row, structuredClone(row)), 1);
  const bytePlant = structuredClone(row); bytePlant['rig/images/part.png'].sha256 = 'changed-file';
  assert.throws(() => compareInventories(row, bytePlant), /PRODUCER_BYTES_OR_PIXELS/);
  const pixelPlant = structuredClone(row); pixelPlant['rig/images/part.png'].rgba.sha256 = 'changed-pixels';
  assert.throws(() => compareInventories(row, pixelPlant), /PRODUCER_BYTES_OR_PIXELS/);
  assert.throws(() => compareInventories(row, {}), /PRODUCER_INVENTORY/);
  assert.throws(() => compareInventories({}, {}), /PRODUCER_EMPTY/);
});
