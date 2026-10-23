"""RTMPose whole-body (rtmlib 'balanced': yolox_m humanart + rtmw-dw-x-l 256x192, onnxruntime CPU) on one still,
read from the rtmlib checkpoint directory named by RTMLIB_CHECKPOINTS, by explicit path, so nothing is downloaded. Output shape:
width, height, joints{body-18 name: [x, y, score]} (neck = shoulders' midpoint, score = the lower shoulder's), wholebody (133).
keypoints.py <image.png> <out.json>"""
import json, os, sys, cv2, numpy as np
from rtmlib import Wholebody
C = os.environ['RTMLIB_CHECKPOINTS'].rstrip('/') + '/'   # the directory holding the two .onnx files below
m = Wholebody(det=C + 'yolox_m_8xb8-300e_humanart-c2c7a14a.onnx', det_input_size=(640, 640),
              pose=C + 'rtmw-dw-x-l_simcc-cocktail14_270e-256x192_20231122.onnx', pose_input_size=(192, 256),
              backend='onnxruntime', device='cpu')
img = cv2.imread(sys.argv[1]); H, W = img.shape[:2]
kp, sc = m(img)
k = int(np.argmax([s[:17].mean() for s in sc]))
P, S = kp[k], sc[k]
COCO = ['nose','l_eye','r_eye','l_ear','r_ear','l_shoulder','r_shoulder','l_elbow','r_elbow','l_wrist','r_wrist','l_hip','r_hip','l_knee','r_knee','l_ankle','r_ankle']
J = {n: [round(float(P[i][0]), 1), round(float(P[i][1]), 1), round(float(S[i]), 3)] for i, n in enumerate(COCO)}
J['neck'] = [round(float((P[5][0] + P[6][0]) / 2), 1), round(float((P[5][1] + P[6][1]) / 2), 1), round(float(min(S[5], S[6])), 3)]
doc = {'width': W, 'height': H, 'people_detected': len(kp), 'joints': J,
       'wholebody': [[round(float(x), 1), round(float(y), 1), round(float(c), 3)] for (x, y), c in zip(P, S)]}
json.dump(doc, open(sys.argv[2], 'w'), indent=1); print(sys.argv[1], 'people', len(kp), 'mean body score', round(float(S[:17].mean()), 3))
