/**
 * Reproducibility gate (Issue #27):
 * Rebuild every accepted rig (5 characters × 4 outfits = 20 rigs) from its
 * committed config.json + declared repairs ("x-repairs"), compile via rigc,
 * and diff both the authoring rig and the compiled model per character,
 * outfit, and part.
 */
import { createHash } from 'node:crypto';
import { cpSync, existsSync, mkdirSync, mkdtempSync, openSync, closeSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { materialProfileRig, validateMaterialProfile } from './material-profile.mjs';

const defaultFamily = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const CHARACTERS = ['roa', 'luna', 'jinni', 'naru', 'nova'];
export const OUTFITS = ['office', 'homewear', 'swimwear', 'uniform'];

const sha = value => createHash('sha256').update(value).digest('hex');
const json = path => JSON.parse(readFileSync(path, 'utf8'));
const fail = message => { throw Error(message); };

export function rigPaths(root, character, outfit) {
  const baseDir = outfit === 'office'
    ? join(root, character)
    : join(root, 'outfits', outfit, character);
  const configDir = outfit === 'office' ? baseDir : join(baseDir, 'authoring');
  const configPath = join(configDir, 'config.json');
  const partsInputDir = outfit === 'office' ? join(baseDir, 'out') : join(baseDir, 'authoring', 'inputs');
  const outDir = join(baseDir, 'out');
  return { baseDir, configDir, configPath, partsInputDir, outDir };
}

export function slotsForPart(skinsDefault, partName) {
  const out = {};
  if (!skinsDefault) return out;
  for (const [slotName, slotMap] of Object.entries(skinsDefault)) {
    if (slotName === partName || slotName.startsWith(`${partName}__island`)) {
      out[slotName] = slotMap;
    }
  }
  return out;
}

export function modelSlotsForPart(modelAttachments, partName) {
  const out = {};
  if (!modelAttachments) return out;
  for (const [slotName, slotMap] of Object.entries(modelAttachments)) {
    if (slotName === partName || slotName.startsWith(`${partName}__island`)) {
      out[slotName] = slotMap;
    }
  }
  return out;
}

export function formatVT(slotMapObj, isModel = false) {
  const entries = Object.values(slotMapObj).flatMap(slotMap => Object.values(slotMap));
  if (entries.length === 0) return 'MISSING';
  let v = 0;
  let t = 0;
  let hasMesh = false;
  for (const att of entries) {
    const kind = isModel ? att.kind : att.type;
    if (kind === 'mesh') {
      hasMesh = true;
      v += (att.uvs?.length ?? 0) / 2;
      t += (att.triangles?.length ?? 0) / 3;
    }
  }
  return hasMesh ? `${v}v/${t}t` : 'region';
}

export function loadAndVerifyDeclaredRepairs(root, character, outfit) {
  const { configDir, configPath } = rigPaths(root, character, outfit);
  const cfg = json(configPath);
  const repairRef = cfg['x-repairs'] ?? cfg.repairs;
  if (!repairRef || typeof repairRef.file !== 'string' || typeof repairRef.sha256 !== 'string') {
    fail(`REPRODUCIBILITY_REPAIR_DECLARATION_MISSING ${character}/${outfit}`);
  }
  const repairPath = resolve(configDir, repairRef.file);
  if (!existsSync(repairPath)) {
    fail(`REPRODUCIBILITY_REPAIR_FILE_MISSING ${character}/${outfit} ${repairRef.file}`);
  }
  const repairBytes = readFileSync(repairPath);
  const actualSha = sha(repairBytes);
  if (actualSha !== repairRef.sha256) {
    fail(`REPRODUCIBILITY_REPAIR_HASH_MISMATCH ${character}/${outfit} expected=${repairRef.sha256} actual=${actualSha}`);
  }
  const declared = JSON.parse(repairBytes.toString('utf8'));
  if (declared.spec !== 'family-declared-repairs/1' || declared.character !== character || declared.outfit !== outfit) {
    fail(`REPRODUCIBILITY_REPAIR_SCHEMA ${character}/${outfit}`);
  }
  if (outfit !== 'office') {
    if (!declared.baseline) fail(`REPRODUCIBILITY_BASELINE_DECLARATION_MISSING ${character}/${outfit}`);
    const asmPath = resolve(configDir, declared.baseline.assemblyFile);
    const stitchPath = resolve(configDir, declared.baseline.stitchFile);
    if (sha(readFileSync(asmPath)) !== declared.baseline.assemblySHA256) {
      fail(`REPRODUCIBILITY_ASSEMBLY_HASH_MISMATCH ${character}/${outfit}`);
    }
    if (sha(readFileSync(stitchPath)) !== declared.baseline.stitchSHA256) {
      fail(`REPRODUCIBILITY_STITCH_HASH_MISMATCH ${character}/${outfit}`);
    }
  }
  if (declared.constraints?.source && declared.constraints.source !== 'declared') {
    const srcPath = resolve(configDir, declared.constraints.source);
    if (!existsSync(srcPath) || sha(readFileSync(srcPath)) !== declared.constraints.sourceSHA256) {
      fail(`REPRODUCIBILITY_CONSTRAINT_SOURCE_HASH_MISMATCH ${character}/${outfit}`);
    }
  }
  if (declared.materialProfile) {
    validateMaterialProfile(declared.materialProfile, character, outfit);
    for (const row of declared.materialProfile.constraints) {
      const matches = cfg.constraints.filter(c => c.type === 'physics' && c.name === row.name && c.bone === row.bone);
      if (matches.length !== 1 || Object.entries(row.after).some(([field, value]) => matches[0][field] !== value)) fail(`REPRODUCIBILITY_PROFILE_CONFIG_DRIFT ${character}/${row.name}`);
    }
  }
  return { cfg, declared, repairPath };
}

export function applyDeclaredRepairsToRig({
  character,
  outfit,
  rawRig,
  rawReport,
  declared,
  ignoreRepairs = false,
}) {
  let rig = structuredClone(rawRig);
  let report = structuredClone(rawReport);
  if (ignoreRepairs || !declared) {
    return { rig, report };
  }

  if (declared.materialProfile) {
    validateMaterialProfile(declared.materialProfile, character, outfit);
    rig = materialProfileRig(rig, declared.materialProfile, 'raw', 'reverse');
  }

  for (const [partName, entry] of Object.entries(declared.parts ?? {})) {
    const currentSlots = slotsForPart(rig.skins.default, partName);
    const currentSha = sha(JSON.stringify(currentSlots));
    if (currentSha !== entry.regenerated.sha256) {
      fail(`REPRODUCIBILITY_REGENERATED_DRIFT ${character}/${outfit}/${partName} expected=${entry.regenerated.sha256} actual=${currentSha}`);
    }
    const repairedSha = sha(JSON.stringify(entry.repaired.slots));
    if (repairedSha !== entry.repaired.sha256) {
      fail(`REPRODUCIBILITY_REPAIRED_PAYLOAD_CORRUPT ${character}/${outfit}/${partName}`);
    }
    for (const k of Object.keys(currentSlots)) {
      delete rig.skins.default[k];
    }
    for (const [slotName, slotMap] of Object.entries(entry.repaired.slots)) {
      rig.skins.default[slotName] = structuredClone(slotMap);
    }
    if (entry.repaired.meshReport) {
      const idx = report.findIndex(r => r.part === partName);
      if (idx >= 0) report[idx] = structuredClone(entry.repaired.meshReport);
      else report.push(structuredClone(entry.repaired.meshReport));
    }
  }

  if (declared.slots) {
    if (sha(JSON.stringify(rig.slots)) !== declared.slots.regeneratedSHA256) {
      fail(`REPRODUCIBILITY_SLOTS_DRIFT ${character}/${outfit}`);
    }
    if (sha(JSON.stringify(declared.slots.slots)) !== declared.slots.repairedSHA256) {
      fail(`REPRODUCIBILITY_SLOTS_PAYLOAD_CORRUPT ${character}/${outfit}`);
    }
    rig.slots = structuredClone(declared.slots.slots);
  }

  if (declared.constraints) {
    if (sha(JSON.stringify(rig.constraints)) !== declared.constraints.regeneratedSHA256) {
      fail(`REPRODUCIBILITY_CONSTRAINTS_DRIFT ${character}/${outfit}`);
    }
    if (sha(JSON.stringify(declared.constraints.constraints)) !== declared.constraints.repairedSHA256) {
      fail(`REPRODUCIBILITY_CONSTRAINTS_PAYLOAD_CORRUPT ${character}/${outfit}`);
    }
    rig.constraints = structuredClone(declared.constraints.constraints);
  }

  const slotKeyOrder = declared.skinSlotOrder ?? rig.slots.map(s => s.name);
  const orderedDefault = {};
  for (const name of slotKeyOrder) {
    if (rig.skins.default[name]) {
      orderedDefault[name] = rig.skins.default[name];
    }
  }
  for (const [k, v] of Object.entries(rig.skins.default)) {
    if (!orderedDefault[k]) orderedDefault[k] = v;
  }
  rig.skins.default = orderedDefault;

  for (const [partName, repOv] of Object.entries(declared.reportOverrides ?? {})) {
    const idx = report.findIndex(r => r.part === partName);
    const curRep = idx >= 0 ? report[idx] : null;
    if (sha(JSON.stringify(curRep)) !== repOv.regeneratedSHA256) {
      fail(`REPRODUCIBILITY_REPORT_DRIFT ${character}/${outfit}/${partName}`);
    }
    if (sha(JSON.stringify(repOv.meshReport)) !== repOv.repairedSHA256) {
      fail(`REPRODUCIBILITY_REPORT_PAYLOAD_CORRUPT ${character}/${outfit}/${partName}`);
    }
    if (idx >= 0) report[idx] = structuredClone(repOv.meshReport);
    else report.push(structuredClone(repOv.meshReport));
  }

  if (declared.reportPartOrder) {
    const byPart = Object.fromEntries(report.map(r => [r.part, r]));
    report = declared.reportPartOrder.map(p => byPart[p]).filter(Boolean);
  }

  const baselineRig = structuredClone(rig);
  if (declared.materialProfile) rig = materialProfileRig(rig, declared.materialProfile, 'repaired', 'forward');
  return { rig, report, baselineRig };
}

/** Outfit profiles were not retuned by #32; preserve their declared office preimage. */
export function officeBaselineForOutfits(root, character) {
  const rig = json(join(root, character, 'out/rig/rig.json'));
  const { declared } = loadAndVerifyDeclaredRepairs(root, character, 'office');
  return declared.materialProfile ? materialProfileRig(rig, declared.materialProfile, 'repaired', 'reverse') : rig;
}

export function mergeOutfitWithOfficeBaseline({
  officeRig,
  officeReport,
  rawOutfitRig,
  rawOutfitReport,
  assembly,
}) {
  const merged = structuredClone(officeRig);
  const oldBoneNames = new Set(merged.bones.map(b => b.name));
  const extraBones = rawOutfitRig.bones.filter(b => !oldBoneNames.has(b.name));
  merged.bones.push(...extraBones);

  const oldConstraintKeys = new Set(merged.constraints.map(c => `${c.type}:${c.name}`));
  const extraConstraints = (rawOutfitRig.constraints ?? []).filter(c => !oldConstraintKeys.has(`${c.type}:${c.name}`));
  merged.constraints.push(...extraConstraints);

  const oldSlots = Object.fromEntries(merged.slots.map(s => [s.name, s]));
  const newSlots = Object.fromEntries(rawOutfitRig.slots.map(s => [s.name, s]));
  const newNames = assembly.newClothingSlots;
  const commonSlots = assembly.commonSlots;
  const slotOrder = ['hair_back', ...newNames, ...commonSlots.filter(n => n !== 'hair_back')];
  merged.slots = slotOrder.map(n => (newNames.includes(n) ? newSlots[n] : oldSlots[n]));
  merged.skins = {
    default: Object.fromEntries(
      slotOrder.map(n => [
        n,
        newNames.includes(n)
          ? structuredClone(rawOutfitRig.skins.default[n])
          : structuredClone(officeRig.skins.default[n]),
      ]),
    ),
  };

  const commonReportParts = new Set(commonSlots.map(s => s.split('__island')[0]));
  const mergedReport = [
    ...officeReport.filter(r => commonReportParts.has(r.part)),
    ...structuredClone(rawOutfitReport),
  ];
  return { rig: merged, report: mergedReport };
}

export function diffRigAndModelParts({
  character,
  outfit,
  partsList,
  deliveredRig,
  rebuiltRig,
  deliveredReport,
  rebuiltReport,
  deliveredModel,
  rebuiltModel,
}) {
  const rows = [];
  const dModelAtts = deliveredModel?.skins?.[0]?.attachments;
  const rModelAtts = rebuiltModel?.skins?.[0]?.attachments;

  for (const part of partsList) {
    const partName = part.name;
    const dRigSlots = slotsForPart(deliveredRig.skins.default, partName);
    const rRigSlots = slotsForPart(rebuiltRig.skins.default, partName);
    const dRep = deliveredReport.find(r => r.part === partName) ?? null;
    const rRep = rebuiltReport.find(r => r.part === partName) ?? null;

    let dVT = formatVT(dRigSlots, false);
    let rVT = formatVT(rRigSlots, false);
    let modelEqual = true;

    if (dModelAtts && rModelAtts) {
      const dModSlots = modelSlotsForPart(dModelAtts, partName);
      const rModSlots = modelSlotsForPart(rModelAtts, partName);
      dVT = formatVT(dModSlots, true);
      rVT = formatVT(rModSlots, true);
      modelEqual = JSON.stringify(dModSlots) === JSON.stringify(rModSlots);
    }

    const rigEqual = JSON.stringify(dRigSlots) === JSON.stringify(rRigSlots);
    const reportEqual = JSON.stringify(dRep) === JSON.stringify(rRep);
    const equal = dVT === rVT && rigEqual && reportEqual && modelEqual;

    rows.push({
      character,
      outfit,
      part: partName,
      deliveredVT: dVT,
      rebuiltVT: rVT,
      equal,
    });
  }
  return rows;
}

export function formatReproducibilityTable(rows) {
  const headers = ['character', 'outfit', 'part', 'delivered v/t', 'rebuilt v/t', 'equal?'];
  const cells = rows.map(r => [
    r.character,
    r.outfit,
    r.part,
    r.deliveredVT,
    r.rebuiltVT,
    String(r.equal),
  ]);
  const widths = headers.map((h, i) => Math.max(h.length, ...cells.map(c => c[i].length)));
  const fmtRow = cols => cols.map((c, i) => c.padEnd(widths[i])).join(' | ');
  const sep = widths.map(w => '-'.repeat(w)).join('-+-');
  return [fmtRow(headers), sep, ...cells.map(fmtRow)].join('\n');
}

/**
 * Fast in-memory verification of declared repairs and mesh coherence across
 * all 5 characters × 3 outfits. Used by `--check-inputs` and unit/mutant tests.
 */
export function verifyDeclaredReproducibility(root = defaultFamily, { ignoreRepairs = false } = {}) {
  const allRows = [];
  const provenanceFaults = [];
  for (const outfit of OUTFITS) {
    for (const character of CHARACTERS) {
      const { outDir } = rigPaths(root, character, outfit);
      const { declared } = loadAndVerifyDeclaredRepairs(root, character, outfit);
      const deliveredRig = json(join(outDir, 'rig/rig.json'));
      if (declared.materialProfile) {
        materialProfileRig(deliveredRig, declared.materialProfile, 'repaired', 'reverse');
        const provenancePath = join(outDir, 'rig/material-profile.provenance.json');
        if (!existsSync(provenancePath)) fail(`REPRODUCIBILITY_PROFILE_PROVENANCE_MISSING ${character}`);
        const provenance = json(provenancePath);
        if (provenance.spec !== 'family-material-profile-provenance/1' || provenance.profileSHA256 !== sha(JSON.stringify(declared.materialProfile)) || provenance.configSHA256 !== sha(readFileSync(rigPaths(root, character, outfit).configPath)) || provenance.authoringSHA256 !== sha(readFileSync(join(outDir, 'rig/rig.json'))) || provenance.compiledModelSHA256 !== sha(readFileSync(join(outDir, 'check/build/skeleton.model.json')))) provenanceFaults.push(`REPRODUCIBILITY_PROFILE_PROVENANCE_DRIFT ${character}`);
      }
      const deliveredReport = json(join(outDir, 'rig/mesh_report.json'));
      const deliveredModel = json(join(outDir, 'check/build/skeleton.model.json'));
      const partsList = json(join(outDir, 'parts.json')).parts;

      for (const part of partsList) {
        const partName = part.name;
        const dRigSlots = slotsForPart(deliveredRig.skins.default, partName);
        const dModSlots = modelSlotsForPart(deliveredModel.skins?.[0]?.attachments, partName);
        const dRep = deliveredReport.find(r => r.part === partName) ?? null;
        const digest = declared.modelDigests?.[partName];
        const repairEntry = declared.parts?.[partName];

        const dVT = formatVT(dModSlots, true);
        let rVT = digest
          ? (digest.region ? 'region' : `${digest.vertices}v/${digest.triangles}t`)
          : dVT;
        let equal = true;

        if (ignoreRepairs && repairEntry) {
          const reg = repairEntry.regenerated;
          rVT = reg.region ? 'region' : `${reg.vertices}v/${reg.triangles}t`;
          equal = false;
        } else {
          if (!digest) {
            equal = false;
          } else {
            const rigMatch = sha(JSON.stringify(dRigSlots)) === digest.rigSHA256;
            const repMatch = sha(JSON.stringify(dRep)) === digest.reportSHA256;
            const modMatch = sha(JSON.stringify(dModSlots)) === digest.modelSHA256;
            const repairMatch = !repairEntry || sha(JSON.stringify(dRigSlots)) === repairEntry.repaired.sha256;
            equal = (dVT === rVT) && rigMatch && repMatch && modMatch && repairMatch;
          }
        }

        allRows.push({
          character,
          outfit,
          part: partName,
          deliveredVT: dVT,
          rebuiltVT: rVT,
          equal,
        });
      }
    }
  }

  const table = formatReproducibilityTable(allRows);
  const failures = allRows.filter(r => !r.equal);
  if (failures.length > 0) {
    const summary = failures
      .map(f => `${f.character}/${f.outfit}/${f.part} (delivered=${f.deliveredVT} rebuilt=${f.rebuiltVT})`)
      .join(', ');
    fail(`REPRODUCIBILITY_MISMATCH ${summary}\n${table}`);
  }
  if (provenanceFaults.length) fail(provenanceFaults.join("; "));
  return { rows: allRows, table };
}

/**
 * Full end-to-end rebuild from config.json via `rig-parts rig` + declared repairs +
 * `rigc build` compilation and compiled `skeleton.model.json` diff across all
 * 5 characters × 3 outfits (15 rigs).
 */
export function rebuildAndVerifyAll({
  root = defaultFamily,
  out,
  ignoreRepairs = false,
  characters = CHARACTERS,
  outfits = OUTFITS,
} = {}) {
  if (!process.versions.bun) fail('REPRODUCIBILITY_BUILD_REQUIRES_BUN');
  const toolRoot = join(root, 'tools/outline-field-islands');
  const binDir = join(toolRoot, 'node_modules/.bin');
  const rigPartsBin = join(binDir, 'rig-parts');
  const rigcBin = join(binDir, 'rigc');

  const workRoot = out ? resolve(out) : mkdtempSync(join(tmpdir(), 'family-reproducibility-'));
  mkdirSync(workRoot, { recursive: true });

  const runCmd = (binary, args, logPath) => {
    const fd = openSync(logPath, 'w');
    const result = spawnSync(process.execPath, ['--bun', 'run', binary, ...args], {
      cwd: root,
      stdio: ['ignore', fd, fd],
    });
    closeSync(fd);
    if (result.error || result.status !== 0) {
      fail(`REPRODUCIBILITY_COMMAND_FAILED ${binary} exit=${result.status} log=${logPath}`);
    }
  };

  const rebuiltOfficeByChar = {};
  const allRows = [];

  for (const outfit of outfits) {
    for (const character of characters) {
      const { baseDir, configDir, configPath, partsInputDir, outDir } = rigPaths(root, character, outfit);
      const { declared } = loadAndVerifyDeclaredRepairs(root, character, outfit);
      const targetDir = join(workRoot, outfit, character);
      mkdirSync(targetDir, { recursive: true });

      const rawRigDir = join(targetDir, 'raw-rig');
      runCmd(
        rigPartsBin,
        ['rig', '--config', configPath, '--parts', partsInputDir, '--out', rawRigDir],
        join(targetDir, 'rig-parts-rig.log'),
      );

      let baseRawRig = json(join(rawRigDir, 'rig.json'));
      let baseRawReport = json(join(rawRigDir, 'mesh_report.json'));

      if (outfit !== 'office') {
        const officeData = rebuiltOfficeByChar[character] ?? {
          rig: officeBaselineForOutfits(root, character),
          report: json(join(root, character, 'out/rig/mesh_report.json')),
          imagesDir: join(root, character, 'out/rig/images'),
        };
        const assembly = json(resolve(configDir, declared.baseline.assemblyFile));
        const merged = mergeOutfitWithOfficeBaseline({
          officeRig: officeData.rig,
          officeReport: officeData.report,
          rawOutfitRig: baseRawRig,
          rawOutfitReport: baseRawReport,
          assembly,
        });
        baseRawRig = merged.rig;
        baseRawReport = merged.report;
      }

      const { rig: finalRig, report: finalReport, baselineRig } = applyDeclaredRepairsToRig({
        character,
        outfit,
        rawRig: baseRawRig,
        rawReport: baseRawReport,
        declared,
        ignoreRepairs,
      });

      const deliveredSkel = json(join(outDir, 'check/build/skeleton.json'));
      const match = /^\.\.\/\.\.\/([A-Za-z0-9][A-Za-z0-9_-]*)\/images\/$/.exec(deliveredSkel.skeleton.images);
      const histRigDirName = match ? match[1] : 'rig';
      const compileRigDir = join(targetDir, histRigDirName);
      mkdirSync(join(compileRigDir, 'images'), { recursive: true });

      // Copy images from raw-rig (and office baseline for common parts in outfits)
      if (outfit === 'office') {
        cpSync(join(rawRigDir, 'images'), join(compileRigDir, 'images'), { recursive: true });
      } else {
        const officeImagesDir = rebuiltOfficeByChar[character]?.imagesDir ?? join(root, character, 'out/rig/images');
        const assembly = json(resolve(configDir, declared.baseline.assemblyFile));
        for (const [slotName, slotMap] of Object.entries(finalRig.skins.default)) {
          const isNew = assembly.newClothingSlots.includes(slotName);
          const srcImgDir = isNew ? join(rawRigDir, 'images') : officeImagesDir;
          for (const att of Object.values(slotMap)) {
            cpSync(join(srcImgDir, att.image), join(compileRigDir, 'images', att.image));
          }
        }
      }

      const motionPath = outfit === 'office'
        ? join(rawRigDir, 'motion.json')
        : join(rebuiltOfficeByChar[character]?.compileRigDir ?? join(root, character, 'out/rig'), 'motion.json');
      cpSync(motionPath, join(compileRigDir, 'motion.json'));
      writeFileSync(join(compileRigDir, 'rig.json'), `${JSON.stringify(finalRig, null, 2)}\n`);
      writeFileSync(join(compileRigDir, 'mesh_report.json'), `${JSON.stringify(finalReport, null, 2)}\n`);

      if (outfit === 'office') {
        rebuiltOfficeByChar[character] = {
          rig: baselineRig ?? finalRig,
          report: finalReport,
          imagesDir: join(compileRigDir, 'images'),
          compileRigDir,
        };
      }

      const compileOutDir = join(targetDir, 'check/build');
      runCmd(
        rigcBin,
        [
          'build',
          '--rig', join(compileRigDir, 'rig.json'),
          '--motion', join(compileRigDir, 'motion.json'),
          '--images', join(compileRigDir, 'images'),
          '--out', compileOutDir,
          '--profile', 'rig-play',
          '--pack',
          '--page-edges', 'free',
          '--pack-shape', 'polygon',
        ],
        join(targetDir, 'rigc-build.log'),
      );

      const deliveredRig = json(join(outDir, 'rig/rig.json'));
      const deliveredReport = json(join(outDir, 'rig/mesh_report.json'));
      const deliveredModel = json(join(outDir, 'check/build/skeleton.model.json'));
      const rebuiltModel = json(join(compileOutDir, 'skeleton.model.json'));
      const partsList = json(join(outDir, 'parts.json')).parts;

      const rows = diffRigAndModelParts({
        character,
        outfit,
        partsList,
        deliveredRig,
        rebuiltRig: finalRig,
        deliveredReport,
        rebuiltReport: finalReport,
        deliveredModel,
        rebuiltModel,
      });

      if (!ignoreRepairs && declared.materialProfile && !readFileSync(join(outDir, 'rig/rig.json')).equals(readFileSync(join(compileRigDir, 'rig.json')))) fail(`REPRODUCIBILITY_AUTHORING_BYTES_CHANGED ${character}/${outfit}`);

      // Also verify full compiled model and skeleton.json byte equality when all parts are equal
      if (!ignoreRepairs && rows.every(r => r.equal)) {
        const dModelBytes = readFileSync(join(outDir, 'check/build/skeleton.model.json'));
        const rModelBytes = readFileSync(join(compileOutDir, 'skeleton.model.json'));
        if (!dModelBytes.equals(rModelBytes)) {
          fail(`REPRODUCIBILITY_COMPILED_MODEL_BYTES_CHANGED ${character}/${outfit}`);
        }
        const dSkelBytes = readFileSync(join(outDir, 'check/build/skeleton.json'));
        const rSkelBytes = readFileSync(join(compileOutDir, 'skeleton.json'));
        if (!dSkelBytes.equals(rSkelBytes)) {
          fail(`REPRODUCIBILITY_COMPILED_SKELETON_BYTES_CHANGED ${character}/${outfit}`);
        }
      }

      allRows.push(...rows);
    }
  }

  const table = formatReproducibilityTable(allRows);
  console.log(table);
  writeFileSync(join(workRoot, 'reproducibility.txt'), `${table}\n`);
  writeFileSync(join(workRoot, 'reproducibility.json'), `${JSON.stringify({ rows: allRows }, null, 2)}\n`);

  const failures = allRows.filter(r => !r.equal);
  if (failures.length > 0) {
    const summary = failures
      .map(f => `${f.character}/${f.outfit}/${f.part} (delivered=${f.deliveredVT} rebuilt=${f.rebuiltVT})`)
      .join(', ');
    fail(`REPRODUCIBILITY_MISMATCH ${summary}`);
  }

  return { rows: allRows, table, workRoot };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const ignoreRepairs = args.includes('--without-repairs');
  const checkOnly = args.includes('--check-declared');
  const outIdx = args.indexOf('--out');
  const out = outIdx >= 0 ? args[outIdx + 1] : undefined;
  try {
    if (checkOnly) {
      const res = verifyDeclaredReproducibility(defaultFamily, { ignoreRepairs });
      console.log(res.table);
    } else {
      rebuildAndVerifyAll({ root: defaultFamily, out, ignoreRepairs });
    }
  } catch (error) {
    console.error(String(error));
    process.exitCode = 1;
  }
}
