#!/usr/bin/env python3
"""A manually opened terminal with its own on-screen keyboard; no SSH changes."""
import fcntl
import os
from pathlib import Path
import subprocess

lock = (Path(os.environ['XDG_RUNTIME_DIR']) / 'biapod-maintenance.lock').open('w')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit(0)
subprocess.run(['swaymsg', 'fullscreen disable'], check=True)
keyboard = subprocess.Popen(['wvkbd-mobintl', '-H', '480'])
try:
    subprocess.run(['foot', '--app-id=biapod-maintenance', '--title=BiaPod terminal', '/bin/sh'], check=True)
finally:
    keyboard.terminate()
    keyboard.wait()
    subprocess.run(['swaymsg', '[title="^BiaPod$"] focus, fullscreen enable'], check=False)
