import { test } from 'node:test';
import assert from 'node:assert/strict';
import { outfitAssets, ownAssets } from './outfits.mjs';

test('registry preserves office paths and isolates only Naru homewear', () => {
  for (const name of ['roa', 'luna', 'jinni', 'naru', 'nova']) {
    assert.equal(outfitAssets(name).modelUrl, `/${name}/out/check/build/skeleton.model.json`);
  }
  assert.deepEqual(outfitAssets('naru', 'homewear'), {
    modelUrl: '/outfits/homewear/naru/out/check/build/skeleton.model.json',
    referenceUrl: '/outfits/homewear/naru/inputs/painting.png',
  });
  for (const [name, outfit] of [['nova', 'homewear'], ['naru', '../'], ['../naru', 'office']]) assert.throws(() => outfitAssets(name, outfit));
});

test('asset owner forwards final scene cleanup after a variant transfer exactly once', () => {
  let office = 0, homewear = 0;
  const a = ownAssets({ dispose() { office++; } });
  const b = ownAssets({ dispose() { homewear++; } });
  const previous = a.owner.current;
  a.owner.current = b.owner.current;
  b.owner.current = null;
  previous.dispose();
  b.assets.dispose();
  assert.equal(office, 1); assert.equal(homewear, 0);
  a.assets.dispose(); a.assets.dispose();
  assert.equal(homewear, 1);
});
