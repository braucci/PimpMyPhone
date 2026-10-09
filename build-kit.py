#!/usr/bin/env python3
"""Build the small public source kit, excluding caches and private local data."""
from pathlib import Path
import hashlib
import tarfile

ROOT = Path(__file__).resolve().parent
kit = ROOT / 'kit/biapod-kit'
files = sorted(p for p in kit.rglob('*') if p.is_file()
               and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name != 'SHA256SUMS')
manifest = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(kit).as_posix()}\n' for p in files)
(kit / 'SHA256SUMS').write_text(manifest)
archive = ROOT / 'downloads/biapod-kit-0.1.tar.gz'
with tarfile.open(archive, 'w:gz') as tar:
    for p in files + [kit / 'SHA256SUMS']:
        info = tar.gettarinfo(str(p), arcname='biapod-kit/' + p.relative_to(kit).as_posix())
        info.uid = info.gid = 0
        info.uname = info.gname = ''
        info.mtime = 1791468000
        info.mode = 0o755 if p.suffix == '.py' or p.name in ('biapod-session', 'biapod-audio-route') else 0o644
        with p.open('rb') as f:
            tar.addfile(info, f)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(ROOT / 'downloads/biapod-kit-0.1.sha256').write_text(f'{digest}  {archive.name}\n')
print(f'{archive.name}: {archive.stat().st_size} bytes, {len(files)} source files, SHA-256 {digest}')
