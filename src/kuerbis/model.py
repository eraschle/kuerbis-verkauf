"""Datenmodell und Berechnungen (Kalenderwochen, Totale, Statistik)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

FORMAT = "kuerbisverkauf"
VERSION = 2
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


@dataclass
class Saison:
    jahr: int
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


# ---- Kalenderwochen ----


def _montag_kw1(jahr: int) -> date:
    return date.fromisocalendar(jahr, 1, 1)


def achsentag(jahr: int, tag: date) -> int:
    """Tage seit dem Montag der KW 1 des Saisonjahres. Gleiche KW + Wochentag ergibt in jedem Jahr denselben Wert."""
    return (tag - _montag_kw1(jahr)).days


def kw(jahr: int, tag: date) -> int:
    """ISO-Kalenderwoche im Saisonjahr; Ende Dezember wird als KW 53/54 weitergezählt."""
    return achsentag(jahr, tag) // 7 + 1


# ---- Berechnungen ----


def _tage(s: Saison) -> list[date]:
    if not s.eintraege:
        return []
    erster, letzter = min(s.eintraege), max(s.eintraege)
    return [erster + timedelta(i) for i in range((letzter - erster).days + 1)]


def tageszeilen(s: Saison) -> list[dict]:
    """Alle Tage vom ersten bis zum letzten Eintrag (Lücken als leere Tage)."""
    tage = _tage(s)
    zeilen = []
    laufend = 0.0
    wochensumme = 0.0
    woche_hat_eintrag = False
    for i, tag in enumerate(tage):
        betrag = s.eintraege.get(tag)
        if betrag is not None:
            laufend += betrag
            wochensumme += betrag
            woche_hat_eintrag = True
        wochenende = tag.weekday() == 6 or i == len(tage) - 1
        zeilen.append(
            {
                "datum": tag.isoformat(),
                "wochentag": WOCHENTAGE[tag.weekday()],
                "kw": kw(s.jahr, tag),
                "wochenstart": i == 0 or tag.weekday() == 0,
                "betrag": betrag,
                "laufend": _zahl(laufend) if betrag is not None else None,
                "wochentotal": _zahl(wochensumme) if wochenende and woche_hat_eintrag else None,
            }
        )
        if wochenende:
            wochensumme = 0.0
            woche_hat_eintrag = False
    return zeilen


def wochentotale(s: Saison) -> dict[int, float]:
    """Total pro Kalenderwoche, lückenlos von der ersten bis zur letzten KW mit Eintrag."""
    if not s.eintraege:
        return {}
    von, bis = kw(s.jahr, min(s.eintraege)), kw(s.jahr, max(s.eintraege))
    summen = {w: 0.0 for w in range(von, bis + 1)}
    for tag, betrag in s.eintraege.items():
        summen[kw(s.jahr, tag)] += betrag
    return {w: _zahl(x) for w, x in summen.items()}


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


def vergleichsreihe(s: Saison) -> dict:
    """Laufendes Total pro Tag ab dem ersten Eintrag; erster_tag ist die Position auf der gemeinsamen Achse."""
    tage = _tage(s)
    if not tage:
        return {"erster_tag": None, "erstes_datum": None, "kumuliert": []}
    kumuliert = []
    laufend = 0.0
    for tag in tage:
        laufend += s.eintraege.get(tag, 0)
        kumuliert.append(_zahl(laufend))
    return {"erster_tag": achsentag(s.jahr, tage[0]), "erstes_datum": tage[0].isoformat(), "kumuliert": kumuliert}


def vorgeschlagener_start(jahr: int) -> date:
    """Letzter Montag im August."""
    letzter = date(jahr, 8, 31)
    return letzter - timedelta(letzter.weekday())


def naechster_tag(s: Saison, heute: date | None = None) -> date:
    """Vorschlag für die Zeile „Neuer Tag“."""
    heute = heute or date.today()
    if s.eintraege:
        return min(max(s.eintraege) + timedelta(1), date(s.jahr, 12, 31))
    if heute.year == s.jahr:
        return heute
    return vorgeschlagener_start(s.jahr)


def min_max_jahre(d: Daten, aktuelles_jahr: int, ausgenommen=()) -> dict:
    """Jahr mit dem tiefsten und höchsten Jahrestotal unter den abgeschlossenen Jahren (vor dem aktuellen Jahr)."""
    totale = {
        j: statistik(s)["total"]
        for j, s in d.saisons.items()
        if j < aktuelles_jahr and s.eintraege and j not in set(ausgenommen)
    }
    if not totale:
        return {"min": None, "max": None}
    return {"min": min(totale, key=totale.get), "max": max(totale, key=totale.get)}


# ---- Serialisierung ----


def daten_zu_dict(d: Daten) -> dict:
    return {
        "format": FORMAT,
        "version": VERSION,
        "saisons": {
            str(jahr): {"eintraege": {tag.isoformat(): s.eintraege[tag] for tag in sorted(s.eintraege)}}
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
            saisons[jahr] = Saison(jahr, eintraege)  # Version 1: "start" wird ignoriert
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        raise ValueError(f"Die Datendatei ist fehlerhaft: {e}") from None
    return Daten(saisons)


def _zahl(x: float) -> float | int:
    x = round(x, 2)
    return int(x) if float(x).is_integer() else x
