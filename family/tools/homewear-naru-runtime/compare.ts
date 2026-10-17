/** Serving closure identity: exact inventory/text bytes and decoded RGBA. */
import {readFileSync,readdirSync,writeFileSync,mkdirSync,cpSync,mkdtempSync,rmSync} from 'node:fs';
import {join,relative,resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {readPlate,Plate} from 'rig-c/plate';

function files(dir:string):string[]{return readdirSync(dir,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name)).flatMap(e=>e.isDirectory()?files(join(dir,e.name)):[join(dir,e.name)]);}
export function compareClosure(recorded:string,candidate:string){
 const expected=files(recorded).map(p=>relative(recorded,p)),actual=files(candidate).map(p=>relative(candidate,p));
 if(JSON.stringify(expected)!==JSON.stringify(actual))throw Error('HOMEWEAR_CLOSURE_INVENTORY');
 const result=[];
 for(const path of expected){const a=join(recorded,path),b=join(candidate,path);
  if(path.endsWith('.png')){const x=readPlate(a),y=readPlate(b);if(x.width!==y.width||x.height!==y.height||!Buffer.from(x.data).equals(Buffer.from(y.data)))throw Error('HOMEWEAR_CLOSURE_PIXELS '+path);result.push({path,kind:'decoded-RGBA',width:x.width,height:x.height,PASS:true});}
  else{if(!readFileSync(a).equals(readFileSync(b)))throw Error('HOMEWEAR_CLOSURE_BYTES '+path);result.push({path,kind:'exact-bytes',PASS:true});}
 }
 return {PASS:true,files:result};
}
const args=process.argv.slice(2);
if(args.includes('--selftest')){
 const root=mkdtempSync(join(tmpdir(),'homewear-closure-controls-')),a=join(root,'recorded'),b=join(root,'candidate');
 const rows=[];const check=(name:string,test:()=>boolean)=>{if(!test())throw Error('HOMEWEAR_CLOSURE_CONTROL '+name);rows.push({name,PASS:true});};
 const rejects=(code:string)=>{try{compareClosure(a,b);return false;}catch(e){return e instanceof Error&&e.message.startsWith(code);}};
 try{mkdirSync(a);writeFileSync(join(a,'skeleton.model.json'),'{}\n');const png=new Plate(2,2);png.blend(0,0,[180,90,40,255]);png.writePng(join(a,'skeleton.png'));cpSync(a,b,{recursive:true});
  check('identical closure accepted',()=>compareClosure(a,b).PASS);
  writeFileSync(join(b,'skeleton.model.json'),'{"changed":true}\n');check('changed model bytes refused',()=>rejects('HOMEWEAR_CLOSURE_BYTES'));cpSync(join(a,'skeleton.model.json'),join(b,'skeleton.model.json'));
  png.blend(1,1,[20,100,200,255]);png.writePng(join(b,'skeleton.png'));check('changed decoded pixels refused',()=>rejects('HOMEWEAR_CLOSURE_PIXELS'));cpSync(join(a,'skeleton.png'),join(b,'skeleton.png'));
  writeFileSync(join(b,'extra.json'),'{}');check('extra serving file refused',()=>rejects('HOMEWEAR_CLOSURE_INVENTORY'));rmSync(join(b,'extra.json'));
  rmSync(join(b,'skeleton.png'));check('missing serving file refused',()=>rejects('HOMEWEAR_CLOSURE_INVENTORY'));
  console.log(JSON.stringify({spec:'family-homewear-closure-controls/1',rows,PASS:true}));
 }finally{rmSync(root,{recursive:true,force:true});}
}else{
 const option=(name:string)=>{const i=args.indexOf('--'+name);if(i<0||!args[i+1])throw Error('HOMEWEAR_COMPARE_ARG '+name);return resolve(args[i+1]);};
 const recorded=option('recorded'),result={spec:'family-homewear-serving-identity/1',compiler:compareClosure(recorded,option('compiler')),check:compareClosure(recorded,option('check'))};
 writeFileSync(option('out'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
}
