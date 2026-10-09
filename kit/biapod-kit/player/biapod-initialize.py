#!/usr/bin/env python3
"""Initial low volume; subsequent sessions preserve MPD state. Update the index."""
from pathlib import Path
import time
from mpdclient import MPD, first

flag = Path.home() / '.local/state/biapod-initialized'
for attempt in range(30):
    try:
        client = MPD()
        status = client.command('status')
        if not flag.exists():
            client.command('setvol', 10)
            if first(status, 'state') == 'play':
                client.command('pause', 1)
            flag.write_text('Initial volume configured\n')
        client.command('update')
        break
    except (OSError, RuntimeError):
        time.sleep(1)
else:
    raise SystemExit('MPD non disponibile: controlla biapod-mpd.service')
