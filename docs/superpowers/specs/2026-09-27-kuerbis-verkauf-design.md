# Kürbisverkauf – Design

Datum: 2026-09-27
Status: Freigegeben

## Ziel

Die Excel-Datei `Kürbissverkauf 1998-2025.xlsx` wird durch ein Windows-Programm (.exe) ersetzt.
Man erfasst jedes Jahr ab einem Startdatum die täglichen Einnahmen aus dem Hofkürbisverkauf,
sieht pro Jahr ein Diagramm und kann die Jahre miteinander vergleichen. Die Daten lassen sich
per Export/Import mit anderen Personen teilen.

## Ausgangslage (Excel)

- Pro Jahr ein Blatt (`98` … `25`): Zelle C5 = Startdatum, ab Zeile 5 pro Tag Wochentag, Datum (Spalte C),
  Betrag (Spalte D), laufendes Total, Wochentotal (jeweils am Sonntag bzw. 7. Tag).
- Blatt `Üb`: Wochentotale pro Jahr (Wo 1 …), kumulierte Wochentotale, Statistik pro Jahr
  (Min, Max, Mittel, Tage, Total), dazu ein Diagrammblatt.
- Echte Daten 2000–2025, ca. 60–80 Verkaufstage pro Jahr, Beträge in CHF, teils mit Kommastellen.

## Technik

- **Python 3.14** mit **uv** als Paketmanager (`pyproject.toml`, `uv.lock`).
- **pywebview**: Python-Programm mit HTML/CSS/JavaScript-Oberfläche in einem Windows-Fenster (Edge WebView2,
  in Windows 11 enthalten).
- **Chart.js** für die Diagramme, als Datei mitgeliefert (läuft offline, kein CDN zur Laufzeit).
- **openpyxl** für Excel-Import/-Export.
- **PyInstaller** erzeugt eine einzelne `Kuerbisverkauf.exe` (ca. 30–40 MB).
- **pytest** für Tests.

## Datenmodell und Speicherung

Eine JSON-Datei, standardmässig `kuerbis-daten.json` im selben Ordner wie die .exe (im Entwicklungsmodus im Projektordner).
Dasselbe Format dient als JSON-Export.

**Speicherort wählbar:** Unter „Speicherort…“ wird der aktuelle Pfad angezeigt und kann geändert werden:
- „Daten hierhin verschieben“: aktuelle Daten werden an den neuen Ort gespeichert (z. B. OneDrive-Ordner); existiert dort
  schon eine Datei, wird nachgefragt (überschreiben oder stattdessen öffnen).
- „Vorhandene Datei öffnen“: eine bestehende Datendatei wird ab sofort verwendet.
Der gewählte Pfad wird in `%APPDATA%\Kuerbisverkauf\einstellungen.json` gemerkt. Fehlt die Datei am gemerkten Ort
(z. B. USB-Stick nicht eingesteckt), meldet das Programm dies und bietet an, einen anderen Ort zu wählen.

```json
{
  "format": "kuerbisverkauf",
  "version": 1,
  "saisons": {
    "2025": {
      "start": "2025-08-25",
      "eintraege": { "2025-09-05": 45, "2025-09-06": 106 }
    }
  }
}
```

- Eine Saison = Jahr + Startdatum + Beträge pro Datum. Tage ohne Verkauf werden nicht gespeichert.
- Betrag leer = kein Eintrag. Betrag 0 = Verkaufstag ohne Einnahmen (zählt bei Tagen, Min und Mittel mit,
  wie im Blatt `Üb`). Negative Beträge werden abgelehnt.
- Speichern ist sicher: zuerst in eine temporäre Datei schreiben, dann ersetzen. Die vorherige Version bleibt als
  `kuerbis-daten.json.bak`.
- Gespeichert wird automatisch nach jeder Änderung.

## Berechnungen (wie in Excel)

- **Woche**: Woche 1 = Startdatum bis Startdatum + 6 Tage, dann fortlaufende 7-Tage-Blöcke.
- **Laufendes Total** pro Tag, **Wochentotal** pro Woche, **kumuliertes Wochentotal**.
- **Statistik pro Jahr**: Min, Max, Mittel (über alle erfassten Tage, auch 0), Anzahl Verkaufstage, Total.
- Die Saison ist so lang wie nötig: mindestens 16 Wochen, bei Einträgen danach entsprechend länger.

## Oberfläche

Drei Ansichten, oben als Reiter umschaltbar:

1. **Erfassung**
   - Jahr auswählen, „Neue Saison“ (fragt nach dem Startdatum, vorgeschlagen wird der letzte Montag im August).
     Das Startdatum lässt sich nachträglich ändern.
   - Tabelle wie in Excel: Woche, Wochentag, Datum, Betrag (Eingabefeld), laufendes Total, Wochentotal.
     Mit Enter/Pfeiltasten geht es zur nächsten Zeile. Der heutige Tag ist hervorgehoben.
   - Daneben das **Diagramm des Jahres**: Tagesbeträge als Balken plus laufendes Total als Linie.
   - Kennzahlen des Jahres (Total, Tage, Mittel, Max).
2. **Vergleich**
   - Liniendiagramm: laufendes Total über die Saisontage (Tag 1 = Startdatum), eine Linie pro Jahr.
     Jahre per Checkbox wählbar (Standard: aktuelles Jahr + die 4 davor).
   - Balkendiagramm: Jahrestotal aller Jahre.
3. **Übersicht**
   - Tabelle Wochentotale pro Jahr (Wo 1 … n) und Statistik pro Jahr (Min, Max, Mittel, Tage, Total), wie Blatt `Üb`.

## Import / Export

Menüknöpfe „Exportieren…“ und „Importieren…“ mit den Windows-Dateidialogen.

- **Export JSON**: die Datendatei, als exaktes Backup bzw. zum Teilen.
- **Export Excel**: Blatt `Daten` (Jahr, Startdatum, Datum, Betrag), Blatt `Übersicht` (Wochentotale + Statistik).
  Auch ohne das Programm lesbar.
- **Import** erkennt das Format automatisch:
  - eigenes JSON,
  - eigenes Excel (Blatt `Daten`),
  - die alte Excel-Datei (Blätter mit zweistelligen Jahresnamen; `98`/`99` → 1998/1999, sonst 20xx; C5 = Startdatum,
    Spalte C Datum, Spalte D Betrag; gelesen werden die gespeicherten Werte).
- **Zusammenführen**:
  - Neue Jahre und neue Tage werden übernommen.
  - Gleicher Betrag: nichts passiert.
  - Anderer Betrag oder anderes Startdatum: Konfliktliste (Datum, mein Wert, importierter Wert, Auswahl pro Zeile,
    dazu „alle meine behalten“ / „alle importierten übernehmen“). Erst nach Bestätigung wird gespeichert.
  - Danach eine Zusammenfassung (x Tage neu, y Konflikte gelöst).
- Ungültige oder unbekannte Dateien ergeben eine verständliche Fehlermeldung; die Daten bleiben unverändert.

## Aufbau des Codes

```
pyproject.toml
src/kuerbis/
  model.py      Datenklassen Saison/Daten, Berechnungen (Wochen, Totale, Statistik)
  storage.py    JSON laden/speichern (sicher, mit .bak)
  settings.py   Einstellungen (gewählter Datenpfad) in %APPDATA%
  excel_io.py   Import alte Excel + eigenes Excel, Excel-Export
  merge.py      Konflikte erkennen und Auflösungen anwenden
  api.py        Schnittstelle Python ↔ JavaScript (pywebview js_api)
  app.py        Programmstart, Fenster
  web/          index.html, app.js, style.css, chart.umd.min.js
tests/          pytest für model, storage, excel_io, merge
build.ps1       PyInstaller-Build der .exe
```

Die Oberfläche enthält keine Rechenlogik: Sie holt die berechneten Werte über `api.py` und schickt nur Eingaben zurück.

## Tests

- Berechnungen: Wochenzuordnung, laufendes Total, Wochentotal, Statistik.
- Speicherung: Rundlauf speichern/laden, .bak entsteht, kaputte Datei → Fehlermeldung statt Datenverlust.
- Import der alten Excel: Statistik jedes Jahres muss mit dem Blatt `Üb` übereinstimmen (Sollwerte werden zur Laufzeit
  aus der lokalen Datei gelesen; die Datei ist nicht im Repository, ohne sie wird der Test übersprungen).
- Export → Import ergibt dieselben Daten (JSON und Excel).
- Zusammenführen: neue Tage, gleiche Werte, Konflikte, Startdatum-Konflikt.
- Zum Schluss: .exe bauen und von Hand starten (Erfassen, Diagramm, Import, Export).

## Nicht im Umfang

Mehrere Verkaufsstellen, Produkte/Stückzahlen, Benutzerverwaltung, Online-Synchronisation, Drucken.
