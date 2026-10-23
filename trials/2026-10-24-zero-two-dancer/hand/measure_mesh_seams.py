"""Seam metric: max visible background thickness from central-60%, terminal-5%-of-height
alpha contour of either adjacent region to nearest opaque pixel of the other.
Adapts gapscan.py grey tolerance6 and per-joint localization; replaces disc
closing area with Euclidean contour gaps (no 3px closing ceiling), alpha>128.
Mesh extension: each shin alpha island is projected through the actual UV triangle barycentrics; source midline x417 splits r/l. All alpha pixels must bind to a triangle. Metric thresholds unchanged. All distances in original 736x960 frame pixels, quarter-pixel sample precision.
"""
import sys,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.spatial import cKDTree
from scipy.ndimage import map_coordinates
geof,build,framesf,outf=sys.argv[1:];g=json.load(open(geof));v=g['viewport'];scale=v['scale'];build=Path(build);frames=Path(framesf);out=Path(outf);out.mkdir(parents=True,exist_ok=True)
pairs=[('knee_r','thigh_r','shin_r'),('knee_l','thigh_l','shin_l'),('ankle_r','shin_r','shoe_r'),('ankle_l','shin_l','shoe_l')]
tex={}
for n in {s for _,a,b in pairs for s in [a,b]}:
 alpha=np.asarray(Image.open(build.parent/'rig/images'/ (('shins' if n.startswith('shin_') else n)+'.png')).convert('RGBA'))[:,:,3]>128
 if n.startswith('shin_'):
  # Source parts x329,width174 plus 4px padding. Split at authored midline x417.
  if n.endswith('_r'): alpha[:,92:]=False
  else: alpha[:,:92]=False
 y,x=np.where(alpha);xmin,xmax=x.min(),x.max();xs=np.arange(int(np.ceil(xmin+.2*(xmax-xmin))),int(np.floor(xmin+.8*(xmax-xmin)))+1)
 top=[];bottom=[]
 for col in xs:
  ys=np.where(alpha[:,col])[0]
  if len(ys):
   if ys.min() <= y.min()+.05*(y.max()-y.min()): top.append([col,ys.min()])
   if ys.max() >= y.max()-.05*(y.max()-y.min()): bottom.append([col,ys.max()])
 h,w=alpha.shape;tex[n]={'all':np.column_stack([x,y]),'top':np.array(top),'bottom':np.array(bottom),'wh':np.array([w-1,h-1])}
skeleton=json.load(open(build/'skeleton.json'))
mesh=skeleton['skins'][0]['attachments']['shins']['shins'];tri=np.array(mesh['triangles']).reshape(-1,3)
uv=np.array(mesh['uvs']).reshape(-1,2);bindings={}
for n in ['shin_r','shin_l']:
 for key in ['all','top','bottom']:
  pts=tex[n][key];uvpts=pts/tex[n]['wh'];ids=np.zeros((len(pts),3),dtype=int);wgt=np.zeros((len(pts),3));covered=np.zeros(len(pts),dtype=bool)
  for t in tri:
   a,b,c=uv[t];M=np.column_stack([b-a,c-a])
   if abs(np.linalg.det(M))<1e-12:continue
   pq=np.linalg.solve(M,(uvpts-a).T).T;weights=np.column_stack([1-pq.sum(1),pq]);take=(weights.min(1)>=-1e-5)&(~covered)
   ids[take]=t;wgt[take]=weights[take];covered[take]=True
  if not covered.all():raise RuntimeError(f'{n} {key}: UV mesh misses {sum(~covered)}/{len(pts)} alpha pixels')
  bindings[n,key]=(ids,wgt)
def project(a,pts,n):
 if n.startswith('shin_'):
  key=next(k for k in ['all','top','bottom'] if pts is tex[n][k]);ids,wgt=bindings[n,key];q=np.array(a['vertices']).reshape(-1,2);xy=(q[ids]*wgt[:,:,None]).sum(1)
  return np.column_stack([(xy[:,0]-v['x'])*scale,(v['y']+v['height']-xy[:,1])*scale])

 q=np.asarray(a['vertices']).reshape(-1,2);q=np.column_stack([(q[:,0]-v['x'])*scale,(v['y']+v['height']-q[:,1])*scale]);uv=pts/tex[n]['wh'];return q[1]+uv[:,0,None]*(q[2]-q[1])+uv[:,1,None]*(q[0]-q[1])
rows=[];worst={};selected=[]
for f in g['frames']:
 fi=frames/f"f{f['index']:04d}.png"
 if not fi.exists():continue
 im=np.asarray(Image.open(fi).convert('RGB'));ats={x['slot']:x for x in f['attachments']};ats['shin_r']=ats['shins'];ats['shin_l']=ats['shins'];cache={}
 for n in tex:
  pts=project(ats[n],tex[n]['all'],n);cache[n]=(pts,cKDTree(pts))
 for name,a,b in pairs:
  best=0;line=None;minsep=1e9
  for upper,lower,edge in [(a,b,'bottom'),(b,a,'top')]:
   cap=project(ats[upper],tex[upper][edge],upper);dist,ind=cache[lower][1].query(cap);near=cache[lower][0][ind];minsep=min(minsep,float(dist.min()))
   for A,B,d in zip(cap,near,dist):
    if d<1:continue
    n=max(2,int(np.ceil(d*4))+1);pts=np.linspace(A,B,n);rgb=np.array([map_coordinates(im[:,:,c],[pts[:,1],pts[:,0]],order=0,mode='constant',cval=232) for c in range(3)]).T;bg=(np.abs(rgb.astype(int)-232)<=6).all(1);run=0;longest=0;start=0;longstart=0
    for i,z in enumerate(bg):
     if z:
      if run==0:start=i
      run+=1
      if run>longest:longest=run;longstart=start
     else:run=0
    gap=longest*d/(n-1)
    if gap>best:best=gap;line=[pts[longstart].tolist(),pts[min(n-1,longstart+longest-1)].tolist()]
  r={'frame':f['index'],'time':f['time'],'joint':name,'upper':a,'lower':b,'max_visible_gap_px':round(best,2),'min_terminal_to_other_alpha_px':round(minsep,2),'line':line};rows.append(r)
  if name not in worst or best>worst[name]['max_visible_gap_px']:worst[name]=r
  if f['index'] in [237,305]:selected.append(r)
for name,r in worst.items():
 im=Image.open(frames/f"f{r['frame']:04d}.png").convert('RGB');line=r['line'];center=np.mean(line,0) if line else [368,700];box=(int(center[0]-60),int(center[1]-60),int(center[0]+60),int(center[1]+60));crop=im.crop(box);d=ImageDraw.Draw(crop)
 if line:d.line([(x-box[0],y-box[1]) for x,y in line],fill='red',width=1)
 crop=crop.resize((480,480));ImageDraw.Draw(crop).text((8,8),f"{name} f{r['frame']} {r['max_visible_gap_px']}px",fill='red');crop.save(out/(name+'-worst.png'))
(out/'measurements.json').write_text(json.dumps({'method':__doc__,'frame_scale':scale,'rows':rows,'worst':worst,'selected':selected},indent=2));print(json.dumps(worst,indent=2))
