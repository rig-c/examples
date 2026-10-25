"""Hash ordered frame PNG bytes, retain a receipt, and optionally delete only those frames."""
from pathlib import Path
import argparse
import hashlib
import json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('frames')
parser.add_argument('receipt')
parser.add_argument('--command', required=True)
parser.add_argument('--viewport')
parser.add_argument('--delete', action='store_true')
args = parser.parse_args()
root = Path(args.frames)
files = sorted(root.rglob('f[0-9]*.png'))
if not files:
    raise SystemExit('FRAMES_ABSENT: no numbered frame PNGs; no receipt written')
digest = hashlib.sha256()
for file in files:
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
record = {'spec': 'dancer-frame-receipt/1', 'command': args.command,
          'frames': len(files), 'order': [file.relative_to(root).as_posix() for file in files],
          'sha256': digest.hexdigest(), 'deleted': args.delete}
if args.viewport:
    record['viewport'] = json.loads(Path(args.viewport).read_text())
output = Path(args.receipt)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(record, indent=2) + '\n')
if args.delete:
    for file in files:
        file.unlink()
print('FRAME_RECEIPT', len(files), digest.hexdigest(), 'deleted' if args.delete else 'retained')
