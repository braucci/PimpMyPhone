#!/usr/bin/env python3
"""Prepare BiaPod user files; never flash or partition a disk. Public preview 0.1."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
HOME = Path.home()
BACKUP = HOME / '.local/state/pimpmyphone-backup'
USER_UNITS = ('mmsd-tng.service', 'vvmd.service', 'pipewire.service',
              'pipewire.socket', 'pipewire-pulse.service', 'pipewire-pulse.socket',
              'wireplumber.service')


def run(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True)


def device_check():
    if platform.machine() != 'aarch64' or not Path('/proc/device-tree/model').is_file():
        raise SystemExit('Kit specifico per PinePhone originale A64; esegui il controllo sul telefono.')
    model = Path('/proc/device-tree/model').read_text().rstrip('\0')
    compatible = Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
    if platform.machine() != 'aarch64' or b'pine64,pinephone' not in compatible or 'Pro' in model:
        raise SystemExit('Kit specifico per PinePhone originale A64.')
    if platform.release() != '6.17.5':
        raise SystemExit('Kernel diverso da 6.17.5: usa la base documentata; non forzare il controllo.')
    if not Path('/run/systemd/system').is_dir():
        raise SystemExit('Questa edizione richiede la base systemd documentata.')
    if os.getuid() == 0:
        raise SystemExit('Esegui setup.py come utente normale, senza sudo.')
    if not str(HOME).startswith('/home/') or any(c.isspace() or c in '"\'$\\' for c in str(HOME)):
        raise SystemExit('Questa anteprima richiede una home standard sotto /home, senza spazi.')
    for name in ('mpd', 'pulseaudio', 'pactl', 'sway', 'amixer', 'foot', 'wvkbd-mobintl', 'systemctl'):
        if not shutil.which(name):
            raise SystemExit(f'Manca {name}: verifica l’immagine e i pacchetti installati.')
    import gi
    import cairo  # noqa: F401
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk  # noqa: F401
    print('BASE_COMPATIBILE:', model, platform.release(), HOME)


def bus():
    os.environ.setdefault('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
    os.environ.setdefault('DBUS_SESSION_BUS_ADDRESS', f'unix:path={os.environ["XDG_RUNTIME_DIR"]}/bus')


def backup_file(relative, manifest):
    source = HOME / relative
    target = BACKUP / 'files' / relative
    exists = source.exists() or source.is_symlink()
    manifest['files'][relative] = exists
    if exists:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        else:
            shutil.copy2(source, target)


def install():
    device_check()
    if (HOME / 'pinepod').exists() or BACKUP.exists():
        raise SystemExit('Esiste già un’installazione o un backup PimpMyPhone. Non sovrascrivo.')
    run('systemctl', '--user', 'show-environment')
    BACKUP.mkdir(parents=True, mode=0o700)
    manifest = {'files': {}, 'units': {}}
    configs = {
        '.config/mpd/mpd.conf': f'''music_directory "{HOME}/Music"
playlist_directory "{HOME}/.local/share/mpd/playlists"
db_file "{HOME}/.local/share/mpd/database"
state_file "{HOME}/.local/share/mpd/state"
log_file "{HOME}/.local/state/mpd/log"
bind_to_address "127.0.0.1"
port "6600"
auto_update "no"
audio_output {{
    type "pulse"
    name "BiaPod"
    mixer_type "software"
}}
''',
        '.config/systemd/user/biapod-mpd.service': '''[Unit]
Description=BiaPod music engine
[Service]
Type=simple
ExecStart=/usr/bin/mpd --no-daemon %h/.config/mpd/mpd.conf
Restart=on-failure
RestartSec=2
[Install]
WantedBy=default.target
''',
        '.config/pulse/default.pa': (HERE / 'player/pulse-default.pa').read_text(),
    }
    for relative in configs:
        backup_file(relative, manifest)
    for unit in USER_UNITS:
        if run('systemctl', '--user', 'show', '-p', 'LoadState', '--value', unit).stdout.strip() != 'not-found':
            manifest['units'][unit] = run('systemctl', '--user', 'is-enabled', unit, check=False).stdout.strip()
            backup_file('.config/systemd/user/' + unit, manifest)
    (BACKUP / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    app = HOME / 'pinepod'
    app.mkdir()
    for source in (HERE / 'player').iterdir():
        if source.is_file():
            target = app / source.name
            target.write_text(source.read_text().replace('/home/user', str(HOME)))
            target.chmod(0o755 if source.suffix != '.svg' else 0o644)
    for relative, text in configs.items():
        target = HOME / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            target.unlink()
        target.write_text(text)
    for relative in ('Music', '.local/share/mpd/playlists', '.local/state/mpd'):
        (HOME / relative).mkdir(parents=True, exist_ok=True)
    for unit, state in manifest['units'].items():
        if state != 'masked':
            run('systemctl', '--user', 'mask', '--now', unit)
    run('systemctl', '--user', 'daemon-reload')
    print('FILE_UTENTE_PRONTI. Copia due album e continua alla tappa 07.')


def restore():
    if os.getuid() == 0:
        raise SystemExit('Ripristino utente: esegui senza sudo.')
    manifest = json.loads((BACKUP / 'manifest.json').read_text())
    run('systemctl', '--user', 'stop', 'biapod-mpd.service', check=False)
    for unit, state in manifest['units'].items():
        if state != 'masked':
            run('systemctl', '--user', 'unmask', unit, check=False)
    for relative, existed in manifest['files'].items():
        target = HOME / relative
        if target.exists() or target.is_symlink():
            target.unlink()
        if existed:
            source = BACKUP / 'files' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                target.symlink_to(os.readlink(source))
            else:
                shutil.copy2(source, target)
    run('systemctl', '--user', 'daemon-reload')
    for unit, state in manifest['units'].items():
        if state == 'enabled':
            run('systemctl', '--user', 'enable', unit)
    print('CONFIGURAZIONI_UTENTE_RIPRISTINATE. Codice, musica e backup sono conservati.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    for option in ('check', 'install', 'restore'):
        group.add_argument('--' + option, action='store_true')
    args = parser.parse_args()
    bus()
    if args.check:
        device_check()
    elif args.install:
        install()
    else:
        restore()
