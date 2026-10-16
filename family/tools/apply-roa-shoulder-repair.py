#!/usr/bin/env python3
"""Restore the bounded source-backed shoulder as authoring input; official build/check must follow."""
import argparse, hashlib, json, shutil
from pathlib import Path
from PIL import Image

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def require_hash(path, expected, code):
    if not path.is_file() or digest(path) != expected: raise ValueError(f'{code}: {path}')
def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-out',required=True);parser.add_argument('--out',required=True);parser.add_argument('--policy',required=True)
    args=parser.parse_args();source=Path(args.source_out).resolve();out=Path(args.out).resolve();policy_path=Path(args.policy).resolve();policy=json.loads(policy_path.read_text());home=policy_path.parent
    if policy.get('spec')!='roa-shoulder-repair/1': raise ValueError('ROA_SHOULDER_POLICY_REQUIRED')
    if out.exists() or source==out or source in out.parents:raise ValueError('ROA_SHOULDER_FRESH_OUTSIDE_OUTPUT_REQUIRED')
    actual={str(p.relative_to(source)) for sub in ['rig','parts'] for p in (source/sub).rglob('*') if p.is_file()}|{'parts.json'}
    if actual!=set(policy['sourceManifest']):raise ValueError('ROA_SHOULDER_SOURCE_INVENTORY_CHANGED')
    for path,sha in policy['sourceManifest'].items():require_hash(source/path,sha,'ROA_SHOULDER_SOURCE_CHANGED')
    for path,sha in policy['assets'].items():require_hash(home/path,sha,'ROA_SHOULDER_ASSET_CHANGED')
    for path,sha in policy['sourceArt'].items():require_hash(source.parent/path,sha,'ROA_SHOULDER_ORIGINAL_CHANGED')
    # Enforce the exact bitmap boundary independently of content hashes.
    old=Image.open(source/'parts/topwear.png').convert('RGBA');new=Image.open(home/policy['partsImage']).convert('RGBA');mask=Image.open(home/policy['mask']).convert('RGBA')
    if old.size!=new.size or old.size!=mask.size:raise ValueError('ROA_SHOULDER_IMAGE_DOMAIN_CHANGED')
    rig_image=Image.open(home/policy['rigImage']).convert('RGBA')
    if rig_image.size!=(new.width+8,new.height+8) or rig_image.crop((4,4,new.width+4,new.height+4)).tobytes()!=new.tobytes():raise ValueError('ROA_SHOULDER_RIG_PARTS_PIXELS_DIFFER')
    roi=policy['cropROI'];offset=policy['partOffset'];changed=0
    for i,(a,b,m) in enumerate(zip(old.getdata(),new.getdata(),mask.getdata())):
        if a==b:continue
        x=i%old.width+offset[0];y=i//old.width+offset[1]
        if m[3]==0 or not(roi[0]<=x<=roi[2] and roi[1]<=y<=roi[3]):raise ValueError(f'ROA_SHOULDER_OUTSIDE_MASK pixel={i}')
        if b[3]<a[3]:raise ValueError(f'ROA_SHOULDER_ALPHA_ERASED pixel={i}')
        changed+=1
    rig=json.loads((source/'rig/rig.json').read_text());a=rig['skins']['default']['topwear']['topwear'];before=json.loads(json.dumps(a));allowed=set()
    for change in policy['vertices']:
        i=change['vertex'];allowed.add(i)
        if i>=a['hull']:raise ValueError('ROA_SHOULDER_ONLY_HULL_VERTICES')
        a['uvs'][i*2:i*2+2]=change['uvs']
        for w in a['weights'][i]:w['x']+=change['delta'][0];w['y']-=change['delta'][1]
    if a['triangles']!=before['triangles']:raise ValueError('ROA_SHOULDER_TOPOLOGY_CHANGED')
    for i,row in enumerate(a['weights']):
        if [w['weight'] for w in row]!=[w['weight'] for w in before['weights'][i]]:raise ValueError('ROA_SHOULDER_SCALAR_WEIGHT_CHANGED')
        if i not in allowed and (row!=before['weights'][i] or a['uvs'][2*i:2*i+2]!=before['uvs'][2*i:2*i+2]):raise ValueError('ROA_SHOULDER_INTERIOR_CHANGED')
    text=json.dumps(rig,indent=2)+'\n'
    if hashlib.sha256(text.encode()).hexdigest()!=policy['outputRigSHA256']:raise ValueError('ROA_SHOULDER_OUTPUT_RIG_CHANGED')
    out.mkdir(parents=True);shutil.copytree(source/'rig',out/'rig');shutil.copytree(source/'parts',out/'parts')
    (out/'rig/rig.json').write_text(text)
    for asset,target in policy['outputs'].items():
        (out/target).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(home/asset,out/target)
    for path,sha in policy['outputManifest'].items():require_hash(out/path,sha,'ROA_SHOULDER_OUTPUT_CHANGED')
    record={'spec':'roa-shoulder-repair-result/1','policySHA256':digest(policy_path),'changedPixels':changed,'hullVertices':sorted(allowed),'scope':'Bounded original-head shirt pixels and five existing topwear hull vertices only. Triangles, scalar weights, all interior vertices, all other attachments/bones/constraints/stops/motion unchanged. Normal official build/check required.','visibilityProvenance':policy['visibilityProvenance']}
    (out/'rig/shoulder-repair.provenance.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
if __name__=='__main__':run()
