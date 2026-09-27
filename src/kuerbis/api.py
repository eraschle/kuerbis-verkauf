"""Schnittstelle zwischen Oberfläche (JavaScript) und Python.

Alle öffentlichen Methoden geben JSON-fähige Werte zurück; Fehler als {"fehler": text}.
"""

from __future__ import annotations

import functools
from datetime import date
from pathlib import Path

from . import excel_io, merge, settings, storage
from .model import (
    Daten,
    Saison,
    betrag_normalisieren,
    min_max_jahre,
    naechster_tag,
    statistik,
    tageszeilen,
    vergleichsreihe,
    wochentotale,
)


# Beschreibung darf nur Buchstaben/Leerzeichen enthalten (pywebview prüft das Format).
DATEIFILTER = {
    "excel": ("Excel Datei (*.xlsx)",),
    "json": ("JSON Datei (*.json)",),
    "import": ("Kürbisverkauf Daten (*.json;*.xlsx)", "Excel Datei (*.xlsx)", "JSON Datei (*.json)", "Alle Dateien (*.*)"),
}


ANZAHL_JAHRE_STANDARD = 5
MAX_JAHRE = 10  # Linien im Vergleich (Farben nach Alter, siehe app.js)


def _fehler_als_antwort(methode):
    @functools.wraps(methode)
    def wrapper(self, *args, **kwargs):
        try:
            return methode(self, *args, **kwargs)
        except (ValueError, OSError, storage.DatenFehler) as e:
            return {"fehler": str(e)}

    return wrapper


class Api:
    def __init__(self, datenpfad: Path, einstellungen_basis: Path | None = None, heute: date | None = None):
        # Unterstrich-Attribute werden von pywebview nicht an JavaScript weitergegeben.
        self._basis = einstellungen_basis
        self._heute = heute  # nur für Tests; sonst das echte Datum
        self._import: Daten | None = None
        self._fenster = None
        self._oeffnen(Path(datenpfad))

    @classmethod
    def aus_einstellungen(cls, einstellungen_basis: Path | None = None) -> "Api":
        return cls(settings.datenpfad_lesen(einstellungen_basis), einstellungen_basis)

    def fenster_setzen(self, fenster) -> None:
        self._fenster = fenster

    # ---- intern ----

    def _oeffnen(self, pfad: Path) -> None:
        self._pfad = pfad
        try:
            self._daten = storage.laden(pfad)
            self._ladefehler = None
        except storage.DatenFehler as e:
            self._daten = Daten()
            self._ladefehler = str(e)

    def _speichern(self) -> None:
        storage.speichern(self._pfad, self._daten)

    def _pruefe_schreibbar(self) -> None:
        if self._ladefehler:
            raise ValueError("Die Datendatei konnte nicht gelesen werden. Bitte zuerst einen anderen Speicherort wählen.")

    def _saison(self, jahr) -> Saison:
        s = self._daten.saisons.get(int(jahr))
        if s is None:
            raise ValueError(f"Für {jahr} gibt es keine Saison.")
        return s

    def _saison_antwort(self, s: Saison) -> dict:
        return {
            "jahr": s.jahr,
            "zeilen": tageszeilen(s),
            "statistik": statistik(s),
            "naechster_tag": naechster_tag(s).isoformat(),
        }

    # ---- Abfragen ----

    def status(self) -> dict:
        antwort = {"datenpfad": str(self._pfad), "jahre": sorted(self._daten.saisons, reverse=True)}
        if self._ladefehler:
            antwort["fehler"] = self._ladefehler
        return antwort

    @_fehler_als_antwort
    def saison(self, jahr) -> dict:
        return self._saison_antwort(self._saison(jahr))

    def _aktuelles_jahr(self) -> int:
        return (self._heute or date.today()).year

    def _ausgenommen(self) -> list[int]:
        werte = settings.einstellung_lesen("bereich_ausgenommen", [], self._basis)
        return sorted(int(j) for j in werte) if isinstance(werte, list) else []

    def _bereich(self) -> dict:
        return min_max_jahre(self._daten, self._aktuelles_jahr(), self._ausgenommen())

    def vergleich(self) -> dict:
        """Pro Jahr das laufende Total; erster_tag = Position auf der gemeinsamen Achse (KW + Wochentag).

        bereich = MIN-/MAX-Jahr der abgeschlossenen Jahre (ohne ausgenommene) für die Fläche im Diagramm.
        """
        aktuell = self._aktuelles_jahr()
        anzahl = settings.einstellung_lesen("vergleich_jahre", ANZAHL_JAHRE_STANDARD, self._basis)
        return {
            "jahre": [
                {"jahr": j, **vergleichsreihe(s), "total": statistik(s)["total"]}
                for j, s in sorted(self._daten.saisons.items())
            ],
            "aktuelles_jahr": aktuell,
            "bereich": self._bereich(),
            "anzahl_jahre": anzahl if isinstance(anzahl, int) and 1 <= anzahl <= MAX_JAHRE else ANZAHL_JAHRE_STANDARD,
            "ausgenommen": self._ausgenommen(),
            "abgeschlossen": [
                {"jahr": j, "total": statistik(s)["total"]}
                for j, s in sorted(self._daten.saisons.items(), reverse=True)
                if j < aktuell and s.eintraege
            ],
        }

    @_fehler_als_antwort
    def vergleich_einstellen(self, anzahl_jahre, ausgenommen) -> dict:
        anzahl = int(anzahl_jahre)
        if not 1 <= anzahl <= MAX_JAHRE:
            raise ValueError(f"Die Anzahl Jahre muss zwischen 1 und {MAX_JAHRE} liegen.")
        settings.einstellung_setzen("vergleich_jahre", anzahl, self._basis)
        settings.einstellung_setzen("bereich_ausgenommen", sorted(int(j) for j in ausgenommen or []), self._basis)
        return self.vergleich()

    def uebersicht(self) -> dict:
        saisons = sorted(self._daten.saisons.items(), reverse=True)
        totale = {j: wochentotale(s) for j, s in saisons}
        alle_kw = [w for t in totale.values() for w in t]
        kws = list(range(min(alle_kw), max(alle_kw) + 1)) if alle_kw else []
        return {
            "kws": kws,
            "bereich": self._bereich(),
            "zeilen": [
                {
                    "jahr": j,
                    "erster_tag": min(s.eintraege).isoformat() if s.eintraege else None,
                    "letzter_tag": max(s.eintraege).isoformat() if s.eintraege else None,
                    "wochen": [totale[j].get(w) for w in kws],
                    "statistik": statistik(s),
                }
                for j, s in saisons
            ],
        }

    # ---- Änderungen ----

    @_fehler_als_antwort
    def neue_saison(self, jahr) -> dict:
        self._pruefe_schreibbar()
        jahr = int(jahr)
        if not 1990 <= jahr <= 2100:
            raise ValueError(f"Ungültiges Jahr: {jahr}")
        if jahr in self._daten.saisons:
            raise ValueError(f"Die Saison {jahr} gibt es schon.")
        self._daten.saisons[jahr] = Saison(jahr, {})
        self._speichern()
        return self._saison_antwort(self._daten.saisons[jahr])

    @_fehler_als_antwort
    def saison_loeschen(self, jahr) -> dict:
        self._pruefe_schreibbar()
        self._saison(jahr)
        del self._daten.saisons[int(jahr)]
        self._speichern()
        return self.status()

    @_fehler_als_antwort
    def betrag_setzen(self, jahr, datum_iso, wert) -> dict:
        self._pruefe_schreibbar()
        s = self._saison(jahr)
        try:
            tag = date.fromisoformat(datum_iso)
        except (TypeError, ValueError):
            raise ValueError("Bitte ein gültiges Datum wählen.") from None
        if tag.year != s.jahr:
            raise ValueError(f"Das Datum muss im Jahr {s.jahr} liegen.")
        betrag = betrag_normalisieren(wert)
        if betrag is None:
            s.eintraege.pop(tag, None)
        else:
            s.eintraege[tag] = betrag
        self._speichern()
        return self._saison_antwort(s)

    # ---- Import / Export ----

    @_fehler_als_antwort
    def export_nach(self, pfad, art) -> dict:
        if art == "excel":
            excel_io.excel_exportieren(Path(pfad), self._daten)
        else:
            excel_io.json_exportieren(Path(pfad), self._daten)
        return {"ok": True}

    @_fehler_als_antwort
    def import_vorbereiten(self, pfad) -> dict:
        self._pruefe_schreibbar()
        importiert = excel_io.importieren(Path(pfad))
        self._import = importiert
        konflikte = merge.konflikte_finden(self._daten, importiert)
        _, vorschau = merge.zusammenfuehren(self._daten, importiert, {})
        return {
            "konflikte": konflikte,
            "neue_jahre": vorschau["neue_jahre"],
            "neue_tage": vorschau["neue_tage"],
            "jahre": sorted(importiert.saisons),
        }

    @_fehler_als_antwort
    def import_abschliessen(self, wahl) -> dict:
        if self._import is None:
            raise ValueError("Es wurde kein Import vorbereitet.")
        self._daten, info = merge.zusammenfuehren(self._daten, self._import, dict(wahl or {}))
        self._import = None
        self._speichern()
        return info

    def import_abbrechen(self) -> dict:
        self._import = None
        return {"ok": True}

    # ---- Speicherort ----

    @_fehler_als_antwort
    def speicherort_verschieben(self, pfad, ueberschreiben) -> dict:
        self._pruefe_schreibbar()
        ziel = Path(pfad)
        if ziel.exists() and not ueberschreiben:
            return {"existiert": True}
        storage.speichern(ziel, self._daten)
        self._pfad = ziel
        settings.datenpfad_setzen(ziel, self._basis)
        return self.status()

    @_fehler_als_antwort
    def speicherort_oeffnen(self, pfad) -> dict:
        ziel = Path(pfad)
        storage.laden(ziel)  # prüfen, bevor umgestellt wird
        self._oeffnen(ziel)
        settings.datenpfad_setzen(ziel, self._basis)
        return self.status()

    # ---- Dateidialoge (nur im Programmfenster) ----

    @staticmethod
    def _dialog_fehler(methode):
        @functools.wraps(methode)
        def wrapper(self, *args):
            try:
                return methode(self, *args)
            except Exception as e:  # Dialogfehler sollen in der Oberfläche sichtbar werden
                return {"fehler": f"Dateidialog: {e}"}

        return wrapper

    def _dialog(self, art, **kwargs):
        import webview

        typen = {"oeffnen": webview.FileDialog.OPEN, "speichern": webview.FileDialog.SAVE}
        ergebnis = self._fenster.create_file_dialog(typen[art], **kwargs)
        if not ergebnis:
            return None
        return ergebnis if isinstance(ergebnis, str) else ergebnis[0]

    @_dialog_fehler
    def export_dialog(self, art) -> dict:
        heute = date.today().isoformat()
        if art == "excel":
            name, typ = f"Kuerbisverkauf-{heute}.xlsx", DATEIFILTER["excel"]
        else:
            name, typ = f"Kuerbisverkauf-{heute}.json", DATEIFILTER["json"]
        pfad = self._dialog("speichern", save_filename=name, file_types=typ)
        if not pfad:
            return {"abgebrochen": True}
        return self.export_nach(pfad, art)

    @_dialog_fehler
    def import_dialog(self) -> dict:
        pfad = self._dialog(
            "oeffnen",
            file_types=DATEIFILTER["import"],
        )
        if not pfad:
            return {"abgebrochen": True}
        return self.import_vorbereiten(pfad)

    @_dialog_fehler
    def speicherort_verschieben_dialog(self) -> dict:
        pfad = self._dialog("speichern", save_filename=self._pfad.name, file_types=DATEIFILTER["json"])
        if not pfad:
            return {"abgebrochen": True}
        antwort = self.speicherort_verschieben(pfad, False)
        if antwort.get("existiert"):
            antwort["pfad"] = pfad
        return antwort

    @_dialog_fehler
    def speicherort_oeffnen_dialog(self) -> dict:
        pfad = self._dialog("oeffnen", file_types=DATEIFILTER["json"])
        if not pfad:
            return {"abgebrochen": True}
        return self.speicherort_oeffnen(pfad)
