"""Targeted file/map closure only; not a render or rig correctness gate."""
from pathlib import Path
import hashlib,json
root=Path('.')
manifest=json.loads(Path('source-manifest.json').read_text())
for row in manifest['files']:
    file=Path(row['path'])
    assert file.is_file(), 'MISSING_SOURCE: '+row['path']
    assert hashlib.sha256(file.read_bytes()).hexdigest()==row['sha256'], 'SOURCE_HASH: '+row['path']
for name in ['config.json','config-base.json']:
    config=json.loads(Path(name).read_text())
    for cut in config['assemble'].get('cuts',[]):
        if 'under' in cut:assert Path(cut['under']).is_file(), 'MISSING_UNDER: '+cut['under']
    assert Path(config['motion']['animations_from']).is_file()
for side in ['full','head']:
    directory=Path('layers')/side
    layers=json.loads((directory/'layers.json').read_text())['layers']
    assert len(layers)==29
    for layer in layers:assert (directory/'parts'/(layer['name']+'.png')).is_file(), layer['name']
rig=json.loads(Path('accepted/rig.json').read_text())
bones={b['name']:b for b in rig['bones']};slots={s['name']:s for s in rig['slots']}
skin=rig['skins']['default'];mapping=json.loads(Path('map.json').read_text())
for chain in mapping['chains']:
    for bone in chain['bones']:assert bone in bones, bone
    for parent,child in zip(chain['bones'],chain['bones'][1:]):assert bones[child].get('parent')==parent
for alternate in mapping['alternates']:
    for slot,attachment in alternate['slots'].items():assert attachment in skin.get(slot,{}), slot+':'+attachment
    for slot in alternate.get('hides',[]):assert slot in slots, slot
for face in mapping.get('face',{}).values():assert face['bone'] in bones
images=rig.get('images','images')
for attachments in skin.values():
    for attachment in attachments.values():
        if 'image' in attachment:assert (Path('accepted')/images/attachment['image']).is_file(), attachment['image']
physics=sum(c.get('type')=='physics' for c in json.loads(Path('config.json').read_text())['constraints'])
assert physics==11
v3=json.loads(Path('declared-repairs-v3.json').read_text())
assert json.loads(Path('config.json').read_text())['x-repairs']=={'file':'declared-repairs-v3.json','sha256':hashlib.sha256(Path('declared-repairs-v3.json').read_bytes()).hexdigest()}, 'V3_METADATA_PIN'
for row in list(v3['canonical'].values())+v3['parts']+v3['generation']+[v3['previousRepairs']]:
    assert hashlib.sha256(Path(row['file']).read_bytes()).hexdigest()==row['sha256'], 'V3_SOURCE_HASH: '+row['file']
v3rig=json.loads(Path(v3['canonical']['rig']['file']).read_text())
for attachments in v3rig['skins']['default'].values():
    for attachment in attachments.values():
        if 'image' in attachment:assert (Path('accepted/images')/attachment['image']).is_file(), 'V3_IMAGE: '+attachment['image']
assert [s['name'] for s in v3rig['slots']]==v3['slotOrder'], 'V3_SLOT_ORDER'
assert sum(c.get('type')=='physics' for c in v3rig['constraints'])==11, 'V3_PHYSICS_PRESERVED'
print('CLOSURE PASS: source hashes; full/head29+29; under/stress;11physics config; accepted-map bones/slots/attachments/images.')
print('V3 CLOSURE PASS: canonical accepted bytes; 3 new parts; metadata and prior-v1 pins; exact slot order; 11 physics.')

# Current producer adoption is separate from the immutable accepted dance history.
producer_manifest=Path('producer-manifest.json')
if producer_manifest.exists():
    current=json.loads(producer_manifest.read_text())
    assert current['spec']=='dancer-producer/1', 'PRODUCER_SCHEMA'
    for file,key in [('config.json','configSHA256'),('package.json','packageSHA256')]:
        assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==current[key], 'PRODUCER_INPUT_HASH: '+file
    for file,row in current['files'].items():
        data=(Path('producer')/file).read_bytes()
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'], 'PRODUCER_FILE_HASH: '+file
    print('PRODUCER CLOSURE PASS: canonical adopted file bytes and active config/package pins.')
