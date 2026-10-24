#!/usr/bin/env python3
"""Upper-body inpaint masks, latent px (832x1216): keys3/inpaint_<K>/mask.png, and mask_overlay.png over the base.
include = (the base's topwear + both handwear + neck, from sheet/layers/full)  U  the new skeleton's arms as thick capsules
          U  the new torso (shoulders to hips) — all grown by MARGIN.
protect = the face oval (inpaint.py's formula)  U  front hair, headwear, back hair (grown 2 px)
          U  (bottomwear + legwear + footwear, where visible)  minus  the new forearm and hand capsules (a hand that now lies over the skirt
          has to be painted there).
mask = blur(include minus protect), then clamped to 0 on protect, so the protected pixels come back identical."""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
KEYS = ['H1_hold_head', 'H2_hold_low', 'H2x_hold_low', 'H2y_hold_low', 'H2z_hold_low', 'H1m_hold_head']
LW, LH = 832, 1216; MARGIN = 21; ARM_W = 70
# how far past the new forearm and hand the skirt/legs may be repainted. 21 (= MARGIN) on the first K1-K4 runs; K1 has no
# forearm over the skirt and K4's runs kept it; K2 and K3 were rebuilt at 9 after a 21 px band painted stripes onto the skirt.
# the hand disc's radius (latent px), centred 0.6 radius past the wrist. 50 on K1, K2, K4; 36 on K3, whose 50 px disc reached
# down the skirt below the hip hand and the sampler filled it with a stripe in 3 of 4 seeds.
HAND_R = int(__import__('os').environ.get('HAND_R', '50'))
FORE_GROW = int(__import__('os').environ.get('FORE_GROW', '9'))
cj = json.load(open('char_keypoints.json'))['joints']
LAYERS = {l['name']: l for l in json.load(open('sheet/layers/full/layers.json'))['layers']}
def layer(tag):
    c = Image.new('L', (1024, 1024), 0); l = LAYERS[tag]  # a part PNG is its box's size, placed at the box
    c.paste(Image.open(f'sheet/layers/full/parts/{tag}.png').split()[-1], (l['left'], l['top']))
    a = c.resize((2432, 2432), Image.BILINEAR).crop((384, 0, 384 + 1664, 2432))
    return np.array(a.resize((LW, LH), Image.BILINEAR)) > 64
def grow(b, px): return np.array(Image.fromarray((b * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(px))) > 127
def capsules(kp, segs, w):
    m = Image.new('L', (LW, LH), 0); d = ImageDraw.Draw(m)
    for a, b in segs:
        d.line([tuple(kp[a]), tuple(kp[b])], fill=255, width=w); 
        for p in (a, b): d.ellipse([kp[p][0] - w / 2, kp[p][1] - w / 2, kp[p][0] + w / 2, kp[p][1] + w / 2], fill=255)
    return np.array(m) > 127
def build(K, write=True):
    kp = json.load(open(f'keys3/{K}.json'))['points']
    base_up = layer('topwear') | layer('handwear-l') | layer('handwear-r') | layer('neck')
    arms = capsules(kp, [(f'{s}_{a}', f'{s}_{b}') for s in 'lr' for a, b in (('shoulder', 'elbow'), ('elbow', 'wrist'))], ARM_W)
    hands = Image.new('L', (LW, LH), 0); hd = ImageDraw.Draw(hands)
    for s in 'lr':  # the hand reaches past the wrist joint along the forearm: a disc one forearm-width out
        e, w = np.array(kp[f'{s}_elbow']), np.array(kp[f'{s}_wrist']); u = (w - e) / np.linalg.norm(w - e); c = w + u * HAND_R * 0.6
        hd.ellipse([c[0] - HAND_R, c[1] - HAND_R, c[0] + HAND_R, c[1] + HAND_R], fill=255)
    hands = np.array(hands) > 127
    torso = Image.new('L', (LW, LH), 0); ImageDraw.Draw(torso).polygon([tuple(kp['r_shoulder']), tuple(kp['l_shoulder']), tuple(kp['l_hip']), tuple(kp['r_hip'])], fill=255)
    inc = grow(base_up | arms | hands | (np.array(torso) > 127), MARGIN)
    fore = grow(capsules(kp, [(f'{s}_elbow', f'{s}_wrist') for s in 'lr'], ARM_W) | hands, FORE_GROW)
    # See-through's layers are amodal (bottomwear runs on under the jacket, back hair under the collar and, as a hidden
    # ponytail, down behind the skirt — protecting that hidden tail blocked K2's forearm over the skirt until v11): protect only what the
    # base painting shows, i.e. each layer minus the layers drawn in front of it.
    upper = layer('topwear') | layer('handwear-l') | layer('handwear-r')
    hair = grow(layer('front hair') | layer('headwear') | (layer('back hair') & ~upper & ~layer('neck') & ~layer('bottomwear') & ~layer('legwear')), 5)
    low = (layer('bottomwear') | layer('legwear') | layer('footwear')) & ~upper
    face = Image.new('L', (LW, LH), 0)
    ex, ey = (cj['l_eye'][0] + cj['r_eye'][0]) / 4, (cj['l_eye'][1] + cj['r_eye'][1]) / 4; rx = abs(cj['l_ear'][0] - cj['r_ear'][0]) / 4 * 1.05
    ImageDraw.Draw(face).ellipse([ex - rx, ey - rx * 1.05, ex + rx, ey + rx * 1.35], fill=255)
    protect = (np.array(face) > 127) | hair | (low & ~fore)
    m = Image.fromarray(((inc & ~protect) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
    m = np.array(m); m[protect] = 0; m = Image.fromarray(m)
    stats = {'mask_px': int((np.array(m) > 127).sum()), 'arm_px_lost_to_hair': int((arms & hair).sum()), 'hand_px_lost_to_hair': int((hands & hair).sum()), 'arm_px_over_low_kept': int((low & fore & inc).sum())}
    if write:
        os.makedirs(f'keys3/inpaint_{K}', exist_ok=True); m.save(f'keys3/inpaint_{K}/mask.png')
        b = Image.open('sheet/painting.png').convert('RGB').resize((LW, LH), Image.LANCZOS)
        red = Image.new('RGB', (LW, LH), (255, 0, 0)); ov = Image.composite(Image.blend(b, red, 0.45), b, m)
        ctrl = Image.open(f'keys3/control_{K}.png').convert('RGB'); ov = Image.blend(ov, ctrl, 0.0)
        cm = np.array(ctrl).sum(2) > 30; o = np.array(ov); o[cm] = np.array(ctrl)[cm]; Image.fromarray(o).save(f'keys3/inpaint_{K}/mask_overlay.png')
    return stats
if __name__ == '__main__':
    for K in (sys.argv[1:] or KEYS): print(K, build(K))
