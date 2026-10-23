"""Encode existing pinned core-render PNGs; this is not a browser screen recording."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--frames',default='work/fold-diagnostic/toca-toca@30fps')
p.add_argument('--out',default='work/recording/toca-toca-dancer-core-render.mp4')
p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe')
a=p.parse_args();frames=Path(a.frames);output=Path(a.out)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
manifest=json.loads(Path('fold-diagnostic/hashes.json').read_text())['files']
expected={Path(r['path']).name:r['sha256'] for r in manifest if Path(r['path']).name.startswith('f') and Path(r['path']).suffix=='.png'}
assert len(expected)==492
assert sorted(expected)==[f'f{i:04d}.png' for i in range(492)]
for name,digest in expected.items():assert sha(frames/name)==digest,name
versions={name:subprocess.check_output([exe,'-version'],text=True).splitlines()[0] for name,exe in [('ffmpeg',a.ffmpeg),('ffprobe',a.ffprobe)]}
output.parent.mkdir(parents=True,exist_ok=True)
command=[a.ffmpeg,'-hide_banner','-loglevel','error','-y','-framerate','30','-start_number','0','-i',str(frames/'f%04d.png'),'-frames:v','492','-an','-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2,setsar=1','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-threads','4',str(output)]
print('ENCODE_COMMAND',json.dumps(command),flush=True);subprocess.run(command,check=True)
probe=json.loads(subprocess.check_output([a.ffprobe,'-v','error','-count_frames','-show_entries','stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,sample_aspect_ratio,pix_fmt:format=duration','-of','json',str(output)],text=True))
video=[s for s in probe['streams'] if s['codec_type']=='video'];assert len(video)==1
assert video[0]['nb_read_frames']=='492' and video[0]['r_frame_rate']=='30/1'
assert video[0]['width']==186 and video[0]['height']==256
record={'kind':'CLI rendered animation, not an actual Play screen recording','sourceCompiledSHA256':'cc8205444b76ae2c312d4a15f41bd44b56b1c3f7d0f56dd4e3fa28268e921577','sourceFrameManifest':'fold-diagnostic/hashes.json','frameCount':492,'fps':30,'sourcePoser':'rig-c 2.67.2 core; 11 physics constraints stepped at 30 fps','versions':versions,'command':command,'video':str(output),'bytes':output.stat().st_size,'sha256':sha(output),'probe':probe,'noAcquisitionCleanRetargetBuildOrRenderRepeated':True}
output.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n');print('VIDEO_RESULT',json.dumps(record),flush=True)
