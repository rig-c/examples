/** Verify frozen final authoring inputs, then run the ordinary public compiler/check. */
import { createHash } from 'node:crypto';
import { cpSync, existsSync, mkdirSync, openSync, closeSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, relative, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { rebuildAndVerifyAll, verifyDeclaredReproducibility } from './verify-reproducibility.mjs';

const family = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const characters = ['roa', 'luna', 'jinni', 'naru', 'nova'];
const sha = value => createHash('sha256').update(value).digest('hex');
const json = path => JSON.parse(readFileSync(path, 'utf8'));
const fail = message => { throw Error(message); };
const list = dir => readdirSync(dir).sort().flatMap(name => {
  const path = join(dir, name);
  return statSync(path).isDirectory() ? list(path) : [path];
});
const pngSize = path => {
  const bytes = readFileSync(path);
  if (bytes.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') fail(`ACCEPTED_PNG_REQUIRED ${path}`);
  return [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
};

export function historicalRigName(imagesPath) {
  // Preserve the stored exporter layout without accepting arbitrary filesystem paths.
  const match = typeof imagesPath === 'string' && /^\.\.\/\.\.\/([A-Za-z0-9][A-Za-z0-9_-]*)\/images\/$/.exec(imagesPath);
  if (!match || ['check', 'compiler'].includes(match[1])) fail(`ACCEPTED_HISTORICAL_LAYOUT_REFUSED ${String(imagesPath)}`);
  return match[1];
}

export function inventoryPaths(root = family) {
  return characters.flatMap(name => {
    const base = join(root, name);
    return ['out/rig', 'out/parts', 'out/check/build'].flatMap(dir => list(join(base, dir)))
      .concat(['out/parts.json', 'out/check/check.json', 'inputs/painting.png', 'inputs/painting_rgba.png'].map(p => join(base, p)));
  }).concat(list(join(root, 'viewer')).filter(path => !path.endsWith('server.mjs')))
    .map(path => relative(root, path).split('\\').join('/')).sort();
}

export function checkInputs(root = family, manifest = json(join(root, 'accepted-inputs.json'))) {
  if (manifest.spec !== 'family-accepted-inputs/1' || JSON.stringify(manifest.characters) !== JSON.stringify(characters)) fail('ACCEPTED_MANIFEST_SCHEMA');
  const paths = inventoryPaths(root);
  if (JSON.stringify(paths) !== JSON.stringify(Object.keys(manifest.files).sort())) fail('ACCEPTED_INPUT_INVENTORY_CHANGED');
  for (const path of paths) {
    const bytes = readFileSync(join(root, path));
    const row = manifest.files[path];
    if (bytes.length !== row.bytes || sha(bytes) !== row.sha256) fail(`ACCEPTED_INPUT_CHANGED ${path}`);
  }
  const summaries = characters.map(name => {
    const base = join(root, name, 'out');
    const rig = json(join(base, 'rig/rig.json'));
    const parts = json(join(base, 'parts.json'));
    const reports = json(join(base, 'rig/mesh_report.json'));
    const attachments = Object.values(rig.skins.default).flatMap(slot => Object.values(slot));
    for (const part of parts.parts) {
      const actual = pngSize(join(base, 'parts', `${part.name}.png`));
      if (actual[0] !== part.w || actual[1] !== part.h) fail(`ACCEPTED_PART_DIMENSIONS ${name}/${part.name} found=${actual} required=${part.w},${part.h}`);
      const padded = pngSize(join(base, 'rig/images', `${part.name}.png`));
      if (padded[0] !== part.w + 8 || padded[1] !== part.h + 8) fail(`ACCEPTED_PART_PADDING ${name}/${part.name}`);
    }
    for (const attachment of attachments) {
      const image = pngSize(join(base, 'rig/images', attachment.image));
      if (attachment.type === 'mesh' && (attachment.width !== image[0] || attachment.height !== image[1])) fail(`ACCEPTED_ATTACHMENT_IMAGE_DOMAIN ${name}/${attachment.image}`);
    }
    for (const report of reports) {
      const meshes = attachments.filter(a => a.type === 'mesh' && a.image === `${report.part}.png`);
      const vertices = meshes.reduce((n, a) => n + a.uvs.length / 2, 0);
      const triangles = meshes.reduce((n, a) => n + a.triangles.length / 3, 0);
      if (vertices !== report.vertices || triangles !== report.triangles) fail(`ACCEPTED_MESH_REPORT ${name}/${report.part} found=${vertices}v/${triangles}t required=${report.vertices}v/${report.triangles}t`);
    }
    const saved = json(join(base, 'check/check.json'));
    if (saved.PASS !== true || saved.gate_spine_html_green !== true) fail(`ACCEPTED_SAVED_VERDICT ${name}`);
    const sourceDirectory = historicalRigName(json(join(base, 'check/build/skeleton.json')).skeleton.images);
    return { character: name, savedPASS: saved.PASS,
      sourceDirectory,
      savedSkips: Object.entries(saved).filter(([, value]) => value?.status === 'SKIP').map(([key, value]) => ({ key, reason: value.reason })),
      savedPhysicsExcluded: saved.ANIMATIONS_DO_NOT_FOLD.physics_left_out };
  });
  let declaredReproducibility = null;
  if (existsSync(join(root, 'roa/config.json'))) {
    const repro = verifyDeclaredReproducibility(root);
    declaredReproducibility = { partsChecked: repro.rows.length, allEqual: repro.rows.every(r => r.equal) };
  }
  return { scope: 'Input inventory, declared repair hashes, and metadata coherence.',
    files: paths.length, manifestSHA256: sha(readFileSync(join(root, 'accepted-inputs.json'))), declaredReproducibility, summaries };
}

function equalPixels(readPlate, beforePath, afterPath) {
  const before = readPlate(beforePath), after = readPlate(afterPath);
  if (before.width !== after.width || before.height !== after.height || !Buffer.from(before.data).equals(Buffer.from(after.data))) fail(`ACCEPTED_EMITTED_PIXELS_CHANGED ${afterPath}`);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 1 && args[0] === '--check-inputs') {
    console.log(JSON.stringify(checkInputs(), null, 2));
    return;
  }
  if (args.length !== 2 || args[0] !== '--out') fail('Usage: bun family/tools/verify-accepted.mjs --out /new/evidence-directory | node family/tools/verify-accepted.mjs --check-inputs');
  if (!process.versions.bun) fail('ACCEPTED_BUILD_REQUIRES_BUN');
  const out = resolve(args[1]);
  if (existsSync(out) || out === family || !relative(family, out).startsWith('..')) fail('ACCEPTED_FRESH_OUTPUT_OUTSIDE_FAMILY_REQUIRED');
  const inventory = checkInputs();
  const toolRoot = join(family, 'tools/outline-field-islands');
  const modules = join(toolRoot, 'node_modules');
  const versions = {};
  for (const [name, expected] of [['@rig-c/parts', '1.63.0'], ['rig-c', '2.68.0'], ['@esotericsoftware/spine-core', '4.3.13']]) {
    const actual = json(join(modules, name, 'package.json')).version;
    if (actual !== expected) fail(`ACCEPTED_PACKAGE_VERSION ${name} found=${actual} required=${expected}`);
    versions[name] = actual;
  }
  const require = createRequire(join(toolRoot, 'package.json'));
  const { readPlate } = await import(pathToFileURL(require.resolve('rig-c/plate')).href);
  mkdirSync(out, { recursive: true });
  writeFileSync(join(out, 'inputs.json'), JSON.stringify(inventory, null, 2));
  const reproOut = join(out, 'reproducibility');
  const reproducibility = rebuildAndVerifyAll({ root: family, out: reproOut });
  const results = [];
  for (const name of characters) {
    const base = join(family, name, 'out'), target = join(out, name);
    mkdirSync(target);
    const row = { character: name, PASS: false };
    results.push(row);
    try {
      // Use the freshly rebuilt rig from config + declared repairs rather than copying out/rig directly.
      const histName = historicalRigName(json(join(base, 'check/build/skeleton.json')).skeleton.images);
      const rigDirectory = join(target, histName);
      cpSync(join(reproOut, 'office', name, histName), rigDirectory, { recursive: true });
      // Compare each unpadded saved part to its actual padded authoring image.
      for (const part of json(join(base, 'parts.json')).parts) {
        const raw = readPlate(join(base, 'parts', `${part.name}.png`));
        const padded = readPlate(join(base, 'rig/images', `${part.name}.png`));
        for (let y = 0; y < raw.height; y++) {
          const start = ((y + 4) * padded.width + 4) * 4;
          if (!Buffer.from(raw.data.subarray(y * raw.width * 4, (y + 1) * raw.width * 4)).equals(Buffer.from(padded.data.subarray(start, start + raw.width * 4)))) fail(`ACCEPTED_PADDED_PIXELS ${name}/${part.name}`);
        }
      }
      const run = (binary, flags, log) => {
        const fd = openSync(join(target, log), 'w');
        const command = [join(modules, '.bin', binary), ...flags];
        console.log(JSON.stringify({ character: name, command, log: join(target, log) }));
        const result = spawnSync(process.execPath, ['--bun', 'run', ...command], { cwd: family, stdio: ['ignore', fd, fd] });
        closeSync(fd);
        if (result.error || result.status !== 0) fail(`ACCEPTED_PUBLIC_COMMAND_FAILED ${name}/${binary} exit=${result.status} ${result.error?.message ?? ''} log=${join(target, log)}`);
      };
      run('rigc', ['build', '--rig', join(rigDirectory, 'rig.json'), '--motion', join(rigDirectory, 'motion.json'), '--images', join(rigDirectory, 'images'), '--out', join(target, 'compiler/build'), '--profile', 'rig-play', '--pack', '--page-edges', 'free', '--pack-shape', 'polygon'], 'build.log');
      run('rig-parts', ['check', '--rig', rigDirectory, '--parts', base, '--source', join(family, name, 'inputs/painting.png'), '--out', join(target, 'check'), '--page-edges', 'free', '--pack-shape', 'polygon', '--seam-pairs'], 'check.log');
      const check = json(join(target, 'check/check.json'));
      row.check = check;
      if (check.PASS !== true || check.gate_spine_html_green !== true || check.rigc_entry?.spine_core !== '4.3.13' || check.rigc_entry?.entry !== 'cli.ts') fail(`ACCEPTED_FRESH_VERDICT_OR_ORACLE ${name}`);
      const expected = join(base, 'check/build');
      for (const dir of [join(target, 'compiler/build'), join(target, 'check/build')]) {
        const expectedFiles = list(expected).map(p => relative(expected, p));
        const actualFiles = list(dir).map(p => relative(dir, p));
        if (JSON.stringify(expectedFiles) !== JSON.stringify(actualFiles)) fail(`ACCEPTED_EMITTED_INVENTORY ${dir}`);
        for (const file of expectedFiles) {
          if (file.endsWith('.png')) equalPixels(readPlate, join(expected, file), join(dir, file));
          else if (!readFileSync(join(expected, file)).equals(readFileSync(join(dir, file)))) fail(`ACCEPTED_EMITTED_BYTES_CHANGED ${name}/${file}`);
        }
      }
      row.PASS = true;
      row.emittedIdentity = 'Spine/model/atlas bytes and decoded PNG pixels equal stored serving assets; PNG encoder bytes may differ.';
    } catch (error) {
      row.error = String(error);
      console.error(row.error);
    }
    writeFileSync(join(out, 'results.json'), JSON.stringify({ versions, reproducibility: { partsChecked: reproducibility.rows.length }, results, livePhysics: 'Not run; ordinary animation fold check excludes physics. See retained per-stage measurements.' }, null, 2));
  }
  checkInputs(); // A build is never allowed to rewrite the frozen inputs.
  if (results.some(row => !row.PASS)) fail(`ACCEPTED_VERIFICATION_FAILED ${results.filter(r => !r.PASS).map(r => r.character).join(',')} see ${out}/results.json`);
  console.log(JSON.stringify({ PASS: true, versions, characters: results.map(r => r.character), reproducibilityParts: reproducibility.rows.length, evidence: out, livePhysics: 'Not run by this command.' }, null, 2));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(String(error)); process.exitCode = 1; });
}
