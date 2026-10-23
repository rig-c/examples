#!/usr/bin/env python3
"""gen.py <free|pose> <seed> [<seed> ...] -> <mode>/<seed>.png (1664x2432) + <mode>/<seed>.json
txt2img on a ComfyUI server. Recipe (inherited from an earlier full-body standing recipe, see README): checkpoint, 30 steps,
cfg 5.5, euler_ancestral / normal, latent 832x1216, that recipe's negative minus the words that forbid this composition
(DROP below), plus ADD. Decode -> 4x-AnimeSharp -> 0.5 lanczos = 1664x2432.
pose: + OpenPose ControlNet (controlnet-openpose-sdxl-1.0) on control_pose.png, strength 1.0, end 0.85.
Queue rule: wait for the server's queue to be empty, submit at the back, never reorder or cancel, exit 3 after 900 s of waiting.
COMFY_HOST comes from the environment (the server's base URL)."""
import json, os, sys, time, io, uuid, urllib.request
from PIL import Image
MODE = sys.argv[1]; SEEDS = [int(s) for s in sys.argv[2:]]; HOST = os.environ['COMFY_HOST'].rstrip('/'); WAIT_MAX = 900
# The inherited recipe, inlined (the run read these values from that recipe's metadata file).
meta = {
    'checkpoint': 'novaAnimeXL_ilV80.safetensors',
    'sampler': {'steps': 30, 'cfg': 5.5, 'sampler': 'euler_ancestral', 'scheduler': 'normal'},
    'control': {'strength': 1, 'end_percent': 0.85, 'model': 'controlnet-openpose-sdxl-1.0.safetensors'},
    'negative': ('score_4, score_3, score_2, score_1, worst quality, low quality, lowres, blurry, jpeg artifacts, nsfw, nude, naked, '
                 'cleavage, underwear, sexual, suggestive, child, loli, shota, kid, toddler, text, watermark, signature, logo, '
                 'bad anatomy, bad hands, extra fingers, deformed, mutated, revealing clothes, bare shoulders, off shoulder, 2girls, '
                 'multiple girls, holding, bag, weapon, hat, clouds, sky, grey background, gradient background, scenery, outdoors, '
                 'from behind, back view, vignette, dark background, flat color, monochrome, lineart, open mouth, teeth, tongue, '
                 'closed eyes, half-closed eyes, wind, floating hair, white hair, blonde hair, twin tails, jacket, cropped, '
                 'out of frame, cut off feet, close-up, portrait, upper body, from side, profile, from behind, sitting, kneeling, '
                 'lying, crossed arms, hands in pockets, hands behind back, holding, contact shadow, cast shadow, floor, ground, '
                 'multiple views, reference sheet, wind, floating hair, arms touching body, hands on hips, long jacket, '
                 'jacket covering skirt, text, logo, number, wings, extra limbs, extra arms'),
}
HEAD = 'score_9, score_8_up, score_7_up, source_anime, masterpiece, best quality, highly detailed'
CHAR = ('1girl, (solo:1.3), young adult woman, (black hair:1.2), (long twintails:1.3), black hair ribbons, blunt bangs, '
        'long sidelocks, ears visible, green eyes, eyes open, gentle smile, closed mouth')
OUTFIT = '(dark navy blue knit sweater:1.2), white collared shirt, green necktie'
COMP = ('(upper body:1.2), sitting at a wooden school desk, (arms folded on the desk:1.2), (both forearms flat on the desk:1.3), '
        'desk in front of her covering her waist, (front view:1.2), (facing viewer:1.3), (looking at viewer:1.2), '
        'head straight, level eyes, symmetrical composition, centered')
STYLE = 'anime illustration, detailed, soft shading, vibrant colors, (plain light grey background:1.3), simple background, plain background'
positive = ', '.join([HEAD, CHAR, OUTFIT, COMP, STYLE])
# words in the inherited negative that forbid this composition: twintails, half body, sitting, folded arms, a grey background,
# arms on the body, close framing (the head must be >= 1/3 of the frame)
DROP = {'twin tails', 'upper body', 'sitting', 'crossed arms', 'grey background', 'arms touching body', 'close-up', 'portrait'}
ADD = ('full body, legs, feet, standing, looking away, looking up, looking down, head tilt, from above, from below, '
       'from side, three-quarter view, closed eyes, wink, short hair, single ponytail, school uniform with sailor collar, '
       'chair back visible, detailed background, classroom, window, multiple girls, '
       # iterations/v1/free_1: two stacked panels, the upper one a grey-haired girl in a blazer
       '2koma, comic, multiple panels, split screen, panel border, grey hair, silver hair, blazer, jacket, '
       # iterations/v2: seed 2 drew light-blue hair, a grey sweater and hands on the cheeks
       'blue hair, light blue hair, grey sweater, hands on own face, hand on own cheek, chin rest, head rest, '
       # iterations/v3: seeds 1 and 3 drew a second, red-haired girl in front; seed 2 bled red into the hair
       '(multiple girls:1.3), another girl, duplicate, clone, red hair, multicolored hair, streaked hair, colored inner hair, two-tone hair, '
       # iterations/v4: seeds 2 and 4 crossed the arms over the chest instead of on the desk
       'arms crossed over chest, hands on own shoulders, self hug, hugging own arms')
seen = set(); neg = []
for t in [t.strip() for t in meta['negative'].split(',')]:
    if t and t not in DROP and t not in seen: seen.add(t); neg.append(t)
negative = ', '.join(neg) + ', ' + ADD
def upload(img, name):
    b = io.BytesIO(); img.save(b, 'PNG'); bd = uuid.uuid4().hex
    body = (f'--{bd}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: image/png\r\n\r\n').encode() + b.getvalue() + f'\r\n--{bd}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n--{bd}--\r\n'.encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(HOST + '/upload/image', body, {'Content-Type': f'multipart/form-data; boundary={bd}'})))['name']
def queue_len():
    q = json.load(urllib.request.urlopen(HOST + '/queue')); return len(q['queue_running']), len(q['queue_pending'])
tag = f'rigc-look-{MODE}'
if MODE == 'pose': nc = upload(Image.open('control_pose.png').convert('RGB'), f'{tag}-control.png')
os.makedirs(MODE, exist_ok=True); log = open(f'{MODE}/run.log', 'a')
for seed in SEEDS:
    g = {'1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': meta['checkpoint']}},
         '2': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['1', 1], 'text': positive}},
         '3': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['1', 1], 'text': negative}},
         '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 832, 'height': 1216, 'batch_size': 1}}}
    pos, ng = ['2', 0], ['3', 0]
    if MODE == 'pose':
        g['7'] = {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': meta['control']['model']}}
        g['8'] = {'class_type': 'LoadImage', 'inputs': {'image': nc}}
        g['9'] = {'class_type': 'ControlNetApplyAdvanced', 'inputs': {'positive': pos, 'negative': ng, 'control_net': ['7', 0], 'image': ['8', 0],
                  'strength': meta['control']['strength'], 'start_percent': 0.0, 'end_percent': meta['control']['end_percent']}}
        pos, ng = ['9', 0], ['9', 1]
    s = meta['sampler']
    g['11'] = {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'seed': seed, 'steps': s['steps'], 'cfg': s['cfg'], 'sampler_name': s['sampler'],
               'scheduler': s['scheduler'], 'positive': pos, 'negative': ng, 'latent_image': ['4', 0], 'denoise': 1.0}}
    g['12'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['11', 0], 'vae': ['1', 2]}}
    g['13'] = {'class_type': 'UpscaleModelLoader', 'inputs': {'model_name': '4x-AnimeSharp.pth'}}
    g['14'] = {'class_type': 'ImageUpscaleWithModel', 'inputs': {'upscale_model': ['13', 0], 'image': ['12', 0]}}
    g['15'] = {'class_type': 'ImageScaleBy', 'inputs': {'upscale_method': 'lanczos', 'scale_by': 0.5, 'image': ['14', 0]}}
    g['16'] = {'class_type': 'SaveImage', 'inputs': {'images': ['15', 0], 'filename_prefix': tag}}
    w0 = time.time()
    while True:
        r, p = queue_len()
        if r + p == 0: break
        if time.time() - w0 > WAIT_MAX: print(f'{MODE} s{seed}: queue busy {WAIT_MAX} s (running {r}, pending {p}) - STOP', file=log, flush=True); sys.exit(3)
        time.sleep(5)
    waited = round(time.time() - w0, 1)
    pid = json.load(urllib.request.urlopen(urllib.request.Request(HOST + '/prompt', json.dumps({'prompt': g, 'client_id': 'rigc-hq-look'}).encode(), {'Content-Type': 'application/json'})))['prompt_id']
    t0 = time.time()
    while True:
        h = json.load(urllib.request.urlopen(HOST + f'/history/{pid}'))
        if pid in h and h[pid].get('outputs'): break
        if pid in h and h[pid].get('status', {}).get('status_str') == 'error': sys.exit(f'{MODE} s{seed}: job error {json.dumps(h[pid]["status"])[:800]}')
        if time.time() - t0 > 900: sys.exit(f'{MODE} s{seed}: timed out')
        time.sleep(3)
    im = h[pid]['outputs']['16']['images'][0]
    raw = urllib.request.urlopen(HOST + f"/view?filename={im['filename']}&subfolder={im['subfolder']}&type={im['type']}").read()
    out = Image.open(io.BytesIO(raw)).convert('RGB'); assert out.size == (1664, 2432), out.size
    out.save(f'{MODE}/{seed}.png')
    json.dump({'mode': MODE, 'seed': seed, 'prompt_id': pid, 'checkpoint': meta['checkpoint'], 'sampler': s, 'latent': [832, 1216], 'size': list(out.size),
               'control': ({'image': 'control_pose.png', 'model': meta['control']['model'], 'strength': meta['control']['strength'], 'end_percent': meta['control']['end_percent']} if MODE == 'pose' else None),
               'positive': positive, 'negative': negative, 'queue_wait_s': waited, 'gpu_s': round(time.time() - t0, 1)}, open(f'{MODE}/{seed}.json', 'w'), indent=1)
    print(MODE, seed, 'waited', waited, 's, job', round(time.time() - t0, 1), 's', file=log, flush=True); print(MODE, seed, waited, round(time.time() - t0, 1), flush=True)
