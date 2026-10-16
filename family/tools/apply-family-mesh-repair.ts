/** Apply frozen, publicly generated authoring attachments; normal build/check must follow. */
import {readFileSync,writeFileSync,existsSync,mkdirSync,cpSync} from 'node:fs';
import {resolve,dirname,join,relative} from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
function object(v:unknown,label:string):Record<string,unknown>{if(!v||typeof v!=='object'||Array.isArray(v))throw Error(label+' object required');return v as Record<string,unknown>;}
function canonical(v:unknown):unknown{if(Array.isArray(v))return v.map(canonical);if(v&&typeof v==='object'){const x=object(v,'canonical');return Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])]));}return v;}
const digest=(v:unknown)=>createHash('sha256').update(JSON.stringify(canonical(v))).digest('hex');
const bytes=(p:string)=>createHash('sha256').update(readFileSync(p)).digest('hex');
const read=(p:string)=>JSON.parse(readFileSync(p,'utf8')) as unknown;
function attachment(rig:Record<string,unknown>,slot:string){return object(object(object(rig.skins,'skins').default,'skin')[slot],'slot')[slot];}
export function repairFamilyMesh(rigValue:unknown,payloadValue:unknown,policyValue:unknown,imageHash:(name:string)=>string){
 const rig=object(rigValue,'rig'),payload=object(payloadValue,'payload'),policy=object(policyValue,'policy');
 if(policy.spec!=='family-mesh-repair/1'||!Array.isArray(policy.targets))throw Error('FAMILY_MESH_POLICY_REQUIRED');
 if(digest({bones:rig.bones,constraints:rig.constraints,stops:rig.stops})!==policy.bindingContextSHA256)throw Error('FAMILY_MESH_BINDING_CONTEXT_CHANGED');
 const out=structuredClone(rig),provenance:unknown[]=[];const seen=new Set<string>();
 for(const raw of policy.targets){const t=object(raw,'target');if(typeof t.part!=='string'||seen.has(t.part))throw Error('FAMILY_MESH_TARGET_INVALID');seen.add(t.part);const part=t.part,old=object(attachment(rig,part),'attachment'),next=object(payload[part],'payload attachment');
  if(digest(old)!==t.sourceAttachmentSHA256)throw Error('FAMILY_MESH_SOURCE_CHANGED '+part);
  if(digest(next)!==t.outputAttachmentSHA256)throw Error('FAMILY_MESH_PAYLOAD_CHANGED '+part);
  if(old.image!==part+'.png'||next.image!==old.image||next.type!=='mesh'||next.width!==old.width||next.height!==old.height)throw Error('FAMILY_MESH_IMAGE_DOMAIN_CHANGED '+part);
  if(imageHash(part+'.png')!==t.imageSHA256)throw Error('FAMILY_MESH_IMAGE_CHANGED '+part);
  object(object(out.skins,'skins').default,'skin')[part]={[part]:structuredClone(next)};
  provenance.push({part,sourceAttachmentSHA256:t.sourceAttachmentSHA256,outputAttachmentSHA256:t.outputAttachmentSHA256,imageSHA256:t.imageSHA256,producer:t.producer});
 }
 // Replace only declared attachment values; all other authoring state must survive.
 const restored=structuredClone(out);for(const part of seen)object(object(restored.skins,'skins').default,'skin')[part]={[part]:structuredClone(attachment(rig,part))};
 if(digest(restored)!==digest(rig))throw Error('FAMILY_MESH_PROTECTED_STATE_CHANGED');
 return {rig:out,provenance:{spec:'family-mesh-repair-provenance/1',policySHA256:digest(policy),bonesSHA256:policy.bonesSHA256,bindingContextSHA256:policy.bindingContextSHA256,targets:provenance,scope:'Authoring rig attachments only. Physics parameters, bones, motion, slots and other attachments preserved. Topwear deformation fields intentionally change. Run normal official build/check.'}};
}
if(import.meta.main){
 const args=process.argv.slice(2),arg=(k:string)=>{const i=args.indexOf(k);if(i<0||!args[i+1])throw Error('Required '+k);return resolve(args[i+1]);};
 const source=arg('--source-rig-dir'),out=arg('--out-rig-dir'),policyPath=arg('--policy');
 if(source===out||!relative(source,out).startsWith('..')||existsSync(out))throw Error('FAMILY_MESH_OUTPUT_MUST_BE_FRESH_OUTSIDE_SOURCE');
 const policy=object(read(policyPath),'policy');if(bytes(join(source,'motion.json'))!==policy.motionSHA256)throw Error('FAMILY_MESH_MOTION_CHANGED');if(typeof policy.payload!=='string')throw Error('FAMILY_MESH_PAYLOAD_PATH_REQUIRED');
 const generated=repairFamilyMesh(read(join(source,'rig.json')),read(resolve(dirname(policyPath),policy.payload)),policy,name=>bytes(join(source,'images',name)));
 const report=read(join(source,'mesh_report.json'));if(!Array.isArray(report))throw Error('FAMILY_MESH_REPORT_REQUIRED');
 for(const raw of policy.targets as unknown[]){const t=object(raw,'target'),at=report.findIndex(r=>object(r,'report').part===t.part);if(at<0)throw Error('FAMILY_MESH_TARGET_REPORT_MISSING '+t.part);report[at]=t.meshReport;}
 mkdirSync(dirname(out),{recursive:true});cpSync(source,out,{recursive:true});
 writeFileSync(join(out,'rig.json'),JSON.stringify(generated.rig,null,2)+'\n');writeFileSync(join(out,'mesh_report.json'),JSON.stringify(report,null,2)+'\n');writeFileSync(join(out,'mesh-repair.provenance.json'),JSON.stringify({...generated.provenance,helperSHA256:bytes(fileURLToPath(import.meta.url))},null,2)+'\n');
 console.log('FAMILY_MESH_AUTHOR_INPUT',out);
}
