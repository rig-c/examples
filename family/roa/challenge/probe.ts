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
const selectedVariants = arg('variants','before,after-light,after-heavy,mode-none').split(',');
const protocolPath = join(import.meta.dir, 'protocol.json');
const P = JSON.parse(readFileSync(protocolPath,'utf8'));
if(selectedCases.some(x=>!P.cases.includes(x))||selectedVariants.some(x=>!P.variants.includes(x))||selectedVariants[0]!=='before')throw Error('DECLARED_SELECTION_REQUIRED');
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
 m.animations.challenge={duration:seconds,loop:false,note:'Deterministic Roa-only '+kind+'; no random input; analytic mound is not measured depth.',tracks};return m;
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
function helpers():Rig{
 const r=clone(base);r.constraints=r.constraints.filter(c=>!['boob_r_phys','boob_l_phys'].includes(String(c.name)));
 for(const h of P.helpers){const b=base.bones.find(b=>b.name===h.bone)!;r.bones.push({name:h.helper,parent:b.parent,x:b.x,y:(b.y??0)+(h.anchorOffsetY??0),rotation:P.driver.rotation,length:h.length});const old=base.constraints.find(c=>c.bone===h.bone)!;r.constraints.push({type:'physics',name:h.helper+'_phys',bone:h.helper,scaleX:1,scaleY:'volume',inertia:old.inertia,strength:old.strength,damping:old.damping,mass:old.mass,wind:old.wind,gravity:old.gravity,mix:1});}return r;
}
// A normal gated, unweighted helper build supplies the official setup bind matrices.
const prep=await build('bind-setup',helpers(),motion('rest',.1));const bind=await render(prep,'spine',1,32);
const bindBone=new Map(bind.setup.bones.map(b=>[b.name,b]));const world=bind.rest.find(a=>a.slot==='topwear')!.vertices;
const local=(b:Matrix,x:number,y:number)=>{const dx=x-b.worldX,dy=y-b.worldY,det=b.a*b.d-b.b*b.c;check(Math.abs(det)>0,'NONCOLLAPSED_BIND');return [(b.d*dx-b.b*dy)/det,(-b.c*dx+b.a*dy)/det];};
function variant(name:string):Rig{
 if(name==='before')return clone(base);
 if(name==='noop-rebind'){const r=clone(base);attachment(r).weights=attachment(r).weights.map((row,i)=>{if(!row.some(w=>P.helpers.some((h:{bone:string})=>h.bone===w.bone)&&w.weight>0))return row;const sum=row.reduce((s,v)=>s+v.weight,0);return row.map(v=>{const q=local(bindBone.get(v.bone)!,world[2*i]/sum,world[2*i+1]/sum);return {...v,x:q[0],y:q[1]};});});return r;}
 const r=helpers();
 if(name==='after-heavy')for(const c of r.constraints)if(String(c.name).startsWith('roa_tension_')){c.mass=Number(c.mass)*P.driver.heavy.massMultiplier;c.strength=Number(c.strength)*P.driver.heavy.strengthMultiplier;c.inertia=P.driver.heavy.inertia;c.damping=P.driver.heavy.damping;}
 if(name==='mode-none')for(const c of r.constraints)if(String(c.name).startsWith('roa_tension_'))c.scaleY='none';
 const a=attachment(r);
 a.weights=a.weights.map((row,i)=>{
  const h=P.helpers.find((h:{bone:string})=>row.some(w=>w.bone===h.bone&&w.weight>0));if(!h)return row;
  const old=row.find(w=>w.bone===h.bone)!;const helper=bindBone.get(h.helper)!;const x=world[i*2],y=world[i*2+1];
  const center=bindBone.get(h.bone)!;const dist=Math.hypot(x-center.worldX,y-center.worldY);
  const w=name==='driver'?old.weight:.5*(1+Math.cos(Math.PI*Math.min(dist/h.reach,1)));
  const rest=row.filter(v=>v.bone!==h.bone);const sum=rest.reduce((s,v)=>s+v.weight,0);
  const supports=sum>0?rest.map(v=>({...v,weight:v.weight/sum*(1-w)})):[{bone:'chest',x:0,y:0,weight:1-w}];
  const weights=[...supports,{bone:h.helper,x:0,y:0,weight:w}].filter(v=>v.weight>0);
  return weights.map(v=>{const q=local(bindBone.get(v.bone)!,x,y);return {...v,x:q[0],y:q[1]};});
 });
 check(JSON.stringify(a.uvs)===JSON.stringify(attachment(base).uvs)&&JSON.stringify(a.triangles)===JSON.stringify(attachment(base).triangles),'TOPOLOGY_UV_PRESERVED');return r;
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
 const driverTrace=native.frames.map(f=>({time:f.time,bones:P.helpers.map((h:{helper:string;bone:string})=>{const b=f.bones.find(b=>b.name===(name==='before'||name==='noop-rebind'?h.bone:h.helper))!;const ch=f.bones.find(b=>b.name==='chest')!;const det=ch.a*ch.d-ch.b*ch.c;const ax=(ch.d*b.a-ch.b*b.c)/det,ay=(-ch.c*b.a+ch.a*b.c)/det,bx=(ch.d*b.b-ch.b*b.d)/det,by=(-ch.c*b.b+ch.a*b.d)/det;return {bone:b.name,localOrigin:local(ch,b.worldX,b.worldY),axisXLength:Math.hypot(ax,ay),axisYLength:Math.hypot(bx,by),localDeterminant:ax*by-ay*bx};})}));put(join(dir,'driver-matrix-trace.json'),{note:'Effective helper local axis lengths, not a claim to native internal scaleOffset field',frames:driverTrace});
 const ref=name==='before'?native:geometry.get(kind+'-before')!;let supportDelta=0,hullDelta=0;for(let i=0;i<native.frames.length;i++){const a=relative(native.frames[i]),b=relative(ref.frames[i]);hullDelta=Math.max(hullDelta,maxDiff(a.slice(0,208),b.slice(0,208)));for(const v of supportIds)supportDelta=Math.max(supportDelta,Math.abs(a[2*v]-b[2*v]),Math.abs(a[2*v+1]-b[2*v+1]));}
 metrics[id]={nativeOwnMaxDelta:delta,setupDelta,supportDelta,supportVertices:supportIds.length,hullDelta,foldCount,peak,peakAt,settle,settleThreshold,frames:native.frames.length};put(join(dir,'response-trace.json'),trace);put(join(out,'metrics.json'),metrics);geometry.set(id,native);
 // Do not turn a failed bar into an unlabelled preview success; preserve values before refusing.
 check(delta===0,'NATIVE_OWN_PARITY '+id+' '+delta);if(setupDelta>P.bars.setupDeltaWorldUnits){setupFailures.push(id);if(!diagnosticSetup)throw Error('SETUP_DRIFT '+id+' '+setupDelta);console.log('DIAGNOSTIC_SETUP_FAIL',id,setupDelta);}check(supportDelta<=P.bars.supportDeltaWorldUnits,'SUPPORT_DRIFT '+id+' '+supportDelta);check(foldCount===0,'FOLDS '+id+' '+foldCount);
}
for(const kind of selectedCases.filter(x=>x!=='rest')){
 if(!selectedVariants.includes('mode-none')||!selectedVariants.includes('after-light'))continue;
 const a=geometry.get(kind+'-after-light')!,n=geometry.get(kind+'-mode-none')!;const delta=Math.max(...a.frames.map((f,i)=>maxDiff(top(f),top(n.frames[i]))));put(join(out,kind+'-mode-control.json'),{volumeNoneDifference:delta});check(delta>P.bars.responsePresentAboveWorldUnits,'MODE_NEGATIVE_NOT_OBSERVED '+kind);
}
// Compose only exact renderer frame names; no contact/setup PNGs enter the video.
const ffmpeg=Bun.which('ffmpeg');
const names=['before','after-light','after-heavy'];
if(ffmpeg && selectedCases.includes('impulse') && names.every(n=>selectedVariants.includes(n))){
 for(const n of names)await render(join(out,'impulse-'+n),'spine',P.timing.fps,P.render.max,P.render.closeViewport,'spine-close');
 const frameDirs=names.map(n=>join(out,'impulse-'+n,'spine-close','challenge@60fps'));
 for(const d of frameDirs)check(existsSync(join(d,'f0000.png')),'RENDER_FRAME_CONVENTION '+d);
 const inputs=frameDirs.flatMap(d=>['-framerate',String(P.timing.fps),'-i',join(d,'f%04d.png')]);
 await run('comparison-video',[ffmpeg,'-y','-threads','4',...inputs,'-filter_complex','[0:v][1:v][2:v]hstack=inputs=3[v]','-map','[v]','-c:v','libx264','-threads','4','-pix_fmt','yuv420p',join(out,'before-light-heavy.mp4')]);
 const times=[0,.55,.75,1,2,7.9];
 const files=names.flatMap((n,row)=>times.map((t,col)=>({row,col,path:join(frameDirs[row],'f'+Math.round(t*P.timing.fps).toString().padStart(4,'0')+'.png')})));
 for(const f of files)check(existsSync(f.path),'CONTACT_FRAME '+f.path);
 const rows=names.map((_,r)=>files.filter(f=>f.row===r).map((f,c)=>`[${r*times.length+c}:v]`).join('')+`hstack=inputs=${times.length}[r${r}]`).join(';');
 await run('comparison-contact',[ffmpeg,'-y','-threads','4',...files.flatMap(f=>['-i',f.path]),'-filter_complex',rows+';[r0][r1][r2]vstack=inputs=3[v]','-map','[v]','-frames:v','1',join(out,'before-light-heavy-contact.png')]);
 put(join(out,'preview-manifest.json'),{rows:names,columnsSeconds:times,images:files,video:'before-light-heavy.mp4',contact:'before-light-heavy-contact.png'});
}else put(join(out,'video-status.json'),{status:'unavailable',ffmpeg:ffmpeg??null});
put(join(out,'complete.json'),{status:setupFailures.length?'diagnostic-setup-failed':'geometry-bars-passed',setupFailures,selectedCases,selectedVariants,metrics,protocolHash:hash(protocolPath),probeHash:hash(import.meta.path),note:'Offline native/own proof; visual quality awaits root review. No browser or publication.'});console.log('ROA_EXPERIMENT_COMPLETE',out);
