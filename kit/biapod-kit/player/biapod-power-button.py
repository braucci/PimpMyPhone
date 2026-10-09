#!/usr/bin/env python3
"""Open manual maintenance on three Power presses; single presses do nothing."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

runtime = Path(os.environ['XDG_RUNTIME_DIR'])
path = runtime / 'biapod-power-clicks.json'
with path.open('a+') as stream:
    os.chmod(path, 0o600)
    fcntl.flock(stream, fcntl.LOCK_EX)
    stream.seek(0)
    try:
        clicks = json.load(stream)
    except (ValueError, TypeError):
        clicks = []
    now = time.monotonic()
    clicks = [stamp for stamp in clicks if 0 <= now - stamp <= 1.5]
    clicks.append(now)
    launch = len(clicks) >= 3
    stream.seek(0)
    stream.truncate()
    json.dump([] if launch else clicks, stream)
if launch:
    subprocess.Popen([sys.executable, '/home/user/pinepod/biapod-maintenance.py'],
                     stdin=subprocess.DEVNULL)
