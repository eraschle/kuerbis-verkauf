"""Datendatei laden und sicher speichern."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .model import Daten, daten_aus_dict, daten_zu_dict


class DatenFehler(Exception):
    pass


def laden(pfad: Path) -> Daten:
    if not pfad.exists():
        return Daten()
    try:
        obj = json.loads(pfad.read_text(encoding="utf-8"))
        return daten_aus_dict(obj)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        raise DatenFehler(f"Die Datendatei {pfad} kann nicht gelesen werden: {e}") from None


def speichern(pfad: Path, d: Daten) -> None:
    """Schreibt zuerst in eine temporäre Datei und ersetzt dann; der alte Stand bleibt als .bak."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_name(pfad.name + ".tmp")
    text = json.dumps(daten_zu_dict(d), ensure_ascii=False, indent=1)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    if pfad.exists():
        shutil.copy2(pfad, pfad.with_name(pfad.name + ".bak"))
    os.replace(tmp, pfad)
