from pathlib import Path
import json,math,hashlib
import numpy as np,cv2
from PIL import Image
out=Path('hand');rig=json.loads((out/'rig.json').read_text());parents={b['name']:b.get('parent') for b in rig['bones']};changes=json.loads((out/'changes.json').read_text());goals={x['frame']:x['handGoal'] for x in changes['foot']};results={}
for tag,path in [('before','hand/work/before-render/zero-two@24fps'),('after','hand/work/final-render/zero-two-hand@24fps')]:
 G=json.loads((Path(path)/'geometry.json').read_text());v=G['viewport'];angles=[];overlap=[];head=[];targets=[];setrows=[];feet=[];source={n:np.asarray(Image.open('work/corpus/dancer/accepted/images/'+n+'.png').convert('RGBA'))[:,:,3] for n in ['shoe_r','shoe_l']}
 for f in G['frames']:
  bs={b['name']:b for b in f['bones']};b=bs['skirt_swing'];a=bs[parents['skirt_swing']];x=math.degrees(math.atan2(b['c'],b['a'])-math.atan2(a['c'],a['a']));angles.append((x+180)%360-180)
  ats={a['slot']:a for a in f['attachments']};setrows.append({'frame':f['index'],'time':f['time'],'topwear':ats.get('topwear',{}).get('attachment')})
  if 4<=f['time']<=220/30+1e-8:head.append({'frame':f['index'],'time':f['time'],'bothK1HandsPresent':all(any(a.get('attachment')=='K1_forearm_'+s for a in f['attachments']) for s in ['r','l'])})
  if f['time']>=337/30-1e-8:
   masks=[]
   for n in ['shoe_r','shoe_l']:
    att=ats[n];q=np.array(att['vertices']).reshape(4,2);q=np.column_stack([(q[:,0]-v['x'])*v['scale'],(v['y']+v['height']-q[:,1])*v['scale']]);im=source[n];h,w=im.shape;M=cv2.getPerspectiveTransform(np.array([[0,h-1],[0,0],[w-1,0],[w-1,h-1]],np.float32),q.astype(np.float32));m=cv2.warpPerspective(im,M,(v['pixelWidth'],v['pixelHeight']),flags=cv2.INTER_LINEAR)>128;masks.append(m)
   overlap.append({'frame':f['index'],'time':f['time'],'shoeOverlapPixels':int((masks[0]&masks[1]).sum())})
  if f['index'] in goals:
   R=bs['foot_r'];L=bs['foot_l'];target=goals[f['index']];targets.append({'frame':f['index'],'time':f['time'],'errorToNewHandGoal':math.hypot(R['worldX']-target[0],R['worldY']-target[1])});feet.append({'frame':f['index'],'time':f['time'],'separationX':L['worldX']-R['worldX'],'heightDiff':R['worldY']-L['worldY']})
 spans=[]
 for row in setrows:
  if not spans or spans[-1]['attachment']!=row['topwear']:spans.append({'attachment':row['topwear'],'startFrame':row['frame'],'endFrame':row['frame'],'startSeconds':row['time'],'lastSampleSeconds':row['time']})
  else:spans[-1].update(endFrame=row['frame'],lastSampleSeconds=row['time'])
 results[tag]={'skirtSwing':{'min':min(angles),'max':max(angles),'spanDeg':max(angles)-min(angles)},'shoeOverlap':overlap,'shoeOverlapMax':max(overlap,key=lambda x:x['shoeOverlapPixels']),'headHandActivity':head,'topwearSpans':spans,'handGoalResiduals':targets,'maxHandGoalResidual':max(targets,key=lambda x:x['errorToNewHandGoal']),'endingFeet':feet,'folds':json.loads((Path(path)/'folds.json').read_text())}
results['method']='Exact v5 verify.py skirt angle and shoe alpha perspective-warp algorithms, same viewport, seconds-aligned ending >=337/30. New hand-goal residual is descriptive, not original pose LAND.';results['physicsCount']=sum(c['type']=='physics' for c in rig['constraints']);(out/'measurements.json').write_text(json.dumps(results,indent=2)+'\n');print('HAND_MEASURE_SUMMARY',json.dumps({k:{n:v[n] for n in ['skirtSwing','shoeOverlapMax','maxHandGoalResidual']} for k,v in results.items() if isinstance(v,dict)}),flush=True)
