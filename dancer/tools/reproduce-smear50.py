"""Replay immutable accepted v3 or the mesh-only v4. No pose or mesh authoring runs."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parent.parent


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def canon(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode()


def validate_source(version):
    before = json.loads((SOURCE / 'accepted-dance/v3/rig.json').read_text())
    after = json.loads((SOURCE / 'accepted-dance/v4/rig.json').read_text())
    record = json.loads((SOURCE / 'accepted-dance/v4/provenance.json').read_text())
    assert sha(SOURCE / record['source']['rig']) == record['source']['rigSHA256'], 'V3_RIG_HASH'
    assert sha(SOURCE / record['source']['motion']) == record['source']['motionSHA256'], 'V3_MOTION_HASH'
    assert sha(SOURCE / 'accepted-dance/v4/rig.json') == record['rigSHA256'], 'V4_RIG_HASH'
    assert sha(SOURCE / 'accepted-dance/v4/motion.json') == record['motionSHA256'], 'V4_MOTION_HASH'
    assert (SOURCE / 'accepted-dance/v3/motion.json').read_bytes() == (SOURCE / 'accepted-dance/v4/motion.json').read_bytes(), 'MOTION_CHANGED'
    before_without_mesh = copy.deepcopy(before)
    after_without_mesh = copy.deepcopy(after)
    for rig in (before_without_mesh, after_without_mesh):
        del rig['skins']['default']['bottomwear']['bottomwear']
    assert before_without_mesh == after_without_mesh, 'NON_MESH_CHANGED'
    render = json.loads((SOURCE / 'declared-repairs-v3.json').read_text())['render']
    assert sha(SOURCE / 'accepted-dance/viewport.json') == render['viewportSHA256'], 'VIEWPORT_CHANGED'
    return SOURCE / ('accepted-dance/' + version), record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', choices=['v3', 'v4'], default='v4')
    p.add_argument('--out', required=True)
    p.add_argument('--preflight', action='store_true')
    p.add_argument('--build-only', action='store_true')
    p.add_argument('--render-only', action='store_true')
    p.add_argument('--keep-frames', action='store_true')
    a = p.parse_args()
    source, provenance = validate_source(a.version)
    root = Path(a.out).resolve()
    subprocess.run(['sh', 'tools/ensure-runtime.sh'], cwd=SOURCE, check=True)
    core = SOURCE / 'work/runtime/node_modules/rig-c'
    assert json.loads((core / 'package.json').read_text())['version'] == '2.67.2', 'PINNED_CORE_REQUIRED'
    commands = []
    def run(label, args):
        normalized = [str(x).replace(str(SOURCE), '<corpus>').replace(str(root), '<workspace>') for x in args]
        print('SMEAR50_COMMAND', label, json.dumps(normalized), flush=True)
        commands.append({'label': label, 'command': normalized})
        subprocess.run([str(x) for x in args], cwd=root, check=True)
    if not a.render_only:
        if root.exists():
            raise SystemExit('OUTPUT_EXISTS: use a new output directory')
        root.mkdir(parents=True)
        images = root / 'work/corpus/dancer/accepted/images'
        shutil.copytree(SOURCE / 'accepted/images', images)
        payload = root / ('hand/' + a.version)
        payload.mkdir(parents=True)
        for name in ['rig.json', 'motion.json']:
            shutil.copyfile(source / name, payload / name)
        run('readers', ['bun', SOURCE / 'tools/read-smear50.ts', core, payload / 'rig.json', payload / 'motion.json', root / 'build'])
        if a.preflight:
            print('SMEAR50_PREFLIGHT_PASS')
            return
        run('build', ['bun', core / 'cli.ts', 'build', '--rig', 'hand/' + a.version + '/rig.json', '--motion', 'hand/' + a.version + '/motion.json', '--out', 'build', '--profile', 'spine'])
        build = {name: sha(root / 'build' / name) for name in ['skeleton.json', 'skeleton.atlas', 'skeleton.model.json']}
        if a.version == 'v3':
            expected = json.loads((SOURCE / 'accepted-dance/v3/reproduction-evidence.json').read_text())['expectedBuild']
            assert build == expected, 'V3_BUILD_MISMATCH'
        checkpoint = {'version': a.version, 'rigSHA256': sha(source / 'rig.json'), 'motionSHA256': sha(source / 'motion.json'), 'build': build, 'commands': commands}
        (root / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2) + '\n')
        if a.build_only:
            print('SMEAR50_BUILD_CHECKPOINT', a.version)
            return
    checkpoint = json.loads((root / 'checkpoint.json').read_text())
    assert checkpoint['version'] == a.version and checkpoint['rigSHA256'] == sha(source / 'rig.json') and checkpoint['motionSHA256'] == sha(source / 'motion.json'), 'CHECKPOINT_SOURCE_CHANGED'
    assert all(sha(root / 'build' / name) == digest for name, digest in checkpoint['build'].items()), 'CHECKPOINT_BUILD_CHANGED'
    render = json.loads((SOURCE / 'declared-repairs-v3.json').read_text())['render']
    run('render', ['bun', core / 'cli.ts', 'render', '--candidate', 'build', '--animation', render['animation'], '--fps', str(render['fps']), '--viewport-from', SOURCE / 'accepted-dance/viewport.json', '--geometry', '--folds', '--out', 'render'])
    frames = root / 'render' / (render['animation'] + '@30fps')
    files = sorted(frames.glob('f[0-9]*.png'))
    assert len(files) == render['frames'], 'FRAME_COUNT'
    digest = hashlib.sha256()
    for file in files:
        digest.update(file.read_bytes())
    if a.version == 'v3':
        assert digest.hexdigest() == render['sha256'], 'V3_NATIVE_FRAMES_MISMATCH'
    receipt = {'spec': 'dancer-smear50-render/1', 'version': a.version, 'sourceRigSHA256': sha(source / 'rig.json'), 'sourceMotionSHA256': sha(source / 'motion.json'), 'build': checkpoint['build'], 'commands': checkpoint['commands'] + commands, 'frames': len(files), 'fps': 30, 'viewport': render['viewport'], 'background': render['background'], 'sha256': digest.hexdigest(), 'deleted': not a.keep_frames, 'geometrySHA256': sha(frames / 'geometry.json'), 'foldsSHA256': sha(frames / 'folds.json')}
    (root / 'render-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if not a.keep_frames:
        for file in files:
            file.unlink()
    print('SMEAR50_RENDER_RECEIPT', a.version, len(files), digest.hexdigest(), flush=True)


if __name__ == '__main__':
    main()
