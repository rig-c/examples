// Lossless full-canvas APNG: keep every renderer sample, including the endpoint.
import {readFileSync,writeFileSync,readdirSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const [mode,framesArg,toolsArg,outArg]=process.argv.slice(2);
if(!['preflight','encode','compress'].includes(mode)||!framesArg||!toolsArg)throw Error('usage: bun encode.mjs preflight|encode|compress <render-dir|source.apng> <isolated-toolchain-dir> [out.apng]');
const frames=resolve(framesArg),tools=resolve(toolsArg);
const {readPlate,pngChunk}=await import(pathToFileURL(join(tools,'node_modules/rig-c/tools/plate.ts')).href);
const version=JSON.parse(readFileSync(join(tools,'node_modules/rig-c/package.json'))).version;
if(version!=='2.68.0')throw Error('rig-c 2.68.0 required');
const hash=b=>createHash('sha256').update(b).digest('hex');
function compare(a,b){if(a.length!==b.length||a.length%4)throw Error('RGBA lengths');let max=0,sum=0,over40=0;for(let p=0;p<a.length;p+=4){let pixel=0;for(let c=0;c<3;c++){const d=Math.abs(a[p+c]-b[p+c]);sum+=d;max=Math.max(max,d);pixel=Math.max(pixel,d);}if(pixel>40)over40++;}return {max,mae:sum/(a.length/4*3),pixelsOver40:over40};}
const black=Uint8Array.from([0,0,0,255]),white=Uint8Array.from([255,255,255,255]);
if(compare(black,black).max!==0||compare(black,white).max!==255||compare(black,white).mae!==255||compare(black,white).pixelsOver40!==1)throw Error('metric controls failed');
function chunks(buffer){const out=[];for(let at=8;at<buffer.length;){const length=buffer.readUInt32BE(at),type=buffer.toString('ascii',at+4,at+8);out.push({type,body:buffer.subarray(at+8,at+8+length)});at+=length+12;}return out;}
function predictorArgs(source,output){return ['-v','error','-threads','1','-filter_threads','1','-filter_complex_threads','1','-ignore_loop','1','-i',source,'-frames:v','41','-fps_mode','passthrough','-pix_fmt','rgba','-plays','0','-compression_level','9','-pred','mixed','-f','apng',output];}
function apngMetadata(bytes){const list=chunks(bytes),header=list.find(c=>c.type==='IHDR').body,actl=list.find(c=>c.type==='acTL').body;return {width:header.readUInt32BE(0),height:header.readUInt32BE(4),frames:actl.readUInt32BE(0),plays:actl.readUInt32BE(4),delays:list.filter(c=>c.type==='fcTL').map(c=>[c.body.readUInt16BE(20),c.body.readUInt16BE(22)||100])};}
function verifyAnimation(meta){if(meta.width!==492||meta.height!==1290||meta.frames!==41||meta.plays!==0||meta.delays.length!==41||!meta.delays.every(([n,d])=>n*12===d))throw Error('requires 492x1290, 41 frames, exact 1/12-second delays, infinite APNG');}
if(mode==='compress'){
  if(!outArg)throw Error('out.apng required');
  const output=resolve(outArg);if(output===frames)throw Error('source and output must differ');
  const source=readFileSync(frames);verifyAnimation(apngMetadata(source));
  execFileSync('ffmpeg',predictorArgs(frames,output),{maxBuffer:1024*1024});
  const encoded=readFileSync(output),meta=apngMetadata(encoded);verifyAnimation(meta);
  const decode=path=>execFileSync('ffmpeg',['-v','error','-threads','1','-ignore_loop','1','-i',path,'-frames:v','41','-pix_fmt','rgba','-fps_mode','passthrough','-f','rawvideo','-'],{maxBuffer:512*1024*1024});
  const original=decode(frames),optimized=decode(output);
  if(original.length!==492*1290*4*41||!original.equals(optimized))throw Error('optimized decoded RGBA differs');
  const receipt={mode:'predictor-lossless',sourceSHA256:hash(source),encodedSHA256:hash(encoded),bytes:encoded.length,...meta,decodedRGBAEqual:true,maxRGBAError:0,nativeRendererLoopLine:null,closureDefinition:'rigc emits no closure verdict; this is the measured wrap'};
  writeFileSync(output+'.json',JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));process.exit(0);
}
const metadata=JSON.parse(readFileSync(join(frames,'frames.json')));const set=metadata.sets[0];
if(metadata.sets.length!==1||set.animation!=='idle'||set.fps!==12||set.written!==41||set.sampled!==41)throw Error('expected idle, 41 samples, 12 fps');
const files=readdirSync(join(frames,set.dir)).filter(n=>/^f\d{4}\.png$/.test(n)).sort();if(files.length!==41)throw Error('missing frames');
const digest=createHash('sha256');let width,height;
for(const file of files){const path=join(frames,set.dir,file),bytes=readFileSync(path),image=readPlate(path);digest.update(bytes);if(width===undefined){width=image.width;height=image.height;}if(image.width!==width||image.height!==height)throw Error('frame dimensions differ');const header=chunks(bytes).find(c=>c.type==='IHDR').body;if(header[8]!==8||header[9]!==6||header[12]!==0)throw Error('requires renderer non-interlaced 8-bit RGBA PNGs');}
if(width<492)throw Error('width below 492');
const inputSHA256=digest.digest('hex');
// This executes the decoder/demuxer on the actual checkpoint, without rendering or encoding.
execFileSync('ffmpeg',['-v','error','-threads','1','-framerate','12','-i',join(frames,set.dir,'f%04d.png'),'-frames:v','41','-f','null','-'],{maxBuffer:1024*1024});
if(mode==='preflight'){console.log(JSON.stringify({pass:true,stage:'all PNG/APNG input readers and metric controls',frames:41,width,height,fps:12,concatPNGBytesSHA256:inputSHA256,encoder:'full canvas RGBA PNG chunks; CRC generated by rig-c pngChunk',decoder:'ffmpeg image2 -> null, 41 frames'}));process.exit(0);}
if(!outArg)throw Error('out.apng required');
const output=resolve(outArg),pieces=[readFileSync(join(frames,set.dir,files[0])).subarray(0,8)];
const first=chunks(readFileSync(join(frames,set.dir,files[0]))).find(c=>c.type==='IHDR').body;pieces.push(pngChunk('IHDR',first));
const actl=Buffer.alloc(8);actl.writeUInt32BE(41,0);actl.writeUInt32BE(0,4);pieces.push(pngChunk('acTL',actl));let sequence=0;
for(let i=0;i<files.length;i++){const control=Buffer.alloc(26);control.writeUInt32BE(sequence++,0);control.writeUInt32BE(width,4);control.writeUInt32BE(height,8);control.writeUInt16BE(1,20);control.writeUInt16BE(12,22);pieces.push(pngChunk('fcTL',control));for(const chunk of chunks(readFileSync(join(frames,set.dir,files[i])))){if(chunk.type!=='IDAT')continue;if(i===0)pieces.push(pngChunk('IDAT',chunk.body));else{const seq=Buffer.alloc(4);seq.writeUInt32BE(sequence++);pieces.push(pngChunk('fdAT',Buffer.concat([seq,chunk.body])));}}}
pieces.push(pngChunk('IEND',new Uint8Array()));const encoded=Buffer.concat(pieces);writeFileSync(output,encoded);
// Read the complete encoded animation through an independent decoder and compare every pixel.
const raw=execFileSync('ffmpeg',['-v','error','-threads','1','-i',output,'-frames:v','41','-pix_fmt','rgba','-f','rawvideo','-'],{maxBuffer:512*1024*1024});
const bytesPerFrame=width*height*4;if(raw.length!==41*bytesPerFrame)throw Error('encoded decoded count');
let prior,firstImage,lastImage,maxAdjacent=0;const adjacent=[];
for(let i=0;i<files.length;i++){const image=readPlate(join(frames,set.dir,files[i])).data;if(!Buffer.from(image).equals(raw.subarray(i*bytesPerFrame,(i+1)*bytesPerFrame)))throw Error('decoded pixels differ at frame '+i);if(prior){const reading=compare(prior,image);adjacent.push(reading.mae);maxAdjacent=Math.max(maxAdjacent,reading.mae);}if(i===0)firstImage=image;prior=image;lastImage=image;}
const endpoint=compare(firstImage,lastImage),smoothWrap=endpoint.mae<=maxAdjacent;
const encodedChunks=chunks(encoded),controls=encodedChunks.filter(c=>c.type==='fcTL').map(c=>({numerator:c.body.readUInt16BE(20),denominator:c.body.readUInt16BE(22)}));
if(controls.length!==41||!controls.every(c=>c.numerator===1&&c.denominator===12))throw Error('APNG timing');
const receipt={sourceCommit:'40db33d91e4aacbe4cd31ac9f3cc557973b4a1d4',source:'family/roa/out/check/build',rigc:version,bun:Bun.version,ffmpeg:execFileSync('ffmpeg',['-version'],{encoding:'utf8'}).split('\n')[0],frames:41,sampledFPS:12,dimensions:{width,height},animationDurationSeconds:set.duration,encodedDurationSeconds:41/12,frameDelays:controls,plays:0,pixelsLossless:true,concatPNGBytesSHA256:inputSHA256,encodedSHA256:hash(encoded),bytes:encoded.length,endpoint,maxAdjacentMAE:maxAdjacent,wrapMAE:endpoint.mae,smoothWrap,exactEndpoints:endpoint.max===0,physics:set.physics??null,nativeRendererLoopLine:null,closureDefinition:'rigc emits no closure verdict; this is the measured wrap',supportingSeamLine:`supporting seam: idle 41 frame(s) at 12 fps, f0000 vs f0040: max |d| ${endpoint.max}; wrap MAE ${endpoint.mae} vs max adjacent ${maxAdjacent} — ${smoothWrap?'PASS':'FAIL'} smooth wrap; ${endpoint.max===0?'identical':'different'} endpoints`};
writeFileSync(output+'.json',JSON.stringify(receipt,null,2)+'\n');console.log(receipt.supportingSeamLine);console.log(JSON.stringify(receipt));
