/** Pixel-centre coverage at alpha >= 1. This contract deliberately includes faint source pixels. */
export function assertAlphaCovered(part:string,png:{width:number;height:number;data:ArrayLike<number>},uvs:number[],triangles:number[]){
 const {width:w,height:h}=png,covered=new Uint8Array(w*h);
 const point=(i:number):[number,number]=>[uvs[i*2]*w,uvs[i*2+1]*h];
 const cross=(a:readonly number[],b:readonly number[],c:readonly number[])=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
 for(let t=0;t<triangles.length;t+=3){const ps=triangles.slice(t,t+3).map(point),det=cross(ps[0],ps[1],ps[2]);if(!det)throw Error('CLIP_ZERO_TRIANGLE');const x0=Math.max(0,Math.floor(Math.min(...ps.map(p=>p[0])))),x1=Math.min(w-1,Math.ceil(Math.max(...ps.map(p=>p[0])))),y0=Math.max(0,Math.floor(Math.min(...ps.map(p=>p[1])))),y1=Math.min(h-1,Math.ceil(Math.max(...ps.map(p=>p[1]))));for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){if(png.data[(y*w+x)*4+3]<1)continue;const p=[x+.5,y+.5],a=cross(p,ps[1],ps[2])/det,b=cross(ps[0],p,ps[2])/det;if(a>=-1e-8&&b>=-1e-8&&a+b<=1+1e-8)covered[y*w+x]=1;}}
 let pixels=0,missing=0;for(let i=0;i<w*h;i++)if(png.data[i*4+3]>=1){pixels++;if(!covered[i])missing++;}if(missing)throw Error(`CLIP_ALPHA_COVERAGE ${part} missing ${missing}/${pixels}`);return{pixels,missing};
}
