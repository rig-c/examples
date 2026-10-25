/** Dancer-owned producer adoption: canonical bytes plus decoded RGBA inventory. */
import { createHash } from 'node:crypto';
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const dancer = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const json = path => JSON.parse(readFileSync(path, 'utf8'));
const refuse = text => { throw new Error(text); };

export function compareInventories(expected, actual) {
  const names = Object.keys(expected).sort();
  if (!names.length) refuse('PRODUCER_EMPTY: no producer files to compare');
  if (JSON.stringify(names) !== JSON.stringify(Object.keys(actual).sort())) refuse('PRODUCER_INVENTORY: added or missing file');
  for (const name of names) {
    if (JSON.stringify(expected[name]) !== JSON.stringify(actual[name])) refuse(`PRODUCER_BYTES_OR_PIXELS: ${name}`);
  }
  return names.length;
}

export async function inventory(root) {
  const walk = dir => readdirSync(dir).sort().flatMap(name => {
    const file = join(dir, name);
    return statSync(file).isDirectory() ? walk(file) : [file];
  });
  if (!existsSync(join(root, 'rig/rig.json'))) refuse('PRODUCER_RIG: no producer-written rig');
  const install = spawnSync('sh', ['tools/ensure-runtime.sh'], { cwd: dancer, stdio: 'inherit' });
  if (install.error || install.status !== 0) refuse('PRODUCER_RUNTIME: frozen install failed');
  const { readPlate } = await import(pathToFileURL(join(dancer, 'work/runtime/node_modules/rig-c/tools/plate.ts')).href);
  const files = {};
  for (const file of walk(join(root, 'rig'))) {
    const data = readFileSync(file);
    const row = { bytes: data.length, sha256: sha(data) };
    if (file.endsWith('.png')) {
      const png = readPlate(file);
      row.rgba = { width: png.width, height: png.height, sha256: sha(png.data) };
    }
    files[relative(root, file).split('\\').join('/')] = row;
  }
  return files;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 2 || !['--record', '--check', '--out'].includes(args[0])) refuse('USAGE: --record <green-build> | --check <fresh-build> | --out <new-build>');
  const accepted = join(dancer, 'producer');
  const manifest = join(dancer, 'producer-manifest.json');
  let input = resolve(args[1]);
  if (args[0] === '--out') {
    if (existsSync(input)) refuse('PRODUCER_OUTPUT_EXISTS: choose a fresh build directory');
    const result = spawnSync('sh', ['build.sh', input], { cwd: dancer, stdio: 'inherit' });
    if (result.error || result.status !== 0) refuse(`PRODUCER_BUILD: exit ${result.status}`);
  }
  const check = join(input, 'check/check.json');
  if (!existsSync(check) || json(check).PASS !== true) refuse('PRODUCER_CHECK: the fresh build is not green');
  const actual = await inventory(input);
  if (args[0] === '--record') {
    if (existsSync(accepted) || existsSync(manifest)) refuse('PRODUCER_ALREADY_RECORDED: do not overwrite accepted bytes');
    mkdirSync(accepted);
    cpSync(join(input, 'rig'), join(accepted, 'rig'), { recursive: true });
    writeFileSync(manifest, JSON.stringify({ spec: 'dancer-producer/1', configSHA256: sha(readFileSync(join(dancer, 'config.json'))), packageSHA256: sha(readFileSync(join(dancer, 'package.json'))), files: actual }, null, 2) + '\n');
  }
  const pinned = json(manifest);
  if (pinned.spec !== 'dancer-producer/1' || pinned.configSHA256 !== sha(readFileSync(join(dancer, 'config.json'))) || pinned.packageSHA256 !== sha(readFileSync(join(dancer, 'package.json')))) refuse('PRODUCER_INPUT_CHANGED: config or package pin');
  compareInventories(pinned.files, await inventory(accepted));
  const count = compareInventories(pinned.files, actual);
  console.log(`PRODUCER_REPRODUCED: ${count} files byte-identical; PNG dimensions and decoded RGBA identical`);
}
if (import.meta.url === pathToFileURL(resolve(process.argv[1] ?? '')).href) await main();
