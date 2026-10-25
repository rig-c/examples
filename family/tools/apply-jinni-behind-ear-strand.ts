/**
 * RETIRED post-pass script (rig-c/parts-examples#69).
 * Jinni (family/jinni/config.json) now declares meshes.hair_front.explicit.islands
 * with hair_front__island2 bound to `head` and placed `before: "ear_l"` on
 * @rig-c/parts 1.63.0, so `rig-parts rig` emits the behind-ear strand slot in place.
 * No character uses this post-pass script anymore.
 */
import{readFileSync,writeFileSync,existsSync,mkdirSync}from'node:fs';
import{createHash}from'node:crypto';
import{dirname,resolve}from'node:path';
const args=process.argv.slice(2),arg=(key:string)=>{const i=args.indexOf(key);if(i<0||!args[i+1])throw Error('STRAND_ARGUMENT_REQUIRED '+key);return args[i+1];};
const input=resolve(arg('--input')),motion=resolve(arg('--motion')),images=resolve(arg('--images')),output=resolve(arg('--output')),policyPath=resolve(arg('--policy'));
const canonical=(v:unknown):string=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v!==null&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical((v as Record<string,unknown>)[k])).join(',')+'}':JSON.stringify(v);
const sha=(v:string|Uint8Array)=>createHash('sha256').update(v).digest('hex');const read=(p:string)=>JSON.parse(readFileSync(p,'utf8'));
if(dirname(input)===dirname(output))throw Error('STRAND_OUTPUT_DIRECTORY_MUST_DIFFER');
for(const p of[output,output+'.provenance.json',dirname(output)+'/mesh_report.json'])if(existsSync(p))throw Error('STRAND_OUTPUT_EXISTS '+p);
const r=read(input),m=read(motion),policy=read(policyPath);
if(policy.spec!=='jinni-behind-ear-strand/1')throw Error('STRAND_POLICY_UNSUPPORTED');
if(sha(canonical(r))!==policy.sourceRigSHA256)throw Error('STRAND_SOURCE_RIG_CHANGED');if(sha(canonical(m))!==policy.motionSHA256)throw Error('STRAND_MOTION_CHANGED');
for(const[name,h]of Object.entries(policy.imageSHA256))if(sha(readFileSync(images+'/'+name))!==h)throw Error('STRAND_IMAGE_CHANGED '+name);
const slot='hair_front__island2',target='head';const attachment=r.skins.default[slot][slot];
if(attachment.type!=='mesh'||attachment.image!=='hair_front.png'||attachment.weights.length!==26||attachment.uvs.length!==52)throw Error('STRAND_IDENTITY_CHANGED');
const before=canonical(r),original=structuredClone(r),boneMap=new Map(r.bones.map((b:Record<string,unknown>)=>[b.name,b]));
type Matrix=[number,number,number,number,number,number];const cache=new Map<string,Matrix>();
function matrix(name:string):Matrix{if(cache.has(name))return cache.get(name)!;const b=boneMap.get(name)as Record<string,number|string>|undefined;if(!b)throw Error('STRAND_BIND_BONE_MISSING '+name);for(const k of Object.keys(b))if(!['name','parent','x','y','rotation','length'].includes(k))throw Error('STRAND_BIND_BONE_SHAPE_UNSUPPORTED '+name+'.'+k);const rad=Number(b.rotation??0)*Math.PI/180,co=Math.cos(rad),si=Math.sin(rad);let q:Matrix=[co,-si,si,co,Number(b.x??0),Number(b.y??0)];if(b.parent){const[a,c,d,e,x,y]=matrix(String(b.parent)),[f,g,h,i,j,k]=q;q=[a*f+c*h,a*g+c*i,d*f+e*h,d*g+e*i,a*j+c*k+x,d*j+e*k+y];}cache.set(name,q);return q;}
const[a,b,c,d,x,y]=matrix(target),det=a*d-b*c;if(Math.abs(det)<1e-12)throw Error('STRAND_HEAD_BIND_SINGULAR');
let setupMax=0;const oldBones=new Set<string>();
if(!Array.isArray(policy.headBindWeights)||policy.headBindWeights.length!==attachment.weights.length)throw Error('STRAND_BIND_TABLE_INVALID');
attachment.weights=attachment.weights.map((weights:{bone:string;x:number;y:number;weight:number}[],index:number)=>{let wx=0,wy=0;for(const w of weights){oldBones.add(w.bone);const[A,B,C,D,X,Y]=matrix(w.bone);wx+=w.weight*(A*w.x+B*w.y+X);wy+=w.weight*(C*w.x+D*w.y+Y);}const lx=(d*(wx-x)-b*(wy-y))/det,ly=(-c*(wx-x)+a*(wy-y))/det;const measured=policy.headBindWeights[index];if(!Array.isArray(measured)||measured.length!==1||measured[0].bone!==target||measured[0].weight!==1||!Number.isFinite(measured[0].x)||!Number.isFinite(measured[0].y)||Math.abs(measured[0].x-lx)>1e-9||Math.abs(measured[0].y-ly)>1e-9)throw Error('STRAND_BIND_TABLE_DOES_NOT_PRESERVE_SETUP '+index);setupMax=Math.max(setupMax,Math.abs(a*measured[0].x+b*measured[0].y+x-wx),Math.abs(c*measured[0].x+d*measured[0].y+y-wy));return measured;});
const from=r.slots.findIndex((s:{name:string})=>s.name===slot),[s]=r.slots.splice(from,1),to=r.slots.findIndex((s:{name:string})=>s.name==='ear_l');if(from<0||to<0)throw Error('STRAND_DRAW_ORDER_ANCHOR_MISSING');r.slots.splice(to,0,s);
// Only the measured island's bind weights and slot position may change.
const proof=structuredClone(r);proof.skins.default[slot][slot].weights=original.skins.default[slot][slot].weights;proof.slots=original.slots;if(canonical(proof)!==before)throw Error('STRAND_PROTECTED_PAYLOAD_CHANGED');
const sourceReport=dirname(input)+'/mesh_report.json';if(!existsSync(sourceReport))throw Error('STRAND_SOURCE_REPORT_MISSING');if(sha(readFileSync(sourceReport))!==policy.sourceReportSHA256)throw Error('STRAND_SOURCE_REPORT_CHANGED');const report=read(sourceReport);if(!Array.isArray(report))throw Error('STRAND_SOURCE_REPORT_ARRAY_REQUIRED');const reportRow=report.find((q:{part:string})=>q.part==='hair_front');if(!reportRow)throw Error('STRAND_SOURCE_PART_REPORT_REQUIRED');
const provenance={spec:'jinni-behind-ear-strand-result/1',input:policy.sourceRigSHA256,motion:policy.motionSHA256,slot,targetBone:target,oldWeightBones:[...oldBones].sort(),oldSlotIndex:from,newSlotIndex:to,setupWorldMaxDelta:setupMax,preserved:'All other rig payload, source UV, topology, source pixels and motion unchanged',sourceReason:'Source side strand emerges behind ear and follows neck edge into shoulder curl; front bang ownership and topmost slot are incorrect.'};
if(sha(canonical(r))!==policy.expectedOutputRigSHA256)throw Error('STRAND_OUTPUT_RIG_NOT_MEASURED_CANDIDATE');
reportRow.behindEarStrand=provenance;mkdirSync(dirname(output),{recursive:true});writeFileSync(output,JSON.stringify(r,null,2)+'\n');writeFileSync(output+'.provenance.json',JSON.stringify(provenance,null,2)+'\n');writeFileSync(dirname(output)+'/mesh_report.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(provenance));
