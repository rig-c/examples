#!/usr/bin/env python3
"""The start image and the per-pixel denoise mask for the 'warp' arm (keys3/inpaint2.py <K> warp ...).
Why: a full-strength repaint of the whole jacket (arm 'plain') redraws the badge, drops the sleeve stripes and the waist ribbing
(measured on K1 s1). Instead the jacket the base painting already has is MOVED to the key's shoulders, and the sampler is only
asked to refine it (DifferentialDiffusion, mask value = how much of the schedule a pixel is repainted for), while the arms, which
change completely, are repainted at full strength.
Per key, in painting px:
  torso source  = the base painting where the jacket body is visible (sheet/layers/full topwear, minus both handwear layers drawn
                  over it), See-through's amodal topwear RGB where a sleeve hid it (the shoulder caps); alpha = topwear's.
  warp          = destination p takes source p - d(p): dy = -lift(x) * w(y), dx = dneck * wx(y). lift(x) runs from the r to the l
                  shoulder lift of keys3/keys.json; w = 1 at and above the shoulder line, falling linearly to HEM_RIDE at the jacket
                  hem for a rising side (the hem rides up) and to 0 for a dropping side (the hem stays: the skirt below is protected);
                  wx = 1 above the shoulders, 0 at the hem.
  start image   = the base, with the old arms and the old jacket body cleared to the background, the skirt's amodal top
                  (bottomwear) where the hem lifted off it, and the warped jacket over that.
  sleeves       = the base painting's pixels inside each handwear layer, cut at the elbow (perpendicular to the bisector) and
                  moved rigidly: upper arm about the shoulder onto the new shoulder->elbow, forearm+hand onto the new elbow->wrist
                  (the new skeleton keeps the character's segment lengths, so the pieces fit), pasted over the jacket.
  softmask      = TORSO_T inside the warped jacket, ARM_T inside a moved sleeve, JOINT_T on shoulder and elbow discs, EDGE_T on the jacket's moved edge, 0 on the chest patch (BADGE_BOX), 1.0 on the
                  hands, on the old arms' place and on a band along the jacket outline where it moved; 0 on everything keys3/masks.py protects. Latent px.
  keepmask      = the chest patch, pasted back from the start image after sampling (painting px).
  compmask      = where the result replaces the base: softmask > 0, grown and blurred, protected clamped to 0. Latent px."""
import json, sys
import numpy as np, cv2
from PIL import Image, ImageFilter
sys.path.insert(0, 'keys2'); import masks as M
KEYS = ['H1_hold_head', 'H2_hold_low', 'H2x_hold_low', 'H2y_hold_low', 'H2z_hold_low', 'H1m_hold_head']
BADGE_BOX = (868, 688, 952, 746)  # painting px, the chest patch with a margin (measured on sheet/painting.png)
EDGE_T = 0.55; JOINT_T = 0.7; VHAND_T = 0.3
SKIRT_HAND_T = float(__import__('os').environ.get('SKIRT_HAND_T', '1.0'))  # 1.0 (no cap) on K1, K2, K4's runs; 0.5 on K3's
HEM_RIDE = float(__import__('os').environ.get('HEM_RIDE', '0.6')); TORSO_T = float(sys.argv[1]) if len(sys.argv) > 1 else 0.35; ARM_T = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6
BW, BH = 1664, 2432
base = np.array(Image.open('sheet/painting.png').convert('RGB')).astype(np.float32)
cj = json.load(open('char_keypoints.json'))['joints']; K2 = json.load(open('keys3/keys.json'))['keys']
def rgba(tag):
    c = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0)); l = M.LAYERS[tag]; c.paste(Image.open(f'sheet/layers/full/parts/{tag}.png').convert('RGBA'), (l['left'], l['top']))
    a = np.array(c.resize((2432, 2432), Image.BICUBIC).crop((384, 0, 384 + BW, BH))).astype(np.float32); return a[..., :3], a[..., 3] / 255
T_rgb, T_a = rgba('topwear'); B_rgb, B_a = rgba('bottomwear'); _, Hl = rgba('handwear-l'); _, Hr = rgba('handwear-r'); sleeves_all = np.maximum(Hl, Hr)
# See-through put a strip of the jacket front (half the chest badge) into handwear-l (and the matching strip into handwear-r):
# a sleeve is only what lies outside its shoulder's column; the strip stays with the jacket body.
_xx = np.arange(BW)[None, :]
Hl = Hl * (_xx >= cj['l_shoulder'][0] - 15); Hr = Hr * (_xx <= cj['r_shoulder'][0] + 15)
sleeves = np.maximum(Hl, Hr)
vis_T = (T_a > 0.5) & (sleeves < 0.5)
src = np.where(vis_T[..., None], base, T_rgb)
ys = np.where(T_a.max(1) > 0.5)[0]; hem_y = float(ys.max()); top_y = float(ys.min())
sh_y = (cj['l_shoulder'][1] + cj['r_shoulder'][1]) / 2; xr, xl = cj['r_shoulder'][0], cj['l_shoulder'][0]
def lat(b): return np.array(Image.fromarray((b * 255).astype(np.uint8)).resize((832, 1216), Image.BILINEAR)) / 255.0
def build(K):
    k = K2[K]; Lr, Ll = k['shoulder_lift_px']['r'], k['shoulder_lift_px']['l']; dn = k['neck_offset_x_px']
    yy, xx = np.mgrid[0:BH, 0:BW].astype(np.float32)
    lift = Lr + (Ll - Lr) * np.clip((xx - xr) / (xl - xr), 0, 1)
    f = np.clip((yy - sh_y) / (hem_y - sh_y), 0, 1)
    w = 1 - f * (1 - np.where(lift > 0, HEM_RIDE, 0.0)); wx = 1 - f
    mx = (xx - dn * wx).astype(np.float32); my = (yy + lift * w).astype(np.float32)   # destination p reads source p - d(p), d = (dn*wx, -lift*w)
    rem = lambda img: cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    Tw_a = rem(T_a); Tw_rgb = rem(np.ascontiguousarray(src))
    kp = json.load(open(f'keys3/{K}.json'))['points']
    # clear the old arms and the old jacket body to the background, but never a protected pixel
    old_arms = cv2.dilate(((sleeves_all > 0.3) * 1).astype(np.uint8), np.ones((13, 13), np.uint8)) > 0
    start = base.copy(); clear = (old_arms | (T_a > 0.3))
    prot_lat = protect_of(K); prot = np.array(Image.fromarray((prot_lat * 255).astype(np.uint8)).resize((BW, BH), Image.NEAREST)) > 127
    clear &= ~prot
    start[clear] = 255.0
    reveal = clear & (B_a > 0.5); start[reveal] = B_rgb[reveal]         # the skirt's own top under a hem that lifted
    a = Tw_a[..., None]; start = np.where(clear[..., None], start * (1 - a) + Tw_rgb * a, start)
    # the base sleeves (painting pixels inside each handwear layer), cut at the elbow and moved rigidly onto the new arm
    pieces = []
    for s, Hs in (('r', Hr), ('l', Hl)):
        S0, E0, W0 = (np.array(cj[f'{s}_{j}'][:2], np.float32) for j in ('shoulder', 'elbow', 'wrist'))
        S1, E1, W1 = (np.array(kp[f'{s}_{j}'], np.float32) * 2 for j in ('shoulder', 'elbow', 'wrist'))
        u0, f0 = (E0 - S0) / np.linalg.norm(E0 - S0), (W0 - E0) / np.linalg.norm(W0 - E0)
        n = u0 + f0; n /= np.linalg.norm(n)            # the cut: through the elbow, perpendicular to the mean limb direction
        side = ((xx - E0[0]) * n[0] + (yy - E0[1]) * n[1]) < 0   # True = shoulder side
        a_s = Hs * (Hs > 0.05)
        beyond = ((xx - S0[0]) * u0[0] + (yy - S0[1]) * u0[1]) > 0   # distal of the shoulder point: a cap above it would swing
        fore_sel = ~side
        if K == 'K3_v_sign' and s == 'r':  # the carried V hand brings its own cuff: end the base forearm where the base cuff starts
            # (K2's carried cuffs lie over the base cuffs instead: trimming there left the sleeves short of the cuffs, v9 trial)
            fore_sel = fore_sel & (((xx - E0[0]) * f0[0] + (yy - E0[1]) * f0[1]) < np.linalg.norm(W0 - E0) - 60)
        for part, sel, P0, D0, P1, D1 in (('upper', side & beyond, S0, E0 - S0, S1, E1 - S1), ('fore', fore_sel, E0, W0 - E0, E1, W1 - E1)):  # across the chest
            ang = np.degrees(np.arctan2(D1[1], D1[0]) - np.arctan2(D0[1], D0[0]))
            A = cv2.getRotationMatrix2D((float(P0[0]), float(P0[1])), -ang, 1.0); A[:, 2] += P1 - P0
            rgba_ = np.dstack([base, (a_s * sel)[..., None] * 255]).astype(np.float32)
            wp = cv2.warpAffine(rgba_, A, (BW, BH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            pieces.append((s, part, wp[..., :3], wp[..., 3] / 255))
    for s, part, rgb, al in sorted(pieces, key=lambda t: t[1] == 'fore'):   # upper arms, then forearms over them
        al = np.where(prot, 0, al)[..., None]; start = start * (1 - al) + rgb * al
    arm_a = np.max([al for *_, al in pieces], axis=0)
    vhand = np.zeros((BH, BW), np.float32)
    if K == 'K3_v_sign':
        # Body-only OpenPose cannot say "V": ten K3 seeds drew an open hand, a fist or one pointing finger. The V hand and its cuff
        # are carried over from the arm-only pick (alts K3 s2, RTMPose wrist/elbow in alts/K3_v_sign/keypoints.json): rotated
        # by the change in forearm direction about its wrist and moved onto the new wrist, then refined at VHAND_T.
        oj = json.load(open('alts/K3_v_sign/keypoints.json'))['joints']; old = np.array(Image.open('alts/K3_v_sign/inpaint_s2.png').convert('RGB')).astype(np.float32)
        Wo, Eo = np.array(oj['r_wrist'][:2], np.float32), np.array(oj['r_elbow'][:2], np.float32)
        Wn, En = np.array(kp['r_wrist'], np.float32) * 2, np.array(kp['r_elbow'], np.float32) * 2
        sel = (old.min(2) < 235) & (old.sum(2) > 200); sel[:, :680] = False; sel[:, 830:] = False; sel[300:] = False; sel[:23] = False   # rows to 300 = the whole cuff (measured along the forearm)
        n_, lab = cv2.connectedComponents(sel.astype(np.uint8)); keep = lab == np.bincount(lab[sel]).argmax()
        keep = cv2.morphologyEx(keep.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(np.float32)
        keep = cv2.GaussianBlur(keep, (0, 0), 1.2)
        ang = np.degrees(np.arctan2(*(Wn - En)[::-1]) - np.arctan2(*(Wo - Eo)[::-1]))
        A = cv2.getRotationMatrix2D((float(Wo[0]), float(Wo[1])), -ang, 1.0); A[:, 2] += Wn - Wo
        ha = cv2.warpAffine(keep, A, (BW, BH)); top = np.where(ha.max(1) > 0.5)[0].min()
        drop_ = max(0, 4 - int(top)); A[1, 2] += drop_   # the frame ends above the fingertips: slide the hand down its forearm until they fit
        hrgb = cv2.warpAffine(old, A, (BW, BH)); ha = cv2.warpAffine(keep, A, (BW, BH))
        ha = np.where(prot & (ha < 0.99), 0, ha)[..., None]; start = start * (1 - ha) + hrgb * ha; vhand = ha[..., 0]
        print(K, 'V hand pasted: turned', round(float(ang), 1), 'deg, slid down', drop_, 'px so the fingertips stay in frame')
    if K == 'K2_hands_low_front':
        # The clasped hands and both cuffs of the arm-only pick (alts K2 s2), inside a polygon drawn around them on that picture
        # (painting px; it stops above the thighs) and not skirt-dark, moved so the old wrists' midpoint lands on the new contact
        # point. Four seeds with the moved base hands drew broken fingers where the skirt protection cut them.
        oj = json.load(open('alts/K2_hands_low_front/keypoints.json'))['joints']; old = np.array(Image.open('alts/K2_hands_low_front/inpaint_s2.png').convert('RGB')).astype(np.float32)
        poly = np.array([(812, 1180), (960, 1195), (958, 1262), (935, 1268), (925, 1320), (905, 1348), (880, 1348), (850, 1320), (838, 1258), (818, 1250)], np.int32)
        pm = np.zeros((BH, BW), np.uint8); cv2.fillPoly(pm, [poly], 1); keep = ((pm > 0) & (old.sum(2) > 230)).astype(np.float32)
        keep = cv2.GaussianBlur(cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)), (0, 0), 1.2)
        off = (np.array(kp['r_wrist']) * 2 + np.array(kp['l_wrist']) * 2) / 2 - (np.array(oj['r_wrist'][:2]) + np.array(oj['l_wrist'][:2])) / 2
        A = np.float32([[1, 0, off[0]], [0, 1, off[1]]]); hrgb = cv2.warpAffine(old, A, (BW, BH)); ha = cv2.warpAffine(keep, A, (BW, BH))
        ha = ha[..., None]; start = start * (1 - ha) + hrgb * ha; vhand = ha[..., 0]
        print(K, 'clasped hands carried, moved by', off.round(1).tolist())
    Image.fromarray(np.clip(start, 0, 255).astype(np.uint8)).save(f'keys3/inpaint_{K}/warped.png')
    # the denoise map, latent px
    arms = M.capsules(kp, [(f'{s}_{a}', f'{s}_{b}') for s in 'lr' for a, b in (('shoulder', 'elbow'), ('elbow', 'wrist'))], M.ARM_W)
    hands = M.capsules({**kp, **{f'{s}_hand': list(np.array(kp[f'{s}_wrist']) + M.HAND_R * 0.6 * (np.array(kp[f'{s}_wrist']) - np.array(kp[f'{s}_elbow'])) / np.linalg.norm(np.array(kp[f'{s}_wrist']) - np.array(kp[f'{s}_elbow']))) for s in 'lr'}},
                       [(f'{s}_wrist', f'{s}_hand') for s in 'lr'], 2 * M.HAND_R)
    Tl, Twl = lat(T_a) > 0.5, lat(Tw_a) > 0.5
    moved = M.grow(Tl ^ Twl, 15)
    vacated = moved & ~Twl                                   # where the jacket was and is no more: painted from scratch
    full = M.grow(lat(sleeves) > 0.3, 15) | M.grow(arms | hands, M.MARGIN) | vacated
    sm = full * 1.0
    sm = np.where(full & ~M.grow(Twl, 7), 1.0, np.where(M.grow(Twl, 7), np.maximum(sm * 0, TORSO_T), sm))
    sm = np.where(full, 1.0, sm)
    sm[Twl & moved] = EDGE_T                                 # the jacket's own edge where its outline moved
    sm[~M.grow(~Twl, 9) & ~moved] = TORSO_T                 # the jacket body away from where its outline moved
    sm[M.grow(lat(arm_a) > 0.5, 5) & ~(prot_lat > 0.5)] = ARM_T   # a moved sleeve and its own outline (the stripe runs along it)
    for s in 'lr':                                          # joints are repainted harder, hands from scratch
        for j, v, r in (('shoulder', JOINT_T, 26), ('elbow', JOINT_T, 26)):
            c = kp[f'{s}_{j}']; yy_, xx_ = np.ogrid[0:1216, 0:832]; sm[((xx_ - c[0]) ** 2 + (yy_ - c[1]) ** 2) < r * r] = np.maximum(sm[((xx_ - c[0]) ** 2 + (yy_ - c[1]) ** 2) < r * r], v)
    sm[hands] = 1.0
    if vhand.any():  # a carried hand's whole disc is only refined: at 1.0 the sampler drew a second hand beside it
        sides = 'r' if K == 'K3_v_sign' else ''   # K2: only the carried pixels; a disc over the forearms kept the skirt there (v9)
        rd = np.zeros((1216, 832), bool) if not sides else M.capsules({**kp, **{f'{s}_hand': list(np.array(kp[f'{s}_wrist']) + M.HAND_R * 0.6 * (np.array(kp[f'{s}_wrist']) - np.array(kp[f'{s}_elbow'])) / np.linalg.norm(np.array(kp[f'{s}_wrist']) - np.array(kp[f'{s}_elbow']))) for s in sides}}, [(f'{s}_wrist', f'{s}_hand') for s in sides], 2 * M.HAND_R)
        sm[M.grow(rd | (lat(vhand) > 0.3), 9)] = VHAND_T
    # a hand landing on the skirt: the start image already has a hand there (the moved base hand); at 1.0 the skirt around it
    # was painted with straps and stripes (K3 s1, s4), so the skirt part of a hand disc is refined at SKIRT_HAND_T only.
    low_vis = protect_low_visible(); sm[hands & low_vis] = np.minimum(sm[hands & low_vis], SKIRT_HAND_T)
    bx = BADGE_BOX; cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2   # the patch moves by the warp at its centre
    lc = Lr + (Ll - Lr) * np.clip((cx - xr) / (xl - xr), 0, 1); fc = np.clip((cy - sh_y) / (hem_y - sh_y), 0, 1)
    d_ = np.array([dn * (1 - fc), -lc * (1 - fc * (1 - (HEM_RIDE if lc > 0 else 0.0)))]) / 2
    sm[int(bx[1] / 2 + d_[1]):int(bx[3] / 2 + d_[1]), int(bx[0] / 2 + d_[0]):int(bx[2] / 2 + d_[0])] = 0.0   # the chest patch is carried, never redrawn
    # DifferentialDiffusion still repaints a 0 pixel on the last steps (measured: MAD 33 on the patch at mask 0), so the patch is
    # also pasted back from the start image after sampling: keepmask.png, painting px, feathered 3 px.
    kb = np.zeros((BH, BW), np.uint8); d2 = d_ * 2
    kb[int(bx[1] + d2[1]):int(bx[3] + d2[1]), int(bx[0] + d2[0]):int(bx[2] + d2[0])] = 255
    if vhand.any():  # the carried V hand is pasted back too, eroded 3 px so its rim blends with the refined sleeve
        kb = np.maximum(kb, (cv2.erode((vhand > 0.5).astype(np.uint8), np.ones((7, 7), np.uint8)) * 255).astype(np.uint8))
    Image.fromarray(kb).filter(ImageFilter.GaussianBlur(3)).save(f'keys3/inpaint_{K}/keepmask.png')
    sm = np.array(Image.fromarray((sm * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))) / 255.0; sm[prot_lat > 0.5] = 0
    Image.fromarray((sm * 255).astype(np.uint8)).save(f'keys3/inpaint_{K}/softmask.png')
    cm = M.grow(sm > 0.02, 9); cm = np.array(Image.fromarray((cm * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))); cm[prot_lat > 0.5] = 0
    Image.fromarray(cm.astype(np.uint8)).save(f'keys3/inpaint_{K}/compmask.png')
    json.dump({'torso_t': TORSO_T, 'arm_t': ARM_T, 'edge_t': EDGE_T, 'joint_t': JOINT_T, 'vhand_t': VHAND_T if K in ('K3_v_sign', 'K2_hands_low_front') else None, 'hand_r_latent': M.HAND_R, 'skirt_hand_t': SKIRT_HAND_T, 'fore_grow': M.FORE_GROW, 'badge_box': BADGE_BOX, 'hem_ride': HEM_RIDE, 'hem_y': hem_y, 'lift_r': Lr, 'lift_l': Ll, 'dneck': dn}, open(f'keys3/inpaint_{K}/prewarp.json', 'w'))
    print(K, 'hem_y', hem_y, 'lift r/l', Lr, Ll, 'dneck', dn, 'cleared px', int(clear.sum()), 'revealed skirt px', int((reveal & (Tw_a < 0.5)).sum()), 'softmask>0.9 px', int((sm > 0.9).sum()), 'torso-t px', int(((sm > 0.02) & (sm <= 0.9)).sum()))
_prot = {}
def protect_low_visible():
    upper = M.layer('topwear') | M.layer('handwear-l') | M.layer('handwear-r')
    return (M.layer('bottomwear') | M.layer('legwear') | M.layer('footwear')) & ~upper
def protect_of(K):
    if K not in _prot:
        cj_ = cj; kp = json.load(open(f'keys3/{K}.json'))['points']
        upper = M.layer('topwear') | M.layer('handwear-l') | M.layer('handwear-r')
        hair = M.grow(M.layer('front hair') | M.layer('headwear') | (M.layer('back hair') & ~upper & ~M.layer('neck') & ~M.layer('bottomwear') & ~M.layer('legwear')), 5)
        low = (M.layer('bottomwear') | M.layer('legwear') | M.layer('footwear')) & ~upper
        from PIL import ImageDraw
        hd = Image.new('L', (832, 1216), 0); d = ImageDraw.Draw(hd)
        for s in 'lr':
            e, w = np.array(kp[f'{s}_elbow']), np.array(kp[f'{s}_wrist']); u = (w - e) / np.linalg.norm(w - e); c = w + u * M.HAND_R * 0.6
            d.ellipse([c[0] - M.HAND_R, c[1] - M.HAND_R, c[0] + M.HAND_R, c[1] + M.HAND_R], fill=255)
        fore = M.grow(M.capsules(kp, [(f'{s}_elbow', f'{s}_wrist') for s in 'lr'], M.ARM_W) | (np.array(hd) > 127), M.FORE_GROW)
        face = Image.new('L', (832, 1216), 0)
        ex, ey = (cj_['l_eye'][0] + cj_['r_eye'][0]) / 4, (cj_['l_eye'][1] + cj_['r_eye'][1]) / 4; rx = abs(cj_['l_ear'][0] - cj_['r_ear'][0]) / 4 * 1.05
        ImageDraw.Draw(face).ellipse([ex - rx, ey - rx * 1.05, ex + rx, ey + rx * 1.35], fill=255)
        _prot[K] = ((np.array(face) > 127) | hair | (low & ~fore)).astype(np.float32)
    return _prot[K]
if __name__ == '__main__':
    for K in (sys.argv[3:] or KEYS): build(K)
