"""Rebuild the accepted dance from this corpus alone; no trial imports or inference."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys
source=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--out',default='work/accepted-dance');p.add_argument('--version',choices=['v1','v3'],default='v3');p.add_argument('--preflight',action='store_true');a=p.parse_args()
if a.version=='v3':
 args=[sys.executable,str(source/'tools/reproduce-accepted-dance-v3.py'),'--out',a.out]
 if a.preflight:args.append('--preflight')
 os.execv(sys.executable,args)
workspace=Path(a.out).resolve()
if workspace.exists():raise SystemExit('OUTPUT_EXISTS: choose a new output directory; existing evidence is preserved')
record=json.loads((source/'declared-repairs.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def baseline_sha(row):
 path=source/row['file']
 if row.get('hashMode')=='json-indent2-lf-without-x-repairs':
  config=json.loads(path.read_text());config.pop('x-repairs',None)
  return hashlib.sha256((json.dumps(config,indent=2,ensure_ascii=False)+'\n').encode()).hexdigest()
 if 'hashMode' in row:raise SystemExit('BASELINE_HASH_MODE: '+row['file'])
 return sha(path)
config=json.loads((source/'config.json').read_text())
if config.get('x-repairs')!={'file':'declared-repairs-v3.json','sha256':sha(source/'declared-repairs-v3.json')}:raise SystemExit('REPAIRS_HASH: current config.json x-repairs')
for row in record['baseline'].values():
 if baseline_sha(row)!=row['sha256']:raise SystemExit('BASELINE_HASH: '+row['file'])
subprocess.run([sys.executable,'check-inputs.py'],cwd=source,check=True)
if a.preflight:print('V1_PREFLIGHT_PASS: historical baseline hashes; current metadata pin; full corpus closure');sys.exit(0)
workspace.mkdir(parents=True);corpus=workspace/'work/corpus/dancer';shutil.copytree(source,corpus,ignore=shutil.ignore_patterns('work','node_modules','__pycache__','.git'))
runtime=workspace/'work/runtime';runtime.mkdir(parents=True)
for name in ['package.json','bun.lock']:shutil.copy2(corpus/'accepted-dance'/name,runtime/name)
h=workspace/'hand/r3';h.mkdir(parents=True);shutil.copy2(corpus/'accepted-dance/viewport.json',h/'viewport.json');logs=workspace/'logs';logs.mkdir();commands=[]
env=dict(os.environ)
for k in ['UV_THREADPOOL_SIZE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','RAYON_NUM_THREADS']:env[k]='4'
def run(label,cmd,cwd=workspace):
 print('ACCEPTED_COMMAND',label,json.dumps(cmd),flush=True);commands.append({'label':label,'command':cmd,'cwd':'work/runtime' if cwd==runtime else '.'})
 with (logs/(label+'.txt')).open('w') as log:
  process=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace')
  for line in process.stdout:log.write(line);log.flush();print(line,end='',flush=True)
  code=process.wait()
 if code:raise SystemExit(code)
run('install',['bun','install','--frozen-lockfile'],runtime)
pose=['bun','--bun','run','work/runtime/node_modules/.bin/rig-pose'];core=['bun','--bun','run','work/runtime/node_modules/.bin/rigc']
run('retarget',pose+['retarget','--rig','work/corpus/dancer/accepted','--map','work/corpus/dancer/map.json','--sequence','work/corpus/dancer/accepted/sequence.json','--out','hand/r3/work/retarget/motion.json','--animation','zero-two-r3','--profile','spine','--build','hand/r3/work/retarget/build','--camera','hand/r3/work/retarget/camera.json','--report','hand/r3/work/retarget/report.json','--flip','90','--short','0.35','--bends','clamp','--leg-scale','0.8,1.05','--plant-feet','--stance','0.04','--carry-idle','--raised-by-head'])
run('before-geometry',core+['render','--candidate','hand/r3/work/retarget/build','--animation','zero-two-r3','--fps','30','--geometry','--folds','--viewport-from','hand/r3/viewport.json','--out','hand/r3/work/before-render'])
run('apply-declared',[sys.executable,'work/corpus/dancer/tools/apply-accepted-dance.py'])
run('final-build',core+['build','--rig','hand/r3/rig.json','--motion','hand/r3/motion.json','--out','hand/r3/work/build','--profile','spine'])
run('final-geometry',core+['render','--candidate','hand/r3/work/build','--animation','zero-two-r3-hand','--fps','30','--geometry','--folds','--pass-through','bottomwear:thigh_r,bottomwear:thigh_l,bottomwear:shins','--viewport-from','hand/r3/viewport.json','--out','hand/r3/work/final-render'])
checks={'compiledModelSHA256':sha(h/'work/build/skeleton.model.json'),'finalRigSHA256':sha(h/'rig.json'),'finalMotionSHA256':sha(h/'motion.json'),'finalGeometrySHA256':sha(h/'work/final-render/zero-two-r3-hand@30fps/geometry.json')}
result={'spec':'dancer-accepted-reproduction/1','commands':commands,'hashes':checks,'expected':record['expected'],'matches':{k:v==record['expected'][k] for k,v in checks.items()},'source':'dancer corpus only; no trial or historical checkout dependency','geometryProof':'Exact full geometry-file byte hash, not merely a foot residual; all391 sample records included','inputFrames':313,'inputFPS':24,'renderFrames':391,'renderFPS':30,'output':'hand/r3/work/build','ownerAcceptedVideo':'The reference video was accepted on2026-10-24; this command reproduces its rig/animation, not a new owner acceptance.'};(workspace/'reproduction.json').write_text(json.dumps(result,indent=2)+'\n');print('ACCEPTED_REPRODUCTION',json.dumps(result),flush=True)
if not all(result['matches'].values()):raise SystemExit('REPRODUCTION_HASH_MISMATCH: inspect reproduction.json; no tolerance or geometry changes are applied')
