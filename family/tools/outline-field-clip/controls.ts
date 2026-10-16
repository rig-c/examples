/** Self-contained controls: no family artwork, browser, saved checkout or private corpus is required. */
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {writePng} from '@rig-c/parts/src/raster/png.ts';
import {assertAlphaCovered} from './coverage.ts';
import {mergeAffineStars} from './affine.ts';
const root=resolve(import.meta.dir),out=resolve(process.argv[2]??'control-results');
if(existsSync(out))throw Error('CONTROL_OUTPUT_EXISTS '+out);mkdirSync(out,{recursive:true});
const results:{name:string;pass:boolean}[]=[];
function check(name:string,test:()=>boolean){const pass=test();results.push({name,pass});if(!pass)throw Error('CONTROL_FAILED '+name);console.log('PASS',name);}
function refuses(action:()=>unknown,code:string){try{action();return false;}catch(e){return e instanceof Error&&e.message.includes(code);}}
const png={width:12,height:12,data:new Uint8Array(12*12*4)},uvs=[.25,.25,.75,.25,.75,.75,.25,.75],triangles=[0,2,1,0,3,2];png.data[(5*12+5)*4+3]=255;
check('alpha positive',()=>assertAlphaCovered('fixture',png,uvs,triangles).missing===0);
png.data[(11*12+11)*4+3]=1;check('faint alpha-one outside mesh refuses',()=>refuses(()=>assertAlphaCovered('fixture',png,uvs,triangles),'CLIP_ALPHA_COVERAGE'));
const points:[number,number][]=[[0,0],[10,0],[10,10],[0,10],[5,5]],weights=points.map(([x,y])=>[{bone:'root',x,y,weight:1}]),fan=[0,4,1,1,4,2,2,4,3,3,4,0];
check('exact affine star removes only interior',()=>mergeAffineStars(points,weights,fan,1e-9).removed.length===1);
const changed=structuredClone(weights);changed[4][0].x+=.01;check('non-affine star is retained',()=>mergeAffineStars(points,changed,fan,1e-9).removed.length===0);
const images=join(out,'images');mkdirSync(images);const plate={width:24,height:24,data:new Uint8Array(24*24*4)};for(let y=8;y<16;y++)for(let x=8;x<16;x++){const i=(y*24+x)*4;plate.data[i]=170;plate.data[i+1]=90;plate.data[i+2]=40;plate.data[i+3]=255;}plate.data[(7*24+8)*4+3]=1;writePng(join(images,'art.png'),plate);
const fixture={spec:'rigc/1',name:'outline_control',images:'images',bones:[{name:'root',x:0,y:0}],slots:[{name:'art',bone:'root',attachment:'art'}],skins:{default:{art:{art:{type:'mesh',image:'art.png',width:24,height:24,uvs:[0,0,1,0,1,1,0,1],triangles:[0,2,1,0,3,2],hull:4,weights:[[0,24],[24,24],[24,0],[0,0]].map(([x,y])=>[{bone:'root',x,y,weight:1}])}}}}};
const input=join(out,'rig.json'),motion=join(out,'motion.json'),policy=join(out,'policy.json');writeFileSync(input,JSON.stringify(fixture));writeFileSync(motion,JSON.stringify({spec:'rigc-motion/1',archetype:'outline_control',cut:'outline_control',animations:{idle:{duration:1,loop:true,tracks:[]}}}));
const run=(file:string,args:string[])=>spawnSync('bun',[join(root,file),...args],{encoding:'utf8'});
const freeze=(sourceMotion:string,target:string)=>run('author-policy.ts',['--input',input,'--images',images,'--output',target,'--parts','art','--motion',sourceMotion]);
check('policy freezes reviewed source',()=>freeze(motion,policy).status===0);
const command=(source:string,dest:string,p=policy,m=motion)=>run('clip.ts',['--input',source,'--images',images,'--output',dest,'--parts','art','--policy',p,'--motion',m]);
const a=join(out,'a.json'),b=join(out,'b.json');check('guarded authoring positive',()=>command(input,a).status===0);check('independent deterministic repeat',()=>command(input,b).status===0&&readFileSync(a,'utf8')===readFileSync(b,'utf8')&&readFileSync(a+'.provenance.json','utf8')===readFileSync(b+'.provenance.json','utf8'));
const mutated=structuredClone(fixture);mutated.bones[0].x+=1;const mutant=join(out,'changed-source.json');writeFileSync(mutant,JSON.stringify(mutated));const target=join(out,'must-not-exist.json');const stale=command(mutant,target);check('changed source is refused before output',()=>stale.status!==0&&stale.stderr.includes('CLIP_SOURCE_RIG_MISMATCH')&&!existsSync(target));
const wrong=JSON.parse(readFileSync(policy,'utf8'));wrong.targets[0].imageSHA256='0'.repeat(64);const wrongPolicy=join(out,'wrong-image-policy.json');writeFileSync(wrongPolicy,JSON.stringify(wrong));const img=command(input,target,wrongPolicy);check('changed source image identity is refused',()=>img.status!==0&&img.stderr.includes('CLIP_SOURCE_IMAGE_MISMATCH')&&!existsSync(target));
const overwrite=command(input,a);check('existing output is refused',()=>overwrite.status!==0&&overwrite.stderr.includes('CLIP_OUTPUT_MUST_BE_NEW'));
const deform=JSON.parse(readFileSync(motion,'utf8'));deform.animations.idle.deform=[{slot:'art',attachment:'art',keys:[{t:0,vertices:[1,0]}]}];const dm=join(out,'deform-motion.json'),dp=join(out,'deform-policy.json');writeFileSync(dm,JSON.stringify(deform));check('deform fixture policy',()=>freeze(dm,dp).status===0);const dr=command(input,target,dp,dm);check('topology-dependent target deform is refused',()=>dr.status!==0&&dr.stderr.includes('CLIP_TARGET_DEFORM_UNSUPPORTED')&&!existsSync(target));
const linked=JSON.parse(JSON.stringify(fixture));linked.skins.default.art.linked={type:'linkedmesh',parent:'art'};const linkedInput=join(out,'linked-rig.json'),linkedPolicy=join(out,'linked-policy.json');writeFileSync(linkedInput,JSON.stringify(linked));const lp=run('author-policy.ts',['--input',linkedInput,'--images',images,'--output',linkedPolicy,'--parts','art','--motion',motion]);check('linked fixture policy',()=>lp.status===0);const lr=command(linkedInput,target,linkedPolicy);check('linked dependency on target is refused',()=>lr.status!==0&&lr.stderr.includes('CLIP_LINKED_TARGET_UNSUPPORTED')&&!existsSync(target));
const crossLinked=JSON.parse(JSON.stringify(fixture));crossLinked.skins.alternate={other:{dependent:{type:'linkedmesh',skin:'default',parent:'art'}}};const crossInput=join(out,'cross-slot-linked-rig.json'),crossPolicy=join(out,'cross-slot-linked-policy.json');writeFileSync(crossInput,JSON.stringify(crossLinked));const cp=run('author-policy.ts',['--input',crossInput,'--images',images,'--output',crossPolicy,'--parts','art','--motion',motion]);check('cross-slot alternate-skin linked fixture policy',()=>cp.status===0);const cr=command(crossInput,target,crossPolicy);check('cross-slot alternate-skin linked parent dependency is refused',()=>cr.status!==0&&cr.stderr.includes('CLIP_LINKED_TARGET_UNSUPPORTED other parent art')&&!cr.stderr.includes('CLIP_SOURCE_RIG_MISMATCH')&&!existsSync(target));
writeFileSync(join(out,'controls.json'),JSON.stringify(results,null,2)+'\n');
