import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { checkInputs, historicalRigName } from './verify-accepted.mjs';
import {
  applyDeclaredRepairsToRig,
  officeBaselineForOutfits,
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
        if (outfit === 'office') copyFileSync(join(src.outDir, 'rig/material-profile.provenance.json'), join(dst.outDir, 'rig/material-profile.provenance.json'));
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

    const provenancePath = join(fixture, 'luna/out/rig/material-profile.provenance.json');
    const originalProvenance = readFileSync(provenancePath);
    const badProvenance = JSON.parse(originalProvenance); badProvenance.profileSHA256 = '0'.repeat(64);
    writeFileSync(provenancePath, JSON.stringify(badProvenance));
    assert.throws(() => verifyDeclaredReproducibility(fixture), /REPRODUCIBILITY_PROFILE_PROVENANCE_DRIFT luna/);
    writeFileSync(provenancePath, originalProvenance);
    const configPath = join(fixture, 'luna/config.json'), originalConfig = readFileSync(configPath);
    const badConfig = JSON.parse(originalConfig); badConfig.constraints.find(c => c.type === 'physics' && /^hair/.test(c.bone)).mass += .1;
    writeFileSync(configPath, JSON.stringify(badConfig));
    assert.throws(() => verifyDeclaredReproducibility(fixture), /REPRODUCIBILITY_PROFILE_CONFIG_DRIFT luna/);
    writeFileSync(configPath, originalConfig);


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


test('declared office profile passes the unchanged full constraint repair guard and preserves outfit baseline', () => {
  const digest = v => createHash('sha256').update(JSON.stringify(v)).digest('hex');
  const before = { mass: 1, strength: 100, damping: .8, inertia: 1, wind: 1 };
  const after = { mass: .45, strength: 110, damping: .74, inertia: .85, wind: 1.4 };
  const hair = { type: 'physics', name: 'hair_phys', bone: 'hair0', ...before };
  const cuff = { type: 'physics', name: 'cuff_phys', bone: 'cuff0', ...before };
  const rawBefore = { constraints: [hair, cuff], skins: { default: {} }, slots: [] };
  const rawAfter = structuredClone(rawBefore); Object.assign(rawAfter.constraints[0], after);
  const repairedBefore = structuredClone(rawBefore); repairedBefore.constraints.pop();
  const repairedAfter = structuredClone(rawAfter); repairedAfter.constraints.pop();
  const profile = { spec: 'family-material-profile/1', character: 'nova', outfit: 'office', constraints: [{ name: hair.name, bone: hair.bone, before, after }], raw: { before: digest(rawBefore), after: digest(rawAfter) }, repaired: { before: digest(repairedBefore), after: digest(repairedAfter) } };
  const declared = { constraints: { regeneratedSHA256: digest(rawBefore.constraints), repairedSHA256: digest(repairedBefore.constraints), constraints: repairedBefore.constraints }, materialProfile: profile };
  const apply = (rawRig = rawAfter, declaration = declared) => applyDeclaredRepairsToRig({ character: 'nova', outfit: 'office', rawRig, rawReport: [], declared: declaration });
  assert.deepEqual(apply().rig, repairedAfter);
  assert.deepEqual(apply().baselineRig, repairedBefore);
  assert.deepEqual(rawAfter.constraints[0], { ...hair, ...after });
  const noProfile = structuredClone(declared); delete noProfile.materialProfile;
  assert.throws(() => apply(rawAfter, noProfile), /REPRODUCIBILITY_CONSTRAINTS_DRIFT/);
  const badRepair = structuredClone(declared); badRepair.constraints.regeneratedSHA256 = '0'.repeat(64);
  assert.throws(() => apply(rawAfter, badRepair), /REPRODUCIBILITY_CONSTRAINTS_DRIFT/);
  const corruptRepair = structuredClone(declared); corruptRepair.constraints.constraints[0].rotate = 2;
  assert.throws(() => apply(rawAfter, corruptRepair), /REPRODUCIBILITY_CONSTRAINTS_PAYLOAD_CORRUPT/);
  for (const mutate of [r => r.constraints[0].mass++, r => r.constraints[1].wind++, r => r.constraints.push({ ...cuff, name: 'extra' }), r => r.skins.default.topwear = {}]) {
    const bad = structuredClone(rawAfter); mutate(bad);
    assert.throws(() => apply(bad), /REPRODUCIBILITY_PROFILE_INPUT_DRIFT/);
  }
  for (const [mutate, rule] of [
    [p => p.constraints.push(p.constraints[0]), 'TARGET'],
    [p => p.constraints[0].bone = 'boob_r', 'TARGET'],
    [p => p.constraints[0].after.mass = .5, 'VALUE'],
    [p => p.constraints[0].after.mix = 1, 'FIELDS'],
    [p => p.raw.before = '0'.repeat(64), 'OUTPUT_DRIFT'],
    [p => p.repaired.after = '0'.repeat(64), 'OUTPUT_DRIFT'],
  ]) {
    const bad = structuredClone(declared); mutate(bad.materialProfile);
    assert.throws(() => apply(rawAfter, bad), new RegExp('REPRODUCIBILITY_PROFILE_' + rule));
  }
  for (const character of CHARACTERS) {
    const baseline = officeBaselineForOutfits(family, character);
    const current = JSON.parse(readFileSync(join(family, character, 'out/rig/rig.json')));
    assert.notDeepEqual(baseline.constraints, current.constraints);
    assert.deepEqual(baseline.skins, current.skins);
    assert.deepEqual(baseline.bones, current.bones);
  }
});
