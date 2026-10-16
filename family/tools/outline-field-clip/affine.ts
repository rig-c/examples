/** Remove only interior stars whose per-bone homogeneous bind contributions share one affine field. */
import { earClip, traceOutline } from 'rig-c/mesh';
type Point = [number, number];
type Binding = {bone:string;x:number;y:number;weight:number};
const cross=(a:Point,b:Point,c:Point)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
export function mergeAffineStars(points:Point[], weights:Binding[][], input:number[], tolerance:number){
 let triangles=input.slice();const boundary=new Set(traceOutline(points.length,triangles).walk);const removed:{vertex:number;neighbours:number[];residual:number}[]=[];
 const values=weights.map(ws=>new Map(ws.map(b=>[b.bone,[b.weight,b.weight*b.x,b.weight*b.y]])));
 for(let vertex=0;vertex<points.length;vertex++){
  if(boundary.has(vertex))continue;
  const incident:number[]=[],adj=new Map<number,number[]>();let referenceSign=0;
  for(let i=0;i<triangles.length;i+=3){const tri=triangles.slice(i,i+3);if(!tri.includes(vertex))continue;incident.push(i);const edge=tri.filter(v=>v!==vertex);if(edge.length!==2)throw Error('AFFINE_REPEATED_VERTEX');adj.set(edge[0],[...(adj.get(edge[0])??[]),edge[1]]);adj.set(edge[1],[...(adj.get(edge[1])??[]),edge[0]]);referenceSign=cross(points[tri[0]],points[tri[1]],points[tri[2]]);}
  if(incident.length<3||[...adj.values()].some(v=>v.length!==2))continue;
  const start=Math.min(...adj.keys()),ring=[start];let last=-1,at=start;
  for(let j=0;j<adj.size;j++){const ns=adj.get(at)!;const next=last<0?Math.min(...ns):ns.find(n=>n!==last)!;if(next===start)break;ring.push(next);last=at;at=next;}
  if(ring.length!==adj.size)continue;
  let seed:number[]=[];let largest=0;
  for(let a=0;a<ring.length;a++)for(let b=a+1;b<ring.length;b++)for(let c=b+1;c<ring.length;c++){const ar=Math.abs(cross(points[ring[a]],points[ring[b]],points[ring[c]]));if(ar>largest){largest=ar;seed=[ring[a],ring[b],ring[c]];}}
  if(largest<1e-8)continue;const [a,b,c]=seed.map(i=>points[i]),det=cross(a,b,c),bones=new Set([vertex,...ring].flatMap(i=>[...values[i].keys()]));let residual=0;
  for(const id of [vertex,...ring]){const p=points[id],bs=[cross(p,b,c)/det,cross(a,p,c)/det,0];bs[2]=1-bs[0]-bs[1];for(const bone of bones)for(let k=0;k<3;k++){const expected=seed.reduce((sum,j,index)=>sum+bs[index]*(values[j].get(bone)?.[k]??0),0);residual=Math.max(residual,Math.abs(expected-(values[id].get(bone)?.[k]??0)));}}
  if(residual>tolerance)continue;
  let replacement:number[];try{replacement=earClip(ring.map(i=>points[i]));}catch{continue;}
  const remove=new Set(incident);triangles=triangles.filter((_,i)=>!remove.has(i-i%3));
  for(let k=0;k<replacement.length;k+=3){const tri=replacement.slice(k,k+3).map(i=>ring[i]);if(cross(points[tri[0]],points[tri[1]],points[tri[2]])*referenceSign<0)[tri[1],tri[2]]=[tri[2],tri[1]];triangles.push(...tri);}
  removed.push({vertex,neighbours:ring,residual});
 }
 return {triangles,removed,tolerance};
}
