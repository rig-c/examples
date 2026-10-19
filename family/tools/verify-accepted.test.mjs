import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { checkInputs, historicalRigName } from './verify-accepted.mjs';
import {
  CHARACTERS,
  OUTFITS,
  rigPaths,
  verifyDeclaredReproducibility,
} from './verify-reproducibility.mjs';

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

test('reproducibility gate checks all 5 characters × 4 outfits, goes red without declared repairs, and catches mesh mutants by character/outfit/part name', () => {
  // Bar 1 & Bar 2 (green with declared repairs across all 5 characters × 4 outfits)
  const green = verifyDeclaredReproducibility(family);
  const seenRigs = new Set(green.rows.map(r => `${r.character}/${r.outfit}`));
  assert.equal(seenRigs.size, CHARACTERS.length * OUTFITS.length);
  assert.ok(green.rows.every(r => r.equal === true));
  assert.match(green.table, /character\s*\|\s*outfit\s*\|\s*part\s*\|\s*delivered v\/t\s*\|\s*rebuilt v\/t\s*\|\s*equal\?/);
  assert.match(green.table, /luna\s*\|\s*office\s*\|\s*hair_front\s*\|\s*156v\/174t\s*\|\s*156v\/174t\s*\|\s*true/);

  // Bar 2 (red without declared repairs for topwear, hair_front, etc.)
  assert.throws(
    () => verifyDeclaredReproducibility(family, { ignoreRepairs: true }),
    err => {
      assert.match(err.message, /REPRODUCIBILITY_MISMATCH/);
      assert.match(err.message, /luna\/office\/topwear/);
      assert.match(err.message, /luna\/office\/hair_front \(delivered=156v\/174t rebuilt=52v\/74t\)/);
      assert.match(err.message, /roa\/office\/bottomwear \(delivered=319v\/422t rebuilt=183v\/298t\)/);
      assert.match(err.message, /roa\/office\/hair_front \(delivered=84v\/88t rebuilt=20v\/24t\)/);
      return true;
    },
  );

  // Bar 3 (Mutant: hand-edit one accepted mesh -> red by character/outfit/part name)
  const fixture = mkdtempSync(join(tmpdir(), 'family-repro-mutant-'));
  try {
    for (const outfit of OUTFITS) {
      for (const character of CHARACTERS) {
        const src = rigPaths(family, character, outfit);
        const dst = rigPaths(fixture, character, outfit);
        mkdirSync(dst.configDir, { recursive: true });
        mkdirSync(join(dst.outDir, 'rig'), { recursive: true });
        mkdirSync(join(dst.outDir, 'check/build'), { recursive: true });
        copyFileSync(src.configPath, dst.configPath);
        copyFileSync(join(src.configDir, 'declared-repairs.json'), join(dst.configDir, 'declared-repairs.json'));
        if (outfit === 'office' && existsSync(join(src.baseDir, 'cuff-physics.json'))) {
          copyFileSync(join(src.baseDir, 'cuff-physics.json'), join(dst.baseDir, 'cuff-physics.json'));
        }
        if (outfit !== 'office') {
          copyFileSync(join(src.outDir, 'assembly.json'), join(dst.outDir, 'assembly.json'));
          copyFileSync(join(src.outDir, 'neck-seam-stitch.json'), join(dst.outDir, 'neck-seam-stitch.json'));
        }
        copyFileSync(join(src.outDir, 'parts.json'), join(dst.outDir, 'parts.json'));
        copyFileSync(join(src.outDir, 'rig/rig.json'), join(dst.outDir, 'rig/rig.json'));
        copyFileSync(join(src.outDir, 'rig/mesh_report.json'), join(dst.outDir, 'rig/mesh_report.json'));
        copyFileSync(join(src.outDir, 'check/build/skeleton.model.json'), join(dst.outDir, 'check/build/skeleton.model.json'));
      }
    }

    assert.equal(verifyDeclaredReproducibility(fixture).rows.every(r => r.equal), true);

    // Mutant 1: hand-edit compiled mesh vertex in luna/office/hair_front
    const lunaModelPath = join(fixture, 'luna/out/check/build/skeleton.model.json');
    const origLunaModel = readFileSync(lunaModelPath);
    const mutatedLunaModel = JSON.parse(origLunaModel.toString('utf8'));
    mutatedLunaModel.skins[0].attachments.hair_front.hair_front.uvs[0] += 0.01;
    writeFileSync(lunaModelPath, JSON.stringify(mutatedLunaModel));
    assert.throws(
      () => verifyDeclaredReproducibility(fixture),
      /REPRODUCIBILITY_MISMATCH luna\/office\/hair_front/,
    );
    writeFileSync(lunaModelPath, origLunaModel);

    // Mutant 2: hand-edit authoring mesh weight in roa/homewear/sleeves (an unrepaired part)
    const roaHomeRigPath = join(fixture, 'outfits/homewear/roa/out/rig/rig.json');
    const origRoaHomeRig = readFileSync(roaHomeRigPath);
    const mutatedRoaHomeRig = JSON.parse(origRoaHomeRig.toString('utf8'));
    mutatedRoaHomeRig.skins.default.sleeves.sleeves.weights[0][0].x += 5;
    writeFileSync(roaHomeRigPath, JSON.stringify(mutatedRoaHomeRig));
    assert.throws(
      () => verifyDeclaredReproducibility(fixture),
      /REPRODUCIBILITY_MISMATCH roa\/homewear\/sleeves/,
    );
    writeFileSync(roaHomeRigPath, origRoaHomeRig);

    // Mutant 3: tamper with declared-repairs.json without updating config.json sha256
    const novaRepairPath = join(fixture, 'nova/declared-repairs.json');
    const origNovaRepair = readFileSync(novaRepairPath);
    writeFileSync(novaRepairPath, Buffer.concat([origNovaRepair, Buffer.from('\n')]));
    assert.throws(
      () => verifyDeclaredReproducibility(fixture),
      /REPRODUCIBILITY_REPAIR_HASH_MISMATCH nova\/office/,
    );
    writeFileSync(novaRepairPath, origNovaRepair);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});
