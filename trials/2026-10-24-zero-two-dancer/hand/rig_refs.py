"""Resolve declared hash references and reconstruct portable rig adapters only."""
import argparse,copy,hashlib,json
from pathlib import Path
REFERENCE=Path('hand/r3/rig-reference.json')
def digest(data):return hashlib.sha256(data).hexdigest()
def rig_bytes(variant='final'):
 record=json.loads(REFERENCE.read_text());source=(REFERENCE.parent/record['canonical']['path']).resolve();data=source.read_bytes();assert digest(data)==record['canonical']['sha256'],'canonical rig hash mismatch';rig=json.loads(data);adapter=record['adapters'][variant]
 for patch in adapter['patch']:
  assert patch['op']=='replace' and patch['path']=='/images','only the recorded portable images adapter is permitted';rig['images']=patch['value']
 fmt=adapter['serialization'];data=(json.dumps(rig,indent=fmt['indent'],ensure_ascii=fmt['ensureAscii'])+('\n' if fmt['trailingNewline'] else '')).encode();assert digest(data)==adapter['expectedSHA256'],variant+' reconstructed rig hash mismatch';return data
def load_rig(variant='historical'):return json.loads(rig_bytes(variant))
def load_corrections():
 ref=Path('hand/r3/source-corrections-reference.json');r=json.loads(ref.read_text());data=(ref.parent/r['target']).read_bytes();assert digest(data)==r['targetSHA256'],'source correction hash mismatch';return json.loads(data)
def materialize_rig():
 r=json.loads(REFERENCE.read_text());p=Path(r['adapters']['final']['materializedPath']);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(rig_bytes('final'));return p
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--materialize',action='store_true');a=p.parse_args();result={name:digest(rig_bytes(name)) for name in ['final','historical']};load_corrections()
 if a.materialize:result['materialized']=str(materialize_rig())
 print(json.dumps(result,sort_keys=True))
