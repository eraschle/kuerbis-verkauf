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


def datenpfad_lesen(basis: Path | None = None) -> Path:
    try:
        obj = json.loads(_datei(basis).read_text(encoding="utf-8"))
        return Path(obj["datenpfad"])
    except (OSError, ValueError, KeyError, TypeError):
        return standard_datenpfad()


def datenpfad_setzen(pfad: Path, basis: Path | None = None) -> None:
    datei = _datei(basis)
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(json.dumps({"datenpfad": str(pfad)}, ensure_ascii=False, indent=1), encoding="utf-8")
