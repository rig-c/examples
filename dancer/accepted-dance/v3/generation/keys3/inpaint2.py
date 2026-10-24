#!/usr/bin/env python3
"""Repaint the UPPER BODY (torso + arms + shoulders) of the base dancer into a key pose: SDXL inpaint with the OpenPose control
of keys3/<K>.json, on the shared ComfyUI box (COMFY_HOST). inpaint.py's plumbing; what changed is said where it changed.
inpaint2.py <key> <arm: plain|ipa> <seed> [<seed> ...]  ->  keys3/inpaint_<K>/<arm>_s<seed>.png (painting size) + .json (graph inputs)
- mask: keys3/inpaint_<K>/mask.png (keys3/masks.py), latent px; the composite goes back through it, protected pixels are 0 in it.
- decode -> 4x-AnimeSharp -> 0.5 lanczos, the base painting's own path (graphs.ts), instead of inpaint.py's LANCZOS x2 of the latent decode.
- prompt: the base generation's identity and style, the costume as the base painting shows it, and the KEY's pose words
  (keys/config_<K>.json), not the base's A-pose words that inpaint.py carried.
- arm 'warp': start from keys3/inpaint_<K>/warped.png with DifferentialDiffusion over softmask.png, composite through compmask.png.
- arm 'ipa': IP-Adapter Plus SDXL (ViT-H) with a square crop of the base painting's upper body as the reference image.
Queue: waits for the box's queue to be empty before each job, submits at the back, never reorders or cancels; gives up after
WAIT_MAX s of waiting and exits 3."""
import json, os, sys, time, uuid, urllib.request, io
from PIL import Image
HOST = os.environ['COMFY_HOST'].rstrip('/'); K = sys.argv[1]; ARM = sys.argv[2]; SEEDS = [int(s) for s in sys.argv[3:]]
WAIT_MAX = 900; IPA_W = float(os.environ.get('IPA_W', '0.6'))
assert ARM in ('plain', 'ipa', 'warp')
base = Image.open('sheet/painting.png').convert('RGB'); BW, BH = base.size; LW, LH = 832, 1216
gen = json.load(open('config.json'))['generation']; kg = json.load(open(f'keys/config_{K}.json'))['generation']
HEAD = 'score_9, score_8_up, score_7_up, source_anime, masterpiece, best quality, highly detailed'
NEG_HEAD = ('score_4, score_3, score_2, score_1, worst quality, low quality, lowres, blurry, jpeg artifacts, nsfw, nude, naked, cleavage, underwear, sexual, '
            'suggestive, child, loli, shota, kid, toddler, text, watermark, signature, logo, bad anatomy, bad hands, extra fingers, deformed, mutated')
costume = gen['costume'].replace('white and black color block jacket', 'white jacket with blue stripes along the sleeves, dark blue cuffs and collar, (blue ribbed waistband:1.1), small navy and orange chest patch')
SHOULDERS = {'K1_hands_behind_head': 'shoulders raised, elbows flared out to the sides', 'K2_hands_low_front': '', 'K3_v_sign': 'right shoulder raised', 'K4_hand_up': '', 'H1m_hold_head': 'shoulders raised, elbows raised high and forward, forearms behind the head, hands hidden behind the head, jacket hem lifted, bare midriff', 'H1_hold_head': 'shoulders raised, elbows raised high and forward, forearms behind the head, hands hidden behind the head', 'H2z_hold_low': 'arms extended straight down in front, forearms crossed at the wrists in an X, hands hanging to opposite sides', 'H2y_hold_low': 'arms hanging down in front, forearms crossed at the wrists in an X, hands hanging to opposite sides', 'H2x_hold_low': 'arms hanging down in front, forearms crossed at the wrists in an X, hands hanging to opposite sides', 'H2_hold_low': 'arms hanging down in front, forearms crossed at the wrists in an X, hands hanging to opposite sides'}[K]
# K3, after its first four seeds drew an open hand, a fist and a pointing finger and no V: the hand words weighted (env V_WEIGHT=1).
# (A first wording, '(index finger and middle finger raised:1.2)', drew one pointing finger in 6 of 6 seeds and was dropped.)
if K == 'K3_v_sign' and os.environ.get('V_WEIGHT') == '1': SHOULDERS += ', (v sign:1.3), (peace sign:1.2)'
pose = kg['pose'] + (', ' + SHOULDERS if SHOULDERS else '')
positive = ', '.join([HEAD, gen['identity'], costume, pose, gen['style']])
def drop(text, words): return ', '.join(t.strip() for t in text.split(',') if t.strip() not in words)
neg_pose = drop(kg['negative_pose'], {'hands on hips'} if K == 'K3_v_sign' else set())
if K == 'K3_v_sign' and os.environ.get('V_WEIGHT') == '1': neg_pose += ', fist, open palm, waving, pointing, index finger raised, single finger'
negative = ', '.join([NEG_HEAD, drop(gen['negative_extra'], {'jacket'}), neg_pose,
    'cyan jacket, green jacket, double bun, extra arms, extra hands, visor, hat, covered face, collar over face',
    'black jacket, red jacket, hood, pockets, text on jacket, letters, large emblem, missing waistband, different outfit, sleeveless, short sleeves, gloves'])
out_dir = f'keys3/inpaint_{K}'; m = Image.open(f'{out_dir}/mask.png').convert('L')
start = base
if ARM == 'warp':  # keys3/prewarp.py: the base jacket moved to the key's shoulders, the old arms cleared; a per-pixel denoise map
    start = Image.open(f'{out_dir}/warped.png').convert('RGB'); sm = Image.open(f'{out_dir}/softmask.png').convert('L'); m = Image.open(f'{out_dir}/compmask.png').convert('L')
def upload(img, name):
    b = io.BytesIO(); img.save(b, 'PNG'); bd = uuid.uuid4().hex
    body = (f'--{bd}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: image/png\r\n\r\n').encode() + b.getvalue() + f'\r\n--{bd}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n--{bd}--\r\n'.encode()
    r = urllib.request.Request(HOST + '/upload/image', body, {'Content-Type': f'multipart/form-data; boundary={bd}'}); return json.load(urllib.request.urlopen(r))['name']
def queue_len():
    q = json.load(urllib.request.urlopen(HOST + '/queue')); return len(q['queue_running']), len(q['queue_pending'])
tag = f'rigc-dancer2-{K}'
nb = upload(start.resize((LW, LH), Image.LANCZOS), f'{tag}-{ARM}-start.png'); nm = upload((sm if ARM == 'warp' else m).convert('RGB'), f'{tag}-{ARM}-mask.png')
nc = upload(Image.open(f'keys3/control_{K}.png').convert('RGB'), f'{tag}-pose.png')
REF_BOX = (432, 560, 1232, 1360)  # painting px: the jacket, both sleeves to the cuffs, the waistband; no face
nr = upload(base.crop(REF_BOX), 'rigc-dancer2-ref.png') if ARM == 'ipa' else None
log = open(f'{out_dir}/run.log', 'a')
for seed in SEEDS:
    model = ['1', 0]
    g = {
     '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': gen['checkpoint']}},
     '2': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['1', 1], 'text': positive}},
     '3': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['1', 1], 'text': negative}},
     '4': {'class_type': 'LoadImage', 'inputs': {'image': nb}}, '5': {'class_type': 'LoadImage', 'inputs': {'image': nm}},
     '6': {'class_type': 'ImageToMask', 'inputs': {'image': ['5', 0], 'channel': 'red'}},
     '7': {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': 'controlnet-openpose-sdxl-1.0.safetensors'}}, '8': {'class_type': 'LoadImage', 'inputs': {'image': nc}},
     '9': {'class_type': 'ControlNetApplyAdvanced', 'inputs': {'positive': ['2', 0], 'negative': ['3', 0], 'control_net': ['7', 0], 'image': ['8', 0], 'strength': 1.0, 'start_percent': 0.0, 'end_percent': 0.9}},
     '10': {'class_type': 'InpaintModelConditioning', 'inputs': {'positive': ['9', 0], 'negative': ['9', 1], 'vae': ['1', 2], 'pixels': ['4', 0], 'mask': ['6', 0], 'noise_mask': True}},
     '12': {'class_type': 'VAEDecode', 'inputs': {'samples': ['11', 0], 'vae': ['1', 2]}},
     '13': {'class_type': 'UpscaleModelLoader', 'inputs': {'model_name': '4x-AnimeSharp.pth'}},
     '14': {'class_type': 'ImageUpscaleWithModel', 'inputs': {'upscale_model': ['13', 0], 'image': ['12', 0]}},
     '15': {'class_type': 'ImageScaleBy', 'inputs': {'upscale_method': 'lanczos', 'scale_by': 0.5, 'image': ['14', 0]}},
     '16': {'class_type': 'SaveImage', 'inputs': {'images': ['15', 0], 'filename_prefix': tag}}}
    if ARM == 'ipa':
        g['20'] = {'class_type': 'IPAdapterModelLoader', 'inputs': {'ipadapter_file': 'ip-adapter-plus_sdxl_vit-h.safetensors'}}
        g['21'] = {'class_type': 'CLIPVisionLoader', 'inputs': {'clip_name': 'CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors'}}
        g['22'] = {'class_type': 'LoadImage', 'inputs': {'image': nr}}
        g['23'] = {'class_type': 'IPAdapterAdvanced', 'inputs': {'model': ['1', 0], 'ipadapter': ['20', 0], 'clip_vision': ['21', 0], 'image': ['22', 0], 'weight': IPA_W, 'weight_type': 'linear', 'combine_embeds': 'concat', 'start_at': 0.0, 'end_at': 1.0, 'embeds_scaling': 'V only'}}
        model = ['23', 0]
    if ARM == 'warp':
        g['24'] = {'class_type': 'DifferentialDiffusion', 'inputs': {'model': ['1', 0]}}; model = ['24', 0]
    g['11'] = {'class_type': 'KSampler', 'inputs': {'model': model, 'seed': seed, 'steps': 30, 'cfg': 5.5, 'sampler_name': 'euler_ancestral', 'scheduler': 'normal', 'positive': ['10', 0], 'negative': ['10', 1], 'latent_image': ['10', 2], 'denoise': 1.0}}
    w0 = time.time()
    while True:
        r, p = queue_len()
        if r + p == 0: break
        if time.time() - w0 > WAIT_MAX: print(f'{K} {ARM} s{seed}: queue busy for {WAIT_MAX} s (running {r}, pending {p}) - stopping', file=log, flush=True); sys.exit(3)
        time.sleep(5)
    waited = round(time.time() - w0, 1)
    pid = json.load(urllib.request.urlopen(urllib.request.Request(HOST + '/prompt', json.dumps({'prompt': g, 'client_id': 'rigc-hq-keys2'}).encode(), {'Content-Type': 'application/json'})))['prompt_id']
    t0 = time.time()
    while True:
        h = json.load(urllib.request.urlopen(HOST + f'/history/{pid}'))
        if pid in h and h[pid].get('outputs'): break
        if pid in h and h[pid].get('status', {}).get('status_str') == 'error': sys.exit(f'{K} {ARM} s{seed}: job error {json.dumps(h[pid]["status"])[:800]}')
        if time.time() - t0 > 900: sys.exit(f'seed {seed}: timed out')
        time.sleep(3)
    im = h[pid]['outputs']['16']['images'][0]
    raw = urllib.request.urlopen(HOST + f"/view?filename={im['filename']}&subfolder={im['subfolder']}&type={im['type']}").read()
    out = Image.open(io.BytesIO(raw)).convert('RGB'); assert out.size == (BW, BH), out.size
    out.save(f'{out_dir}/{ARM}_s{seed}_raw.png')
    res = Image.composite(out, base, m.resize((BW, BH), Image.BILINEAR))
    if ARM == 'warp': res = Image.composite(start, res, Image.open(f'{out_dir}/keepmask.png').convert('L'))
    res.save(f'{out_dir}/{ARM}_s{seed}.png')
    json.dump({'key': K, 'arm': ARM, 'seed': seed, 'prompt_id': pid, 'positive': positive, 'negative': negative, 'ipadapter_weight': IPA_W if ARM == 'ipa' else None, 'warp_torso_t': json.load(open(f'{out_dir}/prewarp.json'))['torso_t'] if ARM == 'warp' else None,
               'reference_box_painting_px': REF_BOX if ARM == 'ipa' else None, 'queue_wait_s': waited, 'gpu_s': round(time.time() - t0, 1)}, open(f'{out_dir}/{ARM}_s{seed}.json', 'w'), indent=1)
    print(K, ARM, seed, 'waited', waited, 's, job', round(time.time() - t0, 1), 's', file=log, flush=True); print(K, ARM, seed, waited, round(time.time() - t0, 1))
