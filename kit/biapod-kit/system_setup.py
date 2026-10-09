#!/usr/bin/env python3
"""Select/restore a dedicated tinydm session. Does not write storage images."""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys

STATE = Path('/var/lib/pimpmyphone')
SESSION = Path('/var/lib/tinydm/default-session.desktop')
DESKTOP = Path('/usr/share/wayland-sessions/biapod.desktop')
UNITS = ('ModemManager.service', 'eg25-manager.service', 'bluetooth.service',
         'wpa_supplicant.service', 'hkdm.service')


def run(*args, check=True):
    return subprocess.run(args, text=True, capture_output=True, check=check)


def main():
    if os.getuid() != 0 or len(sys.argv) != 3 or sys.argv[1] not in ('activate', 'restore'):
        raise SystemExit('Uso: sudo python3 system_setup.py activate|restore nome_utente')
    action, username = sys.argv[1:]
    user = pwd.getpwnam(username)
    if user.pw_uid == 0:
        raise SystemExit('Indica l’utente normale del lettore.')
    home = Path(user.pw_dir)
    if action == 'restore':
        manifest = json.loads((STATE / 'session.json').read_text())
        if SESSION.is_symlink() or SESSION.exists():
            SESSION.unlink()
        shutil.copy2(STATE / 'original-session.desktop', SESSION, follow_symlinks=False)
        for unit, previous in manifest['units'].items():
            if previous != 'masked':
                run('systemctl', 'unmask', unit)
                if previous == 'enabled':
                    run('systemctl', 'enable', unit)
        print('SESSIONE_PRECEDENTE_RIPRISTINATA. Esegui il ripristino utente e riavvia.')
        return
    if run('uname', '-r').stdout.strip() != '6.17.5':
        raise SystemExit('Kernel diverso dalla base documentata.')
    if b'pine64,pinephone' not in Path('/proc/device-tree/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Dispositivo non supportato.')
    if not SESSION.is_symlink() or not (home / 'pinepod/biapod-session').is_file():
        raise SystemExit('Mancano la sessione tinydm originale o i file utente del kit.')
    if STATE.exists() or DESKTOP.exists():
        raise SystemExit('Esiste già un backup o una sessione BiaPod. Non sovrascrivo.')
    STATE.mkdir(mode=0o700)
    shutil.copy2(SESSION, STATE / 'original-session.desktop', follow_symlinks=False)
    manifest = {'username': username, 'units': {}}
    for unit in UNITS:
        if run('systemctl', 'show', '-p', 'LoadState', '--value', unit).stdout.strip() != 'not-found':
            manifest['units'][unit] = run('systemctl', 'is-enabled', unit, check=False).stdout.strip()
    (STATE / 'session.json').write_text(json.dumps(manifest, indent=2))
    for unit, previous in manifest['units'].items():
        if previous != 'masked':
            run('systemctl', 'disable', '--now', unit)
            run('systemctl', 'mask', unit)
    DESKTOP.write_text(f'[Desktop Entry]\nName=BiaPod\nComment=PimpMyPhone dedicated music player\nExec={home}/pinepod/biapod-session\nType=Application\n')
    SESSION.unlink()
    SESSION.symlink_to(DESKTOP)
    run('systemctl', 'daemon-reload')
    print('SESSIONE_BIAPOD_PRONTA. Riavvia per attivarla; SSH non è stato abilitato all’avvio.')


if __name__ == '__main__':
    main()
