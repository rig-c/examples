/** Roa-only, gated native/own offline experiment. No source art is edited. */
import { readFileSync, writeFileSync, mkdirSync, cpSync, readdirSync, existsSync } from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { createHash } from 'node:crypto';
import { cpus } from 'node:os';
type Weight = { bone: string; x: number; y: number; weight: number };
type Bone = { name: string; parent?: string; x?: number; y?: number; rotation?: number; length?: number };
type Attachment = { type: string; image: string; width: number; height: number; uvs: number[]; triangles: number[]; hull: number; weights: Weight[][] };
type Rig = { bones: Bone[]; constraints: Record<string, unknown>[]; images: string; skins: Record<string, Record<string, Record<string, Attachment>>> };
type Track = { bone: string; property: string; keys: { t: number; v: number[]; curve?: number[] }[] };
type Motion = { animations: Record<string, { duration: number; loop: boolean; tracks: Track[]; note?: string }> };
type Matrix = { name: string; a: number; b: number; c: number; d: number; worldX: number; worldY: number };
type Frame = { time: number; bones: Matrix[]; attachments: {slot: string; attachment: string; vertices: number[]}[] };
type Geometry = { setup: Frame; rest: {slot: string; vertices: number[]; triangles: number[]; hull: number}[]; frames: Frame[] };
const argv = process.argv.slice(2);
function arg(name: string, fallback?: string): string { const at = argv.indexOf('--'+name); const v = at < 0 ? fallback : argv[at+1]; if (!v) throw Error('ARG_REQUIRED '+name); return v; }
const source = resolve(arg('source', resolve(import.meta.dir, '..')));
const out = resolve(arg('out', join(import.meta.dir, 'results')));
const core = resolve(arg('core'));
const diagnosticSetup=argv.includes('--diagnostic-setup');
const setupFailures:string[]=[];
const selectedCases = arg('cases','impulse').split(',');
const selectedVariants = arg('variants','light,heavy').split(',');
const protocolPath = join(import.meta.dir, 'protocol.json');
const P = JSON.parse(readFileSync(protocolPath,'utf8'));
if(selectedCases.some(x=>!P.cases.includes(x))||selectedVariants.some(x=>!P.variants.includes(x))||selectedVariants[0]!=='light')throw Error('DECLARED_SELECTION_REQUIRED');
const hash = (p: string) => createHash('sha256').update(readFileSync(p)).digest('hex');
const read = <T>(p: string): T => JSON.parse(readFileSync(p,'utf8')) as T;
const clone = <T>(o: T): T => structuredClone(o);
const put = (p: string, o: unknown) => { mkdirSync(dirname(p),{recursive:true}); writeFileSync(p,JSON.stringify(o,null,2)+'\n'); };
function check(ok: unknown, code: string) { if (!ok) throw Error(code); }
mkdirSync(out,{recursive:true});
const commands: unknown[] = [];
// Additional guard inside the standard nova-run submission. Refuse local execution.
check(process.platform==='linux' && existsSync('/proc/self/status'),'NOVA_LINUX_REQUIRED');
const allowed = readFileSync('/proc/self/status','utf8').match(/^Cpus_allowed_list:\s*(.+)$/m)?.[1];
check(allowed,'CPU_AFFINITY_REQUIRED');
const ids = allowed!.split(',').flatMap(x => { const [a,b]=x.split('-').map(Number); return Array.from({length:(b??a)-a+1},(_,i)=>a+i); }).slice(0,4);
check(ids.length>0 && ids.length<=4 && cpus().length>0,'CPU_BUDGET');
check(Bun.spawnSync(['taskset','-pc',ids.join(','),String(process.pid)]).exitCode===0,'CPU_AFFINITY_REJECTED');
Object.assign(process.env,{UV_THREADPOOL_SIZE:'4',GOMAXPROCS:'4',BUN_CONFIG_MAX_HTTP_REQUESTS:'4',NODE_OPTIONS:'--max-old-space-size=2048'});
function treeRss(rootPid: number): number {
 const table = new Map<number,{parent:number;group:number;rss:number}>();
 for (const name of readdirSync('/proc')) { if (!/^\d+$/.test(name)) continue; try { const stat=readFileSync('/proc/'+name+'/stat','utf8').split(') ').slice(1).join(') ').split(' '); const status=readFileSync('/proc/'+name+'/status','utf8'); table.set(+name,{parent:+stat[1],group:+stat[2],rss:+(status.match(/^VmRSS:\s+(\d+)/m)?.[1]??0)*1024}); } catch {} }
 const chosen=new Set([rootPid,process.pid]); let changed=true;
 while(changed){changed=false;for(const [pid,p]of table)if((chosen.has(p.parent)||p.group===rootPid)&&!chosen.has(pid)){chosen.add(pid);changed=true;}}
 return [...chosen].reduce((s,p)=>s+(table.get(p)?.rss??0),0);
}
async function run(name: string, cmd: string[], cwd=core) {
 console.log('RUN',name,JSON.stringify(cmd));
 const stdout=Bun.file(join(out,name+'.stdout')), stderr=Bun.file(join(out,name+'.stderr'));
 const child=Bun.spawn(['setsid',...cmd],{cwd,env:process.env,stdout,stderr}); let peak=0, rejected=false;
 const timer=setInterval(()=>{peak=Math.max(peak,treeRss(child.pid));if(peak>4*1024**3){rejected=true;try{process.kill(-child.pid,'SIGKILL');}catch{child.kill();}}},50);
 const code=await child.exited;clearInterval(timer);
 commands.push({name,cmd,exitCode:code,peakTreeRssBytes:peak,rejected});put(join(out,'budget.json'),{cpuAffinity:ids,rssLimitBytes:4*1024**3,commands});
 if(code!==0||rejected){console.log((await stdout.text()).slice(-3500),(await stderr.text()).slice(-3500));throw Error(name+': exit '+code+' rssRejected='+rejected);}
}
for (const [file,sha] of Object.entries(P.sourceHashes)) check(hash(join(source,file))===sha,'SOURCE_HASH '+file);
put(join(out,'protocol.frozen.json'),P);
put(join(out,'input-manifest.json'),{protocol:hash(protocolPath),probe:hash(import.meta.path),source,core,corePackage:read(join(core,'package.json')),sourceHashes:P.sourceHashes});
await run('runtime',['node','-e',"if(process.release.name!=='node'||process.versions.bun)throw Error('REAL_NODE_REQUIRED');console.log(JSON.stringify(process.versions))"]);
if(!existsSync(join(core,'node_modules/@esotericsoftware/spine-core/package.json'))) await run('install',['bun','install','--frozen-lockfile','--ignore-scripts']);
check(read<{version:string}>(join(core,'node_modules/@esotericsoftware/spine-core/package.json')).version==='4.3.13','NATIVE_VERSION');
const base=read<Rig>(join(source,'out/rig/rig.json'));
const originalMotion=read<Motion>(join(source,'out/rig/motion.json'));
const attachment=(r: Rig)=>r.skins.default.topwear.topwear;
check(attachment(base).weights.length===376 && attachment(base).triangles.length===646*3 && attachment(base).hull===104,'BASE_TOPOLOGY');
const env=join(out,'environment.json');put(env,{spec:'rigc-environment/1',steps:[{t:0,wind:[0,0],gravity:[0,0]}]});
const cli=join(core,'cli.ts');
function motion(kind: string, seconds=P.timing.seconds): Motion {
 const m=clone(originalMotion);
 const tracks: Track[]=kind==='breath'?clone(originalMotion.animations.idle.tracks).filter(t=>t.bone==='chest_ctl').map(t=>{
  const period=originalMotion.animations.idle.duration; const k=[] as Track['keys'];
  for(let n=0;n<=Math.ceil(seconds/period);n++)for(const key of t.keys){const time=key.t+n*period;if(time>seconds)continue;const c=key.curve?.map((x,i)=>i%2===0?x+n*period:x);k.push({...key,t:time,...(c?{curve:c}:{})});}
  // End on the loop boundary instead of inventing a sampled curve endpoint.
  return {...t,keys:k};
 }):[];
 if(kind==='impulse')tracks.push({bone:'root',property:'translatey',keys:P.timing.impulse.map(([t,y]:number[])=>({t,v:[y]}))});
 if(tracks.length===0)tracks.push({bone:'root',property:'translatey',keys:[{t:0,v:[0]},{t:seconds,v:[0]}]});
 // Breath has a declared last key, held through the end; it is the same source keys in every variant.
 m.animations.challenge={duration:seconds,loop:false,note:'Deterministic Roa-only '+kind+'; no random input; original translation physics; no mesh rewrite.',tracks};return m;
}
async function build(name:string,r:Rig,m:Motion){
 const dir=join(out,name);mkdirSync(dir,{recursive:true});
 r.images='images';cpSync(join(source,'out/rig/images'),join(dir,'images'),{recursive:true});
 put(join(dir,'rig.json'),r);put(join(dir,'motion.json'),m);
 await run(name+'-gate',['bun',cli,'build','--rig',join(dir,'rig.json'),'--motion',join(dir,'motion.json'),'--images',join(dir,'images'),'--out',join(dir,'build'),'--profile','spine','--report',join(dir,'gate.json')]);return dir;
}
async function render(dir:string,poser:string,fps=P.timing.fps,max=P.render.max,viewport=P.render.viewport,suffix=poser){
 const dest=join(dir,suffix);
 await run(dir.split('/').at(-1)+'-'+poser,['bun',cli,'render','--candidate',join(dir,'build'),'--animation','challenge','--fps',String(fps),'--max',String(max),'--viewport',viewport.join(','),'--geometry','--folds','--environment',env,'--poser',poser,'--out',dest]);
 const files:string[]=[];function walk(p:string){for(const x of readdirSync(p,{withFileTypes:true})){const q=join(p,x.name);if(x.isDirectory())walk(q);else if(x.name==='geometry.json')files.push(q);}}walk(dest);check(files.length===1,'ONE_GEOMETRY '+dir+' '+poser);return read<Geometry>(files[0]);
}
// The baseline is the original rig, including its original translation physics.
const prep=await build('bind-setup',clone(base),motion('rest',.1));const bind=await render(prep,'spine',1,32);
const bindBone=new Map(bind.setup.bones.map(b=>[b.name,b]));const world=bind.rest.find(a=>a.slot==='topwear')!.vertices;
const local=(b:Matrix,x:number,y:number)=>{const dx=x-b.worldX,dy=y-b.worldY,det=b.a*b.d-b.b*b.c;check(Math.abs(det)>0,'NONCOLLAPSED_BIND');return [(b.d*dx-b.b*dy)/det,(-b.c*dx+b.a*dy)/det];};
function variant(name:string):Rig{
 const r=clone(base);check(name==='light'||name==='heavy','VARIANT_NAME '+name);
 if(name==='heavy')for(const h of P.helpers){const c=r.constraints.find(c=>c.type==='physics'&&c.bone===h.bone);check(c,'PHYSICS_BY_NAME '+h.bone);c!.inertia=Number(c!.inertia)*P.heavy.inertiaMultiplier;}
 check(JSON.stringify(r.bones)===JSON.stringify(base.bones)&&JSON.stringify(r.skins)===JSON.stringify(base.skins),'ORIGINAL_BONES_MESH_WEIGHTS_EXACT');
 const expected=clone(base);if(name==='heavy')for(const h of P.helpers){const c=expected.constraints.find(c=>c.type==='physics'&&c.bone===h.bone)!;c.inertia=Number(c.inertia)*P.heavy.inertiaMultiplier;}
 check(JSON.stringify(r)===JSON.stringify(expected),'ONLY_DECLARED_INERTIA_CHANGE');return r;
}
const responseIds=attachment(base).weights.flatMap((row,i)=>row.some(w=>P.helpers.some((h:{bone:string})=>h.bone===w.bone)&&w.weight>0)?[i]:[]);
const supportIds=Array.from({length:376},(_,i)=>i).filter(i=>!responseIds.includes(i));
const metrics: Record<string,unknown>={};const geometry=new Map<string,Geometry>();
const top=(f:Frame)=>f.attachments.find(a=>a.slot==='topwear')!.vertices;
function relative(f:Frame){const b=f.bones.find(b=>b.name==='chest')!;const v=top(f);return Array.from({length:v.length/2},(_,i)=>local(b,v[2*i],v[2*i+1])).flat();}
function maxDiff(a:number[],b:number[]){check(a.length===b.length,'LENGTH_MATCH');return Math.max(0,...a.map((v,i)=>Math.abs(v-b[i])));}
function folds(g:Geometry){const tri=g.rest.find(a=>a.slot==='topwear')!.triangles;const rest=top(g.setup);let count=0;for(const frame of g.frames){const v=top(frame);for(let i=0;i<tri.length;i+=3){const [a,b,c]=tri.slice(i,i+3);const area=(p:number[]) => (p[2*b]-p[2*a])*(p[2*c+1]-p[2*a+1])-(p[2*b+1]-p[2*a+1])*(p[2*c]-p[2*a]);if(area(v)*area(rest)<=0)count++;}}return count;}
for(const kind of selectedCases)for(const name of selectedVariants){
 const id=kind+'-'+name;const dir=await build(id,variant(name),motion(kind));const native=await render(dir,'spine');const own=await render(dir,'core');
 check(native.frames.length===own.frames.length,'FRAME_COUNT');let delta=0;
 for(let i=0;i<native.frames.length;i++)for(const a of native.frames[i].attachments){const b=own.frames[i].attachments.find(v=>v.slot===a.slot&&v.attachment===a.attachment);check(b,'NATIVE_ATTACHMENT '+a.slot);delta=Math.max(delta,maxDiff(a.vertices,b!.vertices));}
 const authored=read<Rig>(join(dir,'rig.json'));const quantization=[];
 for(let i=0;i<376;i++){const row=attachment(authored).weights[i];const ideal=[0,0],quant=[0,0],bound=[0,0];for(const w of row){const b=native.setup.bones.find(b=>b.name===w.bone)!;const x=Math.fround(w.x),y=Math.fround(w.y),q=Math.fround(w.weight);const ix=b.a*w.x+b.b*w.y+b.worldX,iy=b.c*w.x+b.d*w.y+b.worldY;ideal[0]+=ix*w.weight;ideal[1]+=iy*w.weight;quant[0]+=(b.a*x+b.b*y+b.worldX)*q;quant[1]+=(b.c*x+b.d*y+b.worldY)*q;bound[0]+=Math.abs(q-w.weight)*Math.abs(ix)+Math.abs(q)*(Math.abs(b.a*(x-w.x))+Math.abs(b.b*(y-w.y)));bound[1]+=Math.abs(q-w.weight)*Math.abs(iy)+Math.abs(q)*(Math.abs(b.c*(x-w.x))+Math.abs(b.d*(y-w.y)));}quantization.push({vertex:i,ideal,quantized:quant,bound,actual:[top(native.setup)[2*i],top(native.setup)[2*i+1]],target:[world[2*i],world[2*i+1]]});}put(join(dir,'quantization.json'),quantization);
 const setupDelta=maxDiff(top(native.setup),world);const foldCount=folds(native);const initial=relative(native.frames[0]);
 const trace=native.frames.map(f=>{const rel=relative(f);let energy=0;for(const i of responseIds)energy=Math.max(energy,Math.hypot(rel[2*i]-initial[2*i],rel[2*i+1]-initial[2*i+1]));return{time:f.time,displacement:energy};});
 const peak=Math.max(...trace.map(v=>v.displacement));const peakAt=trace.find(v=>v.displacement===peak)!.time;
 const settleThreshold=Math.max(.05,.05*peak);let settle:number|null=null;
 for(let i=trace.findIndex(v=>v.time>=peakAt);i<trace.length;i++)if(trace.slice(i).every(v=>v.displacement<=settleThreshold)){settle=trace[i].time;break;}
 const landmarks=P.helpers.flatMap((h:{helper:string;length:number;reach:number;side:string;bone:string})=>{const center=bindBone.get(h.bone)!;const ids=responseIds.filter(i=>attachment(base).weights[i].some(w=>w.bone===h.bone&&w.weight>0));const closest=(x:number,y:number,points:number[])=>points.reduce((a,i)=>Math.hypot(world[2*i]-x,world[2*i+1]-y)<Math.hypot(world[2*a]-x,world[2*a+1]-y)?i:a,points[0]);let maxId=ids[0],maxValue=0;for(const f of native.frames){const v=relative(f);for(const i of ids){const value=Math.hypot(v[2*i]-initial[2*i],v[2*i+1]-initial[2*i+1]);if(value>maxValue){maxValue=value;maxId=i;}}}return [{name:h.side+'-center-nearest',vertex:closest(center.worldX,center.worldY,ids)},{name:h.side+'-upper-support',vertex:closest(center.worldX,center.worldY+h.reach,Array.from({length:104},(_,i)=>i))},{name:h.side+'-maximum-response',vertex:maxId}];});
 for(const [i,[px,py]]of (P.landmarks?.placketSourceImagePoints??[]).entries()){const x=px-400,y=2284-py;let vertex=0;for(let v=1;v<376;v++)if(Math.hypot(world[2*v]-x,world[2*v+1]-y)<Math.hypot(world[2*vertex]-x,world[2*vertex+1]-y))vertex=v;landmarks.push({name:'placket-'+i,vertex});}
 const signed=native.frames.map(f=>{const v=relative(f);return {time:f.time,landmarks:landmarks.map(l=>({...l,dx:v[2*l.vertex]-initial[2*l.vertex],dy:v[2*l.vertex+1]-initial[2*l.vertex+1]}))};});put(join(dir,'signed-landmarks.json'),{coordinates:'chest-local, y up, relative to frame0; nearest existing vertices, not an invented exact center',landmarks,frames:signed});
 const driverTrace=native.frames.map(f=>({time:f.time,bones:P.helpers.map((h:{helper:string;bone:string})=>{const b=f.bones.find(b=>b.name===(h.bone))!;const ch=f.bones.find(b=>b.name==='chest')!;const det=ch.a*ch.d-ch.b*ch.c;const ax=(ch.d*b.a-ch.b*b.c)/det,ay=(-ch.c*b.a+ch.a*b.c)/det,bx=(ch.d*b.b-ch.b*b.d)/det,by=(-ch.c*b.b+ch.a*b.d)/det;return {bone:b.name,localOrigin:local(ch,b.worldX,b.worldY),axisXLength:Math.hypot(ax,ay),axisYLength:Math.hypot(bx,by),localDeterminant:ax*by-ay*bx};})}));put(join(dir,'driver-matrix-trace.json'),{note:'Effective helper local axis lengths, not a claim to native internal scaleOffset field',frames:driverTrace});
 const ref=name==='light'?native:geometry.get(kind+'-light')!;let supportDelta=0,hullDelta=0;for(let i=0;i<native.frames.length;i++){const a=relative(native.frames[i]),b=relative(ref.frames[i]);hullDelta=Math.max(hullDelta,maxDiff(a.slice(0,208),b.slice(0,208)));for(const v of supportIds)supportDelta=Math.max(supportDelta,Math.abs(a[2*v]-b[2*v]),Math.abs(a[2*v+1]-b[2*v+1]));}
 metrics[id]={nativeOwnMaxDelta:delta,setupDelta,supportDelta,supportVertices:supportIds.length,hullDelta,foldCount,peak,peakAt,settle,settleThreshold,frames:native.frames.length};put(join(dir,'response-trace.json'),trace);put(join(out,'metrics.json'),metrics);geometry.set(id,native);
 // Do not turn a failed bar into an unlabelled preview success; preserve values before refusing.
 check(delta===0,'NATIVE_OWN_PARITY '+id+' '+delta);if(setupDelta>P.bars.setupDeltaWorldUnits){setupFailures.push(id);if(!diagnosticSetup)throw Error('SETUP_DRIFT '+id+' '+setupDelta);console.log('DIAGNOSTIC_SETUP_FAIL',id,setupDelta);}check(supportDelta<=P.bars.supportDeltaWorldUnits,'SUPPORT_DRIFT '+id+' '+supportDelta);check(foldCount===0,'FOLDS '+id+' '+foldCount);
}
// Compare signed center first rebound and recovery to the frozen original, not a slower preset.
const goalRows:unknown[]=[];let goalsPassed=true;
for(const kind of selectedCases.filter(k=>k==='impulse'))for(const h of P.helpers){
 const series=(name:string)=>{const g=geometry.get(kind+'-'+name)!;const center=bindBone.get(h.bone)!;const ids=responseIds.filter(i=>attachment(base).weights[i].some(w=>w.bone===h.bone&&w.weight>0));const vertex=ids.reduce((a:number,i:number)=>Math.hypot(world[2*i]-center.worldX,world[2*i+1]-center.worldY)<Math.hypot(world[2*a]-center.worldX,world[2*a+1]-center.worldY)?i:a,ids[0]);const init=relative(g.frames[0]);return {vertex,values:g.frames.map(f=>({time:f.time,dy:relative(f)[2*vertex+1]-init[2*vertex+1]}))};};
 const ls=series('light'),hs=series('heavy');const measured=(values:{time:number;dy:number}[],threshold:number)=>{const extrema=values.filter((v,i)=>i>0&&i<values.length-1&&v.time>=P.targets.release&&(v.dy-values[i-1].dy)*(values[i+1].dy-v.dy)<0&&Math.abs(v.dy)>.05);const settle=values.find((v,i)=>v.time>=P.targets.release&&values.slice(i).every(q=>Math.abs(q.dy)<=threshold))?.time??null;return{first:extrema[0],next:extrema[1],settle,threshold};};
 const frozen=P.targets[h.side],threshold=.05*frozen.peak;const light=measured(ls.values,threshold),heavy=measured(hs.values,threshold);check(light.first&&light.next&&heavy.first&&heavy.next,'MEASURED_REBOUND '+h.side);
 check(Math.abs(light.first.dy-frozen.firstRebound)<1e-9&&Math.abs(light.first.time-frozen.firstAt)<1e-9&&Math.abs(light.next.time-frozen.nextAt)<1e-9&&Math.abs(light.settle!-frozen.settle)<1e-9,'ORIGINAL_BASELINE_REPRODUCED '+h.side);
 const ratio=Math.abs(heavy.first.dy/light.first.dy),nextRatio=Math.abs(heavy.next.dy/light.next.dy),signsPreserved=heavy.first.dy*light.first.dy>0&&heavy.next.dy*light.next.dy>0,firstTiming=Math.abs(heavy.first.time-light.first.time),halfCycleDelta=Math.abs((heavy.next.time-heavy.first.time)-(light.next.time-light.first.time));const passed=signsPreserved&&nextRatio>1&&ratio>=P.targets.firstReboundRatio[0]&&ratio<=P.targets.firstReboundRatio[1]&&firstTiming<=P.targets.timingFrames/P.timing.fps+1e-12&&halfCycleDelta<=P.targets.timingFrames/P.timing.fps+1e-12&&heavy.settle!==null&&heavy.settle<=light.settle!+P.targets.recoveryExtraSeconds+1e-12;
 goalsPassed&&=passed;goalRows.push({side:h.side,vertex:ls.vertex,light,heavy,ratio,nextRatio,signsPreserved,firstTiming,halfCycleDelta,passed});
}put(join(out,'rebound-goals.json'),{goalsPassed,rows:goalRows,userVisualVerdict:'not inferred from these targets'});
// The movie runs at actual 60Hz; only the 0.4–2.0s editorial excerpt is repeated.
const ffmpeg=Bun.which('ffmpeg');check(ffmpeg,'FFMPEG_REQUIRED_FOR_USER_PREVIEW');
if(selectedCases.includes('impulse')&&selectedVariants.includes('light')&&selectedVariants.includes('heavy')){
 const names=['light','heavy'];for(const n of names)await render(join(out,'impulse-'+n),'spine',P.timing.fps,P.render.max,P.render.closeViewport,'spine-close');
 const frameDirs=names.map(n=>join(out,'impulse-'+n,'spine-close','challenge@60fps'));check(hash(join(frameDirs[0],'f0000.png'))===hash(join(frameDirs[1],'f0000.png')),'INITIAL_NATIVE_FRAME_EXACT');
 const font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';check(existsSync(font),'PREVIEW_FONT');const common='fontfile='+font+':fontcolor=white:box=1:boxcolor=black@0.7';
 const labels=names.map((n,i)=>`drawtext=${common}:text='${n==='light'?'light - original':'heavy - original inertia x1.35'}':fontsize=30:x=${16+800*i}:y=16`);
 labels.push(`drawtext=${common}:text='t %{pts\\:flt}s | impulse dt %{pts\\:flt\\:-0.5}s':fontsize=24:x=16:y=h-42`);
 const inputs=frameDirs.flatMap(d=>['-framerate',String(P.timing.fps),'-i',join(d,'f%04d.png')]);
 await run('original8-video',[ffmpeg!,'-y','-threads','4',...inputs,'-filter_complex','[0:v][1:v]hstack=inputs=2,'+labels.join(',')+'[v]','-map','[v]','-c:v','libx264','-threads','4','-pix_fmt','yuv420p',join(out,'light-heavy-original8s.mp4')]);
 const excerpt=`[0:v]trim=start=${P.preview.segment[0]}:end=${P.preview.segment[1]},setpts=PTS-STARTPTS,split=3[a][b][c];[a][b][c]concat=n=3:v=1:a=0,drawtext=${common}:text='3 editorial repeats - actual speed - not a physics loop':fontsize=22:x=16:y=h-76[v]`;
 await run('repeated-preview',[ffmpeg!,'-y','-threads','4','-i',join(out,'light-heavy-original8s.mp4'),'-filter_complex',excerpt,'-map','[v]','-c:v','libx264','-threads','4','-pix_fmt','yuv420p',join(out,'light-heavy-rebound-3repeats.mp4')]);
 const times=[0,.65,.8833333333333333,1.1,1.5];const files=names.flatMap((_,row)=>times.map((t,col)=>({row,col,path:join(frameDirs[row],'f'+Math.round(t*P.timing.fps).toString().padStart(4,'0')+'.png')})));for(const f of files)check(existsSync(f.path),'CONTACT_FRAME '+f.path);
 const rows=names.map((_,r)=>files.filter(f=>f.row===r).map((f,c)=>`[${r*times.length+c}:v]`).join('')+`hstack=inputs=${times.length}[r${r}]`).join(';');
 await run('rebound-contact',[ffmpeg!,'-y','-threads','4',...files.flatMap(f=>['-i',f.path]),'-filter_complex',rows+';[r0][r1]vstack=inputs=2[v]','-map','[v]','-frames:v','1',join(out,'light-heavy-rebound-contact.png')]);
 await run('clock-check',[ffmpeg!,'-y','-ss','0.35','-i',join(out,'light-heavy-rebound-3repeats.mp4'),'-frames:v','1',join(out,'preview-clock-check-075.png')]);
 put(join(out,'preview-manifest.json'),{rows:names,columnsSeconds:times,images:files,initialFrameHash:hash(join(frameDirs[0],'f0000.png')),segment:P.preview.segment,editorialRepeats:3,speed:1,note:P.preview.note});
}
put(join(out,'complete.json'),{status:setupFailures.length?'diagnostic-setup-failed':goalsPassed?'quantitative-targets-passed':'physical-targets-failed',setupFailures,goalsPassed,selectedCases,selectedVariants,metrics,protocolHash:hash(protocolPath),probeHash:hash(import.meta.path),note:'Original is exact light; user visual verdict remains required. No browser/publication/editor claim.'});console.log('ROA_REBOUND_COMPLETE',out);
