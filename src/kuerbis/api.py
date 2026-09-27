"""Schnittstelle zwischen Oberfläche (JavaScript) und Python.

Alle öffentlichen Methoden geben JSON-fähige Werte zurück; Fehler als {"fehler": text}.
"""

from __future__ import annotations

import functools
import threading
from datetime import date
from pathlib import Path

from . import excel_io, merge, settings, storage
from .sperre import Sperre
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


_OHNE = object()  # betrag_setzen ohne erwarteten Wert: keine Konfliktprüfung


def _fehler_als_antwort(methode):
    """Fehler als {"fehler": text}; alle Aufrufe laufen nacheinander (pywebview ruft aus mehreren Threads)."""

    @functools.wraps(methode)
    def wrapper(self, *args, **kwargs):
        try:
            with self._mutex:
                return methode(self, *args, **kwargs)
        except (ValueError, OSError, storage.DatenFehler) as e:
            return {"fehler": str(e)}

    return wrapper


class Api:
    def __init__(self, datenpfad: Path, einstellungen_basis: Path | None = None, heute: date | None = None):
        # Unterstrich-Attribute werden von pywebview nicht an JavaScript weitergegeben.
        self._mutex = threading.RLock()
        self._basis = einstellungen_basis
        self._heute = heute  # nur für Tests; sonst das echte Datum
        self._import: Daten | None = None
        self._fenster = None
        self._sperre: Sperre | None = None
        self._offen = 0  # von der Oberfläche gemeldete, noch nicht gespeicherte Eingaben
        self._schliessen_erlaubt = False
        self._oeffnen(Path(datenpfad))

    @classmethod
    def aus_einstellungen(cls, einstellungen_basis: Path | None = None) -> "Api":
        return cls(settings.datenpfad_lesen(einstellungen_basis), einstellungen_basis)

    def fenster_setzen(self, fenster) -> None:
        self._fenster = fenster

    # ---- intern ----

    def _oeffnen(self, pfad: Path) -> None:
        """Datei laden und die Sperre dafür holen (sonst nur Ansicht)."""
        if self._sperre:
            self._sperre.freigeben()
        self._pfad = pfad
        try:
            self._daten = storage.laden(pfad)
            self._ladefehler = None
        except storage.DatenFehler as e:
            self._daten = Daten()
            self._ladefehler = str(e)
        self._stand = storage.fingerabdruck(pfad)
        self._sperre = Sperre(pfad)
        self._nur_ansicht = not self._sperre.erwerben()

    def _speichern(self) -> None:
        storage.speichern(self._pfad, self._daten)
        self._stand = storage.fingerabdruck(self._pfad)

    def _synchronisieren(self) -> bool:
        """Lädt die Datei neu, wenn sie jemand anders geändert hat. True, wenn neu geladen wurde."""
        stand = storage.fingerabdruck(self._pfad)
        if stand == self._stand:
            return False
        if stand is None:
            raise ValueError(
                f"Die Datendatei ist nicht mehr vorhanden: {self._pfad}. "
                "Bitte prüfen, ob der Ordner erreichbar ist (z. B. OneDrive), oder einen anderen Speicherort wählen."
            )
        self._daten = storage.laden(self._pfad)
        self._stand = stand
        self._ladefehler = None
        return True

    def _pruefe_schreibbar(self) -> None:
        if self._ladefehler:
            raise ValueError("Die Datendatei konnte nicht gelesen werden. Bitte zuerst einen anderen Speicherort wählen.")
        if self._nur_ansicht:
            info = self._sperre.lesen() or {}
            wer = f"{info.get('benutzer', 'jemand anders')} ({info.get('pc', '?')})"
            raise ValueError(f"Nur Ansicht: Die Daten werden gerade von {wer} bearbeitet.")

    def _vor_aenderung(self) -> bool:
        """Vor jeder Änderung: schreibbar? Fremde Änderungen zuerst übernehmen."""
        self._pruefe_schreibbar()
        return self._synchronisieren()

    def _saison(self, jahr) -> Saison:
        s = self._daten.saisons.get(int(jahr))
        if s is None:
            raise ValueError(f"Für {jahr} gibt es keine Saison.")
        return s

    def _saison_antwort(self, s: Saison, extern_geaendert: bool = False) -> dict:
        return {
            "jahr": s.jahr,
            "zeilen": tageszeilen(s),
            "statistik": statistik(s),
            "naechster_tag": naechster_tag(s).isoformat(),
            "extern_geaendert": extern_geaendert,
        }

    # ---- Abfragen ----

    def status(self) -> dict:
        antwort = {
            "datenpfad": str(self._pfad),
            "jahre": sorted(self._daten.saisons, reverse=True),
            "nur_ansicht": self._nur_ansicht,
            "sperre": None,
            "sperre_veraltet": False,
        }
        if self._nur_ansicht:
            info = self._sperre.lesen() or {}
            antwort["sperre"] = {k: info.get(k) for k in ("benutzer", "pc", "seit", "aktualisiert")}
            antwort["sperre_veraltet"] = self._sperre.zustand() == "veraltet"
        if self._ladefehler:
            antwort["fehler"] = self._ladefehler
        return antwort

    @_fehler_als_antwort
    def pruefen(self) -> dict:
        """Regelmässig von der Oberfläche aufgerufen: Sperre pflegen und fremde Änderungen erkennen."""
        if self._nur_ansicht:
            if self._sperre.zustand() == "frei":
                self._nur_ansicht = not self._sperre.erwerben()
        elif not self._sperre.auffrischen():
            self._nur_ansicht = True  # jemand anders hat die Sperre übernommen
        geaendert = self._synchronisieren()
        return {**self.status(), "geaendert": geaendert}

    def sperre_auffrischen(self) -> None:
        """Für den Hintergrund-Takt in app.py (unabhängig davon, ob die Oberfläche aktiv ist)."""
        with self._mutex:
            if not self._nur_ansicht and not self._sperre.auffrischen():
                self._nur_ansicht = True

    @_fehler_als_antwort
    def sperre_uebernehmen(self) -> dict:
        self._sperre.erwerben(erzwingen=True)
        self._nur_ansicht = self._sperre.zustand() != "eigen"
        self._synchronisieren()
        return self.status()

    # ---- Schliessen ----

    def offen_melden(self, anzahl) -> dict:
        self._offen = max(0, int(anzahl or 0))
        return {"ok": True}

    def darf_schliessen(self) -> bool:
        return self._schliessen_erlaubt or self._offen == 0

    def beenden(self, fenster_schliessen=True) -> dict:
        """Sperre freigeben und (nach der Rückfrage in der Oberfläche) das Fenster schliessen."""
        with self._mutex:
            self._schliessen_erlaubt = True
            if self._sperre:
                self._sperre.freigeben()
        if fenster_schliessen and self._fenster is not None:
            threading.Thread(target=self._fenster.destroy, daemon=True).start()
        return {"ok": True}

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
        extern = self._vor_aenderung()
        jahr = int(jahr)
        if not 1990 <= jahr <= 2100:
            raise ValueError(f"Ungültiges Jahr: {jahr}")
        if jahr in self._daten.saisons:
            raise ValueError(f"Die Saison {jahr} gibt es schon.")
        self._daten.saisons[jahr] = Saison(jahr, {})
        self._speichern()
        return self._saison_antwort(self._daten.saisons[jahr], extern)

    @_fehler_als_antwort
    def saison_loeschen(self, jahr) -> dict:
        self._vor_aenderung()
        self._saison(jahr)
        del self._daten.saisons[int(jahr)]
        self._speichern()
        return self.status()

    @_fehler_als_antwort
    def betrag_setzen(self, jahr, datum_iso, wert, erwartet=_OHNE) -> dict:
        """Setzt einen Tagesbetrag (leer = Eintrag entfernen).

        erwartet = der Wert, den die Oberfläche vor der Eingabe angezeigt hat. Hat jemand anders den Tag
        inzwischen auf einen anderen Wert gesetzt, wird nicht gespeichert, sondern {"konflikt": …} zurückgegeben.
        """
        extern = self._vor_aenderung()
        s = self._saison(jahr)
        try:
            tag = date.fromisoformat(datum_iso)
        except (TypeError, ValueError):
            raise ValueError("Bitte ein gültiges Datum wählen.") from None
        if tag.year != s.jahr:
            raise ValueError(f"Das Datum muss im Jahr {s.jahr} liegen.")
        betrag = betrag_normalisieren(wert)
        aktuell = s.eintraege.get(tag)
        if erwartet is not _OHNE and aktuell != betrag:
            erwartet = betrag_normalisieren(erwartet)
            if erwartet != aktuell:
                return {"konflikt": {"datum": tag.isoformat(), "erwartet": erwartet, "aktuell": aktuell, "neu": betrag}}
        if betrag is None:
            s.eintraege.pop(tag, None)
        else:
            s.eintraege[tag] = betrag
        self._speichern()
        return self._saison_antwort(s, extern)

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
        self._vor_aenderung()
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
        self._vor_aenderung()
        ziel = Path(pfad)
        if ziel.exists() and not ueberschreiben:
            return {"existiert": True}
        if Sperre(ziel).zustand() == "fremd":
            raise ValueError("Die Datei am gewählten Ort wird gerade von jemand anderem bearbeitet.")
        storage.speichern(ziel, self._daten)
        self._oeffnen(ziel)  # gibt die alte Sperre frei und holt die neue
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
