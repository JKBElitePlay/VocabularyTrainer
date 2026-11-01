# Vokabel-Freunde

Ein lokaler, kinderfreundlicher Englisch-Deutsch-Vokabeltrainer mit FastAPI,
SQLite und einer responsiven Browseroberfläche.

## Voraussetzungen

- Python 3.12 oder neuer

## Lokal starten

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python run.py
```

Die Anwendung ist anschließend unter <http://127.0.0.1:8000> erreichbar. Die
SQLite-Datenbank wird beim ersten Start unter `data/vokabeltrainer.db` angelegt.
Mit `VOCABULARY_DATABASE_URL` kann eine andere SQLAlchemy-Datenbank-URL gesetzt
werden. Die interaktive API-Dokumentation findet sich unter
<http://127.0.0.1:8000/docs>.

## Enthaltene Funktionen

- Vokabelmappen und Vokabeln erstellen, bearbeiten und löschen
- UTF-8-CSV-Vorschau, Duplikatprüfung, Import und Export
- Deutsch → Englisch, Englisch → Deutsch, Karteikarten und Zuordnungsspiel
- Wählbare Karteikartenrichtung und Rundenlänge (10, 20, 30, 50, 75 oder 100 Fragen)
- Training nach ausgewählten Vokabelkategorien mit Wortanzahl pro Kategorie
- Optional eine einstellbare Anzahl Vokabeln unter einem frei wählbaren Prozentsatz richtiger Antworten in jedem Spielmodus üben
- Letzte Lerneinstellungen wie Mappe, Spielmodus, Kategorien, Richtung, Fragezahl und Prozentgrenze im Browser speichern
- Erst ungestellte Vokabeln; falsch oder nur teilweise beantwortete Vokabeln werden nach der Lektion bis zur ersten richtigen Antwort wiederholt
- Tippfehlerbewertung, Hilfen mit Punkteabzug und gewichtete Wiederholung
- Tages-Badges, Lernserie, Erfolgsquote und Wortschatz-Statistiken

## Tests

```powershell
python -m pip install -e ".[test]"
python -m pytest
```

## Windows-EXE bauen

```powershell
python -m pip install -e ".[desktop]"
python -m PyInstaller --clean --onefile --name VokabelFreunde --add-data "app\static;app\static" run.py
```

Die EXE liegt anschließend unter `dist\VokabelFreunde.exe`. Beim Start öffnet
sich die Anwendung automatisch im Standardbrowser unter
`http://127.0.0.1:8000`. Wenn dieser Port belegt ist, verwendet die EXE
automatisch einen freien Port und zeigt ihn im Konsolenfenster an. Die
Datenbank liegt dauerhaft unter
`%LOCALAPPDATA%\Vokabel-Freunde\vokabeltrainer.db`. Zum Beenden das
Konsolenfenster der EXE schließen. Der Port kann bei Bedarf über die
Umgebungsvariable `VOKABELTRAINER_PORT` geändert werden.
