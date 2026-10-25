import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { checkInputs, historicalRigName } from './verify-accepted.mjs';
import { uniformHairProfileRig, validateUniformHairProfile, outfitHairProfileRig, validateOutfitHairProfile } from './material-profile.mjs';
import { assertSharedDrawsEqual, assertUniformPhysicsOnly } from './uniform-hair-contract.mjs';
import { measureOutfitHair } from './verify-outfit-hair.mjs';
import { measureUniformHair } from './verify-uniform-hair.mjs';
import {
  applyDeclaredRepairsToRig,
  officeBaselineForOutfits,
  officeModelBaselineForOutfits,
  toMaterialProfilePreimage,
  CHARACTERS,
  OUTFITS,
  rigPaths,
  reportMatchesDeclaration,
  verifyDeclaredReproducibility,
} from './verify-reproducibility.mjs';

const family = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const accepted = JSON.parse(readFileSync(join(family, 'accepted-inputs.json'), 'utf8'));

test('outfit profile binds homewear and swimwear separately while preserving uniform schema and all other fields', () => {
  const digest = v => createHash('sha256').update(JSON.stringify(v)).digest('hex');
  for (const outfit of ['homewear', 'swimwear']) for (const character of CHARACTERS) {
    const office = JSON.parse(readFileSync(join(family, character, 'declared-repairs.json'))).materialProfile;
    const p = rigPaths(family, character, outfit);
    const profile = JSON.parse(readFileSync(join(p.configDir, 'declared-repairs.json'))).outfitHairProfile;
    const before = JSON.parse(readFileSync(join(p.outDir, 'rig/rig.json')));
    // The same test works both before and after adoption without weakening the preimage.
    const preimage = digest(before) === profile.repaired.before ? before : outfitHairProfileRig(before, profile, office, 'reverse');
    const after = outfitHairProfileRig(preimage, profile, office, 'forward');
    assert.deepEqual(outfitHairProfileRig(after, profile, office, 'reverse'), preimage);
    assert.equal(assertUniformPhysicsOnly(preimage, after, profile).constraints, profile.constraints.length);
    for (const wrong of ['office', 'uniform', outfit === 'homewear' ? 'swimwear' : 'homewear']) assert.throws(() => validateOutfitHairProfile(profile, office, character, wrong), /OUTFIT_SCHEMA/);
    assert.throws(() => validateUniformHairProfile(profile, office, character, 'uniform'), /UNIFORM_SCHEMA/);
    for (const mutate of [p => { p.officeProfileSHA256 = '0'.repeat(64); }, p => { p.character = 'other'; }, p => { p.spec = 'family-uniform-hair-profile/1'; }]) {
      const bad = structuredClone(profile); mutate(bad); assert.throws(() => outfitHairProfileRig(preimage, bad, office, 'forward'), /OUTFIT_SCHEMA/);
    }
    for (const mutate of [p => { p.constraints.pop(); }, p => { p.constraints[0].after.mass += .01; }, p => { p.constraints.push({...p.constraints[0], bone: 'skirt_0'}); }]) {
      const bad = structuredClone(profile); mutate(bad); assert.throws(() => outfitHairProfileRig(preimage, bad, office, 'forward'), /OUTFIT_TARGETS/);
    }
    const drift = structuredClone(preimage); drift.bones[0].x = (drift.bones[0].x ?? 0) + 1;
    assert.throws(() => outfitHairProfileRig(drift, profile, office, 'forward'), /OUTFIT_INPUT_DRIFT/);
  }
});

test('uniform shared draw contract rejects coordinate, topology, colour, order and inventory defects', () => {
  const mesh = { slot: 'hair_back', kind: 'mesh', vertices: [0, 0, 1, 0, 0, 1], triangles: [0, 1, 2], tint: [1, 1, 1, 1], blend: 'Normal', uvs: [0, 0], z: 1 };
  const frame = { order: [mesh, { ...structuredClone(mesh), slot: 'face' }] };
  const normal = structuredClone(frame); normal.order[0].uvs = [.4, .6]; normal.order[0].z = 10;
  assert.equal(assertSharedDrawsEqual(frame, normal).draws, 2);
  for (const mutate of [
    f => { f.order[0].vertices[0] += 1e-12; },
    f => { f.order[0].triangles.reverse(); },
    f => { f.order[0].tint[3] = .9; },
    f => { f.order[0].clip = { polygon: [0, 0, 1, 1] }; },
    f => { f.order.reverse(); },
    f => { f.order.pop(); },
    f => { f.order.push({ ...mesh, slot: 'earring' }); },
  ]) {
    const bad = structuredClone(frame); mutate(bad);
    assert.throws(() => assertSharedDrawsEqual(frame, bad), /UNIFORM_SHARED/);
  }
  const nonfinite = structuredClone(frame); nonfinite.order[0].vertices[0] = NaN;
  assert.throws(() => assertSharedDrawsEqual(nonfinite, nonfinite), /UNIFORM_SHARED_COORDINATES/);
  assert.throws(() => assertSharedDrawsEqual({ order: [] }, { order: [] }), /UNIFORM_SHARED_EMPTY/);
});

test('uniform physics allowlist rejects geometry, other physics, missing targets and derived-pin defects', () => {
  const values = { mass: 1, strength: 2, damping: .5, inertia: 1, wind: 1 };
  const before = { constraints: [{ name: 'hair', bone: 'hair_back', type: 'physics', ...values }, { name: 'bust', bone: 'bust', type: 'physics', ...values }], meshes: [{ vertices: [1, 2] }], spine: { sha256: 'old' } };
  const profile = { constraints: [{ name: 'hair', bone: 'hair_back', before: values, after: { ...values, mass: .45 } }] };
  const after = structuredClone(before); Object.assign(after.constraints[0], profile.constraints[0].after);
  const spineText = '{}\n'; after.spine.sha256 = createHash('sha256').update(spineText).digest('hex');
  assert.equal(assertUniformPhysicsOnly(before, after, profile, { spineText }).fields, 5);
  for (const mutate of [d => { d.meshes[0].vertices[0]++; }, d => { d.constraints[1].wind++; }, d => { d.constraints[0].mix = .5; }, d => { d.spine.sha256 = 'bad'; }]) {
    const bad = structuredClone(after); mutate(bad);
    assert.throws(() => assertUniformPhysicsOnly(before, bad, profile, { spineText }), /UNIFORM_PHYSICS_OUTSIDE_ALLOWLIST/);
  }
  assert.throws(() => assertUniformPhysicsOnly(before, after, { constraints: [] }), /UNIFORM_PHYSICS_EMPTY/);
  const missing = structuredClone(before); missing.constraints.push({ ...before.constraints[0], name: 'other-hair' });
  assert.throws(() => assertUniformPhysicsOnly(missing, after, profile), /UNIFORM_PHYSICS_TARGET_SET/);
});

test('uniform actual pinned viewer reproduces all 73 exact shared draws', () => {
  const result = measureUniformHair(family);
  assert.equal(result.totalDraws, 73);
  assert.deepEqual(result.rows.map(row => row.draws), [12, 14, 18, 15, 14]);
  assert.ok(result.rows.every(row => row.exact && row.normal.exact));
  assert.equal(result.pixelZeroClaimed, false);
  const receipt = JSON.parse(readFileSync(join(family, 'docs/uniform-hair-switch.json')));
  const savedPoseBytes = readFileSync(join(family, 'docs/uniform-shared-pose.json'));
  const digest = bytes => createHash('sha256').update(bytes).digest('hex');
  assert.equal(digest(savedPoseBytes), receipt.sharedPose.sha256);
  assert.deepEqual(result, JSON.parse(savedPoseBytes));
  assert.equal(digest(readFileSync(join(family, 'docs', receipt.sheet.file))), receipt.sheet.sha256);
  assert.equal(receipt.pixelHistory.targetExitCode, 1);
  assert.equal(receipt.pixelHistory.originalTargetOutsideNeck, 358);
  assert.equal(receipt.acceptance.pixelZeroClaimed, false);
});

test('uniform delivered rigs reverse to accepted preimages with only 75 by 5 profile fields changed', () => {
  let constraints = 0;
  for (const character of CHARACTERS) {
    const uniform = rigPaths(family, character, 'uniform');
    const office = JSON.parse(readFileSync(join(family, character, 'declared-repairs.json'))).materialProfile;
    const profile = JSON.parse(readFileSync(join(uniform.configDir, 'declared-repairs.json'))).uniformHairProfile;
    const after = JSON.parse(readFileSync(join(uniform.outDir, 'rig/rig.json')));
    const before = uniformHairProfileRig(after, profile, office, 'reverse');
    constraints += assertUniformPhysicsOnly(before, after, profile).constraints;
  }
  assert.equal(constraints, 75);
});

test('report correction binds exact before/after rows and only reversible drawn-bone names', () => {
  const hash = row => createHash('sha256').update(JSON.stringify(row)).digest('hex');
  const before = { part: 'skirt', vertices: 3, bones: ['hip', 'skirt'] };
  const after = { ...before, bones: ['hip', 'skirt_d'] };
  const correction = { beforeSHA256: hash(before), afterSHA256: hash(after), boneChanges: [{ index: 1, before: 'skirt', after: 'skirt_d' }] };
  assert.equal(reportMatchesDeclaration(before, hash(before)), true);
  assert.equal(reportMatchesDeclaration(after, hash(before), correction), true);
  assert.equal(reportMatchesDeclaration(before, hash(before), correction), false);
  assert.equal(reportMatchesDeclaration({ ...after, vertices: 4 }, hash(before), correction), false);
  assert.equal(reportMatchesDeclaration(after, '0'.repeat(64), correction), false);
  assert.equal(reportMatchesDeclaration(after, hash(before), { ...correction, boneChanges: [...correction.boneChanges, ...correction.boneChanges] }), false);
  const other = { ...after, vertices: 4 };
  assert.equal(reportMatchesDeclaration(other, hash(before), { ...correction, afterSHA256: hash(other) }), false);
  assert.equal(reportMatchesDeclaration(after, hash(before), { ...correction, boneChanges: [{ index: 1, before: 'skirt', after: 'other' }] }), false);
});

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
      assert.match(err.message, /jinni\/office\/earring \(delivered=29v\/26t rebuilt=13v\/12t\)/);
      assert.match(err.message, /jinni\/office\/hair_front \(delivered=105v\/112t rebuilt=41v\/50t\)/);
      assert.match(err.message, /roa\/office\/bottomwear \(delivered=319v\/422t rebuilt=183v\/298t\)/);
      assert.match(err.message, /roa\/office\/hair_front \(delivered=84v\/88t rebuilt=20v\/24t\)/);
      return true;
    },
  );

  // Bar 3 (Mutant: hand-edit one accepted mesh -> red by character/outfit/part name)
  const fixture = mkdtempSync(join(tmpdir(), 'family-repro-mutant-'));
  try {
    copyFileSync(join(family, 'accepted-inputs.json'), join(fixture, 'accepted-inputs.json'));
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
        if (outfit === 'uniform') copyFileSync(join(src.outDir, 'rig/uniform-hair-profile.provenance.json'), join(dst.outDir, 'rig/uniform-hair-profile.provenance.json'));
        if (['homewear', 'swimwear'].includes(outfit)) copyFileSync(join(src.outDir, 'rig/outfit-hair-profile.provenance.json'), join(dst.outDir, 'rig/outfit-hair-profile.provenance.json'));
        copyFileSync(join(src.outDir, 'rig/mesh_report.json'), join(dst.outDir, 'rig/mesh_report.json'));
        copyFileSync(join(src.outDir, 'check/build/skeleton.model.json'), join(dst.outDir, 'check/build/skeleton.model.json'));
      }
    }

    assert.equal(verifyDeclaredReproducibility(fixture).rows.every(r => r.equal), true);

    const uniformConfig = join(fixture, 'outfits/uniform/luna/authoring/config.json');
    const uniformConfigBytes = readFileSync(uniformConfig);
    const driftedUniformConfig = JSON.parse(uniformConfigBytes);
    driftedUniformConfig.constraints.find(c => c.type === 'physics' && /^hair/.test(c.bone)).mass += .1;
    writeFileSync(uniformConfig, JSON.stringify(driftedUniformConfig));
    assert.throws(() => verifyDeclaredReproducibility(fixture), /REPRODUCIBILITY_PROFILE_UNIFORM_CONFIG_DRIFT luna/);
    writeFileSync(uniformConfig, uniformConfigBytes);
    const uniformProvenance = join(fixture, 'outfits/uniform/luna/out/rig/uniform-hair-profile.provenance.json');
    const uniformProvenanceBytes = readFileSync(uniformProvenance);
    const driftedUniformProvenance = JSON.parse(uniformProvenanceBytes); driftedUniformProvenance.profileSHA256 = '0'.repeat(64);
    writeFileSync(uniformProvenance, JSON.stringify(driftedUniformProvenance));
    assert.throws(() => verifyDeclaredReproducibility(fixture), /REPRODUCIBILITY_PROFILE_UNIFORM_PROVENANCE_DRIFT luna/);
    writeFileSync(uniformProvenance, uniformProvenanceBytes);

    for (const outfit of ['homewear', 'swimwear']) {
      const cfg = join(fixture, `outfits/${outfit}/luna/authoring/config.json`);
      const original = readFileSync(cfg), drift = JSON.parse(original);
      drift.constraints.find(c => c.type === 'physics' && /^hair/.test(c.bone)).mass += .1;
      writeFileSync(cfg, JSON.stringify(drift));
      assert.throws(() => verifyDeclaredReproducibility(fixture), new RegExp(`REPRODUCIBILITY_PROFILE_OUTFIT_CONFIG_DRIFT luna/${outfit}`));
      writeFileSync(cfg, original);
      const provenance = join(fixture, `outfits/${outfit}/luna/out/rig/outfit-hair-profile.provenance.json`);
      const bytes = readFileSync(provenance), bad = JSON.parse(bytes); bad.outfit = outfit === 'homewear' ? 'swimwear' : 'homewear';
      writeFileSync(provenance, JSON.stringify(bad));
      assert.throws(() => verifyDeclaredReproducibility(fixture), new RegExp(`REPRODUCIBILITY_PROFILE_OUTFIT_PROVENANCE_DRIFT luna/${outfit}`));
      writeFileSync(provenance, bytes);
    }

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


    // Mutant 2: the complete profile preimage must refuse even an unrepaired sleeves weight change.
    const roaHomeRigPath = join(fixture, 'outfits/homewear/roa/out/rig/rig.json');
    const origRoaHomeRig = readFileSync(roaHomeRigPath);
    const mutatedRoaHomeRig = JSON.parse(origRoaHomeRig.toString('utf8'));
    mutatedRoaHomeRig.skins.default.sleeves.sleeves.weights[0][0].x += 5;
    writeFileSync(roaHomeRigPath, JSON.stringify(mutatedRoaHomeRig));
    assert.throws(
      () => verifyDeclaredReproducibility(fixture),
      /REPRODUCIBILITY_PROFILE_OUTFIT_INPUT_DRIFT roa\/homewear\/after/,
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
    const currentDeclared = JSON.parse(readFileSync(join(family, character, 'declared-repairs.json')));
    assert.notDeepEqual(baseline.constraints, current.constraints);
    assert.deepEqual(baseline.skins, toMaterialProfilePreimage(current, currentDeclared).skins);
    assert.deepEqual(baseline.bones, current.bones);
  }
});

test('uniform hair inherits exactly the accepted office targets after existing repairs', () => {
  const digest = v => createHash('sha256').update(JSON.stringify(v)).digest('hex');
  const before = { mass: 1, strength: 100, damping: .8, inertia: 1, wind: 1 };
  const after = { mass: .45, strength: 110, damping: .74, inertia: .85, wind: 1.4 };
  const hair = { type: 'physics', name: 'hair_phys', bone: 'hair0', ...before };
  const skirt = { type: 'physics', name: 'skirt_phys', bone: 'skirt0', ...before };
  const raw = { constraints: [hair, skirt], skins: { default: {} }, slots: [] };
  const repaired = structuredClone(raw); repaired.constraints.pop();
  const expected = structuredClone(repaired); Object.assign(expected.constraints[0], after);
  const office = { spec: 'family-material-profile/1', character: 'nova', outfit: 'office', constraints: [{ name: hair.name, bone: hair.bone, before, after }], raw: { before: '0'.repeat(64), after: '1'.repeat(64) }, repaired: { before: '2'.repeat(64), after: '3'.repeat(64) } };
  const profile = { spec: 'family-uniform-hair-profile/1', character: 'nova', outfit: 'uniform', officeProfileSHA256: digest(office), constraints: office.constraints, repaired: { before: digest(repaired), after: digest(expected) } };
  const declared = { constraints: { regeneratedSHA256: digest(raw.constraints), repairedSHA256: digest(repaired.constraints), constraints: repaired.constraints }, uniformHairProfile: profile };
  const apply = (rig = raw, declaration = declared) => applyDeclaredRepairsToRig({ character: 'nova', outfit: 'uniform', rawRig: rig, rawReport: [], declared: declaration, officeProfile: office });
  assert.deepEqual(apply().rig, expected);
  assert.deepEqual(apply().baselineRig, repaired);
  assert.deepEqual(uniformHairProfileRig(expected, profile, office, 'reverse'), repaired);
  assert.deepEqual(raw.constraints, [hair, skirt]);
  for (const outfit of ['office', 'homewear', 'swimwear']) assert.throws(() => validateUniformHairProfile(profile, office, 'nova', outfit), /UNIFORM_SCHEMA/);
  for (const mutate of [p => p.officeProfileSHA256 = 'f'.repeat(64), p => p.character = 'luna', p => p.outfit = 'homewear', p => p.spec = 'other']) {
    const bad = structuredClone(profile); mutate(bad);
    assert.throws(() => uniformHairProfileRig(repaired, bad, office, 'forward'), /UNIFORM_SCHEMA/);
  }
  for (const mutate of [p => p.constraints.pop(), p => p.constraints.push(p.constraints[0]), p => p.constraints[0].after.wind++, p => p.constraints[0].bone = 'skirt0', p => p.constraints[0].after.mix = 1]) {
    const bad = structuredClone(profile); mutate(bad);
    assert.throws(() => uniformHairProfileRig(repaired, bad, office, 'forward'), /UNIFORM_TARGETS/);
  }
  for (const mutate of [r => r.constraints[0].rotate = 2, r => r.constraints.push(skirt), r => r.skins.default.topwear = {}]) {
    const bad = structuredClone(repaired); mutate(bad);
    assert.throws(() => uniformHairProfileRig(bad, profile, office, 'forward'), /UNIFORM_INPUT_DRIFT/);
  }
  const brokenOutput = structuredClone(profile); brokenOutput.repaired.after = '0'.repeat(64);
  assert.throws(() => uniformHairProfileRig(repaired, brokenOutput, office, 'forward'), /UNIFORM_OUTPUT_DRIFT/);
  const badRepair = structuredClone(declared); badRepair.constraints.regeneratedSHA256 = '0'.repeat(64);
  assert.throws(() => apply(raw, badRepair), /REPRODUCIBILITY_CONSTRAINTS_DRIFT/);
});


test('both outfit inventories reproduce every actual shared pose and bind viewed sheets and cold controls', () => {
  const result = measureOutfitHair(family);
  const inventory = JSON.parse(readFileSync(join(family, 'docs/outfit-hair-inventory.json')));
  assert.equal(result.totalDraws, inventory.rows.reduce((n, row) => n + row.drawCount, 0));
  assert.deepEqual(result.rows.map(r => [r.outfit, r.character, r.draws]), inventory.rows.map(r => [r.outfit, r.character, r.drawCount]));
  assert.ok(result.rows.every(row => row.exact && row.normal.exact));
  const saved = readFileSync(join(family, 'docs/outfit-shared-pose.json'));
  assert.deepEqual(result, JSON.parse(saved));
  const receipt = JSON.parse(readFileSync(join(family, 'docs/outfit-hair-switch.json')));
  const sha = bytes => createHash('sha256').update(bytes).digest('hex');
  assert.equal(sha(saved), receipt.sharedPose.sha256);
  assert.equal(receipt.acceptance.pixelZeroClaimed, false);
  assert.equal(receipt.measurements.officeNormal.sharedDifferingPixels, 0);
  assert.equal(receipt.measurements.preflightOnly, false);
  for (const outfit of ['homewear', 'swimwear']) {
    const row = receipt.measurements.outfits[outfit];
    assert.equal(row.coldSharedAtlas.sharedDifferingPixels, 0);
    assert.equal(sha(readFileSync(join(family, 'docs', row.sheet.file))), row.sheet.sha256);
    assert.ok(row.candidate.outsideNeckPlate > 0);
    assert.ok(row.candidate.outsideNeckPlate < row.before.outsideNeckPlate);
  }
});

test('roa, luna, jinni, naru, and nova office configs state explicit mesh payloads and refuse explicit report drift', () => {
  const explicitByChar = {
    roa: ['bottomwear', 'topwear', 'hair_front'],
    luna: ['handwear_l', 'topwear', 'handwear_r', 'hair_front'],
    jinni: ['earring', 'hair_front'],
    naru: ['hair_back', 'bottomwear', 'hair_front'],
    nova: ['hair_back', 'hair_front'],
  };

  for (const [character, parts] of Object.entries(explicitByChar)) {
    const cfg = JSON.parse(readFileSync(join(family, `${character}/config.json`), 'utf8'));
    const rig = JSON.parse(readFileSync(join(family, `${character}/out/rig/rig.json`), 'utf8'));
    const report = JSON.parse(readFileSync(join(family, `${character}/out/rig/mesh_report.json`), 'utf8'));
    const declared = JSON.parse(readFileSync(join(family, `${character}/declared-repairs.json`), 'utf8'));

    for (const part of parts) {
      const exp = cfg.meshes[part]?.explicit;
      assert.ok(exp, `missing explicit mesh payload for ${character}/${part}`);
      const rep = report.find(r => r.part === part);
      assert.match(exp.image_sha256, /^[a-f0-9]{64}$/);
      assert.match(exp.region_sha256, /^[a-f0-9]{64}$/);
      if (Array.isArray(exp.islands)) {
        assert.equal(exp.islands.length, 2);
        let totalV = 0;
        let totalT = 0;
        let totalHull = 0;
        for (const island of exp.islands) {
          const att = rig.skins.default[island.slot]?.[island.slot];
          assert.ok(att, `missing island attachment ${character}/${part}/${island.slot}`);
          const slotEntry = rig.slots.find(s => s.name === island.slot);
          assert.ok(slotEntry, `missing slot entry ${character}/${part}/${island.slot}`);
          assert.equal(slotEntry.bone, island.bone ?? cfg.meshes[part].segments[0]);
          if (island.before) {
            const slotIdx = rig.slots.findIndex(s => s.name === island.slot);
            const beforeIdx = rig.slots.findIndex(s => s.name === island.before);
            assert.equal(slotIdx + 1, beforeIdx, `${island.slot} must precede ${island.before}`);
          }
          assert.deepEqual(island.uvs, att.uvs);
          assert.deepEqual(island.triangles, att.triangles);
          assert.equal(island.hull, att.hull);
          assert.deepEqual(island.weights, att.weights);
          totalV += island.uvs.length / 2;
          totalT += island.triangles.length / 3;
          totalHull += island.hull;
        }
        assert.equal(rep.vertices, totalV);
        assert.equal(rep.triangles, totalT);
        assert.equal(rep.hull, totalHull);
      } else {
        const att = rig.skins.default[part][part];
        assert.deepEqual(exp.uvs, att.uvs);
        assert.deepEqual(exp.triangles, att.triangles);
        assert.equal(exp.hull, att.hull);
        assert.deepEqual(exp.weights, att.weights);
      }
      assert.equal(rep.mode, 'explicit');
      assert.equal(rep.image_sha256, exp.image_sha256);
      assert.equal(rep.region_sha256, exp.region_sha256);
      assert.ok(declared.parts?.[part]?.regenerated?.meshConfig, `missing regenerated.meshConfig for ${character}/${part}`);
    }

    const applied = applyDeclaredRepairsToRig({
      character,
      outfit: 'office',
      rawRig: rig,
      rawReport: report,
      declared,
    });
    assert.deepEqual(applied.rig, rig);
    assert.deepEqual(applied.report, report);

    const probePart = parts[0];
    const badReport = structuredClone(report);
    badReport.find(r => r.part === probePart).mode = 'contour';
    assert.throws(
      () => applyDeclaredRepairsToRig({ character, outfit: 'office', rawRig: rig, rawReport: badReport, declared }),
      new RegExp(`REPRODUCIBILITY_REPORT_DRIFT ${character}\\/office\\/${probePart}`),
    );
  }

  // naru hair_back adopts _d bindings on hairback_r0..2 and hairback_l0..2 in both rig and compiled model
  const naruModel = JSON.parse(readFileSync(join(family, 'naru/out/check/build/skeleton.model.json'), 'utf8'));
  assert.deepEqual(
    naruModel.rig.meshDeclaredBones.hair_back,
    ['head', 'hairback_r0_d', 'hairback_l0_d', 'hairback_l1_d', 'hairback_l2_d', 'hairback_r2_d', 'hairback_r1_d'],
  );
  const naruBaselineModel = JSON.parse(officeModelBaselineForOutfits(family, 'naru/out/check/build/skeleton.model.json'));
  assert.deepEqual(
    naruBaselineModel.rig.meshDeclaredBones.hair_back,
    ['head', 'hairback_r0', 'hairback_l0', 'hairback_l1', 'hairback_l2', 'hairback_r2', 'hairback_r1'],
  );

  // nova config constraints match nova/out/rig/rig.json (no cuff_*_phys constraints)
  const novaCfg = JSON.parse(readFileSync(join(family, 'nova/config.json'), 'utf8'));
  const novaRig = JSON.parse(readFileSync(join(family, 'nova/out/rig/rig.json'), 'utf8'));
  assert.deepEqual(novaCfg.constraints, novaRig.constraints);
  assert.equal(novaCfg.constraints.some(c => /^cuff_/.test(c.name)), false);

  // Explicit-aware contour readers: bust-region-rebuild.py --action get returns non-empty regions for roa/office and luna/office
  const getRes = spawnSync('python3', [join(family, 'tools/bust-region-rebuild.py'), '--action', 'get'], { encoding: 'utf8' });
  assert.equal(getRes.status, 0, getRes.stderr);
  const allRegions = JSON.parse(getRes.stdout);
  for (const ch of CHARACTERS) {
    for (const outfit of OUTFITS) {
      const regs = allRegions[ch]?.outfits?.[outfit];
      assert.ok(regs?.bust_r && regs?.bust_l, `missing bust_r/bust_l for ${ch}/${outfit}`);
      for (const side of ['bust_r', 'bust_l']) {
        for (const k of ['cx', 'cy', 'r', 'band']) {
          assert.equal(Number.isFinite(regs[side][k]), true, `non-finite ${ch}/${outfit}/${side}.${k}`);
        }
      }
    }
  }
  assert.deepEqual(allRegions.roa.outfits.office, {
    bust_r: { cx: 295, cy: 665, r: 21, band: 83 },
    bust_l: { cx: 496, cy: 661, r: 20, band: 71 },
  });
  assert.deepEqual(allRegions.luna.outfits.office, {
    bust_r: { cx: 319, cy: 769, r: 19, band: 60 },
    bust_l: { cx: 477, cy: 768, r: 22, band: 52 },
  });

  // Explicit-aware contour rebuild refuses by name and states what to edit instead
  for (const ch of ['roa', 'luna']) {
    const setRes = spawnSync(
      'python3',
      [
        join(family, 'tools/bust-region-rebuild.py'),
        '--action', 'set',
        '--character', ch,
        '--bust-r', '295,665,21,83',
        '--bust-l', '496,661,20,71',
      ],
      { encoding: 'utf8' },
    );
    assert.notEqual(setRes.status, 0);
    assert.doesNotMatch(setRes.stderr + setRes.stdout, /KeyError/);
    assert.match(
      setRes.stderr + setRes.stdout,
      new RegExp(`FAMILY_EXPLICIT_MESH_REFUSED: ${ch}/office/topwear declares meshes\\.topwear\\.explicit.*Edit meshes\\.topwear\\.explicit\\.weights`),
    );
  }

  // Viewer path: activeBustRegions and syncBustEditorInputs do not crash when office (or all outfits) has empty {} regions
  const viewerHtml = readFileSync(join(family, 'viewer/index.html'), 'utf8');
  const fnMatch = /function hasValidBustPair\(regs\)[\s\S]*?function syncBustEditorInputs\(\) \{[\s\S]*?\n    \}/.exec(viewerHtml);
  assert.ok(fnMatch, 'viewer bust region helpers must exist in viewer/index.html');
  const makeInput = () => ({ value: 'init' });
  const inputs = {
    bustCharSelect: makeInput(),
    bustRX: makeInput(), bustRY: makeInput(), bustRR: makeInput(), bustRB: makeInput(),
    bustLX: makeInput(), bustLY: makeInput(), bustLR: makeInput(), bustLB: makeInput(),
  };
  const runViewerBustSync = (bustDataFixture, activeOutfit = 'office') => {
    const fn = new Function(
      'bustData', 'activeBustOutfit', 'CHARACTER_LABELS', 'ui', 'outfitTarget', 'activeBustChar',
      'bustCharSelect', 'bustRX', 'bustRY', 'bustRR', 'bustRB', 'bustLX', 'bustLY', 'bustLR', 'bustLB',
      `${fnMatch[0]}; syncBustEditorInputs(); return activeBustRegions(activeBustChar);`,
    );
    return fn(
      bustDataFixture,
      () => activeOutfit,
      { roa: '로아', luna: '루나' },
      { character: 'roa' },
      'roa',
      'roa',
      inputs.bustCharSelect,
      inputs.bustRX, inputs.bustRY, inputs.bustRR, inputs.bustRB,
      inputs.bustLX, inputs.bustLY, inputs.bustLR, inputs.bustLB,
    );
  };
  // Case A: office is {} (missing region), swimwear has valid regions -> falls back without crashing
  const fallbackRegs = runViewerBustSync({
    roa: {
      chest: [360, 657],
      outfits: {
        office: {},
        swimwear: { bust_r: { cx: 295, cy: 665, r: 21, band: 83 }, bust_l: { cx: 496, cy: 661, r: 20, band: 71 } },
      },
    },
  }, 'office');
  assert.deepEqual(fallbackRegs, {
    bust_r: { cx: 295, cy: 665, r: 21, band: 83 },
    bust_l: { cx: 496, cy: 661, r: 20, band: 71 },
  });
  assert.equal(inputs.bustRX.value, '295');
  assert.equal(inputs.bustLX.value, '496');

  // Case B: every outfit is {} -> returns null and does not throw TypeError
  const emptyRegs = runViewerBustSync({
    roa: { chest: [360, 657], outfits: { office: {}, homewear: {}, swimwear: {}, uniform: {} } },
  }, 'office');
  assert.equal(emptyRegs, null);
});
