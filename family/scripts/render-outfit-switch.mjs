#!/usr/bin/env node
/** Render the family idle once per outfit and cut office -> uniform -> office.
 * Same requirements as render-readme-preview.mjs, plus ffmpeg and ffprobe.
 * PLAYWRIGHT_MODULE=/tmp/family-preview-tools/node_modules/playwright/index.mjs \
 *   node family/scripts/render-outfit-switch.mjs --work /tmp/family-outfit-switch
 * Both renders use the preview's lineup, warm-up, frame set and blink schedule,
 * so frame 0 of every loop is the same idle phase: each cut lands on a loop
 * boundary and only the clothes change. The cut frames are compared outside
 * the clothing (render-readme-preview.mjs --cut-layers) and written beside the
 * clip as a side-by-side PNG and as figures in the JSON.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';

const family = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
function option(name, fallback) { const i = args.indexOf(name); return i < 0 ? fallback : args[i + 1]; }
const work = path.resolve(option('--work', '/tmp/family-outfit-switch'));
const output = path.resolve(option('--out', path.join(family, 'docs/family-outfit-switch.mp4')));
const sideBySide = output.replace(/\.mp4$/, '-cut.png');
const outfits = ['office', 'uniform'];
const sequence = ['office', 'uniform', 'office'];
const sha = async filename => createHash('sha256').update(await fs.readFile(filename)).digest('hex');
function run(command, argv, capture = false) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, argv, { stdio: ['ignore', capture ? 'pipe' : 'inherit', 'inherit'] });
    let out = '';
    if (capture) child.stdout.on('data', chunk => { out += chunk; });
    child.on('error', reject);
    child.on('exit', code => code === 0 ? resolve(out) : reject(new Error(`${command} exited ${code}`)));
  });
}

await fs.mkdir(work, { recursive: true });
const segments = {};
for (const outfit of outfits) {
  const evidence = path.join(work, `${outfit}-frames`), mp4 = path.join(work, `${outfit}.mp4`);
  await run(process.execPath, [path.join(family, 'scripts/render-readme-preview.mjs'), '--outfit', outfit, '--evidence', evidence, '--mp4', mp4, '--cut-layers', ...(option('--crf', null) === null ? [] : ['--crf', option('--crf')])]);
  segments[outfit] = { evidence, mp4, capture: JSON.parse(await fs.readFile(path.join(evidence, 'capture-inputs.json'), 'utf8')), encode: JSON.parse(await fs.readFile(path.join(evidence, 'mp4.json'), 'utf8')), runtime: JSON.parse(await fs.readFile(path.join(evidence, 'runtime.json'), 'utf8')) };
}
for (const key of ['fps', 'frames', 'width', 'height', 'background', 'crf']) if (segments.office.encode[key] !== segments.uniform.encode[key]) throw new Error(`segments disagree on ${key}`);
if (JSON.stringify(segments.office.encode.sourceFrameIndices) !== JSON.stringify(segments.uniform.encode.sourceFrameIndices)) throw new Error('segments use different frame sets');
for (const [i, entry] of segments.office.runtime.entries()) if (entry.time !== segments.uniform.runtime[i].time) throw new Error(`${entry.key}: animation time differs between outfits`);

const list = path.join(work, 'concat.txt');
await fs.writeFile(list, sequence.map(outfit => `file '${segments[outfit].mp4.replace(/'/g, "'\\''")}'`).join('\n') + '\n');
await fs.mkdir(path.dirname(output), { recursive: true });
await run('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', '-movflags', '+faststart', output]);

// Cut-frame comparison, on frame 0 of each render composited over the clip's background.
const lineupKeys = segments.office.runtime.map(entry => entry.key);
const figures = JSON.parse(await run(process.env.PYTHON ?? 'python3', ['-c', `import json
from PIL import Image, ImageChops, ImageDraw
from pathlib import Path
ev={k:Path(v) for k,v in ${JSON.stringify(Object.fromEntries(outfits.map(o => [o, segments[o].evidence])))}.items()}
keys=${JSON.stringify(lineupKeys)}
bg=${JSON.stringify(segments.office.encode.background)}
def flat(p):
  f=Image.open(p).convert('RGBA'); return Image.alpha_composite(Image.new('RGBA',f.size,bg),f).convert('RGB')
def diff(a,b,t):
  d=ImageChops.difference(a,b).convert('RGB'); r,g,bb=d.split(); m=ImageChops.lighter(ImageChops.lighter(r,g),bb)
  return m.point(lambda v:255 if v>t else 0)
def count(m): return m.histogram()[255]
o,u=flat(ev['office']/'frame-000.png'),flat(ev['uniform']/'frame-000.png')
W,H=o.size
boxes={}
cloth=Image.new('L',(W,H),0)
for k in keys:
  bx=[]
  for name in ev:
    a=Image.open(ev[name]/f'cut-clothing-{k}.png').getchannel('A').point(lambda v:255 if v>0 else 0)
    cloth=ImageChops.lighter(cloth,a); bb=a.getbbox()
    if bb: bx.append(bb)
  boxes[k]=[min(b[0] for b in bx),min(b[1] for b in bx),max(b[2] for b in bx),max(b[3] for b in bx)]
boxmask=Image.new('L',(W,H),0); dr=ImageDraw.Draw(boxmask)
for b in boxes.values(): dr.rectangle([b[0],b[1],b[2]-1,b[3]-1],fill=255)
out={'cutFrameSize':[W,H],'clothingSlots':'per character, union of both outfits','clothingBoxes':boxes}
for t in (0,8):
  m=diff(o,u,t)
  out[f'threshold{t}']={'differingPixels':count(m),'outsideClothingBoxes':count(ImageChops.subtract(m,boxmask)),'outsideClothingAlpha':count(ImageChops.subtract(m,cloth))}
s=diff(flat(ev['office']/'cut-shared.png'),flat(ev['uniform']/'cut-shared.png'),0)
out['sharedSlotsOnly']={'differingPixels':count(s),'bbox':s.getbbox()}
r=diff(flat(ev['office']/'cut-shared-without-hair.png'),flat(ev['uniform']/'cut-shared-without-hair.png'),0)
out['sharedSlotsWithoutHair']={'differingPixels':count(r),'bbox':r.getbbox()}
m=diff(o,u,0)
vis=Image.new('RGB',(W,H),'white'); vis.paste((200,200,200),mask=boxmask); vis.paste((120,120,120),mask=ImageChops.multiply(m,boxmask)); vis.paste((220,0,0),mask=ImageChops.subtract(m,boxmask))
w=640; h=round(H*w/W)
sheet=Image.new('RGB',(w*3,h),'white')
for i,im in enumerate((o,u,vis)): sheet.paste(im.resize((w,h),Image.Resampling.LANCZOS),(i*w,0))
sheet.save(${JSON.stringify(sideBySide)},optimize=True)
print(json.dumps(out))`], true));

const probe = JSON.parse(await run('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries', 'stream=codec_name,pix_fmt,width,height,r_frame_rate,nb_read_frames:format=duration,size', '-of', 'json', output], true));
const loopSeconds = segments.office.encode.frames / segments.office.encode.fps;
const metadata = {
  schema: 'family-outfit-switch/1',
  sequence, cuts: sequence.slice(1).map((outfit, i) => ({ atSeconds: (i + 1) * loopSeconds, from: sequence[i], to: outfit, loopFrame: 0 })),
  loopSeconds, fps: segments.office.encode.fps, framesPerLoop: segments.office.encode.frames, sourceFrameIndices: segments.office.encode.sourceFrameIndices,
  width: segments.office.encode.width, height: segments.office.encode.height, background: segments.office.encode.background,
  codec: 'H.264 (libx264, preset slow, single thread), yuv420p, concatenated without re-encoding', crf: segments.office.encode.crf,
  capture: { frames: 100, physicsStepSeconds: 1 / 60, warmupCycles: 6, environment: { wind: [4, 0], gravity: [0, 0] }, blink: 'viewer smooth curve, deterministic staggered schedule (same as family-preview.json)' },
  outfits: Object.fromEntries(outfits.map(outfit => [outfit, { captureRecipeSha256: segments[outfit].capture.recipe.htmlSha256, browser: segments[outfit].capture.browser, sources: segments[outfit].capture.sources, frame000Sha256: segments[outfit].capture.frames['frame-000.png'], segmentBytes: segments[outfit].encode.bytes, segmentSha256: segments[outfit].encode.sha256 }])),
  cutFrame: { ...figures, sideBySide: path.basename(sideBySide), sideBySideSha256: await sha(sideBySide) },
  probe: { duration: Number(probe.format.duration), size: Number(probe.format.size), ...probe.streams[0] },
  bytes: (await fs.stat(output)).size, sha256: await sha(output),
};
await fs.writeFile(output.replace(/\.mp4$/, '.json'), JSON.stringify(metadata, null, 2) + '\n');
console.log(JSON.stringify({ output, bytes: metadata.bytes, probe: metadata.probe, cutFrame: figures }, null, 2));
