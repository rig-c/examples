"""Encode f240-290: v3/v4 full figures and both flanks at 4x nearest."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('v3');p.add_argument('v4');p.add_argument('out')
p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe')
a=p.parse_args();out=Path(a.out).resolve();out.parent.mkdir(parents=True,exist_ok=True)
caption=out.with_suffix('.caption.png');im=Image.new('RGBA',(3072,32),(16,16,16,255));draw=ImageDraw.Draw(im);font=ImageFont.load_default(size=18)
for x,text in [(8,'V3 ACCEPTED | full figure; 4x nearest left / right flank'),(1544,'V4 SMEAR50 CANDIDATE | full figure; 4x nearest left / right flank')]:draw.text((x,6),text,fill='white',font=font)
im.save(caption)
windows=a.ffmpeg.lower().endswith('.exe')
def path(file):
    file=str(Path(file).resolve())
    return subprocess.check_output(['wslpath','-w',file],text=True).strip() if windows else file
filters=[]
for i in [0,1]:
    filters += [f'[{i}:v]split=3[f{i}][l{i}][r{i}]',f'[f{i}]pad=736:1600:0:0:color=0x181818,setsar=1[full{i}]',f'[l{i}]crop=200:200:220:380,scale=800:800:flags=neighbor,setsar=1[left{i}]',f'[r{i}]crop=200:200:420:380,scale=800:800:flags=neighbor,setsar=1[right{i}]',f'[left{i}][right{i}]vstack=inputs=2[flanks{i}]',f'[full{i}][flanks{i}]hstack=inputs=2[col{i}]']
filters += ['[col0][col1]hstack=inputs=2[mosaic]','[mosaic][2:v]overlay=0:0:shortest=1,setsar=1[out]']
command=[a.ffmpeg,'-y','-loglevel','error','-filter_complex_threads','4','-start_number','240','-framerate','30','-i',path(Path(a.v3)/'f%04d.png'),'-start_number','240','-framerate','30','-i',path(Path(a.v4)/'f%04d.png'),'-loop','1','-framerate','30','-i',path(caption),'-frames:v','51','-filter_complex',';'.join(filters),'-map','[out]','-an','-c:v','libx264','-threads','4','-pix_fmt','yuv420p','-crf','22','-preset','fast','-movflags','+faststart',path(out)]
subprocess.run(command,check=True)
info=json.loads(subprocess.check_output([a.ffprobe,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,sample_aspect_ratio,nb_frames,codec_name,duration','-of','json',path(out)],text=True));stream=info['streams'][0]
assert stream['sample_aspect_ratio']=='1:1','VIDEO_SAR'
assert int(stream['nb_frames'])==51 and (stream['width'],stream['height'])==(3072,1600),'VIDEO_FRAMES_OR_SIZE'
assert out.stat().st_size<20_000_000,'VIDEO_OVER_20_MB'
receipt={'spec':'dancer-smear50-video/1','window':[240,290],'fps':30,'left':'v3','right':'v4','cropBoxes':{'left':[220,380,420,580],'right':[420,380,620,580]},'scale':4,'filter':'nearest','stream':stream,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'ffmpeg':subprocess.check_output([a.ffmpeg,'-version'],text=True).splitlines()[0],'captionSHA256':hashlib.sha256(caption.read_bytes()).hexdigest()}
out.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('VIDEO_PASS',out.name,receipt['bytes'],stream['sample_aspect_ratio'],receipt['sha256'])
