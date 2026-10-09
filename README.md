# PimpMyPhone — Da PinePhone a BiaPod

Guida HTML autonoma in italiano, edizione laboratorio 0.1 del 2026-10-08.

## Aprire la guida

Aprire `index.html` con un browser moderno. Non servono compilazione, npm, account o connessione per leggere la guida. I collegamenti alle immagini Linux, ai pacchetti e alle fonti richiedono Internet.

Per una normale anteprima HTTP locale:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Aprire `http://127.0.0.1:8765` dalla cartella di questo progetto. La copia dei comandi usa Clipboard API oppure un fallback per l’apertura diretta da file.

## Contenuto

- `index.html`: dieci tappe, materiale, immagine di riferimento, SD, accesso, kit, primo ascolto, sessione, eMMC, musica e collaudo.
- `assets/style.css`: grafica adattabile a schermi piccoli, stampa e preferenza di movimento ridotto.
- `assets/app.js`: progressi locali, indice della tappa visibile, comandi copiabili, schede macOS/Linux e ricerca tra i problemi.
- `assets/biapod-logo.svg`, `favicon.svg`: risorse locali. La copertina della demo è un’illustrazione CSS originale.
- `kit/biapod-kit/`: sorgenti del lettore e installatore pubblico preliminare.
- `downloads/biapod-kit-0.1.tar.gz`, `.sha256`: kit scaricabile e hash.

La pagina non usa CDN, font remoti, telemetria o richieste di rete automatiche. I progressi sono conservati in localStorage; se il browser lo impedisce, la lettura e i comandi continuano a funzionare.

## Ambito e stato

Dispositivo di riferimento: PinePhone **originale**, Allwinner A64, 3 GB RAM / 32 GB eMMC. Base: postmarketOS v25.12, build Sxmo/Sway 20260803-0755, kernel 6.17.5.

Il player deriva dal prototipo usato sul PinePhone del progetto. La prova di confronto con cinque album è risultata utilizzabile; l’ascolto prolungato della raccolta completa richiede ancora una convalida. Il 2026-10-08 la nuova base è stata copiata sulla eMMC del prototipo. Il primo avvio ha rilevato un UUID musicale errato in fstab: il valore macOS non coincideva con quello exFAT di Linux. Dopo la correzione, MPD ha indicizzato 2.551 brani, 201 album e 159 artisti. Questi conteggi descrivono il prototipo, non un limite o una garanzia per altri dispositivi.

L’installatore pubblico è **nuovo e non ancora eseguito integralmente su una nuova scheda del telefono**. Le verifiche del progetto HTML e del pacchetto sono documentate in `VERIFICA.md`. Nessuno script del sito viene eseguito automaticamente sul dispositivo: i download e i comandi sono azioni del lettore.

La guida propone una reinstallazione della stessa base sulla eMMC tramite JumpDrive, dopo backup verificato. Non distribuisce i precedenti script di clonazione specifici per il singolo telefono.

Il kit non contiene password personali, chiavi SSH, UUID del prototipo, musica, playlist personali o fotografie dell’utente. La password iniziale indicata nella guida è quella pubblicata per le immagini ufficiali di prova e va cambiata durante la preparazione. Il file PulseAudio conserva la sua intestazione LGPL originale; Linux, Sxmo, MPD, GTK e gli altri progetti restano dei rispettivi autori e conservano le proprie licenze. PimpMyPhone è un progetto indipendente; non è una guida ufficiale di PINE64, Apple o Nura.

## Aggiornare il progetto

Modificare testo, stili e script direttamente. Dopo aver cambiato il kit, ricreare il manifest SHA256SUMS e l’archivio con lo script `build-kit.py` dalla cartella del progetto:

```sh
python3 build-kit.py
```

Prima di presentare l’installer come collaudato: provarlo su una microSD separata, verificare il ritorno alla sessione originale, la gestione di una scheda musicale e due avvii regolari. Non rimuovere gli avvisi sul collaudo finché questi passaggi non sono stati completati.
