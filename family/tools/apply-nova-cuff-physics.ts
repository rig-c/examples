/** Final Nova authoring stage. Run the normal official build and parts check afterwards. */
import {readFileSync,writeFileSync,existsSync,mkdirSync,cpSync} from 'node:fs';
import {resolve,relative,dirname,join} from 'node:path';
import {createHash} from 'node:crypto';
const canonical=(value:unknown):unknown=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).sort(([a],[b])=>a<b?-1:a>b?1:0).map(([key,item])=>[key,canonical(item)])):value;
const digest=(value:unknown)=>createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
const bytes=(path:string)=>createHash('sha256').update(readFileSync(path)).digest('hex');
const args=process.argv.slice(2),arg=(key:string)=>{const i=args.indexOf(key);if(i<0||!args[i+1])throw Error('Required '+key);return resolve(args[i+1]);};
const source=arg('--source-rig-dir'),out=arg('--out-rig-dir'),policyPath=arg('--policy');
if(source===out||!relative(source,out).startsWith('..')||existsSync(out))throw Error('NOVA_CUFF_OUTPUT_MUST_BE_FRESH_OUTSIDE_SOURCE');
const policy=JSON.parse(readFileSync(policyPath,'utf8')) as {spec:string;sourceRigSHA256:string;outputRigSHA256:string;motionSHA256:string;images:Record<string,string>;constraints:{name:string;remove:boolean}[]};
if(policy.spec!=='nova-cuff-physics/1'||policy.constraints.length!==4)throw Error('NOVA_CUFF_POLICY_REQUIRED');
const rig=JSON.parse(readFileSync(join(source,'rig.json'),'utf8')) as {constraints:{name:string;type:string;mix:number}[]};
if(digest(rig)!==policy.sourceRigSHA256)throw Error('NOVA_CUFF_SOURCE_RIG_CHANGED');
if(bytes(join(source,'motion.json'))!==policy.motionSHA256)throw Error('NOVA_CUFF_MOTION_CHANGED');
for(const [name,hash]of Object.entries(policy.images))if(bytes(join(source,'images',name))!==hash)throw Error('NOVA_CUFF_IMAGE_CHANGED '+name);
const names=new Set(['cuff_r0_phys','cuff_r1_phys','cuff_l0_phys','cuff_l1_phys']);
for(const target of policy.constraints){
 if(!names.delete(target.name)||target.remove!==true)throw Error('NOVA_CUFF_TARGET_INVALID '+target.name);
 const matches=rig.constraints.filter(c=>c.name===target.name);
 if(matches.length!==1||matches[0].type!=='physics')throw Error('NOVA_CUFF_CONSTRAINT_CHANGED '+target.name);
 rig.constraints=rig.constraints.filter(c=>c.name!==target.name);
}
if(names.size||digest(rig)!==policy.outputRigSHA256)throw Error('NOVA_CUFF_PROTECTED_STATE_CHANGED');
mkdirSync(dirname(out),{recursive:true});cpSync(source,out,{recursive:true});
writeFileSync(join(out,'rig.json'),JSON.stringify(rig,null,2)+'\n');
writeFileSync(join(out,'cuff-physics.provenance.json'),JSON.stringify({spec:'nova-cuff-physics-provenance/1',policySHA256:digest(policy),sourceRigSHA256:policy.sourceRigSHA256,outputRigSHA256:policy.outputRigSHA256,constraints:policy.constraints,scope:'Only four named cuff physics constraints are removed. Authored idle, bones, weights, topology, images and all other constraints remain unchanged. Authoring input only; normal official build/check must follow.'},null,2)+'\n');
console.log('NOVA_CUFF_AUTHOR_INPUT',out);
