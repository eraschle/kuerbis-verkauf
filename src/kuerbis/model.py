"""Datenmodell und Berechnungen (Wochen, Totale, Statistik)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

FORMAT = "kuerbisverkauf"
VERSION = 1
MIN_WOCHEN = 16
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


@dataclass
class Saison:
    jahr: int
    start: date
    eintraege: dict[date, float] = field(default_factory=dict)


@dataclass
class Daten:
    saisons: dict[int, Saison] = field(default_factory=dict)


def betrag_normalisieren(wert) -> float | int | None:
    """Wandelt eine Eingabe in einen Betrag um. Leer ergibt None; 0 ist ein Verkaufstag ohne Einnahmen."""
    if wert is None:
        return None
    if isinstance(wert, str):
        text = wert.strip().replace(",", ".").replace("'", "")
        if not text:
            return None
        try:
            zahl = float(text)
        except ValueError:
            raise ValueError(f"Ungültiger Betrag: {wert}") from None
    elif isinstance(wert, (int, float)) and not isinstance(wert, bool):
        zahl = float(wert)
    else:
        raise ValueError(f"Ungültiger Betrag: {wert}")
    if zahl != zahl or zahl in (float("inf"), float("-inf")):
        raise ValueError(f"Ungültiger Betrag: {wert}")
    if zahl < 0:
        raise ValueError("Der Betrag darf nicht negativ sein.")
    zahl = round(zahl, 2) + 0.0  # + 0.0 macht aus -0.0 eine 0
    return int(zahl) if zahl.is_integer() else zahl


def _woche(s: Saison, tag: date) -> int:
    return (tag - s.start).days // 7 + 1


def anzahl_wochen(s: Saison) -> int:
    letzte = max((_woche(s, d) for d in s.eintraege), default=0)
    return max(MIN_WOCHEN, letzte)


def tageszeilen(s: Saison) -> list[dict]:
    zeilen = []
    laufend = 0.0
    wochensumme = 0.0
    woche_hat_eintrag = False
    for i in range(anzahl_wochen(s) * 7):
        tag = s.start + timedelta(i)
        betrag = s.eintraege.get(tag)
        if betrag is not None:
            laufend += betrag
            wochensumme += betrag
            woche_hat_eintrag = True
        wochenende = i % 7 == 6
        zeilen.append(
            {
                "datum": tag.isoformat(),
                "wochentag": WOCHENTAGE[tag.weekday()],
                "woche": i // 7 + 1,
                "betrag": betrag,
                "laufend": _zahl(laufend) if betrag is not None else None,
                "wochentotal": _zahl(wochensumme) if wochenende and woche_hat_eintrag else None,
            }
        )
        if wochenende:
            wochensumme = 0.0
            woche_hat_eintrag = False
    return zeilen


def wochentotale(s: Saison) -> list[float]:
    summen = [0.0] * anzahl_wochen(s)
    for tag, betrag in s.eintraege.items():
        w = _woche(s, tag)
        if w >= 1:
            summen[w - 1] += betrag
    return [_zahl(x) for x in summen]


def statistik(s: Saison) -> dict:
    werte = list(s.eintraege.values())
    if not werte:
        return {"min": None, "max": None, "mittel": None, "tage": 0, "total": 0}
    total = sum(werte)
    return {
        "min": _zahl(min(werte)),
        "max": _zahl(max(werte)),
        "mittel": _zahl(round(total / len(werte), 2)),
        "tage": len(werte),
        "total": _zahl(total),
    }


def kumuliert_pro_tag(s: Saison) -> list[float]:
    tage = [d for d in s.eintraege if d >= s.start]
    if not tage:
        return []
    ergebnis = []
    laufend = 0.0
    for i in range((max(tage) - s.start).days + 1):
        laufend += s.eintraege.get(s.start + timedelta(i), 0)
        ergebnis.append(_zahl(laufend))
    return ergebnis


def vorgeschlagener_start(jahr: int) -> date:
    letzter = date(jahr, 8, 31)
    return letzter - timedelta(letzter.weekday())


def daten_zu_dict(d: Daten) -> dict:
    return {
        "format": FORMAT,
        "version": VERSION,
        "saisons": {
            str(jahr): {
                "start": s.start.isoformat(),
                "eintraege": {tag.isoformat(): s.eintraege[tag] for tag in sorted(s.eintraege)},
            }
            for jahr, s in sorted(d.saisons.items())
        },
    }


def daten_aus_dict(obj) -> Daten:
    if not isinstance(obj, dict) or obj.get("format") != FORMAT:
        raise ValueError("Die Datei ist keine Kürbisverkauf-Datendatei.")
    if obj.get("version", 1) > VERSION:
        raise ValueError("Die Datei stammt von einer neueren Programmversion.")
    try:
        saisons = {}
        for jahr_text, s in obj.get("saisons", {}).items():
            jahr = int(jahr_text)
            eintraege = {}
            for tag, betrag in s.get("eintraege", {}).items():
                wert = betrag_normalisieren(betrag)
                if wert is not None:
                    eintraege[date.fromisoformat(tag)] = wert
            saisons[jahr] = Saison(jahr, date.fromisoformat(s["start"]), eintraege)
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        raise ValueError(f"Die Datendatei ist fehlerhaft: {e}") from None
    return Daten(saisons)


def _zahl(x: float) -> float | int:
    x = round(x, 2)
    return int(x) if float(x).is_integer() else x
