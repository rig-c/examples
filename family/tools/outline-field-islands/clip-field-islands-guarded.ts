/**
 * RETIRED post-pass script (rig-c/parts-examples#69).
 * Luna (hair_front), Nova (hair_back, hair_front), and Jinni (earring, hair_front)
 * now declare meshes.<part>.explicit / meshes.<part>.explicit.islands directly in
 * their config.json on @rig-c/parts 1.63.0, so `rig-parts rig` emits all single-attachment
 * and multi-island slots in place. No character uses this post-pass script anymore.
 */
import{readFileSync,writeFileSync,mkdirSync,existsSync}from'node:fs';import{dirname,resolve}from'node:path';import{fileURLToPath}from'node:url';import{createHash}from'node:crypto';
import{proveClip}from'./clip-field-coverage.ts';
import polyclip from'polygon-clipping';import{traceAlphaOutline,simplifyClosedPolygon,offsetPolygon,findSelfIntersection,earClip,traceOutline}from'rig-c/mesh';import{readPng}from'@rig-c/parts/src/raster/png.ts';
const args=process.argv.slice(2);function arg(k:string){const i=args.indexOf('--'+k);if(i<0||!args[i+1])throw Error('ARG_REQUIRED '+k);return args[i+1];}
const input=arg('input'),output=arg('output'),parts=arg('parts').split(','),images=arg('images');const rig=JSON.parse(readFileSync(input,'utf8')),records=[];const motion=JSON.parse(readFileSync(arg('motion'),'utf8'));
const canonical=(x:unknown):string=>Array.isArray(x)?'['+x.map(canonical).join(',')+']':x!==null&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical((x as Record<string,unknown>)[k])).join(',')+'}':JSON.stringify(x);
const sha=(x:string|Uint8Array)=>createHash('sha256').update(x).digest('hex');
const policy=JSON.parse(readFileSync(arg('policy'),'utf8'));
if(policy.spec!=='outline-field-islands/1'||JSON.stringify(policy.parts)!==JSON.stringify(parts))throw Error('CLIP_POLICY_PARTS_REQUIRED');
if(resolve(input)===resolve(output))throw Error('CLIP_OUTPUT_MUST_DIFFER_FROM_INPUT');
if(resolve(dirname(input))===resolve(dirname(output)))throw Error('CLIP_OUTPUT_DIRECTORY_MUST_DIFFER_FROM_SOURCE');
for(const path of [output,output+'.provenance.json',dirname(output)+'/mesh_report.json'])if(existsSync(path))throw Error('CLIP_OUTPUT_EXISTS '+path);
if(sha(canonical(rig))!==policy.sourceRigSHA256)throw Error('CLIP_SOURCE_RIG_CHANGED');
if(sha(canonical(motion))!==policy.motionSHA256)throw Error('CLIP_SOURCE_MOTION_CHANGED');
for(const part of parts)if(sha(readFileSync(`${images}/${part}.png`))!==policy.imageSHA256[part])throw Error('CLIP_SOURCE_IMAGE_CHANGED '+part);
for(const [entry,name,version]of [['rig-c/mesh','rig-c','2.57.0'],['@rig-c/parts/src/raster/png.ts','@rig-c/parts','1.25.0'],['polygon-clipping','polygon-clipping','0.15.7']]){let at=dirname(fileURLToPath(import.meta.resolve(entry))),found=false;while(at!==dirname(at)){const p=at+'/package.json';if(existsSync(p)){const d=JSON.parse(readFileSync(p,'utf8'));if(d.name===name){if(d.version!==version)throw Error('CLIP_PACKAGE_PIN_CHANGED '+name);found=true;break;}}at=dirname(at);}if(!found)throw Error('CLIP_PACKAGE_IDENTITY_MISSING '+name);}

for(const part of parts){
 if(Object.keys(rig.skins).length!==1||!rig.skins.default||Object.keys(rig.skins.default[part]??{}).join(',')!==part)throw Error('CLIP_SINGLE_DEFAULT_ATTACHMENT_REQUIRED '+part);
 for(const skin of Object.values(rig.skins)as Record<string,Record<string,{type:string,source?:string,parent?:string}>>[])for(const attachments of Object.values(skin))for(const a of Object.values(attachments))if(a.type==='linkedmesh')throw Error('CLIP_LINKED_MESH_UNSUPPORTED '+part);
 if(motion.setup?.[part]!==undefined)throw Error('CLIP_SLOT_SETUP_UNSUPPORTED '+part);
 for(const [name,anim]of Object.entries(motion.animations??{})as [string,Record<string,unknown[]>][]){
  if(anim.drawOrder?.length)throw Error('CLIP_DRAW_ORDER_UNSUPPORTED '+name);
  for(const family of ['deform','sequence','tracks'])for(const t of anim[family]??[])if((t as {slot?:string}).slot===part)throw Error('CLIP_TARGET_TIMELINE_UNSUPPORTED '+family+' '+part);
 }
 const slot=rig.slots.find((x:{name:string})=>x.name===part);if(!slot||slot.attachment!==part)throw Error('CLIP_SETUP_ATTACHMENT_REQUIRED '+part);
}

type Pt=[number,number];type Binding={bone:string,x:number,y:number,weight:number};
const area=(a:Pt,b:Pt,c:Pt)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
for(const part of parts){const a=rig.skins.default[part][part];if(a.type!=='mesh')throw Error('CLIP_WEIGHTED_MESH_REQUIRED '+part);if(a.image!==part+'.png')throw Error('CLIP_IMAGE_IDENTITY_REQUIRED '+part);if(a.sequence!==undefined)throw Error('CLIP_ATTACHMENT_SEQUENCE_UNSUPPORTED '+part);const png=readPng(`${images}/${part}.png`),w=png.width,h=png.height;if(!a.weights||a.width!==w||a.height!==h)throw Error('WEIGHTED_IMAGE_REQUIRED '+part);
 const alpha=new Uint8Array(w*h);let sourceArt=0;for(let y=0;y<h;y++)for(let x=0;x<w;x++)if(png.data[(y*w+x)*4+3]>=1){sourceArt++;for(let dy=-4;dy<=4;dy++)for(let dx=-4;dx<=4;dx++){const xx=x+dx,yy=y+dy;if(xx>=0&&yy>=0&&xx<w&&yy<h)alpha[yy*w+xx]=255;}}
 // Close only ambiguous corners in the derived dilation mask. Source RGBA is untouched.
 let pinchAdded=0,again=true;while(again){again=false;for(let y=1;y<h;y++)for(let x=1;x<w;x++){const tl=(y-1)*w+x-1,tr=tl+1,bl=y*w+x-1,br=bl+1;if(alpha[tl]&&alpha[br]&&!alpha[tr]&&!alpha[bl]){alpha[tr]=255;pinchAdded++;again=true;}else if(alpha[tr]&&alpha[bl]&&!alpha[tl]&&!alpha[br]){alpha[tl]=255;pinchAdded++;again=true;}}}
 const seen=new Uint8Array(w*h),components:{mask:Uint8Array,pixels:number,first:number}[]=[];
 for(let first=0;first<w*h;first++)if(alpha[first]&&!seen[first]){const mask=new Uint8Array(w*h),queue=[first];seen[first]=1;for(let i=0;i<queue.length;i++){const k=queue[i];mask[k]=255;const x=k%w,y=Math.floor(k/w);for(const j of [x>0?k-1:-1,x+1<w?k+1:-1,y>0?k-w:-1,y+1<h?k+w:-1])if(j>=0&&alpha[j]&&!seen[j]){seen[j]=1;queue.push(j);}}components.push({mask,pixels:queue.length,first});}
 components.sort((a,b)=>b.pixels-a.pixels||a.first-b.first);if(components.length>8)throw Error('CLIP_COMPONENT_LIMIT '+part);
 const pieceResults:typeof a[]=[];const originalSlot=rig.slots.find((x:{name:string})=>x.name===part),originalIndex=rig.slots.indexOf(originalSlot);const splitSlots:string[]=[];
 for(const [pieceIndex,component]of components.entries()){
 const pieceName=pieceIndex===0?part:part+'__island'+(pieceIndex+1);if(pieceIndex&&rig.slots.some((x:{name:string})=>x.name===pieceName))throw Error('CLIP_SPLIT_NAME_COLLISION '+pieceName);
 const traced=traceAlphaOutline({width:w,height:h,alpha:component.mask},1);if(traced.artPixels!==traced.islandPixels)throw Error('CLIP_COMPONENT_TRACE_LOSS '+pieceName);
 const outline=simplifyClosedPolygon(traced.outline,3).map(([x,y])=>[Math.max(0,Math.min(w,x)),Math.max(0,Math.min(h,y))]as Pt);if(findSelfIntersection(outline))throw Error('CLIP_OUTLINE_SELF_INTERSECTION '+part);
 const points:Pt[]=[],weights:Binding[][]=[],origins:{triangle:number,coefficients:number[]}[]=[],triangles:number[]=[],indices=new Map<string,number>();
 const uv:Pt[]=Array.from({length:a.uvs.length/2},(_,i)=>[a.uvs[2*i]*w,a.uvs[2*i+1]*h]);
 function vertex(p:Pt,ids:number[],ti:number){p=p.map(v=>Math.round(v*1e9)/1e9)as Pt;const key=p.join(',');const prior=indices.get(key);if(prior!==undefined)return prior;const[aa,bb,cc]=ids.map(i=>uv[i]);const det=area(aa,bb,cc);const b1=area(p,bb,cc)/det,b2=area(aa,p,cc)/det,b3=1-b1-b2;let bs=[b1,b2,b3];if(Math.min(...bs)<-1e-6)throw Error('CLIP_VERTEX_OUTSIDE_SOURCE_TRIANGLE');bs=bs.map(v=>Math.max(0,Math.min(1,v)));const sum=bs.reduce((a,b)=>a+b,0);bs=bs.map(v=>v/sum);
 const named=new Map<string,{weight:number,x:number,y:number}>();ids.forEach((id,j)=>{for(const b of a.weights[id]as Binding[]){const share=b.weight*bs[j],m=named.get(b.bone)??{weight:0,x:0,y:0};m.weight+=share;m.x+=share*b.x;m.y+=share*b.y;named.set(b.bone,m);}});const ws=[...named].filter(([,b])=>b.weight>1e-14).map(([bone,b])=>({bone,x:b.x/b.weight,y:b.y/b.weight,weight:b.weight}));
 const at=points.length;indices.set(key,at);points.push(p);weights.push(ws);origins.push({triangle:ti,coefficients:bs});return at;}
 for(let t=0;t<a.triangles.length;t+=3){const ids=a.triangles.slice(t,t+3),original=ids.map((i:number)=>uv[i]);const clipped=polyclip.intersection([original],[outline]);for(const polygon of clipped){if(polygon.length!==1)throw Error('CLIP_INTERSECTION_HOLE '+part);let ring=polygon[0].slice(0,-1)as Pt[];ring=ring.filter((p,i)=>i===0||Math.hypot(p[0]-ring[i-1][0],p[1]-ring[i-1][1])>1e-9);if(ring.length<3)continue;const local=earClip(ring);for(let k=0;k<local.length;k+=3){const ps=local.slice(k,k+3).map(i=>ring[i]);if(Math.abs(area(ps[0],ps[1],ps[2]))<1e-8)continue;const out=ps.map(p=>vertex(p,ids,t/3));if(area(ps[0],ps[1],ps[2])*area(original[0],original[1],original[2])<0)[out[1],out[2]]=[out[2],out[1]];triangles.push(...out);}}}
 const used=[...new Set(triangles)].sort((a,b)=>a-b),compact=new Map(used.map((v,i)=>[v,i]));const oldPoints=used.map(i=>points[i]),oldWeights=used.map(i=>weights[i]),oldOrigins=used.map(i=>origins[i]),ts=triangles.map(i=>compact.get(i)!);const border=traceOutline(used.length,ts),walk=border.walk;const order=[...walk,...used.map((_,i)=>i).filter(i=>!walk.includes(i))],remap=new Map(order.map((v,i)=>[v,i]));
 const sourceVertices=a.uvs.length/2,sourceTriangles=a.triangles.length/3;const result={...a,uvs:order.flatMap(i=>[oldPoints[i][0]/w,oldPoints[i][1]/h]),weights:order.map(i=>oldWeights[i]),triangles:ts.map(i=>remap.get(i)!),hull:border.hull};pieceResults.push(result);if(pieceIndex===0){rig.skins.default[part][part]=result;}else{result.path=a.path??part;rig.skins.default[pieceName]={[pieceName]:result};rig.slots.splice(originalIndex+pieceIndex,0,{...originalSlot,name:pieceName,attachment:pieceName});}splitSlots.push(pieceName);
 records.push({part,pieceName,pieceIndex,componentPixels:component.pixels,derivedMaskPinchPixelsAdded:pinchAdded,components:components.length,sourceImage:a.image,sourcePath:a.path??part,method:'Author-input silhouette clip of original triangle cells; weighted local coordinate contributions barycentrically interpolated by bone; no distance-weight solve, no physics change.',sourceVertices,sourceTriangles,vertices:order.length,triangles:ts.length/3,hull:border.hull,sourceAlphaGt0:sourceArt,silhouette:{alphaThreshold:1,dilationChebyshevPixels:4,tolerance:3,margin:0,traceIslands:traced.islands,outlineVertices:outline.length},originTriangles:order.map(i=>oldOrigins[i])});
 console.log('CLIPPED',pieceName,sourceVertices,sourceTriangles,'->',order.length,ts.length/3);}
 const proof=proveClip(a,pieceResults,png.data,w,h);for(const record of records.filter(r=>r.part===part))record.proof=proof;
 const actual=rig.slots.slice(originalIndex,originalIndex+components.length).map((x:{name:string})=>x.name);if(JSON.stringify(actual)!==JSON.stringify(splitSlots))throw Error('CLIP_CONTIGUOUS_DRAW_ORDER_REQUIRED '+part);}
const meshReportPath=dirname(input)+'/mesh_report.json';if(!existsSync(meshReportPath))throw Error('CLIP_SOURCE_MESH_REPORT_REQUIRED');const meshReport=JSON.parse(readFileSync(meshReportPath,'utf8'));for(const part of parts){const index=meshReport.findIndex((r:{part:string})=>r.part===part);if(index<0)throw Error('CLIP_SOURCE_PART_REPORT_REQUIRED '+part);const rows=records.filter(r=>r.part===part),sourceGenerator=meshReport[index];meshReport[index]={part,vertices:rows.reduce((n,r)=>n+r.vertices,0),triangles:rows.reduce((n,r)=>n+r.triangles,0),hull:rows.reduce((n,r)=>n+r.hull,0),mode:'authored-field-clip',sourceGenerator,pieces:rows.map(r=>({slot:r.pieceName,vertices:r.vertices,triangles:r.triangles,hull:r.hull,sourceImage:r.sourceImage,sourcePath:r.sourcePath})),proof:rows[0].proof,params:{alphaThreshold:1,dilationChebyshevPixels:4,tolerance:3,derivedMaskPinchPixelsAdded:rows[0].derivedMaskPinchPixelsAdded}};}
mkdirSync(dirname(output),{recursive:true});writeFileSync(dirname(output)+'/mesh_report.json',JSON.stringify(meshReport,null,2)+'\n');writeFileSync(output,JSON.stringify(rig,null,2)+'\n');writeFileSync(output+'.provenance.json',JSON.stringify(records,null,2)+'\n');
