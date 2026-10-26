"""Reproduce from the committed acquisition; never repeat inference implicitly."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert sha('acquisition/pose.json')=='228dc7f3ffdf52932512243dbbcc09eb3c1ce4fb94ed52578622b4b8c445657f'
assert sha('source-map.json')=='9dca5394f6c0cf9cc72e2456b53b41adf898b963a6081d9f6f9b3c2ad6191096'
original=json.loads(Path('source-map.json').read_text());derived=json.loads(Path('map.json').read_text())
for chain in original['chains']:
    if chain['name'] in ['leg_r','leg_l']: chain['bend']='free'
assert original==derived
commands=[]
def run(label,command,cwd=None):
    guard=os.environ.get('TRIAL_GUARD')
    invoked=([sys.executable,str(Path(guard).resolve()),'--label',label,'--'] if guard else [])+command
    print('REPRO_COMMAND',label,json.dumps(command),flush=True)
    result=subprocess.run(invoked,cwd=cwd)
    commands.append({'stage':label,'command':command,'cwd':cwd or '.','exitCode':result.returncode})
    Path('work').mkdir(exist_ok=True)
    Path('work/commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    if result.returncode: raise SystemExit(result.returncode)
run('fetch',[sys.executable,'fetch-inputs.py','--out','work/corpus'])
assert sha('work/corpus/dancer/accepted/rig.json')=='490fd2116a5c7b5c1188be010d6091b68c35c2d837475cd8540f631367da08d6'
assert sha('work/corpus/dancer/map.json')==sha('source-map.json')
Path('work/runtime').mkdir(parents=True,exist_ok=True)
for filename in ['package.json','bun.lock']: shutil.copy2(filename,Path('work/runtime')/filename)
run('install',['bun','install','--frozen-lockfile'],cwd='work/runtime')
binpath=Path('work/runtime/node_modules/.bin')
def cli(tool,*args): return ['bun','--bun','run',str(binpath/tool),*args]
run('clean',cli('rig-pose','clean','--pose','acquisition/pose.json','--out','work/cleanedpose.json','--legs','5','--rest','7'))
assert sha('work/cleanedpose.json')=='8a45320006253d8bff0e14366659afff89877dced434b5a90f3e34c39332f903'
run('retarget',cli('rig-pose','retarget','--rig','work/corpus/dancer/accepted','--map','map.json','--sequence','work/cleanedpose.json','--out','work/motion.json','--animation','zero-two','--plant-feet','--profile','spine','--reference','withheld/orig.webm','--report','work/report.json','--build','work/build'))
site=Path('work/site');site.mkdir(exist_ok=True)
shutil.copy2('play.html',site/'index.html')
shutil.copy2('work/runtime/node_modules/@rig-c/play/dist/index.js',site/'player.js')
shutil.copytree('work/build',site/'build',dirs_exist_ok=True)
shutil.copytree('work/corpus/dancer/accepted/images',site/'corpus/dancer/accepted/images',dirs_exist_ok=True)
paths=['work/cleanedpose.json','work/motion.json','work/build/skeleton.model.json','work/build/skeleton.json','work/build/skeleton.atlas']
record={p:sha(p) for p in paths}
Path('work/reproduction-hashes.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2),flush=True)
# Optional actual UI: python3 -m http.server 8765 --bind 127.0.0.1 --directory work/site
