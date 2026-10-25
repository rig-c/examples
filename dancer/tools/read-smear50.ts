// Preflight the exact staged rig, motion and images through the real compiler reader, without emission.
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const [core, rig, motion, out] = process.argv.slice(2);
if (!core || !rig || !motion || !out) throw new Error('INPUT_PATH: core, rig, motion and output required');
const { compileModel } = await import(pathToFileURL(resolve(core, 'src/compile.ts')).href);
compileModel({ rigPath: resolve(rig), motionPath: resolve(motion), outDir: resolve(out) });
console.log('SMEAR50_REAL_READER_PASS');
