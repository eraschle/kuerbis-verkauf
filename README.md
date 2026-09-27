# Kürbisverkauf

Windows-Programm zur Erfassung der täglichen Einnahmen aus dem Hofkürbisverkauf –
mit Jahresdiagramm, Jahresvergleich, Übersicht und Import/Export (Excel und JSON).

## Herunterladen

Die aktuelle `Kuerbisverkauf.exe` gibt es unter **[Releases](../../releases/latest)**. Sie wird bei jedem Push
auf `master` automatisch gebaut (GitHub Actions, `.github/workflows/build.yml`).

## Benutzen

1. `Kuerbisverkauf.exe` starten (keine Installation nötig).
2. Beim ersten Mal: **Importieren…** → die alte Excel-Datei (`Kürbissverkauf 1998-2025.xlsx`) wählen → **Übernehmen**.
3. Jedes Jahr: **Neue Saison** → Startdatum bestätigen → Beträge pro Tag eintippen
   (Enter/Pfeiltasten springen zur nächsten Zeile, gespeichert wird automatisch).

**Teilen:** *Exportieren* → Excel (für alle lesbar) oder JSON (exaktes Backup). Die andere Person
wählt *Importieren…*; bei abweichenden Werten erscheint eine Liste zur Auswahl.

**Speicherort:** Standardmässig liegt `kuerbis-daten.json` neben der .exe. Unter *Speicherort…* kann
er geändert werden (z. B. in einen OneDrive-Ordner). Beim Speichern bleibt jeweils der vorherige
Stand als `kuerbis-daten.json.bak` erhalten.

## Entwicklung

Benötigt [uv](https://docs.astral.sh/uv/).

```powershell
uv sync                 # Abhängigkeiten installieren
uv run pytest           # Tests
uv run kuerbis          # Programm starten
.\build.ps1             # Tests + dist\Kuerbisverkauf.exe bauen
uv run python tools/symbol_erstellen.py   # Programmsymbol neu erzeugen
```

Aufbau: `src/kuerbis/` – `model.py` (Berechnungen), `storage.py` (Speichern), `settings.py`
(Speicherort), `excel_io.py` (Import/Export), `merge.py` (Zusammenführen), `api.py`
(Brücke zur Oberfläche), `app.py` (Start), `web/` (HTML/JS-Oberfläche mit Chart.js).

Die alte Excel-Datei mit den Verkaufszahlen ist bewusst nicht im Repository. Liegt sie lokal im
Projektordner, prüfen die Tests den Import gegen ihr Blatt `Üb`; sonst wird dieser Test übersprungen.
