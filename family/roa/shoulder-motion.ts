import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {readModel,underNoSkin,openTrack,physicsClockStep} from 'rig-c/core';
import {loadPosable,piecesOf,renderFrame} from 'rig-c/render';
import {Skeleton,AnimationState,AnimationStateData,Physics,MeshAttachment,RegionAttachment} from '@esotericsoftware/spine-core';
import {createWindControls} from './shoulder-wind-controls.mjs';
const names=['baseline','candidate'],read=(p:string)=>JSON.parse(readFileSync(p,'utf8')),changed='topwear';
const delta=(a:readonly number[],b:readonly number[])=>{if(a.length!==b.length)throw Error('Length changed');let d=0;for(let i=0;i<a.length;i++)d=Math.max(d,Math.abs(a[i]-b[i]));return d;};
const profiles=[{name:'calm',base:0,peak:0,duration:2.4,seconds:4},{name:'gust48',base:0,peak:48,duration:2.4,seconds:4},{name:'gust96',base:0,peak:96,duration:2.4,seconds:4}];
const results=[];mkdirSync('shots',{recursive:true});
for(const p of profiles){
 const tracks=names.map(n=>openTrack(underNoSkin(readModel(readFileSync(n+'/build/skeleton.model.json','utf8'),n+'/build')),'idle',{loop:true,reset:'animation',clock:physicsClockStep}));
 const native=names.map(n=>{const loaded=loadPosable(n+'/build/skeleton.json',n+'/build/skeleton.atlas',n+'/build'),sk=new Skeleton(loaded.data),st=new AnimationState(new AnimationStateData(loaded.data));st.setAnimation(0,'idle',true);sk.setupPose();sk.updateWorldTransform(Physics.none);st.apply(sk);sk.update(0);sk.updateWorldTransform(Physics.reset);return{loaded,sk,st};});
 const wind=createWindControls();wind.setBase(p.base);wind.setGustPeak(p.peak);wind.setGustDuration(p.duration);wind.triggerGust();let nativeMax=0,protectedMax=0,boneMax=0,peakFoldBaseline=0,peakFoldCandidate=0,topwearProtectedMax=0;const folded=[new Set<number>(),new Set<number>()];
 const rest=tracks.map(t=>t.first.drawn.find(d=>d.slot===changed)!.vertices),atts=names.map(n=>read(n+'/rig/rig.json').skins.default[changed][changed]);
 const area=(v:readonly number[],a:number,b:number,c:number)=>(v[2*b]-v[2*a])*(v[2*c+1]-v[2*a+1])-(v[2*b+1]-v[2*a+1])*(v[2*c]-v[2*a]);
 function save(f:number){native.forEach((n,i)=>{for(const[bg,color]of[['light',[238,238,238,255]],['dark',[30,33,40,255]]]as const)renderFrame({index:f,time:f/60,pieces:piecesOf(n.sk)},n.loaded.pages,{minX:-285,minY:1749,maxX:-135,maxY:1864,scale:3,width:450,height:345},color).writePng(`shots/${p.name}-${names[i]}-${bg}-f${f}.png`);});}
 for(let f=0;f<=p.seconds*60;f++){
  const w=f===0?wind.read().wind:wind.advance(1/60).wind;tracks.forEach(t=>t.setEnvironment({wind:[w,0],gravity:[0,0]}));const poses=tracks.map(t=>f===0?t.first:t.step(1/60)),draws=poses.map(q=>new Map(q.drawn.map(d=>[d.slot,d.vertices])));
  native.forEach((n,i)=>{n.sk.windX=w;n.sk.windY=n.sk.gravityX=n.sk.gravityY=0;if(f>0){n.st.update(1/60);n.sk.setupPoseBones();n.st.apply(n.sk);n.sk.update(physicsClockStep(1/60));n.sk.updateWorldTransform(Physics.update);}for(const s of n.sk.drawOrder.appliedPose){const a=s.appliedPose.attachment;if(!(a instanceof MeshAttachment)&&!(a instanceof RegionAttachment))continue;const v=new Array(a instanceof MeshAttachment?a.worldVerticesLength:8).fill(0);if(a instanceof MeshAttachment)a.computeWorldVertices(n.sk,s,0,v.length,v,0,2);else a.computeWorldVertices(s,a.getOffsets(s.appliedPose),v,0,2);nativeMax=Math.max(nativeMax,delta(v,draws[i].get(s.data.name)!));}});
  for(const[s,v]of draws[0])if(s!==changed)protectedMax=Math.max(protectedMax,delta(v,draws[1].get(s)!));poses[0].bones.forEach((b,k)=>{const c=poses[1].bones[k];boneMax=Math.max(boneMax,delta([b.a,b.b,b.c,b.d,b.worldX,b.worldY],[c.a,c.b,c.c,c.d,c.worldX,c.worldY]));});
  const vs=draws.map(d=>d.get(changed)!);for(let v=0;v<vs[0].length/2;v++)if(v<98||v>102)topwearProtectedMax=Math.max(topwearProtectedMax,Math.abs(vs[0][2*v]-vs[1][2*v]),Math.abs(vs[0][2*v+1]-vs[1][2*v+1]));const folds=vs.map((v,k)=>{let n=0;for(let j=0;j<atts[k].triangles.length;j+=3){const ids=atts[k].triangles.slice(j,j+3);if(area(rest[k],...ids)*area(v,...ids)<=0){n++;folded[k].add(j/3);}}return n;});peakFoldBaseline=Math.max(peakFoldBaseline,folds[0]);peakFoldCandidate=Math.max(peakFoldCandidate,folds[1]);
  if(f===0||f===50||f===72||f===200)save(f);
 }
 const row={profile:p,nativeMax,protectedMax,boneMax,peakFoldBaseline,peakFoldCandidate,topwearProtectedMax,folded:folded.map((set,k)=>[...set].map(t=>({triangle:t,uv:atts[k].triangles.slice(t*3,t*3+3).map((i:number)=>[atts[k].uvs[i*2],atts[k].uvs[i*2+1]])})))};results.push(row);writeFileSync('motion-results.json',JSON.stringify(results,null,2)+'\n');console.log(row);if(nativeMax!==0||protectedMax!==0||boneMax!==0||topwearProtectedMax!==0||peakFoldCandidate>peakFoldBaseline)throw Error('Paired proof failed');
}
