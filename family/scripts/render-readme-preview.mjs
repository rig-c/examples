#!/usr/bin/env node
/** Render the accepted family rigs, retaining the browser compositor's alpha.
 * Requires Node, Playwright with Chromium installed, img2webp, and Python/Pillow.
 * npm install --prefix /tmp/family-preview-tools playwright@1.62.1
 * /tmp/family-preview-tools/node_modules/.bin/playwright install chromium
 * PLAYWRIGHT_MODULE=/tmp/family-preview-tools/node_modules/playwright/index.mjs \
 *   node family/scripts/render-readme-preview.mjs --evidence /tmp/family-preview-frames
 * Keep heavy runs under the maintainer's normal render admission controls.
 */
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';

const family = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
function option(name, fallback) { const i = args.indexOf(name); return i < 0 ? fallback : args[i + 1]; }
const evidence = path.resolve(option('--evidence', '/tmp/family-preview-frames'));
const output = path.resolve(option('--out', path.join(family, 'docs/family-preview.webp')));
const frames = 100, width = 1200, height = 1040, duration = 10 / 3;
const outputFrames = 67, outputWidth = Number(option('--width', '960'));
const quality = Number(option('--quality', '80'));
if (![800,960,1200].includes(outputWidth) || !Number.isFinite(quality) || quality < 1 || quality > 100) throw new Error('width must be 800, 960 or 1200; quality must be 1..100');
const outputHeight = Math.round(height * outputWidth / width);
const lineup = [['roa', 0, 0, 3], ['luna', 435, .06, 2], ['jinni', 995, .45, 4], ['naru', 1540, .85, 3], ['nova', 1915, 1.25, 2]];
const moduleName = process.env.PLAYWRIGHT_MODULE;
const { chromium } = await import(moduleName ? pathToFileURL(path.resolve(moduleName)).href : 'playwright');
async function run(command, argv) {
  await new Promise((resolve, reject) => {
    const child = spawn(command, argv, { stdio: 'inherit', env: { ...process.env, OMP_NUM_THREADS: '4', OPENBLAS_NUM_THREADS: '1' } });
    child.on('error', reject); child.on('exit', code => code === 0 ? resolve() : reject(new Error(`${command} exited ${code}`)));
  });
}
await fs.mkdir(evidence, { recursive: true });
await fs.mkdir(path.dirname(output), { recursive: true });
const sha = async filename => createHash('sha256').update(await fs.readFile(filename)).digest('hex');
const sources={};
for(const relative of ['accepted-inputs.json','viewer/assets/player.js',...lineup.map(([key])=>`${key}/out/check/build/skeleton.model.json`)]) sources[relative]=await sha(path.join(family,relative));
for(const [key] of lineup) {
  const relative=`${key}/out/check/build/skeleton.model.json`;
  const model=JSON.parse(await fs.readFile(path.join(family,relative),'utf8'));
  for(const page of model.pages ?? []) {
    const image=path.resolve(family,path.dirname(relative),page.name);
    if(!image.startsWith(family+path.sep)) throw new Error('Atlas page escapes family directory');
    sources[path.relative(family,image)]=await sha(image);
  }
}
const captureInputs = path.join(evidence,'capture-inputs.json');
const settings = { width, height, duration, frames, lineup };
const html = `<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;width:${width}px;height:${height}px;overflow:hidden;background:transparent}
#scene{position:absolute;transform-origin:0 0;transform:scale(.42);left:192px;top:1000px}
</style><div id="scene"></div><script type="module">
import { l as loadModel, R as RigPlayer } from '/viewer/assets/player.js';
const settings = ${JSON.stringify(settings)};
let tick = 0;
const period = 200, dt = 1/60;
const entries = [];
function phase() { return (tick % period) / 60; }
// Deterministic instances of the viewer's smooth blink; no random wall clock.
function closed(index) {
  const u = ((phase() - (.3 + index * .55) + settings.duration) % settings.duration) / .24;
  if (u >= 1) return 0;
  if (u < .30) { const t = u/.30; return t*t*(3-2*t); }
  if (u < .46) return 1;
  const t = (u-.46)/.54; return 1-t*t*(3-2*t);
}
for (const [index, [key, offset, offsetPhase, z]] of settings.lineup.entries()) {
  const root = document.querySelector('#scene').appendChild(document.createElement('div'));
  root.style.cssText = 'position:absolute;left:'+offset+'px;top:0;z-index:'+z;
  const assets = await loadModel({ modelUrl: '/'+key+'/out/check/build/skeleton.model.json' });
  const player = new RigPlayer(root, assets, { adjust(pose) {
    if (!pose.names.includes('eye_r') || !pose.names.includes('eye_l')) return;
    const c = closed(index);
    for (const name of ['eye_r','eye_l']) { const b=pose.bone(name); b.scaleY=(b.setup.scaleY??1)*(1-c*.88); }
    for (const name of ['brow_r','brow_l']) if(pose.names.includes(name)) { const b=pose.bone(name); b.y=(b.setup.y??0)-c*1.2; }
  }});
  player.play('idle');
  if (offsetPhase) player.frame(offsetPhase);
  entries.push({key, assets, player});
}
function step() {
  tick++;
  const t = phase(), u=(t-.35)/1.3;
  const wind=u>0 && u<1 ? 16*Math.sin(Math.PI*u)**2 : 0;
  for (const {player} of entries) { player.environment({wind:[wind,0],gravity:[0,0]}); player.advance(dt); }
}
// Repeat the same gust and blink during warmup, so the captured physics is periodic.
for(let i=0;i<period*6;i++) step();
function draw() { for(const {player} of entries) player.draw(); }
draw();
globalThis.capture = {
  next(){ for(let i=0;i<2;i++) step(); draw(); return { tick, time:phase() }; },
  stats(){ return entries.map(({key,player})=>({key,time:player.time,bounds:player.bounds(),meshBackend:player.renderer.meshBackend,meshBackendActive:player.renderer.meshBackendActive})); },
  dispose(){ for(const {player,assets} of entries){player.dispose();assets.dispose();} }
};
globalThis.ready=true;
</script>`;
const browserArgs=['--renderer-process-limit=2','--num-raster-threads=2'];
const captureRecipe={htmlSha256:createHash('sha256').update(html).digest('hex'),viewport:{width,height},deviceScaleFactor:1,browserArgs};
let receipt;
if(args.includes('--reuse-frames')) {
  receipt=JSON.parse(await fs.readFile(captureInputs,'utf8'));
  if(JSON.stringify(receipt.sources)!==JSON.stringify(sources) || JSON.stringify(receipt.recipe)!==JSON.stringify(captureRecipe)) throw new Error('Capture inputs or recipe changed; render fresh frames into a new evidence directory');
  for(let i=0;i<=frames;i++) {
    const name=`frame-${String(i).padStart(3,'0')}.png`;
    if(await sha(path.join(evidence,name))!==receipt.frames[name]) throw new Error(`Captured PNG changed: ${name}`);
  }
}
const mime = { '.js':'text/javascript', '.mjs':'text/javascript', '.json':'application/json', '.png':'image/png' };
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname === '/') { res.writeHead(200, {'Content-Type':'text/html'}); res.end(html); return; }
    const file = path.resolve(family, '.' + decodeURIComponent(url.pathname));
    if (!file.startsWith(family + path.sep)) { res.writeHead(403); res.end(); return; }
    res.writeHead(200, {'Content-Type':mime[path.extname(file)] ?? 'application/octet-stream'});
    res.end(await fs.readFile(file));
  } catch { res.writeHead(404); res.end(); }
});
if (!args.includes('--reuse-frames')) {
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await chromium.launch({ headless:true, args:browserArgs });
  const context = await browser.newContext({viewport:{width,height},deviceScaleFactor:1});
  const page = await context.newPage();
  const errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction(()=>globalThis.ready, null, {timeout:120000});
  for(let i=0;i<=frames;i++) {
    await page.screenshot({path:path.join(evidence,`frame-${String(i).padStart(3,'0')}.png`),omitBackground:true});
    if(i<frames) await page.evaluate(()=>globalThis.capture.next());
    if(i%20===0) console.log(`captured ${i}/${frames}`);
  }
  if(errors.length) throw new Error(errors.join('\n'));
  receipt={sources,recipe:captureRecipe,browser:browser.version(),frames:{}};
  for(let i=0;i<=frames;i++) { const name=`frame-${String(i).padStart(3,'0')}.png`; receipt.frames[name]=await sha(path.join(evidence,name)); }
  await fs.writeFile(captureInputs,JSON.stringify(receipt,null,2)+'\n');
  await fs.writeFile(path.join(evidence,'runtime.json'), JSON.stringify(await page.evaluate(()=>globalThis.capture.stats()),null,2)+'\n');
  await page.evaluate(()=>globalThis.capture.dispose());
  await context.close();
} finally {
  if(browser) await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
}
const indices=Array.from({length:outputFrames},(_,i)=>Math.round(i*frames/outputFrames));
await run(process.env.PYTHON ?? 'python3',['-c', `from PIL import Image
from pathlib import Path
p=Path(${JSON.stringify(evidence)})
for i,n in enumerate(${JSON.stringify(indices)}):
 Image.open(p/f'frame-{n:03}.png').resize((${outputWidth},${outputHeight}),Image.Resampling.LANCZOS).save(p/f'encoded-{i:03}.png')`]);
const encode=['-min_size','-loop','0','-lossy','-q',String(quality),'-m','4'];
for(let i=0;i<outputFrames;i++) encode.push('-d',String(Math.round((i+1)*duration*1000/outputFrames)-Math.round(i*duration*1000/outputFrames)),path.join(evidence,`encoded-${String(i).padStart(3,'0')}.png`));
encode.push('-o',output);
await run('img2webp',encode);
const metadata={schema:'family-readme-preview/1',...settings,width:outputWidth,height:outputHeight,frames:outputFrames,capture:{width,height,frames},sourceFrameIndices:indices,frameDurationsMs:Array.from({length:outputFrames},(_,i)=>Math.round((i+1)*duration*1000/outputFrames)-Math.round(i*duration*1000/outputFrames)),loop:0,renderer:'accepted viewer DOM/per-part WebGL',background:'transparent; browser compositor alpha, no chromakey',warmupCycles:6,physicsStepSeconds:1/60,gust:{peak:16,start:.35,duration:1.3,profile:'sin(pi*u)^2'},blink:'viewer smooth curve, deterministic staggered schedule',quality,captureRecipeSha256:captureRecipe.htmlSha256,browser:receipt.browser,sources,bytes:(await fs.stat(output)).size,sha256:await sha(output)};
await fs.writeFile(output.replace(/\.webp$/,'.json'),JSON.stringify(metadata,null,2)+'\n');
console.log(JSON.stringify({output,evidence,bytes:metadata.bytes,sha256:metadata.sha256}));
