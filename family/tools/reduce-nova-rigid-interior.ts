/** Consumer authoring step. Produces a rig spec; official build/check remain mandatory. */
import {readFileSync,writeFileSync,cpSync,existsSync,mkdirSync} from 'node:fs';
import {resolve,relative,join} from 'node:path';
import {createHash} from 'node:crypto';
import {measureAuthoredMeshFit} from 'rig-c/mesh';
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

type TriangleQuality={minAngle:number;minAngleP10:number;trianglesBelowFiveDegrees:number};
/** The source, in drawing pixels, supplies each acceptance bound. */
function triangleQuality(points:Array<[number,number]>,triangles:number[]):TriangleQuality{
 const angles:number[]=[];
 for(let k=0;k<triangles.length;k+=3){
  const p=triangles.slice(k,k+3).map(i=>points[i]);
  const lengths=p.map((a,i)=>Math.hypot(a[0]-p[(i+1)%3][0],a[1]-p[(i+1)%3][1]));
  if(lengths.some(x=>!(x>0)))throw Error('NOVA_REDUCTION_ZERO_EDGE');
  const a=lengths.map((u,i)=>{const v=lengths[(i+1)%3],opposite=lengths[(i+2)%3];return Math.acos(Math.max(-1,Math.min(1,(u*u+v*v-opposite*opposite)/(2*u*v))))*180/Math.PI;});
  angles.push(Math.min(...a));
 }
 angles.sort((a,b)=>a-b);if(!angles.length)throw Error('NOVA_REDUCTION_NO_TRIANGLES');
 return {minAngle:angles[0],minAngleP10:angles[Math.ceil(angles.length*.1)-1],trianglesBelowFiveDegrees:angles.filter(a=>a<5).length};
}

/**
 * Compatibility entry for the retired trousers reduction stage.
 * The supplied frozen source topology is retained, including its hip interior.
 * The 214v/276t result was retired after its minimum angle fell to 0.583181deg.
 */
export function reduceNovaRigidInterior(rigValue:unknown,motionValue:unknown,png:{width:number;height:number;data:Uint8Array}){
 const rig=object(rigValue,'rig'),skins=object(rig.skins,'skins'),skin=object(skins.default,'default'),slot=object(skin.bottomwear,'bottomwear'),a=object(slot.bottomwear,'bottomwear attachment');
 if(digest(a)!==EXPECTED_SOURCE)throw Error(`NOVA_REDUCTION_SOURCE_CHANGED: ${digest(a)}; remeasure this attachment before using the frozen recipe`);
 object(motionValue,'motion');
 const {width:w,height:h}=png,uvs=numbers(a.uvs,'uvs'),triangles=numbers(a.triangles,'triangles'),bindings=weights(a.weights),hull=a.hull;
 if(a.type!=='mesh'||typeof hull!=='number'||a.width!==w||a.height!==h||bindings.length!==uvs.length/2)throw Error('NOVA_REDUCTION_SOURCE_SHAPE');
 const points:Array<[number,number]>=bindings.map((_,i)=>[uvs[2*i]*w,uvs[2*i+1]*h]);
 const mask={width:w,height:h,alpha:Uint8Array.from({length:w*h},(_,i)=>png.data[i*4+3])};
 const fit=measureAuthoredMeshFit(mask,1,points,triangles),quality=triangleQuality(points,triangles);
 const bounds={minAngle:4.842578833857446,minAngleP10:24.776721222263504,maxTrianglesBelowFiveDegrees:2};
 const rows=[
  {code:'NOVA_PANTS_MIN_ANGLE',value:quality.minAngle,unit:'degrees',bound:{op:'>=',value:bounds.minAngle},state:quality.minAngle+1e-9>=bounds.minAngle?'pass':'fail'},
  {code:'NOVA_PANTS_MIN_ANGLE_P10',value:quality.minAngleP10,unit:'degrees',bound:{op:'>=',value:bounds.minAngleP10},state:quality.minAngleP10+1e-9>=bounds.minAngleP10?'pass':'fail'},
  {code:'NOVA_PANTS_SLIVERS_BELOW_FIVE_DEGREES',value:quality.trianglesBelowFiveDegrees,unit:'triangles',bound:{op:'<=',value:bounds.maxTrianglesBelowFiveDegrees},state:quality.trianglesBelowFiveDegrees<=bounds.maxTrianglesBelowFiveDegrees?'pass':'fail'},
 ];
 if(rows.some(row=>row.state!=='pass'))throw Error(`NOVA_PANTS_TRIANGLE_QUALITY: ${JSON.stringify(rows)}`);
 const output=structuredClone(rig),outSkin=object(object(output.skins,'skins').default,'default'),outSlot=object(outSkin.bottomwear,'bottomwear');
 if(digest(outSlot.bottomwear)!==EXPECTED_SOURCE)throw Error('NOVA_PANTS_SOURCE_TOPOLOGY_NOT_RETAINED');
 const active=new Set(bindings.flatMap((v,i)=>v.some(b=>b.bone!=='hip'&&b.weight>0)?[i]:[]));
 let mixed=0;for(let i=0;i<triangles.length;i+=3)if(triangles.slice(i,i+3).some(v=>active.has(v)))mixed++;
 const report={spec:'nova-pants-quality-report/1',operation:'retain-frozen-source-topology',sourceAttachmentSHA256:EXPECTED_SOURCE,rows,accepted:true,scope:'Drawing-pixel triangle quality. Official build/check and paired current-motion validation remain required.'};
 const provenance={spec:'nova-rigid-interior-reduction/2',action:'reduction-retired-retain-source-topology',sourceAttachmentSHA256:EXPECTED_SOURCE,pins:{parts:'1.25.0',core:'2.57.0',spine:'4.3.13'},sourceVertices:bindings.length,vertices:bindings.length,sourceTriangles:triangles.length/3,triangles:triangles.length/3,hull,activeVertices:active.size,mixedTrianglesKeptExact:mixed,removedPureHipVertices:0,sourceFit:fit,triangleQuality:{result:quality,bounds},scope:'Retain the complete frozen source attachment. Previous pure-hip interior removal created long sliver fans despite current-motion agreement; that reduction is retired. All cuff/mixed triangles and all bindings remain identical. No later deformation claim.'};
 return {rig:output,report,provenance};
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
 rows[i]={part:'bottomwear',vertices:generated.provenance.vertices,triangles:generated.provenance.triangles,hull:generated.provenance.hull,mode:'retained-source-topology-quality-repair',sourceGenerator:rows[i],provenance:'nova-rigid-interior.provenance.json'};
 writeFileSync(join(out,'mesh_report.json'),JSON.stringify(rows,null,2)+'\n');
 writeFileSync(join(out,'nova-rigid-interior.provenance.json'),JSON.stringify({...generated.provenance,sourceRigSHA256:textDigest(rigText),sourceMotionSHA256:textDigest(motionText),sourcePngSHA256:textDigest(readFileSync(pngPath)),emittedArtifacts:'None: this output is an authoring rig spec. Run official public rigc build and rig-parts check before adoption.'},null,2)+'\n');
 writeFileSync(join(out,'nova-rigid-interior.reducer-report.json'),JSON.stringify(generated.report,null,2)+'\n');
 console.log(`NOVA_PANTS_SOURCE_RETAINED ${generated.provenance.vertices}v ${generated.provenance.triangles}t; triangle quality gates pass`);
}
