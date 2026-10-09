# Verifiche — PimpMyPhone 0.1

Data: 8 ottobre 2026. Questa nota distingue la verifica del sito e del pacchetto dalla convalida sul telefono.

## Guida HTML

Controllata con Google Chrome, tramite Playwright, sia da un server locale sia aprendo il file HTML con JavaScript disattivato.

- Dieci tappe presenti; 31 riferimenti locali e ancore verificati.
- Nessun errore JavaScript durante le interazioni controllate.
- Nessuno scorrimento orizzontale della pagina alle larghezze di 320, 390, 768 e 1440 pixel.
- Copia dei comandi verificata nell’anteprima HTTP.
- Schede macOS/Linux, ricerca dei problemi e stato senza risultati verificati.
- Checklist: salvataggio dopo ricaricamento e azzeramento verificati.
- Navigazione mobile alla tappa selezionata e indice desktop verificati.
- Preferenza di movimento ridotto rispettata.
- Le dieci tappe sono leggibili anche senza JavaScript; le funzioni interattive richiedono JavaScript.
- Schermate desktop e mobile esaminate visivamente.

La copia tramite fallback da file locale è implementata, ma non è stata verificata su tutti i browser. I collegamenti esterni possono cambiare; la pagina non li contatta automaticamente.

## Kit pubblico

- Sintassi Python e script di avvio controllati.
- Controllo preliminare: rifiuto dell’esecuzione sul Mac verificato.
- Installazione e ripristino dei file utente provati in un ambiente temporaneo con comandi di sistema simulati. Configurazione PulseAudio originale ripristinata, cartella Music conservata e percorsi adattati all’utente della prova.
- Manifest SHA-256 e contenuto dell’archivio verificati dopo la compilazione del pacchetto.
- Il pacchetto contiene sorgenti, configurazioni generiche e licenza PulseAudio. Non contiene musica, copertine commerciali, fotografie personali, playlist personali, immagini Linux, chiavi SSH o credenziali personali.

L’installatore pubblico è nuovo. L’attivazione della sessione di sistema e il montaggio della scheda musicale non sono ancora stati eseguiti integralmente su una nuova microSD del PinePhone. La simulazione dei file utente non convalida queste operazioni sul dispositivo.

## Prototipo hardware

Il lettore deriva dal prototipo per PinePhone originale A64. Una prova con cinque album sulla base v25.12 e kernel 6.17.5 è risultata utilizzabile secondo il riscontro dell’utente. Dopo il passaggio di questa base alla eMMC del prototipo, il primo avvio ha mostrato un identificatore della scheda musicale errato: il valore macOS è stato sostituito con quello exFAT letto da Linux.

Dopo la correzione MPD ha indicizzato 2.551 brani, 201 album e 159 artisti. Il montaggio automatico è configurato; un ulteriore avvio completo e un ascolto prolungato dell’intera libreria restano da convalidare. Questo risultato riguarda il prototipo, non dimostra che l’installatore pubblico sia già collaudato.

## Verifiche ancora necessarie prima di una release stabile

1. Installare il kit pubblico su una microSD separata con l’immagine indicata.
2. Provare avvio, audio, tocchi, tasti fisici e ripristino della sessione precedente.
3. Provare il montaggio di una scheda musicale separata dopo l’avvio da eMMC e due avvii completi.
4. Provare ascolto prolungato e gestione dell’intera libreria; registrare eventuali blocchi.
5. Provare telecomandi cuffie Android/CTIA e combinazioni di clic prima di dichiararli compatibili.

Lo spegnimento automatico dello schermo è escluso dalla configurazione di confronto; resta una funzione da reintrodurre solo dopo il collaudo della base.
