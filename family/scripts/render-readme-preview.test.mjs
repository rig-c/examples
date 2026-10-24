import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { parsePreviewArgs, renderPreview } from './render-readme-preview.mjs';
const script=fileURLToPath(new URL('./render-readme-preview.mjs', import.meta.url));
const family=path.resolve(path.dirname(script),'..');
const run=args=>spawnSync(process.execPath,[script,...args],{encoding:'utf8',env:{...process.env,PLAYWRIGHT_MODULE:'/nonexistent-preview-control.mjs'}});
const sha=async file=>createHash('sha256').update(await fs.readFile(file)).digest('hex');

test('help and import require no renderer or output and list the four actual outfits',()=>{
 const r=run(['--help']);assert.equal(r.status,0);assert.match(r.stdout,/office\|homewear\|swimwear\|uniform/);assert.match(r.stdout,/NOT loop acceptance/);assert.equal(r.stderr,'');
 assert.deepEqual(parsePreviewArgs(['--outfit','swimwear','--width','800','--quality','75']),{'--outfit':'swimwear','--width':'800','--quality':'75'});
});
test('unknown, duplicated, missing or mixed-probe arguments refuse before renderer import',()=>{
 for(const args of [['--hlep'],['--outfit'],['--outfit','--help'],['--quality','75','--quality','80'],['--help','--outfit','office'],['--preflight','--reuse-frames'],['--preflight','--mp4','test.mp4']]){
  const r=run(args);assert.notEqual(r.status,0);assert.match(r.stderr,/PREVIEW_(ARGUMENT|HELP_ALONE|PREFLIGHT_MODE)/);assert.doesNotMatch(r.stderr,/ERR_MODULE_NOT_FOUND/);
 }
});
test('invalid outfit, dimensions, quality and extension refuse before renderer import',()=>{
 for(const args of [['--outfit','other'],['--width','0'],['--quality','NaN'],['--quality','101'],['--out','receipt.json'],['--mp4','clip.webp']]){
  const r=run(args);assert.notEqual(r.status,0);assert.doesNotMatch(r.stderr,/ERR_MODULE_NOT_FOUND/);
 }
});
test('preflight with --out pointing into family/docs is refused by name',async()=>{
 const publishedWebp=path.join(family,'docs/family-preview.webp');
 for(const target of [publishedWebp,path.join(family,'docs/probe.webp'),path.join(family,'docs/nested/probe.webp')]){
  await assert.rejects(()=>renderPreview(['--preflight','--out',target]),/PREFLIGHT_OUT_IS_PUBLISHED/);
  const r=run(['--preflight','--out',target]);assert.notEqual(r.status,0);assert.match(r.stderr,/PREFLIGHT_OUT_IS_PUBLISHED/);assert.doesNotMatch(r.stderr,/ERR_MODULE_NOT_FOUND/);
 }
});
test('preflight without --out writes into evidence and leaves family/docs/family-preview.webp byte-identical',async()=>{
 const publishedWebp=path.join(family,'docs/family-preview.webp');
 const publishedJson=path.join(family,'docs/family-preview.json');
 const beforeWebp=await sha(publishedWebp), beforeJson=await sha(publishedJson);
 const probeRoot=path.resolve(family,'..','.lane-evidence/test-preflight-no-out');
 const probeEvidence=path.join(probeRoot,'evidence');
 const mockPlaywright=path.join(probeRoot,'mock-playwright.mjs');
 const mockPython=path.join(probeRoot,'mock-python.sh');
 await fs.rm(probeRoot,{recursive:true,force:true});
 await fs.mkdir(probeRoot,{recursive:true});
 try{
  await fs.writeFile(mockPlaywright,`import fs from 'node:fs/promises';
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==','base64');
export const chromium={async launch(){return{version(){return 'mock-1.0';},async newContext(){return{async newPage(){return{on(){},async goto(){},async waitForFunction(){},async screenshot({path:p}){await fs.writeFile(p,png);},async evaluate(){return[];}};},async close(){}};},async close(){}};}};\n`);
  await fs.writeFile(mockPython,`#!/bin/sh
set -e
out=""
ev=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --evidence) ev="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    *) shift ;;
  esac
done
printf 'RIFFmockWEBP' > "$out"
printf '{"decodedFrames":3,"sourceFrameIndices":[0,1,2],"frameDurationsMs":[1111,1111,1111],"framesSHA256":"00","frameOrder":["frame-000.png","frame-001.png","frame-002.png"],"encoder":{"Pillow":"mock"},"verification":{"preflightOnly":true,"acceptanceMeasured":false,"alphaMaxErrorFromEncodingPNG":0},"alpha":[]}\n' > "$ev/preview-loop.json"
`,{mode:0o755});
  const prevPlaywright=process.env.PLAYWRIGHT_MODULE, prevPython=process.env.PYTHON;
  process.env.PLAYWRIGHT_MODULE=mockPlaywright; process.env.PYTHON=mockPython;
  try{ await renderPreview(['--preflight','--evidence',probeEvidence]); }
  finally{
   if(prevPlaywright===undefined) delete process.env.PLAYWRIGHT_MODULE; else process.env.PLAYWRIGHT_MODULE=prevPlaywright;
   if(prevPython===undefined) delete process.env.PYTHON; else process.env.PYTHON=prevPython;
  }
  assert.equal((await fs.stat(path.join(probeEvidence,'family-preview.webp'))).isFile(),true);
  assert.equal((await fs.stat(path.join(probeEvidence,'family-preview.json'))).isFile(),true);
  assert.equal(await sha(publishedWebp),beforeWebp);
  assert.equal(await sha(publishedJson),beforeJson);
 }finally{
  await fs.rm(probeRoot,{recursive:true,force:true});
 }
});
