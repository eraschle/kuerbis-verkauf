# Kürbisverkauf – Design

Datum: 2026-09-27
Status: Freigegeben

## Ziel

Die Excel-Datei `Kürbissverkauf 1998-2025.xlsx` wird durch ein Windows-Programm (.exe) ersetzt.
Man erfasst jedes Jahr die täglichen Einnahmen aus dem Hofkürbisverkauf,
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
Der gewählte Pfad wird in `%APPDATA%\Kuerbisverkauf\einstellungen.json` gemerkt (dort auch „Anzahl Jahre“ und
die vom MIN/MAX-Bereich ausgenommenen Jahre). Fehlt die Datei am gemerkten Ort
(z. B. USB-Stick nicht eingesteckt), meldet das Programm dies und bietet an, einen anderen Ort zu wählen.

```json
{
  "format": "kuerbisverkauf",
  "version": 2,
  "saisons": {
    "2025": {
      "eintraege": { "2025-09-05": 45, "2025-09-06": 106 }
    }
  }
}
```

- Eine Saison = Jahr + Beträge pro Datum (kein Startdatum; Version 1 mit `start` wird weiterhin gelesen, `start` ignoriert).
  Tage ohne Eintrag werden nicht gespeichert.
- Betrag leer = kein Eintrag. Betrag 0 = Verkaufstag ohne Einnahmen (zählt bei Tagen, Min und Mittel mit,
  wie im Blatt `Üb`). Negative Beträge werden abgelehnt.
- Speichern ist sicher: zuerst in eine temporäre Datei schreiben, dann ersetzen. Die vorherige Version bleibt als
  `kuerbis-daten.json.bak`.
- Gespeichert wird automatisch nach jeder Änderung.

## Gemeinsame Nutzung (z. B. OneDrive) und sicheres Speichern

- **Keine fremden Änderungen überschreiben:** Das Programm merkt sich die Prüfsumme der Datei beim Laden/Speichern.
  Vor jeder Änderung wird verglichen; hat jemand anders die Datei geändert, wird sie neu geladen und nur die eigene
  Änderung darauf angewendet. Die Oberfläche schickt beim Speichern eines Tages den zuvor angezeigten Wert mit; hat
  jemand anders genau diesen Tag anders gesetzt, wird nachgefragt, welcher Wert gilt. Alle 30 s wird zusätzlich auf
  fremde Änderungen geprüft und die Anzeige aktualisiert. Eine plötzlich fehlende Datei wird nie als „leer“ behandelt.
- **Sperrdatei** `<datendatei>.lock` (Benutzer, PC, seit, aufgefrischt): beim Öffnen gesetzt, alle 60 s aufgefrischt,
  beim Beenden gelöscht. Hält jemand anders die Sperre, öffnet das Programm **nur zur Ansicht** (Balken mit Name/PC,
  „Erneut prüfen“, „Sperre übernehmen“); Schreiben wird auch in Python verweigert. Nach 10 min ohne Auffrischen gilt
  eine Sperre als veraltet (Absturz) und kann übernommen werden. Wird die Sperre frei, übernimmt das Programm sie beim
  nächsten Prüfen selbst.
- **Nichts geht verloren:** Tagesfelder werden bei Enter, beim Verlassen und automatisch nach 1 s Tipp-Pause
  gespeichert (nacheinander, nie überlappend). Beim Schliessen mit offenen Eingaben (auch ein Betrag in der Zeile
  „Neu“ ohne Enter) fragt ein Dialog: Speichern und schliessen / Verwerfen und schliessen / Zurück. Vor Jahres-,
  Reiter- und Speicherortwechsel werden offene Eingaben gespeichert. Anzeige unten rechts: gespeichert / speichert /
  nicht gespeichert / Fehler / nur Ansicht.
- JSON-Dateien werden mit `utf-8-sig` gelesen (verträgt ein BOM, z. B. nach Bearbeitung im Windows-Editor).

## Berechnungen (wie in Excel)

- **Woche** = Kalenderwoche (ISO, Montag–Sonntag) im Jahr der Saison; Einträge Ende Dezember zählen als KW 53/54
  weiter. Die Startdaten der alten Excel waren Montage, ihre „Wo n“ entsprechen also Kalenderwochen.
- **Laufendes Total** pro Tag, **Wochentotal** pro Woche, **kumuliertes Wochentotal**.
- **Statistik pro Jahr**: Min, Max, Mittel (über alle erfassten Tage, auch 0), Anzahl Verkaufstage, Total.
- Die Saison reicht vom ersten bis zum letzten erfassten Tag; Lücken dazwischen werden als leere Tage angezeigt.

## Oberfläche

Drei Ansichten, oben als Reiter umschaltbar:

1. **Erfassung**
   - Jahr auswählen, „Neue Saison“ (fragt nur nach dem Jahr).
   - Tabelle: KW, Wochentag, Datum, Betrag (Eingabefeld), laufendes Total, Wochentotal (am Sonntag bzw. letzten Tag).
     Nur vom ersten bis zum letzten erfassten Tag, keine leeren Zeilen am Anfang/Ende.
   - Darunter immer eine Zeile „Neuer Tag“: Datum vorbelegt mit dem Tag nach dem letzten Eintrag (leere Saison: heute
     bzw. letzter Montag im August), änderbar (auch vor dem ersten Eintrag, muss im Saisonjahr liegen). Betrag + Enter
     fügt den Tag an; die Zeile rückt weiter. Leeren eines Betrags entfernt den Tag (Tabelle schrumpft ggf.).
     Mit Enter/Pfeiltasten geht es zur nächsten Zeile. Der heutige Tag ist hervorgehoben.
   - Daneben das **Diagramm des Jahres**: Tagesbeträge als Balken plus laufendes Total als Linie.
   - Kennzahlen des Jahres (Total, Tage, Mittel, Max).
2. **Vergleich**
   - Liniendiagramm: laufendes Total, eine Linie pro Jahr. X-Achse = Kalenderwoche + Wochentag, damit gleiche
     Wochentage übereinanderliegen (Achse beginnt am Montag der frühesten KW der gewählten Jahre, Beschriftung „KW n“;
     Tooltip zeigt das echte Datum je Jahr). Jede Linie beginnt beim ersten und endet beim letzten Verkaufstag.
     Jahre per Checkbox wählbar (Standard: aktuelles Jahr + die 4 davor).
   - Auswahl „Letzte [N] Jahre“ (1–10, Standard 5, in den Einstellungen gemerkt); Jahre zusätzlich per Knopf
     an-/abwählbar (höchstens 10 Linien).
   - Farben nach Alter: laufendes Jahr kräftig orange (dicker), frühere Jahre Blau-Verlauf dunkel (letztes Jahr)
     → hell (älter). Die Farbe hängt am Jahr, nicht an der Auswahl.
   - **MIN/MAX-Bereich** als graue Fläche zwischen den Kurven des MIN- und des MAX-Jahres (gestrichelte Ränder),
     immer sichtbar, zählt nicht als Linie. MIN/MAX = tiefstes/höchstes Jahrestotal der abgeschlossenen Jahre
     (vor dem laufenden Kalenderjahr, nur Jahre mit Einträgen). Einzelne Jahre lassen sich im Dialog
     „MIN/MAX-Jahre…“ ausnehmen (gemerkt in den Einstellungen).
   - Balkendiagramm: Jahrestotal aller Jahre; MIN/MAX dunkel und beschriftet, laufendes Jahr hell.
3. **Übersicht**
   - MIN-/MAX-Jahr sind in beiden Tabellen farbig markiert („▲ Max“, „▼ Min“); alle Jahre bleiben sichtbar.
   - Tabelle Wochentotale pro Jahr (KW n … m) und Statistik pro Jahr (Min, Max, Mittel, Tage, Total), wie Blatt `Üb`.

## Import / Export

Menüknöpfe „Exportieren…“ und „Importieren…“ mit den Windows-Dateidialogen.

- **Export JSON**: die Datendatei, als exaktes Backup bzw. zum Teilen.
- **Export Excel**: Blatt `Daten` (Jahr, Datum, Betrag), Blatt `Übersicht` (Wochentotale je KW + Statistik).
  Der Import liest auch das frühere Format mit Spalte Startdatum.
  Auch ohne das Programm lesbar.
- **Import** erkennt das Format automatisch:
  - eigenes JSON,
  - eigenes Excel (Blatt `Daten`),
  - die alte Excel-Datei (Blätter mit zweistelligen Jahresnamen; `98`/`99` → 1998/1999, sonst 20xx;
    Spalte C Datum, Spalte D Betrag; gelesen werden die gespeicherten Werte).
- **Zusammenführen**:
  - Neue Jahre und neue Tage werden übernommen.
  - Gleicher Betrag: nichts passiert.
  - Anderer Betrag: Konfliktliste (Datum, mein Wert, importierter Wert, Auswahl pro Zeile,
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
- Zusammenführen: neue Tage, gleiche Werte, Konflikte.
- Zum Schluss: .exe bauen und von Hand starten (Erfassen, Diagramm, Import, Export).

## Nicht im Umfang

Mehrere Verkaufsstellen, Produkte/Stückzahlen, Benutzerverwaltung, Online-Synchronisation, Drucken.
