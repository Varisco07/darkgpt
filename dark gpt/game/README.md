# Game Security Research & Modding

Modulo di **ricerca sulla sicurezza dei giochi** e di **modding legittimo**.

## Confini (valgono per tutto il modulo)

| Consentito | Non consentito |
|---|---|
| Giochi **offline** singolo giocatore | Multiplayer pubblico con altri giocatori |
| Progetti **propri** | Software di terzi senza licenza compatibile |
| Software **open source** con licenza che consenta il modding | Aggirare anti-cheat o DRM a scopo di cheat |
| Analisi e modifica di **processi propri** in ambiente di test | Strumenti per rubare account, malware, DDoS |
| Studio delle architetture dei **propri** giochi online | Analisi di servizi di terzi per sfruttarli |

Il modulo **non produce** meccanismi di evasione anti-cheat, strumenti per
compromettere altri giocatori o malware. E non inventa mai indirizzi, offset
o funzioni: ogni dato restituito e' verificato su strutture reali o dichiarato
esplicitamente come non verificato.

## Moduli

### `analyzer.py` — Game Analyzer

Analisi **statica e passiva** di una cartella di gioco: riconosce il motore
(Unity, Unreal, Godot, RPG Maker, GameMaker, Ren'Py), la versione quando e'
leggibile dai metadati, i linguaggi di scripting presenti, i framework di
modding installati, i file di configurazione e di salvataggio.

```python
from game import analyze_directory, suggest_tools

info = analyze_directory(r"C:\Giochi\mio-gioco")
print(info.engine, info.modding_feasibility)
print(suggest_tools(info))
```

Se il motore non e' riconosciuto, il modulo **lo dice** e non ipotizza nulla.

### `mod_creator.py` — Mod Creator

Genera lo **scaffolding** di un mod (scheletri da completare, non codice
pronto all'uso) per BepInEx (C#), UE4SS (Lua), Godot (GDScript) o Python.

```python
from game import ModSpec, generate_mod, install_instructions

spec = ModSpec(name="Dark Demo", author="me", version="0.1.0", target="bepinex")
created = generate_mod(spec, "mods/dark-demo")
print(install_instructions(spec, r"C:\Giochi\mio-gioco"))
```

`generate_mod` **non sovrascrive** file esistenti (salvo `overwrite=True`): un
mod non deve perdere modifiche per una rigenerazione.

Backup e ripristino, con verifica SHA-256:

```python
from game import backup_files, restore_files

entries = backup_files(["game.ini"], "backups")   # copia verificata
restore_files("backups/<timestamp>")               # ripristino verificato
```

Un backup alterato non viene ripristinato: viene trattato come inaffidabile.

### `memory_lab.py` — Memory Research Lab

Dimostrazione del metodo di modifica dei valori su una struttura di gioco
**allocata dallo stesso processo** (ctypes): salute, armatura, munizioni,
punteggio, livello, flag.

```python
from game import allocate_state, scan_for_value, write_value, describe

handle = allocate_state(health=100, ammo=30)
candidates = scan_for_value(handle, 30)   # -> offset e indirizzo verificati
write_value(handle, "ammo", 999)          # scrittura verificata con rilettura
print(describe(handle))
```

Gli indirizzi restituiti sono quelli del buffer creato dal laboratorio:
**non** viene scansionata né modificata la memoria di altri processi. Il
valore del laboratorio e' didattico: mostra il metodo (cercare → candidati →
modificare → verificare) in un ambiente dove ogni passo e' riproducibile.

### `multiplayer.py` — Multiplayer Security Research

Aiuta gli sviluppatori dei **propri** giochi online a trovare problemi di
fiducia eccessiva nel client, a partire da un manifest dichiarato.

```python
from game import ActionSpec, ArchitectureManifest, analyze_architecture, MovementAction, validate_movement

manifest = ArchitectureManifest(
    game="Mio gioco",
    encrypted=True,
    server_authoritative=True,
    actions=[ActionSpec(name="fire", client_sent_fields=["damage"], server_validated=False)],
)
for finding in analyze_architecture(manifest):
    print(finding.severity, finding.title)

validate_movement(MovementAction(x=500, y=0, z=0, dt_ms=50))
# -> rifiutato: spostamento non plausibile
```

I controlli coprono: trasporto non cifrato, modello non server-authoritative,
azioni non validate lato server, campi contemporaneamente autorevoli e inviati
dal client (conflitto di autorita').

## Test

```bash
.venv/Scripts/python -m pytest game/tests -q
```

## Limiti dichiarati

- L'Analyzer riconosce il motore dai **file**: non esegue il gioco e non
  fa reverse engineering del binario.
- Il Mod Creator produce scheletri: la compatibilita' con una versione
  specifica del gioco va verificata dall'operatore.
- Il Memory Lab lavora solo su memoria allocata dal processo stesso.
- L'analisi multiplayer parte da un manifest: non analizza il traffico di
  servizi di terzi.
