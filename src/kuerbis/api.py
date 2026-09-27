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
    kumuliert_pro_tag,
    statistik,
    tageszeilen,
    vorgeschlagener_start,
    wochentotale,
    anzahl_wochen,
)


# Beschreibung darf nur Buchstaben/Leerzeichen enthalten (pywebview prüft das Format).
DATEIFILTER = {
    "excel": ("Excel Datei (*.xlsx)",),
    "json": ("JSON Datei (*.json)",),
    "import": ("Kürbisverkauf Daten (*.json;*.xlsx)", "Excel Datei (*.xlsx)", "JSON Datei (*.json)", "Alle Dateien (*.*)"),
}


def _fehler_als_antwort(methode):
    @functools.wraps(methode)
    def wrapper(self, *args, **kwargs):
        try:
            return methode(self, *args, **kwargs)
        except (ValueError, OSError, storage.DatenFehler) as e:
            return {"fehler": str(e)}

    return wrapper


class Api:
    def __init__(self, datenpfad: Path, einstellungen_basis: Path | None = None):
        # Unterstrich-Attribute werden von pywebview nicht an JavaScript weitergegeben.
        self._basis = einstellungen_basis
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
            "start": s.start.isoformat(),
            "zeilen": tageszeilen(s),
            "statistik": statistik(s),
            "wochentotale": wochentotale(s),
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

    def vorschlag_start(self, jahr) -> dict:
        return {"start": vorgeschlagener_start(int(jahr)).isoformat()}

    def vergleich(self) -> dict:
        return {
            "jahre": [
                {"jahr": j, "start": s.start.isoformat(), "kumuliert": kumuliert_pro_tag(s), "total": statistik(s)["total"]}
                for j, s in sorted(self._daten.saisons.items())
            ]
        }

    def uebersicht(self) -> dict:
        saisons = sorted(self._daten.saisons.items(), reverse=True)
        return {
            "max_wochen": max((anzahl_wochen(s) for _, s in saisons), default=16),
            "zeilen": [
                {"jahr": j, "start": s.start.isoformat(), "wochen": wochentotale(s), "statistik": statistik(s)}
                for j, s in saisons
            ],
        }

    # ---- Änderungen ----

    @_fehler_als_antwort
    def neue_saison(self, jahr, start_iso) -> dict:
        self._pruefe_schreibbar()
        jahr = int(jahr)
        if jahr in self._daten.saisons:
            raise ValueError(f"Die Saison {jahr} gibt es schon.")
        self._daten.saisons[jahr] = Saison(jahr, date.fromisoformat(start_iso), {})
        self._speichern()
        return self._saison_antwort(self._daten.saisons[jahr])

    @_fehler_als_antwort
    def start_aendern(self, jahr, start_iso) -> dict:
        self._pruefe_schreibbar()
        s = self._saison(jahr)
        neu = date.fromisoformat(start_iso)
        if s.eintraege and min(s.eintraege) < neu:
            raise ValueError("Es gibt Einträge vor diesem Startdatum.")
        s.start = neu
        self._speichern()
        return self._saison_antwort(s)

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
        tag = date.fromisoformat(datum_iso)
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
