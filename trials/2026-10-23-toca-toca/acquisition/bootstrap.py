"""Prepare the exact CPU environment and declared model files, not pose data."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--models', required=True)
args, _ = parser.parse_known_args()
here = Path(__file__).resolve().parent
pins = json.loads((here / 'pins.json').read_text())
runtime = here / '.runtime'
uv = here / '.uvbin/uv'
if not uv.exists():
    data = urllib.request.urlopen(pins['uv']['url']).read()
    assert hashlib.sha256(data).hexdigest() == pins['uv']['sha256'], 'uv digest mismatch'
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        binary = next(n for n in archive.namelist() if n.endswith('/uv') and not n.endswith('/bin/uv'))
        uv.parent.mkdir(exist_ok=True)
        uv.write_bytes(archive.read(binary))
    os.chmod(uv, 0o755)
if not runtime.exists():
    subprocess.run([str(uv), 'venv', '--python', 'python3', str(runtime)], check=True)
subprocess.run([str(uv), 'pip', 'install', '--python', str(runtime / 'bin/python'),
                '--no-deps', '--require-hashes', '-r', str(here / 'requirements.lock')], check=True)
# Nova captures only inputs inside its boundary; materialise interpreter links.
for path in (runtime / 'bin').iterdir():
    if path.is_symlink() and not path.resolve().is_relative_to(Path.cwd()):
        target = path.resolve()
        path.unlink()
        shutil.copy2(target, path)
models = Path(args.models)
models.mkdir(parents=True, exist_ok=True)
for row in pins['models'].values():
    target = models / row['file']
    cached = Path.home() / '.cache/rtmlib/hub/checkpoints' / row['file']
    if not target.exists():
        if cached.is_file():
            shutil.copy2(cached, target)
        else:
            data = urllib.request.urlopen(row['url']).read()
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = [n for n in archive.namelist() if Path(n).name == row['file']]
                assert len(names) == 1, 'declared model not found in archive'
                target.write_bytes(archive.read(names[0]))
    h = hashlib.sha256()
    with target.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    assert h.hexdigest() == row['sha256'], 'model digest mismatch: ' + row['file']
print('Environment and both declared model digests verified before inference.', flush=True)
