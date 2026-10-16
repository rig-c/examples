/** Apply an explicitly authored texture repair after assembly, before the gated rig build. */
import {readFileSync,copyFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve,join} from 'node:path';
import {readPlate} from 'rig-c/plate';
const args=process.argv.slice(2);
function required(name:string){const i=args.indexOf('--'+name);if(i<0||!args[i+1])throw Error('REPAIR_ARGUMENT_REQUIRED '+name);return resolve(args[i+1]);}
const parts=required('parts'),baselinePath=required('baseline'),luna=resolve(import.meta.dir,'../luna'),assets=join(luna,'repairs');
type Provenance={targetSha256:string;repairSha256:string;maskSha256:string;sourcePaintingSha256:string;dimensions:[number,number]};
const record=JSON.parse(readFileSync(join(assets,'bottomwear-hidden.json'),'utf8')) as Provenance;
const hash=(path:string)=>createHash('sha256').update(readFileSync(path)).digest('hex');
function requireHash(path:string,expected:string,name:string){const actual=hash(path);if(actual!==expected)throw Error(name+' '+path+' found='+actual+' required='+expected);}
const repairedPath=join(assets,'bottomwear-hidden.png'),maskPath=join(assets,'bottomwear-hidden-mask.png'),target=join(parts,'parts/bottomwear.png');
requireHash(baselinePath,record.targetSha256,'REPAIR_BASELINE_CHANGED');requireHash(repairedPath,record.repairSha256,'REPAIR_ASSET_CHANGED');requireHash(maskPath,record.maskSha256,'REPAIR_MASK_CHANGED');requireHash(join(luna,'inputs/painting.png'),record.sourcePaintingSha256,'REPAIR_PAINTING_CHANGED');
const before=readPlate(baselinePath),after=readPlate(repairedPath),mask=readPlate(maskPath);
for(const [name,image]of[['baseline',before],['repair',after],['mask',mask]]as const)if(image.width!==record.dimensions[0]||image.height!==record.dimensions[1])throw Error('REPAIR_DIMENSIONS '+name+' found='+image.width+'x'+image.height+' required='+record.dimensions.join('x'));
let changed=0,allowed=0;
for(let i=0;i<before.data.length;i+=4){if(before.data[i+3]!==after.data[i+3])throw Error('REPAIR_ALPHA_CHANGED pixel='+i/4);if(mask.data[i+3]===0){for(let c=0;c<4;c++)if(before.data[i+c]!==after.data[i+c])throw Error('REPAIR_OUTSIDE_MASK pixel='+i/4+' channel='+c);}else allowed++;if([0,1,2].some(c=>before.data[i+c]!==after.data[i+c]))changed++;}
if(changed===0||allowed===0)throw Error('REPAIR_EMPTY');
const current=hash(target);if(current!==record.targetSha256&&current!==record.repairSha256)throw Error('REPAIR_TARGET_CHANGED '+target+' found='+current+' required baseline='+record.targetSha256+' or repair='+record.repairSha256);
if(current!==record.repairSha256)copyFileSync(repairedPath,target);
requireHash(target,record.repairSha256,'REPAIR_COPY_FAILED');
console.log(JSON.stringify({status:current===record.repairSha256?'ALREADY_APPLIED':'APPLIED',target,changedPixels:changed,allowedPixels:allowed,alphaMaxDelta:0,outsideMaskMaxDelta:0,repairSha256:record.repairSha256,note:'Authored hidden-cloth repair; no rig/physics/motion/source painting edits. Run the normal gated rig/check next.'},null,2));
