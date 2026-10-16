import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { checkInputs, historicalRigName } from './verify-accepted.mjs';

const family = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const accepted = JSON.parse(readFileSync(join(family, 'accepted-inputs.json'), 'utf8'));

test('historical exporter spelling admits one safe basename and refuses arbitrary paths', () => {
  for (const name of ['rig', 'final', 'pants-repair-rig']) assert.equal(historicalRigName(`../../${name}/images/`), name);
  for (const path of ['/tmp/rig/images/', '../rig/images/', '../../../rig/images/', '../../x/../images/', '../../x/y/images/', '../.././images/', '../../.. /images/', '../../x%2fy/images/', '..\\..\\rig\\images\\', '../../check/images/', '../../compiler/images/', null]) {
    assert.throws(() => historicalRigName(path), /ACCEPTED_HISTORICAL_LAYOUT_REFUSED/);
  }
});

test('frozen accepted input has a positive control and rejects drift or incoherent metadata', () => {
  const fixture = mkdtempSync(join(tmpdir(), 'family-input-controls-'));
  try {
    for (const path of [...Object.keys(accepted.files), 'accepted-inputs.json']) {
      mkdirSync(dirname(join(fixture, path)), { recursive: true });
      copyFileSync(join(family, path), join(fixture, path));
    }
    assert.equal(checkInputs(fixture).summaries.length, 5);
    const rigPath = 'roa/out/rig/rig.json';
    const originalRig = readFileSync(join(fixture, rigPath));
    writeFileSync(join(fixture, rigPath), Buffer.concat([originalRig, Buffer.from('\n')]));
    assert.throws(() => checkInputs(fixture), /ACCEPTED_INPUT_CHANGED roa\/out\/rig\/rig.json/);
    writeFileSync(join(fixture, rigPath), originalRig);

    const extra = join(fixture, 'roa/out/rig/unreviewed.provenance.json');
    writeFileSync(extra, '{}');
    assert.throws(() => checkInputs(fixture), /ACCEPTED_INPUT_INVENTORY_CHANGED/);
    rmSync(extra);

    // Even a newly authored manifest must not make contradictory metadata coherent.
    const mutate = (path, edit, expected) => {
      const original = readFileSync(join(fixture, path));
      const document = JSON.parse(original.toString());
      edit(document);
      const changed = Buffer.from(JSON.stringify(document));
      writeFileSync(join(fixture, path), changed);
      const manifest = structuredClone(accepted);
      manifest.files[path] = { bytes: changed.length, sha256: createHash('sha256').update(changed).digest('hex') };
      assert.throws(() => checkInputs(fixture, manifest), expected);
      writeFileSync(join(fixture, path), original);
    };
    mutate('roa/out/parts.json', d => { d.parts[0].w++; }, /ACCEPTED_PART_DIMENSIONS/);
    mutate('roa/out/rig/mesh_report.json', d => { d[0].triangles++; }, /ACCEPTED_MESH_REPORT/);
    mutate('roa/out/check/check.json', d => { d.gate_spine_html_green = false; }, /ACCEPTED_SAVED_VERDICT/);
    assert.equal(checkInputs(fixture).summaries.length, 5);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});
