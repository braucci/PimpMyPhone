# BiaPod kit 0.1 — PimpMyPhone

Anteprima dell’installatore riutilizzabile, 8 ottobre 2026. Il player deriva dal prototipo; questo installatore non è stato ancora provato integralmente su una nuova scheda del telefono. Iniziare dalla microSD di prova, con la base documentata. Gli script non formattano dischi e non scrivono immagini sulla eMMC.

## Base richiesta

- PinePhone originale A64 aarch64; non PinePhone Pro.
- Immagine postmarketOS v25.12 Sxmo/Sway 20260803-0755, kernel 6.17.5, systemd e tinydm.
- Account normale sotto `/home`, ad esempio `user`, senza spazi o caratteri speciali nella home.
- `mpd`, `py3-gobject3`, `py3-cairo`, `gtk+3.0`; PulseAudio, pactl, amixer, Sway, foot e wvkbd-mobintl forniti dalla base.
- Musica propria nella cartella `~/Music/Artista/Album`.

## Preparazione

Sul telefono, con Internet disponibile per APK:

```sh
sudo apk add mpd py3-gobject3 py3-cairo gtk+3.0
sha256sum -c SHA256SUMS
python3 setup.py --check
python3 setup.py --install
```

`setup.py` si esegue senza sudo. Si ferma se trova un’installazione precedente. Salva i file utente sostituiti e gli stati dei servizi in `~/.local/state/pimpmyphone-backup`, poi prepara `~/pinepod`. Modifica soltanto le configurazioni elencate nel manifest. Disattiva i servizi utente alternativi audio e telefonici, conservandone il riferimento per il ripristino. I pacchetti di sistema già installati non vengono rimossi.

Copia due album in `~/Music`, poi:

```sh
sudo python3 system_setup.py activate "$USER"
sudo reboot
```

Il comando salva la sessione tinydm in `/var/lib/pimpmyphone`, seleziona la sessione BiaPod e maschera ModemManager, eg25-manager, Bluetooth, wpa_supplicant e hkdm, se presenti. Il Wi-Fi può interrompersi: per la manutenzione usare il collegamento USB. SSH non è abilitato all’avvio. Schermo sempre acceso; niente swayidle/sospensione automatica nella base di confronto.

Aprire Album → Aggiorna, attendere, scegliere un brano. Primo volume MPD 10%, uscita PulseAudio 50%; partenza in pausa quando la configurazione è nuova. Il codice delle successive sessioni conserva lo stato MPD. Volume fisico e ghiera variano MPD di 1 punto percentuale.

## Terminale manuale

Tre pressioni rapide di Power richiamano foot con la tastiera. Il nuovo installatore deve ancora convalidare questo gesto su dispositivo. `exit` chiude la manutenzione e torna al player. Non modifica SSH.

## Musica sulla scheda separata

Solo dopo avere avviato il sistema da eMMC: inserire a telefono spento la scheda dati exFAT con `Music` alla radice. Sul telefono leggere l’UUID con `sudo blkid`. Non usare l’identificatore ricavato da macOS.

```sh
sudo python3 music_setup.py UUID_REALE "$USER"
sudo reboot
```

Il comando è da adattare: UUID_REALE è un segnaposto. Verifica hardware, tipo exFAT, dispositivo differente dalla radice del sistema e presenza di Music con un montaggio in sola lettura. Salva fstab, conserva l’eventuale Music locale come `Music.before-pimpmyphone`, crea il collegamento alla scheda e prepara il montaggio in sola lettura ad ogni avvio. Non cambia i brani. Dopo il riavvio: Album → Aggiorna.

Per aggiungere album spegnere normalmente il telefono, copiare sulla scheda dal computer, espellere, reinserire a telefono spento e aggiornare il catalogo. Le playlist rimangono in `~/.local/share/mpd/playlists` nella memoria del sistema; usare percorsi relativi a Music.

## Ripristino

Per ripristinare la sessione e le configurazioni utente:

```sh
sudo python3 system_setup.py restore "$USER"
python3 setup.py --restore
sudo reboot
```

Codice, backup e musica sono conservati. Le configurazioni audio e la precedente selezione tinydm sono ripristinate; al riavvio tornano i servizi precedentemente abilitati. I pacchetti aggiunti restano installati. Questo non ripristina un sistema cancellato sulla eMMC: per quello serve la sua immagine completa.

Se è stato eseguito `music_setup.py`, il collegamento della scheda è una configurazione separata: per annullarlo, a telefono in pausa smontare `/media/music`, ripristinare `/etc/fstab` dal backup `/var/lib/pimpmyphone/fstab.before-music`, rimuovere il solo symlink `~/Music`, rinominare `~/Music.before-pimpmyphone` in `~/Music` se presente, rimuovere il drop-in `/etc/systemd/system/tinydm.service.d/pimpmyphone-music.conf`, ricaricare systemd e riavviare. Verificare i percorsi prima delle modifiche; non cancellare la cartella Music sulla scheda.

## Limiti noti

- Riproduzione continua con libreria completa ancora da convalidare sulla nuova base.
- EarPods Apple: centro provato, volume +/- senza eventi sul prototipo; Android/CTIA e multi-clic da provare.
- Profili audio e controllo jack specifici dell’immagine di riferimento; non universali.
- Installatore con controlli e backup, ma non ancora collaudato integralmente su hardware.
- Nessun file musicale, playlist personale, chiave SSH o immagine Linux nel pacchetto.

Il file PulseAudio conserva l’intestazione LGPL originale; il testo della licenza è incluso in `COPYING.LGPL-2.1`. Le dipendenze vengono installate dai rispettivi repository e conservano le proprie licenze.
