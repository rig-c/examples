"""Fetch only pinned public corpus blobs; never fetch the withheld video."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--out', default='work/corpus')
args = parser.parse_args()
rows = json.loads(Path('corpus-inputs.json').read_text())
for row in rows:
    target = Path(args.out) / row['path']
    if not target.exists():
        url = f"https://raw.githubusercontent.com/rig-c/examples/{row['ref']}/{row['path']}"
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(url, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise SystemExit(f"Hash mismatch: {row['path']}")
        target.write_bytes(data)
    if hashlib.sha256(target.read_bytes()).hexdigest() != row['sha256']:
        raise SystemExit(f"Hash mismatch: {row['path']}")
print(f'Verified {len(rows)} public corpus inputs.')
