// Exercise render's real core backend and every referenced atlas page before a full frame run.
import { readFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
const [core, dir] = process.argv.slice(2);
if (!core || !dir) throw new Error('INPUT_PATH: core and compiled build required');
const root = resolve(dir), skeleton = join(root, 'skeleton.json'), atlas = join(root, 'skeleton.atlas');
const { loadCandidate } = await import(pathToFileURL(resolve(core, 'src/render_shared.ts')).href);
const loaded = loadCandidate({ skeletonText: readFileSync(skeleton, 'utf8'), atlasText: readFileSync(atlas, 'utf8'), atlasDir: root, label: 'smear50-preflight' }, { skeleton, atlas }, 'core');
if (!loaded.choice.core) throw new Error('CORE_BACKEND_REQUIRED');
loaded.choice.core.setup(undefined);
console.log('SMEAR50_RENDER_BACKEND_PASS', loaded.pages.size);
