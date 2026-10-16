/** Consumer authoring step. Produces a rig spec; official build/check remain mandatory. */
import {readFileSync,writeFileSync,cpSync,existsSync,mkdirSync} from 'node:fs';
import {resolve,relative,join} from 'node:path';
import {createHash} from 'node:crypto';
import {reduceMesh,measureAuthoredMeshFit,rasteriseTriangles} from 'rig-c/mesh';
import {readPng} from '@rig-c/parts/src/raster/png.ts';

const EXPECTED_SOURCE='25ce5798f3f1a66362176a5c4ff7d8d83e6a3910938d948892e8d28c999de9da';
function object(v:unknown,label:string):Record<string,unknown>{
 if(!v||typeof v!=='object'||Array.isArray(v))throw Error(`${label}: object required`);
 return v as Record<string,unknown>;
}
function numbers(v:unknown,label:string):number[]{
 if(!Array.isArray(v)||v.some(n=>typeof n!=='number'||!Number.isFinite(n)))throw Error(`${label}: finite number list required`);
 return v as number[];
}
function canonical(v:unknown):unknown{
 if(Array.isArray(v))return v.map(canonical);
 if(v&&typeof v==='object'){const o=object(v,'canonical');return Object.fromEntries(Object.keys(o).sort().map(k=>[k,canonical(o[k])]));}
 return v;
}
const digest=(v:unknown)=>createHash('sha256').update(JSON.stringify(canonical(v))).digest('hex');
const textDigest=(v:string|Uint8Array)=>createHash('sha256').update(v).digest('hex');
type Binding={bone:string;x:number;y:number;weight:number};
function weights(v:unknown):Binding[][]{
 if(!Array.isArray(v))throw Error('NOVA_REDUCE_WEIGHTS_REQUIRED');
 return v.map((row,i)=>{if(!Array.isArray(row)||!row.length)throw Error(`weights[${i}] required`);return row.map((raw,j)=>{
  const b=object(raw,`weights[${i}][${j}]`);
  if(typeof b.bone!=='string'||['x','y','weight'].some(k=>typeof b[k]!=='number'||!Number.isFinite(b[k])))throw Error(`weights[${i}][${j}] by-name finite binding required`);
  return {bone:b.bone,x:b.x as number,y:b.y as number,weight:b.weight as number};
 });});
}

/** Frozen Nova trousers only; no claim for other rigs or later deformation fields. */
export function reduceNovaRigidInterior(rigValue:unknown,motionValue:unknown,png:{width:number;height:number;data:Uint8Array}){
 const rig=object(rigValue,'rig'),skins=object(rig.skins,'skins'),skin=object(skins.default,'default'),slot=object(skin.bottomwear,'bottomwear'),a=object(slot.bottomwear,'bottomwear attachment');
 if(digest(a)!==EXPECTED_SOURCE)throw Error(`NOVA_REDUCTION_SOURCE_CHANGED: ${digest(a)}; remeasure this attachment before using the frozen recipe`);
 const motion=object(motionValue,'motion'),animations=object(motion.animations,'animations');
 for(const [skinName,rawSkin] of Object.entries(skins)){
  const entry=object(rawSkin,`skin ${skinName}`),attachments=entry.attachments===undefined?entry:object(entry.attachments,'skin attachments');
  for(const rawSlot of Object.values(attachments))for(const rawAttachment of Object.values(object(rawSlot,'slot'))){
   const linked=object(rawAttachment,'attachment');
   if(linked.type==='linkedmesh'&&linked.parent==='bottomwear')throw Error('NOVA_REDUCTION_LINKED_MESH_UNSUPPORTED: remap inherited topology first');
  }
 }
 for(const [name,raw] of Object.entries(animations)){
  const animation=object(raw,`animation ${name}`);
  if(Array.isArray(animation.deform)&&animation.deform.some(d=>object(d,'deform').slot==='bottomwear'))throw Error('NOVA_REDUCTION_DEFORM_UNSUPPORTED: bottomwear deform timeline needs remapping');
 }
 const {width:w,height:h}=png,uvs=numbers(a.uvs,'uvs'),triangles=numbers(a.triangles,'triangles'),bindings=weights(a.weights),hull=a.hull;
 if(a.type!=='mesh'||typeof hull!=='number'||a.width!==w||a.height!==h||bindings.length!==uvs.length/2)throw Error('NOVA_REDUCTION_SOURCE_SHAPE');
 const points:Array<[number,number]>=bindings.map((_,i)=>[uvs[2*i]*w,uvs[2*i+1]*h]);
 const mask={width:w,height:h,alpha:Uint8Array.from({length:w*h},(_,i)=>png.data[i*4+3])};
 const active=new Set(bindings.flatMap((v,i)=>v.some(b=>b.bone!=='hip'&&b.weight>0)?[i]:[]));
 const protectedVertices=new Set<number>(),protectedEdges=new Map<string,[number,number]>(),mixed:number[][]=[];
 for(let i=0;i<triangles.length;i+=3){
  const t=triangles.slice(i,i+3);if(!t.some(v=>active.has(v)))continue;mixed.push(t);t.forEach(v=>protectedVertices.add(v));
  for(const [u,v] of [[t[0],t[1]],[t[1],t[2]],[t[2],t[0]]])protectedEdges.set([u,v].sort((x,y)=>x-y).join(','),[u,v]);
 }
 const fit=measureAuthoredMeshFit(mask,1,points,triangles);
 const bounds={minCoverage:fit.coverage,maxOvershoot:fit.overshoot,maxUndercut:null};
 const boneOrder=(rig.bones as unknown[]).map(b=>{const name=object(b,'bone').name;if(typeof name!=='string')throw Error('bone name required');return name;});
 const result=reduceMesh({attachment:{skin:'default',slot:'bottomwear',attachment:'bottomwear'},art:{mask,threshold:1,frame:{space:'part-local-drawing-px-y-down',width:w,height:h,pageScale:1,conversion:'texels = px * pageScale'}},source:{points,uvs,triangles,hull,weights:bindings.map(v=>v.map(b=>({bone:b.bone,weight:b.weight})))},sourceBounds:bounds,targets:{artFit:bounds,maxBoundaryDeviation:0,regions:[]},protect:{hull:true,vertices:[...protectedVertices].sort((a,b)=>a-b),edges:[...protectedEdges.values()],regionBoundaries:[],weightJump:null,influences:['hip','cuff_r0','cuff_r1','cuff_l0','cuff_l1']},influences:{maxInfluences:4,minWeight:0},boneOrder,preset:null,budget:{maxCandidates:512},minArtSamples:1,regionArtSamples:[],deform:[],linkedMeshes:[]});
 const m=result.mesh;if(!m||m.inserted.length)throw Error('NOVA_REDUCTION_NO_REMOVAL_ONLY_RESULT');
 const inverse=Array.from({length:m.points.length},()=>-1);
 m.indexMap.forEach((v,i)=>{if(v!==null)inverse[v]=i;else if(bindings[i].some(b=>b.bone!=='hip'))throw Error('NOVA_REDUCTION_REMOVED_NONRIGID');});
 if(inverse.some(i=>i<0)||m.points.length!==214||m.triangles.length!==828||m.hull!==hull)throw Error('NOVA_REDUCTION_RESULT_CHANGED: revalidate new reducer output');
 const triangleKey=(ids:number[])=>ids.slice().sort((a,b)=>a-b).join(',');
 const kept=new Set(Array.from({length:m.triangles.length/3},(_,i)=>triangleKey(m.triangles.slice(i*3,i*3+3))));
 if(mixed.some(t=>!kept.has(triangleKey(t.map(i=>m.indexMap[i]!)))))throw Error('NOVA_REDUCTION_MIXED_TRIANGLE_CHANGED');
 if(inverse.some((i,j)=>m.uvs[2*j]!==uvs[2*i]||m.uvs[2*j+1]!==uvs[2*i+1]))throw Error('NOVA_REDUCTION_UV_CHANGED');
 const before=rasteriseTriangles(points,triangles,w,h),after=rasteriseTriangles(m.points,m.triangles,w,h);
 let baselineMissingAlphaPositive=0,candidateMissingAlphaPositive=0,newlyOmittedAlphaPositive=0;
 for(let i=0;i<mask.alpha.length;i++)if(mask.alpha[i]>0){if(!before[i])baselineMissingAlphaPositive++;if(!after[i])candidateMissingAlphaPositive++;if(before[i]&&!after[i])newlyOmittedAlphaPositive++;}
 if(newlyOmittedAlphaPositive!==0)throw Error(`NOVA_REDUCTION_NEW_ALPHA_OMISSIONS: ${newlyOmittedAlphaPositive}`);
 const output=structuredClone(rig),outSkin=object(object(output.skins,'skins').default,'default'),outSlot=object(outSkin.bottomwear,'bottomwear');
 outSlot.bottomwear={...a,uvs:m.uvs,triangles:m.triangles,hull:m.hull,edges:m.edges,weights:inverse.map(i=>structuredClone(bindings[i]))};
 const provenance={spec:'nova-rigid-interior-reduction/1',sourceAttachmentSHA256:EXPECTED_SOURCE,publicAPI:'rig-c/mesh.reduceMesh',pins:{parts:'1.25.0',core:'2.57.0',spine:'4.3.13'},sourceVertices:bindings.length,vertices:m.points.length,sourceTriangles:triangles.length/3,triangles:m.triangles.length/3,hull,activeVertices:active.size,protectedVertices:protectedVertices.size,protectedEdges:protectedEdges.size,mixedTrianglesKeptExact:mixed.length,removedPureHipVertices:m.indexMap.filter(v=>v===null).length,baselineMissingAlphaPositive,candidateMissingAlphaPositive,newlyOmittedAlphaPositive,indexMap:m.indexMap,inverse,sourceFit:fit,scope:'Freeze current hull and every triangle carrying any non-hip binding; only pure hip interior removed. Frozen Nova field only; long rigid slivers are not certified for a later deform timeline.'};
 return {rig:output,report:result.report,provenance};
}

if(import.meta.main){
 const args=process.argv.slice(2),arg=(key:string)=>{const i=args.indexOf(key);if(i<0||!args[i+1])throw Error(`Required ${key}`);return resolve(args[i+1]);};
 const source=arg('--source-rig-dir'),out=arg('--out-rig-dir');
 if(source===out||!relative(source,out).startsWith('..')||existsSync(out))throw Error('NOVA_REDUCTION_OUTPUT_MUST_BE_FRESH_OUTSIDE_SOURCE');
 for(const [pkg,version] of [['@rig-c/parts','1.25.0'],['rig-c','2.57.0'],['@esotericsoftware/spine-core','4.3.13']]){
  const found=JSON.parse(readFileSync(resolve('node_modules',pkg,'package.json'),'utf8')).version;if(found!==version)throw Error(`NOVA_REDUCTION_PIN ${pkg} ${found}, required ${version}`);
 }
 const rigText=readFileSync(join(source,'rig.json'),'utf8'),motionText=readFileSync(join(source,'motion.json'),'utf8'),pngPath=join(source,'images/bottomwear.png');
 const generated=reduceNovaRigidInterior(JSON.parse(rigText),JSON.parse(motionText),readPng(pngPath));
 mkdirSync(out,{recursive:true});cpSync(source,out,{recursive:true});
 writeFileSync(join(out,'rig.json'),JSON.stringify(generated.rig,null,2)+'\n');
 const rows=JSON.parse(readFileSync(join(source,'mesh_report.json'),'utf8')) as Array<Record<string,unknown>>,i=rows.findIndex(x=>x.part==='bottomwear');if(i<0)throw Error('NOVA_REDUCTION_REPORT_MISSING');
 rows[i]={part:'bottomwear',vertices:generated.provenance.vertices,triangles:generated.provenance.triangles,hull:generated.provenance.hull,mode:'public-reduceMesh-rigid-interior',sourceGenerator:rows[i],provenance:'nova-rigid-interior.provenance.json'};
 writeFileSync(join(out,'mesh_report.json'),JSON.stringify(rows,null,2)+'\n');
 writeFileSync(join(out,'nova-rigid-interior.provenance.json'),JSON.stringify({...generated.provenance,sourceRigSHA256:textDigest(rigText),sourceMotionSHA256:textDigest(motionText),sourcePngSHA256:textDigest(readFileSync(pngPath)),emittedArtifacts:'None: this output is an authoring rig spec. Run official public rigc build and rig-parts check before adoption.'},null,2)+'\n');
 writeFileSync(join(out,'nova-rigid-interior.reducer-report.json'),JSON.stringify(generated.report,null,2)+'\n');
 console.log(`NOVA_RIGID_INTERIOR ${generated.provenance.sourceVertices}->${generated.provenance.vertices}v ${generated.provenance.sourceTriangles}->${generated.provenance.triangles}t; new alpha omissions ${generated.provenance.newlyOmittedAlphaPositive}`);
}
