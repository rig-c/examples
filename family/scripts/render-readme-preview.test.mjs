import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { parsePreviewArgs } from './render-readme-preview.mjs';
const script=fileURLToPath(new URL('./render-readme-preview.mjs', import.meta.url));
const run=args=>spawnSync(process.execPath,[script,...args],{encoding:'utf8',env:{...process.env,PLAYWRIGHT_MODULE:'/nonexistent-preview-control.mjs'}});

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
