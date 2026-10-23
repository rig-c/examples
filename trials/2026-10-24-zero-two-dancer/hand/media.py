from pathlib import Path
import json,hashlib,subprocess,shutil
from PIL import Image,ImageDraw
root=Path('hand/work/final-render/zero-two-hand@24fps');out=Path('hand/recording');out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
frames=sorted(root.glob('f[0-9][0-9][0-9][0-9].png'));assert len(frames)==313
ffmpeg=shutil.which('ffmpeg');assert ffmpeg,'ffmpeg executable not found'
cmd=[ffmpeg,'-hide_banner','-loglevel','error','-y','-framerate','24','-start_number','0','-i',str(root/'f%04d.png'),'-frames:v','313','-an','-vf','scale=iw*3:ih*3:flags=neighbor,pad=ceil(iw/2)*2:ceil(ih/2)*2,setsar=1','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-threads','4',str(out/'zero-two-dancer-hand-final.mp4')]
print('ENCODE_COMMAND',json.dumps(cmd),flush=True);subprocess.run(cmd,check=True)
selected=[0,18,96,136,176,230,270,299,312];sheet=Image.new('RGB',(900,1248),'#e8e8e8');draw=ImageDraw.Draw(sheet)
for i,f in enumerate(selected):
 im=Image.open(root/f'f{f:04d}.png').convert('RGB');im.thumbnail((300,390),Image.Resampling.NEAREST);x=(i%3)*300+(300-im.width)//2;y=(i//3)*416;sheet.paste(im,(x,y));draw.text(((i%3)*300+8,y+394),f'Hand final frame {f}, t={f/24:.6f}s',fill='black')
sheet.save(out/'zero-two-dancer-hand-final-sheet.jpg',quality=86)
report={'kind':'CLI rendered animation; not a Play screen recording','compiledModelSHA256':sha('hand/work/build/skeleton.model.json'),'frames':313,'fps':24,'nativeSize':list(Image.open(frames[0]).size),'upscale':'3x nearest-neighbour','ffmpeg':subprocess.check_output([ffmpeg,'-version'],text=True).splitlines()[0],'command':cmd,'sheetFrames':selected,'files':[{ 'filename':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.is_file()]}
(out/'media-receipt.json').write_text(json.dumps(report,indent=2)+'\n');print('HAND_MEDIA',json.dumps(report),flush=True)
