#!/usr/bin/env python3
"""Attach a verified exFAT music partition read-only. Never format a device."""
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    if os.getuid() != 0 or len(sys.argv) != 3:
        raise SystemExit('Uso: sudo python3 music_setup.py UUID nome_utente')
    uuid, username = sys.argv[1:]
    if not re.fullmatch(r'[A-Fa-f0-9-]{4,64}', uuid):
        raise SystemExit('Inserisci l’UUID effettivo letto con blkid sul PinePhone.')
    if b'pine64,pinephone' not in Path('/proc/device-tree/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Dispositivo non supportato.')
    user = pwd.getpwnam(username)
    home = Path(user.pw_dir)
    if user.pw_uid == 0 or not (home / 'pinepod/biapod.py').is_file():
        raise SystemExit('Indica l’utente per cui è stato installato BiaPod.')
    device = (Path('/dev/disk/by-uuid') / uuid).resolve(strict=True)
    if not stat.S_ISBLK(device.stat().st_mode):
        raise SystemExit('L’UUID non identifica un dispositivo a blocchi.')
    root = output('findmnt', '-n', '-o', 'SOURCE', '/')
    root_disk = output('lsblk', '-n', '-o', 'PKNAME', root)
    music_disk = output('lsblk', '-n', '-o', 'PKNAME', str(device))
    if not root_disk or not music_disk or root_disk == music_disk:
        raise SystemExit('Rifiuto la scheda del sistema avviato o un dispositivo ambiguo.')
    if output('blkid', '-s', 'TYPE', '-o', 'value', str(device)) != 'exfat':
        raise SystemExit('Questa anteprima prepara soltanto una partizione dati exFAT.')
    mounts = output('lsblk', '-n', '-o', 'MOUNTPOINTS', str(device))
    if mounts:
        raise SystemExit('La partizione risulta già montata: controlla e smontala prima di procedere.')
    point = Path('/media/music')
    if subprocess.run(['mountpoint', '-q', str(point)]).returncode == 0:
        raise SystemExit('/media/music è già occupata. Non sostituisco un montaggio attivo.')
    music = home / 'Music'
    saved_music = home / 'Music.before-pimpmyphone'
    if (music.exists() or music.is_symlink()) and (saved_music.exists() or saved_music.is_symlink()):
        raise SystemExit('Esiste già Music.before-pimpmyphone; conserva e controlla la cartella.')
    fstab = Path('/etc/fstab')
    previous = fstab.read_text()
    if any(len(line.split()) > 1 and line.split()[1] == '/media/music'
           for line in previous.splitlines() if line.strip() and not line.lstrip().startswith('#')):
        raise SystemExit('Esiste già una riga /media/music in fstab: confrontala con blkid, senza duplicarla.')
    options = f'ro,uid={user.pw_uid},gid={user.pw_gid},umask=022'
    with tempfile.TemporaryDirectory(prefix='biapod-music-', dir='/run') as check:
        subprocess.run(['mount', '-t', 'exfat', '-o', options, str(device), check], check=True)
        try:
            if not (Path(check) / 'Music').is_dir():
                raise SystemExit('Non trovo la cartella Music alla radice della scheda.')
        finally:
            subprocess.run(['umount', check], check=True)
    backup = Path('/var/lib/pimpmyphone/fstab.before-music')
    backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if backup.exists():
        raise SystemExit('Esiste già il backup fstab della musica. Non sovrascrivo.')
    shutil.copy2(fstab, backup)
    line = f'UUID={uuid} /media/music exfat {options},nofail,x-systemd.device-timeout=10s 0 0\n'
    fstab.write_text(previous.rstrip() + '\n# PimpMyPhone: music card, Linux UUID\n' + line)
    point.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['mount', '/media/music'], check=True)
        if music.exists() or music.is_symlink():
            music.rename(saved_music)
        music.symlink_to('/media/music/Music')
        os.lchown(music, user.pw_uid, user.pw_gid)
        dropin = Path('/etc/systemd/system/tinydm.service.d/pimpmyphone-music.conf')
        dropin.parent.mkdir(parents=True, exist_ok=True)
        dropin.write_text('[Unit]\nWants=media-music.mount\nAfter=media-music.mount\n')
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
    except Exception:
        print(f'Configurazione da controllare. Backup fstab: {backup}', file=sys.stderr)
        raise
    print('MUSICA_COLLEGATA_IN_SOLA_LETTURA. Riavvia, poi Album → Aggiorna.')


if __name__ == '__main__':
    main()
