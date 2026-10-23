"""Apply named accepted hand corrections to the fresh phase1 motion, never the old full motion."""
import argparse,copy,json,math,bisect,statistics,hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path('hand').resolve()))
from rig_refs import load_rig,load_corrections,materialize_rig
p=argparse.ArgumentParser();p.add_argument('--rig',default='work/corpus/dancer/accepted/rig.json');p.add_argument('--motion',default='hand/r3/work/retarget/motion.json');p.add_argument('--geometry',default='hand/r3/work/before-render/zero-two-r3@30fps/geometry.json');a=p.parse_args()
source=load_corrections();originalRig=json.loads(Path(a.rig).read_text());rig=copy.deepcopy(originalRig);motion=json.loads(Path(a.motion).read_text());original=copy.deepcopy(motion['animations']['zero-two-r3']);animation=copy.deepcopy(original)
assert rig['bones']==source['sourceBones'] and rig['constraints']==source['sourcePhysicsConstraints'] and rig['slots']==source['sourceSlots']
assert rig['skins']['default']['bottomwear']==source['sourceBottomwear']
assert sum(c['type']=='physics' for c in rig['constraints'])==11
for item in source['attachments']:rig['skins']['default'][item['slot']][item['attachment']]=copy.deepcopy(item['value'])
# Exact existing attachment-selection corrections only. Fresh joint keys are not replaced.
attachmentSlots={t['slot'] for t in source['attachmentTracks']}
setup={s['name']:s.get('attachment') for s in rig['slots']}
newTracks=[copy.deepcopy(t) for t in animation['tracks'] if t['property']!='attachment']
newTracks.extend(copy.deepcopy(source['attachmentTracks']))
for t in original['tracks']:
 if t['property']=='attachment' and t['slot'] not in attachmentSlots:newTracks.append({'slot':t['slot'],'property':'attachment','keys':[{'t':0,'v':setup[t['slot']]}]})
animation['tracks']=newTracks
geometry=json.loads(Path(a.geometry).read_text());frames=geometry['frames'];assert len(frames)==391 and abs(frames[-1]['time']-13)<1e-8
bones={b['name']:b for b in rig['bones']};rot=next(t for t in animation['tracks'] if t.get('bone')=='leg_r1' and t['property']=='rotate');scale=next(t for t in animation['tracks'] if t.get('bone')=='leg_r1' and t['property']=='scalex')
def value(track,t):
 keys=track['keys'];i=bisect.bisect_right([k['t'] for k in keys],t)-1
 if i<0:return keys[0]['v'][0]
 if i+1>=len(keys):return keys[-1]['v'][0]
 A,B=keys[i],keys[i+1];return A['v'][0]+(B['v'][0]-A['v'][0])*(t-A['t'])/(B['t']-A['t'])
rule=source['endingFootRule'];floor=statistics.median(next(b for b in f['bones'] if b['name']=='foot_l')['worldY'] for f in frames if f['time']>=rule['floorFromLeftFootAtOrAfterSeconds']-1e-8)
R=[copy.deepcopy(k) for k in rot['keys'] if k['t']<rule['startSeconds']];S=[copy.deepcopy(k) for k in scale['keys'] if k['t']<rule['startSeconds']];foot=[]
for f in frames:
 t=f['time']
 if t<rule['startSeconds']:continue
 bs={b['name']:b for b in f['bones']};fr,fl,knee,parent=[bs[n] for n in ['foot_r','foot_l','leg_r1','leg_r0']]
 z=min(1,max(0,(t-rule['startSeconds'])/rule['blendSeconds']));blend=z*z*(3-2*z);target=[min(fr['worldX'],fl['worldX']-rule['separationUnits']),floor];goal=[min(fr['worldX'],fl['worldX']-rule['separationUnits']),fr['worldY']*(1-blend)+target[1]*blend]
 dx,dy=goal[0]-knee['worldX'],goal[1]-knee['worldY'];A,B,C,D=[parent[k] for k in ['a','b','c','d']];det=A*D-B*C;assert abs(det)>1e-10
 x,y=(D*dx-B*dy)/det,(-C*dx+A*dy)/det;theta=math.degrees(math.atan2(y,x))-bones['leg_r1'].get('rotation',0);old=value(rot,t)
 while theta-old>180:theta-=360
 while theta-old< -180:theta+=360
 length=math.hypot(x,y)/bones['foot_r']['x'];R.append({'t':round(t,8),'v':[round(theta,6)]});S.append({'t':round(t,8),'v':[round(length,6)]});foot.append({'frame':f['index'],'time':t,'beforeFoot':[fr['worldX'],fr['worldY']],'handGoal':goal,'shinRotate':theta,'shinScaleX':length})
rot['keys']=R;scale['keys']=S
# Every non-right-shin joint/channel track is the fresh phase1 track, byte-value equal.
byKey={(t.get('bone'),t['property']):t for t in animation['tracks'] if 'bone' in t};preserved=[]
for t in original['tracks']:
 if 'bone' in t and t['bone']!='leg_r1':assert byKey[t['bone'],t['property']]==t;preserved.append([t['bone'],t['property']])
assert rig['bones']==originalRig['bones'] and rig['constraints']==originalRig['constraints'] and rig['slots']==originalRig['slots'] and rig['skins']['default']['bottomwear']==originalRig['skins']['default']['bottomwear']
actualMeshes=sum(at.get('type')=='mesh' for sl in rig['skins']['default'].values() for at in sl.values());assert actualMeshes==source['sourceMeshInventory']==17
rig['invariants']['meshSlots']=actualMeshes # exact authored inventory, not a geometry/fidelity tolerance
assert rig==load_rig('historical'), 'All original v5 rig fields must match before portable path normalization'
rig['images']='../../work/corpus/dancer/accepted/images'
del motion['animations']['zero-two-r3'];motion['animations']['zero-two-r3-hand']=animation
out=Path('hand/r3');out.mkdir(exist_ok=True);assert rig==load_rig('final');materialize_rig();(out/'motion.json').write_text(json.dumps(motion,indent=2)+'\n');(out/'changes.json').write_text(json.dumps({'source':'../source-corrections.json','alignment':'seconds unchanged, source30fps/current24fps, no pose retiming','attachmentTrackCount':len(source['attachmentTracks']),'namedAttachmentCount':len(source['attachments']),'footRule':rule,'floorDerivedFromCurrentGeometry':floor,'foot':foot,'preservedFreshBoneTracks':preserved,'physicsCount':11,'skirtBonesConstraintsSlotsAndAttachmentUnchanged':True,'meshInventoryBefore':originalRig['invariants']['meshSlots'],'meshInventoryAfter':actualMeshes,'retargetLAND':'R3 20/20 before hand; not an after-hand claim'},indent=2)+'\n');print('HAND_APPLIED',len(source['attachmentTracks']),'source attachment tracks;',len(foot),'fresh right-shin foot samples; 11 physics; other joint tracks preserved',flush=True)
