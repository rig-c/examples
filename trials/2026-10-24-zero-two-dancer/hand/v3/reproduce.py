#!/usr/bin/env python3
"""Replay the accepted payload only. No acquisition, retarget or art generation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
TRIAL = HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight():
    manifest = json.loads((HERE / 'inputs.json').read_text())
    for row in manifest['files']:
        path = HERE / row['path']
        if sha(path) != row['sha256']:
            raise ValueError('INPUT_SHA: ' + row['path'])
    assert sha(TRIAL / 'hand/r3/viewport.json') == manifest['viewportSHA256']
    assert sha(TRIAL / 'hand/r3/inputs/sequence.json') == manifest['sequenceSHA256']
    rig = json.loads((HERE / 'rig.json').read_text())
    motion = json.loads((HERE / 'motion.json').read_text())
    assert rig['images'] == '../../work/corpus/dancer/accepted/images'
    assert motion['animations']['zero-two-r3-hand']['duration'] == 13
    for row in manifest['files']:
        if row['path'].endswith('.png'):
            data = (HERE / row['path']).read_bytes()
            assert data[:8] == b'\x89PNG\r\n\x1a\n'
            offset = 8
            while offset < len(data):
                size = struct.unpack('>I', data[offset:offset + 4])[0]
                tag = data[offset + 4:offset + 8]
                assert tag in (b'IHDR', b'IDAT', b'IEND'), tag
                offset += size + 12
    return manifest


def run(args, cwd):
    print('COMMAND ' + json.dumps(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    manifest = preflight()
    if args.preflight:
        print('INPUT_PREFLIGHT_PASS: exact payloads, PNG chunks, viewport and sequence')
        return
    if args.runtime is None or args.out is None:
        parser.error('--runtime and --out are required for replay')
    runtime, out = args.runtime.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    # Keep the accepted relative images field and every source byte unchanged.
    trial = out / 'trial'
    payload = trial / 'hand/v3'
    payload.mkdir(parents=True)
    for name in ('rig.json', 'motion.json'):
        shutil.copyfile(HERE / name, payload / name)
    images = trial / 'work/corpus/dancer/accepted/images'
    images.mkdir(parents=True)
    corpus = json.loads((TRIAL / 'corpus-inputs.json').read_text())
    image_rows = [r for r in corpus if r['path'].startswith('dancer/accepted/images/')]
    for row in image_rows:
        url = 'https://raw.githubusercontent.com/rig-c/examples/' + row['ref'] + '/' + row['path']
        with urlopen(url, timeout=60) as response:
            data = response.read()
        assert hashlib.sha256(data).hexdigest() == row['sha256'], row['path']
        (images / Path(row['path']).name).write_bytes(data)
    for name in ('arms_hold_head.png', 'arms_hold_front.png', 'waist.png'):
        shutil.copyfile(HERE / 'images' / name, images / name)
    cli = runtime / 'node_modules/rig-c/cli.ts'
    assert json.loads((runtime / 'node_modules/rig-c/package.json').read_text())['version'] == '2.67.2'
    assert json.loads((runtime / 'node_modules/@esotericsoftware/spine-core/package.json').read_text())['version'] == '4.3.13'
    assert subprocess.check_output(['bun', '--version'], text=True).strip() == '1.4.2'
    run(['bun', str(HERE / 'read-inputs.ts'), str(runtime / 'node_modules/rig-c'), str(TRIAL / 'hand/r3/inputs/sequence.json'), str(payload)], trial)
    run(['bun', str(cli), 'build', '--rig', 'hand/v3/rig.json', '--motion', 'hand/v3/motion.json', '--out', 'build', '--profile', 'spine'], trial)
    build = {name: sha(trial / 'build' / name) for name in manifest['acceptedBuild']}
    # A compiled residual is reported before any attempt to render or adapt it.
    partial = {'spec': 'examples-v3-replay/1', 'stage': 'build', 'build': build,
               'expectedBuild': manifest['acceptedBuild'], 'exactSourceBytes': True}
    (out / 'result.json').write_text(json.dumps(partial, indent=2) + '\n')
    assert build == manifest['acceptedBuild'], 'STOP: compiled build differs; no source adaptation attempted'
    run(['bun', str(cli), 'render', '--candidate', 'build', '--animation', 'zero-two-r3-hand', '--fps', '30', '--viewport-from', str(TRIAL / 'hand/r3/viewport.json'), '--out', 'render'], trial)
    frames = trial / 'render/zero-two-r3-hand@30fps'
    paths = sorted(frames.glob('f*.png'))
    assert [p.name for p in paths] == ['f%04d.png' % i for i in range(391)]
    digest = hashlib.sha256()
    frame_rows = []
    for p in paths:
        data = p.read_bytes()
        assert struct.unpack('>II', data[16:24]) == (736, 960)
        assert data[25] == 6, 'native RGBA required'
        digest.update(data)
        frame_rows.append({'file': p.name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    result = {**partial, 'stage': 'render', 'frames': 391, 'fps': 30,
              'nativeSize': [736, 960], 'framesSHA256': digest.hexdigest(),
              'expectedFramesSHA256': manifest['acceptedFramesSHA256'],
              'digestAlgorithm': 'SHA256(concat native f0000.png .. f0390.png bytes, no separators)',
              'frameHashes': frame_rows, 'retargetRerun': False,
              'artOrMotionEdits': False, 'audioOrReferencePixels': False}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    assert digest.hexdigest() == manifest['acceptedFramesSHA256'], 'STOP: accepted frame digest mismatch'
    print('ACCEPTED_REPLAY_PASS ' + digest.hexdigest(), flush=True)


if __name__ == '__main__':
    main()
