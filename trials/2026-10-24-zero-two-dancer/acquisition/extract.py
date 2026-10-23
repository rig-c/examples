"""External RTMPose acquisition: body-18 coordinates, never reference pixels.

Reviewed copy of the supplied extraction recipe. Model files, package versions,
video digest, resource limits and acceptance bars are frozen before inference.
"""
import argparse
import hashlib
import importlib.metadata
import inspect
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from rtmlib import Wholebody

parser = argparse.ArgumentParser()
parser.add_argument('--video', required=True)
parser.add_argument('--models', required=True)
parser.add_argument('--out', required=True)
parser.add_argument('--frames', help='bounded precheck indexes, e.g. 0,156,312')
args = parser.parse_args()
here = Path(__file__).resolve().parent
frozen = json.loads((here / 'pins.json').read_text())
bars = json.loads((here / 'acceptance.json').read_text())
for package, version in frozen['packages'].items():
    if importlib.metadata.version(package) != version:
        raise SystemExit('ACQUISITION_PACKAGE: ' + package + ' differs from the frozen version')
if hashlib.sha256(Path(inspect.getfile(Wholebody)).read_bytes()).hexdigest() != frozen['wholebodySourceSHA256']:
    raise SystemExit('ACQUISITION_PACKAGE: Wholebody source differs from the frozen package')
out = Path(args.out)
out.mkdir(parents=True, exist_ok=False)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

video_sha = sha(args.video)
if video_sha != frozen['video']['sha256']:
    raise SystemExit('ACQUISITION_VIDEO_HASH: source does not match the frozen input')
model_paths = {}
for role, row in frozen['models'].items():
    path = Path(args.models) / row['file']
    if sha(path) != row['sha256']:
        raise SystemExit('ACQUISITION_MODEL_HASH: ' + role + ' differs from the frozen model')
    model_paths[role] = str(path)
cap = cv2.VideoCapture(args.video)
if not cap.isOpened():
    raise SystemExit('ACQUISITION_VIDEO: video did not open')
fps = cap.get(cv2.CAP_PROP_FPS)
W, H = int(cap.get(3)), int(cap.get(4))
if [W, H] != bars['videoSize'] or abs(fps - bars['fps']) > bars['fpsTolerance']:
    raise SystemExit('ACQUISITION_VIDEO: dimensions or fps differ from the frozen input')
original_size = [W, H]
cap.release()
version_line = subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]
if version_line != frozen['decoder']['firstVersionLine']:
    raise SystemExit('ACQUISITION_DECODER: ffmpeg version differs from frozen pin')
W, H = bars['processingSize']
selected = [int(x) for x in args.frames.split(',')] if args.frames else None
cv2.setNumThreads(4)
factory = ort.InferenceSession

def bounded_session(*positional, **keywords):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    keywords['sess_options'] = options
    return factory(*positional, **keywords)

# Configure the supported ONNX SessionOptions without editing rtmlib files.
ort.InferenceSession = bounded_session
try:
    model = Wholebody(det=model_paths['det'], det_input_size=(640, 640),
                      pose=model_paths['pose'], pose_input_size=(192, 256),
                      mode='balanced', backend='onnxruntime', device='cpu')
finally:
    ort.InferenceSession = factory
providers = {'det': model.det_model.session.get_providers(),
             'pose': model.pose_model.session.get_providers()}
if any(value != ['CPUExecutionProvider'] for value in providers.values()):
    raise SystemExit('ACQUISITION_CPU: CPUExecutionProvider alone is required')
COCO = ['nose', 'l_eye', 'r_eye', 'l_ear', 'r_ear', 'l_shoulder', 'r_shoulder',
        'l_elbow', 'r_elbow', 'l_wrist', 'r_wrist', 'l_hip', 'r_hip',
        'l_knee', 'r_knee', 'l_ankle', 'r_ankle']
frames, raw, selections = [], [], []
decode_command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-c:v', 'libdav1d',
                  '-threads', '4', '-i', args.video, '-map', '0:v:0', '-an',
                  '-fps_mode', 'passthrough', '-pix_fmt', 'bgr24', '-f', 'rawvideo', 'pipe:1']
decode_log = (out / 'decode.log').open('w')
decoder = subprocess.Popen(decode_command, stdout=subprocess.PIPE, stderr=decode_log)
frame_bytes = original_size[0] * original_size[1] * 3
i = 0
while True:
    buffer = decoder.stdout.read(frame_bytes)
    if not buffer:
        break
    if len(buffer) != frame_bytes:
        raise SystemExit('ACQUISITION_DECODER: incomplete raw frame')
    img = np.frombuffer(buffer, dtype=np.uint8).reshape((original_size[1], original_size[0], 3))
    if selected is not None and i not in selected:
        i += 1
        continue
    img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
    kp, sc = model(img)
    if len(kp) == 0:
        frames.append({'t': round(i / fps, 5), 'people': []})
        raw.append(None)
        selections.append({'frame': i, 'candidates': 0, 'selected': None})
        i += 1
        continue
    confidence = [float(scores[:17].mean()) for scores in sc]
    if not np.isfinite(confidence).all():
        raise SystemExit('ACQUISITION_PERSON: nonfinite body-17 confidence')
    k = int(np.argmax(confidence))
    P, Sc = kp[k], sc[k]
    if len(P) != 133 or not np.isfinite(P).all() or not np.isfinite(Sc).all():
        raise SystemExit('ACQUISITION_POINTS: 133 finite whole-body points are required')
    J = {}
    for n, name in enumerate(COCO):
        J[name] = {'state': 'observed' if Sc[n] >= 0.3 else 'occluded',
                   'at': [round(float(P[n][0]), 1), round(float(P[n][1]), 1)],
                   'score': round(float(Sc[n]), 3)}
    ls, rs = P[5], P[6]
    score = float(min(Sc[5], Sc[6]))
    J['neck'] = {'state': 'observed' if score >= 0.3 else 'occluded',
                 'at': [round(float((ls[0] + rs[0]) / 2), 1),
                        round(float((ls[1] + rs[1]) / 2), 1)],
                 'score': round(score, 3)}
    frames.append({'t': round(i / fps, 5), 'people': [{'id': 'a', 'joints': J}]})
    raw.append({'t': round(i / fps, 5), 'points': [[round(float(x), 1), round(float(y), 1),
                round(float(c), 3)] for (x, y), c in zip(P, Sc)]})
    selections.append({'frame': i, 'candidates': len(kp), 'selected': k,
                       'body17MeanConfidences': confidence})
    i += 1
    if i % 30 == 0:
        print('acquisition: decoded', i, 'frames', flush=True)
decode_exit = decoder.wait()
decode_log.close()
if decode_exit:
    raise SystemExit('ACQUISITION_DECODER: ffmpeg exited ' + str(decode_exit))
doc = {'spec': 'rig-c-pose-frames/0',
       'space': {'units': 'painting-px', 'origin': 'top-left', 'y': 'down'},
       'width': W, 'height': H, 'fps': fps,
       'source': "ZeroTwo; YouTube Shorts BGyjsZsWndA; creator not identified; original video withheld; "
                 "RTMPose Wholebody balanced, rtmw-dw-x-l, rtmlib/onnxruntime CPU; "
                 "highest mean body-17 confidence per frame; original decoded and resized to 1080x1920 with OpenCV INTER_AREA; "
                 "body-18 names, neck = shoulders' midpoint; model and video digests in pins.json",
       'frames': frames}
empty = sum(not frame['people'] for frame in frames)
expected_indexes = selected if selected is not None else list(range(bars['frames']))
valid = i == bars['frames'] and len(frames) == len(expected_indexes) and empty == bars['emptyFrames']
record = {'stage': 'precheck' if selected is not None else 'fresh full acquisition',
          'PASS': valid, 'decodedFrames': i, 'inferredFrames': len(frames),
          'fps': fps, 'originalSize': original_size, 'size': [W, H], 'emptyFrames': empty, 'frameIndexes': expected_indexes,
          'providers': providers, 'sourceVideoSHA256': video_sha,
          'decodeCommand': decode_command, 'decodeExitCode': decode_exit, 'decoderVersion': version_line,
          'models': frozen['models'], 'selections': selections,
          'limits': 'Detection/structure only; no semantic dance, hand-pass or planted-foot verdict.'}
(out / 'pose.json').write_text(json.dumps(doc, separators=(',', ':')) + '\n')
(out / 'raw_wholebody.json').write_text(json.dumps({'spec': 'coco-wholebody-133',
    'fps': fps, 'width': W, 'height': H, 'frames': raw}, separators=(',', ':')) + '\n')
(out / 'report.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: record[k] for k in ['stage', 'PASS', 'decodedFrames', 'inferredFrames',
                                      'fps', 'size', 'emptyFrames', 'providers']}), flush=True)
raise SystemExit(0 if valid else 1)
