# Dokumentation

## Ideen
- Mehrere Drum-Kits mit jeweils 8 Samples
- Schritt-Sequencer (16 Steps × 8 Spuren)  
- Dunkles GUI-Design mit blauen Akzenten  
- Je Spur separate Lautstärke- und Pitch-Einstellungen  
- Speichern und Laden von Patterns/Sequenzen  
- Wechseln zwischen Kits zur Laufzeit  
- Splash-Screen vor Programmstart  
- Verteilbar als einzelne `.exe` (Windows)

## Features
- **16×8 Grid**: 16 Steps (Spalten), 8 Spuren (Zeilen)  
- **Kit-Management**  
  - Kits liegen als Unterordner in `samples/`  
  - Jeder Kit-Ordner enthält bis zu 8 `.wav`-Dateien  
  - Dropdown-Menü zum Wechsel des Kits  
  - Beim Kit-Wechsel werden Spuren-Labels (Dateinamen ohne `.wav`) aktualisiert  
- **Playbacksteuerung**  
  - Play/Pause (Stop) Buttons  
  - Loop über alle 16 Steps  
  - Aktueller Step wird durch Hervorheben der Buttons angezeigt  
  - Tempo einstellbar (BPM über Eingabefeld und kleine Pfeil-Buttons)  
- **Volume & Pitch pro Spur**  
  - Lautstärke-Dial (0…100)  
  - Pitch-Dial (–8…+8 Halbtöne)  
  - Pitch-Shift intern durch Interpolation und Resampling  
- **Patterns Speichern & Laden**  
  - CSV-Format:  
    - Erste Spalte: Sample-Name  
    - 16 Spalten: „0“ oder „1“ für jeden Step  
    - Letzte 2 Spalten: Volume (0–100) und Pitch (–8…+8)  
  - „Speichern“-Button öffnet Dateidialog (CSV)  
  - „Ordner“-Button öffnet Dateidialog und lädt CSV  
- **Splash-Screen**  
  - Zeigt `logo.png` für 0,5 s, bevor das Hauptfenster erscheint  
- **Standalone-Exe**  
  - Anleitung zur Erzeugung per PyInstaller  
  - Alle Ressourcen (`logo.png`, `img/`, `samples/`) werden eingebunden

## Nötige Bibliotheken und Programme
- Python 3.13  
- PyQt6  
- numpy  
- sounddevice  
- soundfile  
- glob (Standardmodul)  
- csv (Standardmodul)  
- threading (Standardmodul)  
- (Optionale) PyInstaller zum Erstellen einer `.exe`  

## Datenstruktur

### Kits
- Jeder Kit ist ein Unterordner unter `samples/`, z. B. `samples/HouseKit/`  
- In jedem Kit-Ordner liegen bis zu 8 `.wav`-Dateien  
- Beim Laden eines Kits werden die ersten 8 `.wav`-Dateien alphabetisch gelesen; weniger als 8 werden mit stummen Platzhaltern vervollständigt.  
- Beispielstruktur:
samples/
├── HouseKit/
│ ├── kick.wav
│ ├── snare.wav
│ ├── hat.wav
│ └── … (bis 8 Dateien)
├── TechnoKit/
│ ├── kick.wav
│ ├── clap.wav
│ └── …
└── PercussionKit/
├── conga.wav
├── cowbell.wav
└── …
- GUI-Labels der einzelnen Zeilen entsprechen dem Dateinamen (ohne `.wav`).

### Patterns (Sequenzen)
- Gespeichert als CSV. Jede Zeile beschreibt eine Spur:
1. Spalte: Sample-Name (Text)  
2. Spalten 2…17: Step-Flags („1“ = spielen, „0“ = stumm)  
3. Spalte 18: Volume (0–100)  
4. Spalte 19: Pitch (–8…+8)  
- Beispielzeile für eine Spur:
Kick,0,1,0,0,1,0,0,0,0,1,0,0,0,0,0,0,100,0

- „Kick“ → Sample  
- „0,1,0,0,1,…“ → welche Steps angehakt sind  
- „100“ → Lautstärke  
- „0“ → Pitch  

## Devlog

### 1.
- Basis-GUI mit PyQt6 angelegt  
- Grid (8 Zeilen × 16 Spalten), Sample-Labels, Volume- & Pitch-Dials aufgebaut  
- Dunkles Farbschema mit blauen Akzenten implementiert  
- Buttons in grid stehen als leere Felder mit Rundungen bereit

### 2.
- Splash-Screen (`logo.png`) hinzugefügt: 500 ms Ladebildschirm vor Hauptfenster  
- „Play“ und „Pause“ Buttons eingefügt, aber ohne funktionale Logik

### 3.
- Samples aus `samples/` laden  
- `soundfile` und `sounddevice` zum Abspielen integriert  
- Play-Logic:  
- Sequencer-Timer (Step-Advance basierend auf BPM)  
- Aktueller Step wird hervorgehoben  
- Jedes Sample wird in eigenem Thread abgespielt  

### 4.
- Pitch-Shift für Dials implementiert via Interpolation:  
- `rate = 2**(semitone/12)`  
- `numpy.interp` für Neuberechnung der Abtastrate  
- Lautstärke-Skalierung über Multiplikation des Audioarrays  
- Erste Stabilitätsprobleme: CoreAudio initialisiert, führt zu Start-Lag  

### 5.
- „Aufwärmen“ des Audio-Backends durch kurzes Abspielen eines stummen Puffers (256 Samples) in `__init__` → keine Inital-Lags mehr  
- Pitch-Dials Limitiert auf –8…+8 (behebt Abstürze bei zu großem Pitch)

### 6.
- Save/Load-Funktionalität (CSV) hinzugefügt:  
- Speichert Buttons, Volume- & Pitch-Werte  
- Lädt alles aus CSV und setzt GUI-Elemente zurück  
- Folder-Button (Load) implementiert, lädt Sequenz direkt in Grid

### 7.
- Kit-Dropdown:  
- Liest Unterordner in `samples/` aus  
- Erstellt Menüeinträge automatisch  
- `load_kit(kit_name)` aktualisiert Samples + Labels in GUI  
- Stoppt Sequencer, wenn Kit gewechselt wird

### 8.
- `closeEvent` angepasst, um Playback beim Schließen zu stoppen und CoreAudio-Fehler zu unterdrücken:  
- `sd.stop()` in temporärem `sys.stderr = os.devnull`  
- 200 ms Verzögerung vor dem tatsächlichen `close()`, um Audio-Streams zu beenden



