"""Replay the exact accepted v3 payload from dancer/ alone; no motion authoring."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight():
    record = json.loads((SOURCE / 'declared-repairs-v3.json').read_text())
    # Historical replay binds the archived keeper, not the new active producer mesh.
    config = json.loads((SOURCE / 'provenance/keeper-config-before-smear50.json').read_text())
    assert config.pop('x-repairs') == {'file': 'declared-repairs-v3.json', 'sha256': sha(SOURCE / 'declared-repairs-v3.json')}, 'REPAIRS_HASH: config.json'
    producer = (json.dumps(config, indent=2, ensure_ascii=False) + '\n').encode()
    assert hashlib.sha256(producer).hexdigest() == record['baseline']['config.json']['sha256'], 'PRODUCER_HASH: config.json excluding x-repairs'
    for group in ('canonical',):
        for row in record[group].values():
            assert sha(SOURCE / row['file']) == row['sha256'], 'CANONICAL_HASH: ' + row['file']
    for row in record['parts'] + record['generation'] + [record['previousRepairs']]:
        assert sha(SOURCE / row['file']) == row['sha256'], 'SOURCE_HASH: ' + row['file']
    assert sha(SOURCE / 'accepted-dance/viewport.json') == record['render']['viewportSHA256'], 'VIEWPORT_HASH'
    assert sha(SOURCE / 'accepted/sequence.json') == record['baseline']['accepted/sequence.json']['sha256'], 'SEQUENCE_HASH'
    rig = json.loads((SOURCE / record['canonical']['rig']['file']).read_text())
    motion = json.loads((SOURCE / record['canonical']['motion']['file']).read_text())
    assert rig['images'] == '../../work/corpus/dancer/accepted/images'
    assert [s['name'] for s in rig['slots']] == record['slotOrder'], 'SLOT_ORDER'
    slots = {s['name']: s for s in rig['slots']}
    for slot in record['slots']:
        assert slots[slot['name']] == slot, 'SLOT_VALUE: ' + slot['name']
    for item in record['attachments']:
        assert rig['skins']['default'][item['slot']][item['attachment']] == item['value'], 'ATTACHMENT_VALUE: ' + item['attachment']
    tracks = motion['animations']['zero-two-r3-hand']['tracks']
    for tr in record['changedOrAddedMotionTracks']:
        assert tr in tracks, 'MOTION_TRACK: ' + str(tr.get('bone', tr.get('slot')))
    for row in record['parts']:
        data = (SOURCE / row['file']).read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n', 'PNG_HEADER'
        offset = 8
        while offset < len(data):
            size = struct.unpack('>I', data[offset:offset + 4])[0]
            assert data[offset + 4:offset + 8] in (b'IHDR', b'IDAT', b'IEND'), 'PNG_PRIVATE_METADATA'
            offset += size + 12
    subprocess.run([sys.executable, 'check-inputs.py'], cwd=SOURCE, check=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='work/accepted-dance')
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    record = preflight()
    if args.preflight:
        print('V3_PREFLIGHT_PASS: exact source, declarations, producer metadata, PNG hygiene and full corpus closure')
        return
    workspace = Path(args.out).resolve()
    if workspace.exists():
        raise SystemExit('OUTPUT_EXISTS: choose a new output directory; existing evidence is preserved')
    workspace.mkdir(parents=True)
    corpus = workspace / 'work/corpus/dancer'
    shutil.copytree(SOURCE, corpus, ignore=shutil.ignore_patterns('work', 'node_modules', '__pycache__', '.git', '*.pyc'))
    runtime = workspace / 'work/runtime'
    runtime.mkdir(parents=True)
    for name in ('package.json', 'bun.lock'):
        shutil.copyfile(corpus / 'accepted-dance' / name, runtime / name)
    payload = workspace / 'hand/v3'
    payload.mkdir(parents=True)
    for name in ('rig', 'motion'):
        row = record['canonical'][name]
        shutil.copyfile(corpus / row['file'], payload / (name + '.json'))
        assert sha(payload / (name + '.json')) == row['sha256']
    logs = workspace / 'logs'
    logs.mkdir()
    env = dict(os.environ)
    for key in ('UV_THREADPOOL_SIZE', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'RAYON_NUM_THREADS'):
        env[key] = '1'
    env['BUN_CONFIG_MAX_HTTP_REQUESTS'] = '4'
    commands = []

    def run(label, command, cwd=workspace):
        print('V3_COMMAND', label, json.dumps(command), flush=True)
        commands.append({'label': label, 'command': command})
        with (logs / (label + '.txt')).open('w') as log:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                log.write(line)
                print(line, end='', flush=True)
            code = process.wait()
        if code:
            raise SystemExit(code)

    run('install', ['bun', 'install', '--frozen-lockfile'], runtime)
    for package, version in record['pins'].items():
        if package == 'bun':
            assert subprocess.check_output(['bun', '--version'], text=True).strip() == version
        else:
            assert json.loads((runtime / 'node_modules' / package / 'package.json').read_text())['version'] == version, package
    core = ['bun', str(runtime / 'node_modules/rig-c/cli.ts')]
    run('readers', ['bun', str(corpus / 'tools/read-accepted-inputs.ts'), str(runtime / 'node_modules/rig-c'), str(corpus / 'accepted/sequence.json'), str(payload)])
    run('build', core + ['build', '--rig', 'hand/v3/rig.json', '--motion', 'hand/v3/motion.json', '--out', 'build', '--profile', 'spine'])
    build = {name: sha(workspace / 'build' / name) for name in record['render']['build']}
    result = {'spec': 'dancer-v3-reproduction/1', 'version': 'v3', 'source': 'dancer corpus only; no trial, private checkout, inference or retarget dependency',
              'originalRigSHA256': sha(payload / 'rig.json'), 'originalMotionSHA256': sha(payload / 'motion.json'),
              'build': build, 'expectedBuild': record['render']['build'], 'commands': commands, 'stage': 'build'}
    def save():
        (workspace / 'reproduction.json').write_text(json.dumps(result, indent=2) + '\n')
    save()
    assert build == record['render']['build'], 'STOP: compiled bytes differ; no adaptation or correction attempted'
    run('render', core + ['render', '--candidate', 'build', '--animation', 'zero-two-r3-hand', '--fps', '30', '--viewport-from', str(corpus / 'accepted-dance/viewport.json'), '--out', 'render'])
    paths = sorted((workspace / 'render/zero-two-r3-hand@30fps').glob('f*.png'))
    assert [p.name for p in paths] == ['f%04d.png' % i for i in range(391)], 'FRAME_INVENTORY'
    digest = hashlib.sha256()
    hashes = []
    for path in paths:
        data = path.read_bytes()
        assert struct.unpack('>II', data[16:24]) == (736, 960) and data[25] == 6, 'NATIVE_RGBA_SIZE'
        digest.update(data)
        hashes.append({'file': path.name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    result.update(stage='render', nativeFrames=391, fps=30, size=[736, 960], framesSHA256=digest.hexdigest(),
                  expectedFramesSHA256=record['render']['sha256'], frameHashes=hashes,
                  computation='SHA256(concat native f0000.png .. f0390.png file bytes, no separators)',
                  retargetOrHandWork=False, commands=commands)
    save()
    assert result['framesSHA256'] == result['expectedFramesSHA256'], 'STOP: native accepted frame digest differs; no tuning attempted'
    print('V3_REPRODUCTION_PASS ' + digest.hexdigest(), flush=True)


if __name__ == '__main__':
    main()
