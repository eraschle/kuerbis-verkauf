# Kürbisverkauf Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows-Programm (.exe) zur Erfassung der täglichen Kürbisverkauf-Einnahmen pro Saison mit Diagrammen, Jahresvergleich und Import/Export (JSON + Excel).

**Architecture:** Python-Kern (reine Funktionen für Modell/Berechnung, Speicherung, Excel, Zusammenführen) ohne GUI-Abhängigkeit, voll getestet. pywebview-Fenster mit HTML/JS-Oberfläche; `api.py` ist die einzige Brücke. Chart.js lokal mitgeliefert.

**Tech Stack:** Python 3.14, uv, pywebview, openpyxl, Chart.js 4 (lokal), pytest, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-09-27-kuerbis-verkauf-design.md`

## Global Constraints

- Paketmanager: uv (`uv add`, `uv run`), kein pip direkt.
- Oberfläche und Meldungen auf Deutsch (Schweizer Schreibweise, „ss“ statt „ß“), Beträge in CHF.
- Datenformat JSON: `{"format": "kuerbisverkauf", "version": 1, "saisons": {"<jahr>": {"start": "YYYY-MM-DD", "eintraege": {"YYYY-MM-DD": zahl}}}}`
- Beträge: `> 0`, int wenn ganzzahlig sonst float; 0/leer = kein Eintrag; negativ = Fehler.
- Woche 1 = Startdatum … Startdatum+6; Saison mindestens 16 Wochen.
- Keine Rechenlogik in JavaScript; JS zeigt nur an, was `api.py` liefert.
- Läuft offline (keine CDN-Aufrufe zur Laufzeit).
- Kein Git-Repo vorhanden: Commit-Schritte entfallen, bis der User ein Repo wünscht.

## File Structure

```
pyproject.toml                 uv-Projekt, Abhängigkeiten, pytest-Konfig
src/kuerbis/__init__.py
src/kuerbis/model.py           Saison, Daten, Tageszeilen, Wochentotale, Statistik, Serialisierung
src/kuerbis/storage.py         laden/speichern (atomar, .bak), DatenFehler
src/kuerbis/settings.py        Einstellungen (Datenpfad) in %APPDATA%\Kuerbisverkauf
src/kuerbis/excel_io.py        Import (alt + eigen), Export Excel
src/kuerbis/merge.py           Konflikte finden, Zusammenführen anwenden
src/kuerbis/api.py             Klasse Api für pywebview (js_api)
src/kuerbis/app.py             main(): Fenster starten
src/kuerbis/web/index.html, app.js, style.css, chart.umd.min.js
tests/test_model.py, test_storage.py, test_settings.py, test_excel_io.py, test_merge.py, test_api.py
build.ps1                      PyInstaller-Build
```

---

### Task 1: Projekt + Modell und Berechnungen

**Files:** Create `pyproject.toml`, `src/kuerbis/__init__.py`, `src/kuerbis/model.py`, `tests/test_model.py`

**Interfaces – Produces:**
- `@dataclass Saison(jahr: int, start: date, eintraege: dict[date, float])`
- `@dataclass Daten(saisons: dict[int, Saison])`
- `def betrag_normalisieren(wert) -> float | int | None` (None für leer/0, ValueError für negativ/ungültig; akzeptiert "12,50")
- `def tageszeilen(s: Saison) -> list[dict]` Keys: `datum` (ISO), `wochentag` (Montag…), `woche` (int), `betrag` (float|None), `laufend` (float|None, nur wenn Betrag), `wochentotal` (float|None, am letzten Tag der Woche, falls Woche > 0)
- `def anzahl_wochen(s) -> int` (≥16)
- `def wochentotale(s) -> list[float]` (Länge = anzahl_wochen)
- `def statistik(s) -> dict` Keys `min, max, mittel, tage, total` (None-Werte bei leerer Saison ausser tage=0,total=0)
- `def kumuliert_pro_tag(s) -> list[float]` Index 0 = Starttag, bis letzter Tag mit Eintrag
- `def daten_zu_dict(d) -> dict`, `def daten_aus_dict(obj) -> Daten` (ValueError bei falschem Format)
- `def vorgeschlagener_start(jahr) -> date` (letzter Montag im August)

- [ ] Tests: Woche 1 = Tage 0–6, Tag 7 = Woche 2; Wochentotal am 7. Tag; laufendes Total; Statistik (min/max/mittel/tage/total); Saison mit Eintrag in Woche 18 → 18 Wochen; betrag_normalisieren("12,5")==12.5, ("")→None, ("-1")→ValueError; Rundlauf dict; vorgeschlagener_start(2025)==date(2025,8,25).
- [ ] `uv run pytest tests/test_model.py` → FAIL, implementieren, → PASS.

### Task 2: Speicherung + Einstellungen

**Files:** Create `src/kuerbis/storage.py`, `src/kuerbis/settings.py`, `tests/test_storage.py`, `tests/test_settings.py`

**Interfaces – Produces:**
- `class DatenFehler(Exception)`
- `def laden(pfad: Path) -> Daten` (fehlt → leere Daten; kaputt → DatenFehler)
- `def speichern(pfad: Path, d: Daten) -> None` (tmp-Datei + `os.replace`; vorherige Datei → `.bak`)
- `def standard_datenpfad() -> Path` (neben .exe wenn `sys.frozen`, sonst Projektordner) → `kuerbis-daten.json`
- `def einstellungen_pfad() -> Path` (`%APPDATA%/Kuerbisverkauf/einstellungen.json`, Basisordner per Parameter überschreibbar für Tests)
- `def datenpfad_lesen(basis: Path | None = None) -> Path`, `def datenpfad_setzen(pfad: Path, basis: Path | None = None) -> None`

- [ ] Tests: Rundlauf; .bak enthält alten Stand; kaputtes JSON → DatenFehler und Datei unverändert; fehlende Datei → leer; Einstellungen Rundlauf; ohne Einstellung → standard_datenpfad.
- [ ] FAIL → implementieren → PASS.

### Task 3: Zusammenführen

**Files:** Create `src/kuerbis/merge.py`, `tests/test_merge.py`

**Interfaces – Produces:**
- `def konflikte_finden(meine: Daten, import_: Daten) -> list[dict]` Einträge `{"id": str, "jahr": int, "art": "betrag"|"start", "datum": iso|None, "mein": wert, "import": wert}`
- `def zusammenfuehren(meine, import_, wahl: dict[str, str]) -> tuple[Daten, dict]` wahl: id → `"mein"|"import"` (fehlend = "mein"); Rückgabe neue Daten + Zusammenfassung `{"neue_jahre", "neue_tage", "konflikte_import", "konflikte_mein"}`

- [ ] Tests: neues Jahr übernommen; neuer Tag übernommen; gleicher Wert kein Konflikt; anderer Betrag = Konflikt, Wahl "import" übernimmt; Startdatum-Konflikt; Eingabedaten nicht verändert.
- [ ] FAIL → implementieren → PASS.

### Task 4: Excel-Import/-Export

**Files:** Create `src/kuerbis/excel_io.py`, `tests/test_excel_io.py`; Abhängigkeit `uv add openpyxl`

**Interfaces – Produces:**
- `def importieren(pfad: Path) -> Daten` erkennt `.json` (daten_aus_dict), eigenes Excel (Blatt `Daten`), altes Excel (Blätter `\d\d`); sonst ValueError mit deutscher Meldung
- `def excel_exportieren(pfad: Path, d: Daten) -> None` Blätter `Daten` (Jahr, Startdatum, Datum, Betrag) und `Übersicht` (Jahr, Wo 1…n, dann Min, Max, Mittel, Tage, Total)
- `def json_exportieren(pfad, d)` (nutzt storage-Format)

- [ ] Tests mit der echten Datei `Kürbissverkauf 1998-2025.xlsx` (skip falls fehlt): Statistik aller Jahre = Blatt `Üb` (Sollwerte zur Laufzeit gelesen); 1998 leer oder ohne Einträge. Rundlauf Excel-Export → Import identisch; JSON-Rundlauf; unbekannte Datei → ValueError.
- [ ] FAIL → implementieren → PASS.

### Task 5: API-Schicht

**Files:** Create `src/kuerbis/api.py`, `tests/test_api.py`

**Interfaces – Produces** (alle geben JSON-fähige dicts zurück; Fehler als `{"fehler": text}`):
- `Api(datenpfad: Path, einstellungen_basis: Path | None = None)`; `fenster` Attribut wird von app.py gesetzt (für Dateidialoge)
- `status()` → `{"datenpfad", "jahre": [..absteigend], "fehler"?}`
- `saison(jahr)` → `{"jahr","start","zeilen": tageszeilen, "statistik", "wochentotale"}`
- `neue_saison(jahr, start_iso)`, `start_aendern(jahr, start_iso)`, `saison_loeschen(jahr)`
- `betrag_setzen(jahr, datum_iso, wert)` → wie `saison()` (aktualisiert)
- `vergleich()` → `{"jahre": [{"jahr","kumuliert": [...], "total"}]}`
- `uebersicht()` → `{"max_wochen", "zeilen": [{"jahr","wochen","statistik"}]}`
- `vorschlag_start(jahr)` → `{"start"}`
- Datei-Aktionen mit Dialog (nicht unit-getestet, dünn): `export_dialog(art)`, `import_dialog()`, `speicherort_verschieben_dialog()`, `speicherort_oeffnen_dialog()`
- Testbare Kerne: `export_nach(pfad, art)`, `import_vorbereiten(pfad)` → `{"konflikte", "vorschau"}` (merkt Importdaten), `import_abschliessen(wahl)` → Zusammenfassung, `speicherort_verschieben(pfad, ueberschreiben: bool)`, `speicherort_oeffnen(pfad)`

- [ ] Tests mit tmp_path: neue Saison + Betrag → speichert Datei; ungültiger Betrag → fehler; Import mit Konflikt → abschliessen mit Wahl; Speicherort verschieben schreibt neue Datei + Einstellung; existierende Zieldatei ohne überschreiben → `{"existiert": True}`.
- [ ] FAIL → implementieren → PASS.

### Task 6: Oberfläche + Start

**Files:** Create `src/kuerbis/web/{index.html,app.js,style.css}`, `src/kuerbis/web/chart.umd.min.js` (Chart.js 4 von jsdelivr einmalig herunterladen), `src/kuerbis/app.py`; `uv add pywebview`; Script-Eintrag `kuerbis = "kuerbis.app:main"`

- Reiter Erfassung / Vergleich / Übersicht; Kopfzeile mit Import, Export (JSON/Excel), Speicherort.
- Erfassung: Jahr-Auswahl, Neue Saison (Dialog mit Startdatum-Vorschlag), Startdatum ändern, Tabelle mit Eingabefeldern (Enter/Pfeil ↓↑ springt), Speichern bei `change`, heutiger Tag hervorgehoben, Jahresdiagramm (Balken + Linie), Kennzahlen.
- Vergleich: Checkboxen pro Jahr (Standard: neuestes + 4), Linien kumuliert, Balken Jahrestotal.
- Übersicht: Tabelle.
- Konflikt-Dialog: Liste mit Radio mein/import pro Zeile, „alle meine“/„alle importierten“, Übernehmen/Abbrechen.
- [ ] `uv run kuerbis` starten, im Browser-Fenster manuell prüfen.

### Task 7: Build der .exe

**Files:** Create `build.ps1`; `uv add --dev pyinstaller`

```powershell
uv run pyinstaller --noconfirm --onefile --windowed --name Kuerbisverkauf `
  --add-data "src/kuerbis/web;kuerbis/web" src/kuerbis/app.py
```
- [ ] Build ausführen, `dist/Kuerbisverkauf.exe` starten, alte Excel importieren, Eintrag erfassen, exportieren.
