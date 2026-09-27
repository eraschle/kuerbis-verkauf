"""Import (JSON, eigenes Excel, alte Excel) und Export (JSON, Excel)."""

from __future__ import annotations

import json
import re
import warnings
import zipfile
from datetime import date, datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .model import Daten, Saison, betrag_normalisieren, daten_aus_dict, statistik, wochentotale
from .storage import speichern

DATEN_KOPF = ["Jahr", "Datum", "Betrag"]
DATEN_KOPF_V1 = ["Jahr", "Startdatum", "Datum", "Betrag"]


def importieren(pfad: Path) -> Daten:
    endung = pfad.suffix.lower()
    if endung == ".json":
        try:
            obj = json.loads(pfad.read_text(encoding="utf-8-sig"))  # -sig: verträgt ein BOM
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"Die JSON-Datei kann nicht gelesen werden: {e}") from None
        return daten_aus_dict(obj)
    if endung in (".xlsx", ".xlsm"):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                wb = openpyxl.load_workbook(pfad, data_only=True, read_only=True)
        except (OSError, zipfile.BadZipFile, KeyError) as e:
            raise ValueError(f"Die Excel-Datei kann nicht gelesen werden: {e}") from None
        try:
            if "Daten" in wb.sheetnames:
                return _eigenes_excel(wb["Daten"])
            alte = [n for n in wb.sheetnames if re.fullmatch(r"\d\d", n)]
            if alte:
                return _alte_excel(wb, alte)
        finally:
            wb.close()
    raise ValueError("Unbekanntes Dateiformat. Unterstützt: Kürbisverkauf-JSON, Kürbisverkauf-Excel und die alte Excel-Datei.")


def _als_datum(wert) -> date | None:
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    if isinstance(wert, str):
        try:
            return date.fromisoformat(wert.strip()[:10])
        except ValueError:
            return None
    return None


def _alte_excel(wb, blaetter: list[str]) -> Daten:
    """Blätter '98' … '25': Spalte C Datum, Spalte D Betrag ab Zeile 5 (das Startdatum wird nicht mehr gebraucht)."""
    saisons = {}
    for name in blaetter:
        jahr = 1900 + int(name) if int(name) >= 90 else 2000 + int(name)
        eintraege = {}
        for z in wb[name].iter_rows(min_row=5, max_col=4, values_only=True):
            tag = _als_datum(z[2])
            try:
                betrag = betrag_normalisieren(z[3])
            except ValueError:
                raise ValueError(f"Blatt {name}: ungültiger Betrag {z[3]!r} am {tag}") from None
            if tag and betrag is not None:
                eintraege[tag] = betrag
        if eintraege:
            saisons[jahr] = Saison(jahr, eintraege)
    return Daten(saisons)


def _eigenes_excel(ws) -> Daten:
    zeilen = ws.iter_rows(values_only=True)
    kopf = [str(x).strip() if x is not None else "" for x in next(zeilen, [])]
    if kopf[:3] == DATEN_KOPF:
        spalten = (0, 1, 2)
    elif kopf[:4] == DATEN_KOPF_V1:
        spalten = (0, 2, 3)  # früheres Format mit Startdatum
    else:
        raise ValueError("Das Blatt 'Daten' hat nicht die erwarteten Spalten Jahr, Datum, Betrag.")
    sj, sd, sb = spalten
    saisons: dict[int, Saison] = {}
    for nr, z in enumerate(zeilen, start=2):
        if not z or all(v is None for v in z[: sb + 1]):
            continue
        try:
            jahr = int(z[sj])
            s = saisons.setdefault(jahr, Saison(jahr, {}))
            tag = _als_datum(z[sd])
            betrag = betrag_normalisieren(z[sb])
            if tag and betrag is not None:
                s.eintraege[tag] = betrag
        except (TypeError, ValueError) as e:
            raise ValueError(f"Blatt 'Daten', Zeile {nr}: {e}") from None
    return Daten(saisons)


def json_exportieren(pfad: Path, d: Daten) -> None:
    speichern(pfad, d)
    bak = pfad.with_name(pfad.name + ".bak")
    bak.unlink(missing_ok=True)


def excel_exportieren(pfad: Path, d: Daten) -> None:
    wb = openpyxl.Workbook()
    fett = Font(bold=True)

    ws = wb.active
    ws.title = "Daten"
    ws.append(DATEN_KOPF)
    for jahr, s in sorted(d.saisons.items()):
        if not s.eintraege:
            ws.append([jahr, None, None])  # leere Saison erhalten
        for tag in sorted(s.eintraege):
            ws.append([jahr, tag, s.eintraege[tag]])
    for zelle in ws[1]:
        zelle.font = fett
    for zeile in ws.iter_rows(min_row=2):
        zeile[1].number_format = "DD.MM.YYYY"
        zeile[2].number_format = "#,##0.00"
    for i, breite in enumerate([8, 13, 11], start=1):
        ws.column_dimensions[get_column_letter(i)].width = breite
    ws.freeze_panes = "A2"

    ue = wb.create_sheet("Übersicht")
    totale = {jahr: wochentotale(s) for jahr, s in d.saisons.items()}
    alle_kw = [w for t in totale.values() for w in t]
    kws = list(range(min(alle_kw), max(alle_kw) + 1)) if alle_kw else []
    ue.append(["Jahr"] + [f"KW {w}" for w in kws] + ["Min", "Max", "Mittel", "Tage", "Total"])
    for jahr, s in sorted(d.saisons.items()):
        st = statistik(s)
        ue.append([jahr] + [totale[jahr].get(w) for w in kws] + [st["min"], st["max"], st["mittel"], st["tage"], st["total"]])
    for zelle in ue[1]:
        zelle.font = fett
    ue.freeze_panes = "B2"

    pfad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(pfad)
