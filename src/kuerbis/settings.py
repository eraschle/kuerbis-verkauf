"""Einstellungen (gewählter Speicherort der Datendatei)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DATEINAME = "kuerbis-daten.json"


def standard_datenpfad() -> Path:
    """Neben der .exe; im Entwicklungsmodus im Projektordner."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / DATEINAME
    return Path(__file__).resolve().parents[2] / DATEINAME


def einstellungen_ordner() -> Path:
    basis = os.environ.get("APPDATA") or str(Path.home())
    return Path(basis) / "Kuerbisverkauf"


def _datei(basis: Path | None) -> Path:
    return (basis or einstellungen_ordner()) / "einstellungen.json"


def _alle(basis: Path | None) -> dict:
    try:
        obj = json.loads(_datei(basis).read_text(encoding="utf-8-sig"))  # -sig: verträgt ein BOM
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def einstellung_lesen(schluessel: str, standard, basis: Path | None = None):
    return _alle(basis).get(schluessel, standard)


def einstellung_setzen(schluessel: str, wert, basis: Path | None = None) -> None:
    """Ändert eine Einstellung; alle anderen bleiben erhalten."""
    alle = _alle(basis)
    alle[schluessel] = wert
    datei = _datei(basis)
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(json.dumps(alle, ensure_ascii=False, indent=1), encoding="utf-8")


def datenpfad_lesen(basis: Path | None = None) -> Path:
    pfad = einstellung_lesen("datenpfad", None, basis)
    return Path(pfad) if isinstance(pfad, str) and pfad else standard_datenpfad()


def datenpfad_setzen(pfad: Path, basis: Path | None = None) -> None:
    einstellung_setzen("datenpfad", str(pfad), basis)
