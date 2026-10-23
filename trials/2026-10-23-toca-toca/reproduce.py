"""Sequential reproduction from public inputs; optional per-command resource guard."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path

assert hashlib.sha256(Path('acquisition/pose.json').read_bytes()).hexdigest() == 'fe3327cb0f8772f51d3b656889e60fe7a613156391f9dbcff5f40e3141fb9ff1'
commands=[]
def run(label, command, cwd=None):
    guard=os.environ.get('TRIAL_GUARD')
    invoked=([sys.executable,str(Path(guard).resolve()),'--label',label,'--'] if guard else [])+command
    print('REPRO_COMMAND',label,json.dumps(command),flush=True)
    result=subprocess.run(invoked,cwd=cwd)
    commands.append({'stage':label,'command':command,'cwd':cwd or '.','exitCode':result.returncode})
    Path('work').mkdir(exist_ok=True)
    Path('work/commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    if result.returncode:raise SystemExit(result.returncode)
run('fetch',[sys.executable,'fetch-inputs.py','--out','work/corpus'])
Path('work/runtime').mkdir(parents=True,exist_ok=True)
shutil.copy2('package.json','work/runtime/package.json')
shutil.copy2('bun.lock','work/runtime/bun.lock')
run('install',['bun','install'],cwd='work/runtime')
binpath=Path('work/runtime/node_modules/.bin')
def cli(tool,*args):return ['bun','--bun','run',str(binpath/tool),*args]
run('parts',cli('rig-parts','build','--config','rig-config/config.json','--source','work/corpus/wind/painting.png','--full','work/corpus/wind/layers/full','--head','work/corpus/wind/layers/head','--out','work/wind'))
# 1.0.1 accepts rig-c-pose-frames/0 as-is: no conversion changes detector values.
run('clean',cli('rig-pose','clean','--pose','acquisition/pose.json','--out','work/cleanedpose.json','--legs','5','--rest','7'))
run('retarget',cli('rig-pose','retarget','--rig','work/wind/rig','--map','map.json','--sequence','work/cleanedpose.json','--out','work/motion.json','--animation','toca-toca','--plant-feet','--profile','spine-html','--parts','work/wind/parts.json','--reference','withheld/orig.webm','--report','work/report.json','--build','work/build'))
site=Path('work/site');site.mkdir(exist_ok=True)
shutil.copy2('play.html',site/'index.html')
shutil.copy2('work/runtime/node_modules/@rig-c/play/dist/index.js',site/'player.js')
shutil.copytree('work/build',site/'build',dirs_exist_ok=True)
shutil.copytree('work/wind/rig/images',site/'wind/rig/images',dirs_exist_ok=True)
record={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('work/cleanedpose.json'),Path('work/wind/rig/rig.json'),Path('work/build/skeleton.model.json')]}
Path('work/reproduction-hashes.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2),flush=True)
# Optional actual UI: python3 -m http.server 8763 --bind 127.0.0.1 --directory work/site
