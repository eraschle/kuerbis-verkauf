"""Sperrdatei neben der Datendatei: verhindert, dass zwei Personen gleichzeitig bearbeiten.

Die Sperre ist ein kleines JSON (Benutzer, PC, seit, zuletzt aufgefrischt). Wer sie hält, frischt sie
regelmässig auf. Wird sie länger als VERALTET_NACH nicht aufgefrischt (z. B. nach einem Absturz), gilt sie
als veraltet und darf ausdrücklich übernommen werden.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import uuid
from datetime import datetime, timedelta
from pathlib import Path

VERALTET_NACH = timedelta(minutes=10)


def sperrpfad(datenpfad: Path) -> Path:
    return datenpfad.with_name(datenpfad.name + ".lock")


class Sperre:
    def __init__(self, datenpfad: Path, kennung=None, benutzer=None, pc=None, uhr=datetime.now):
        self.pfad = sperrpfad(Path(datenpfad))
        self.kennung = kennung or uuid.uuid4().hex
        self.benutzer = benutzer or _benutzer()
        self.pc = pc or platform.node() or "unbekannt"
        self._uhr = uhr

    def _jetzt(self) -> str:
        return self._uhr().isoformat(timespec="seconds")

    def lesen(self) -> dict | None:
        """Inhalt der Sperrdatei; {} wenn sie unlesbar ist, None wenn es keine gibt."""
        try:
            obj = json.loads(self.pfad.read_text(encoding="utf-8-sig"))
            return obj if isinstance(obj, dict) else {}
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return {}

    def zustand(self) -> str:
        """'frei', 'eigen', 'fremd' oder 'veraltet'."""
        info = self.lesen()
        if info is None:
            return "frei"
        if info.get("kennung") == self.kennung:
            return "eigen"
        try:
            zuletzt = datetime.fromisoformat(info["aktualisiert"])
        except (KeyError, TypeError, ValueError):
            return "veraltet"
        return "veraltet" if self._uhr() - zuletzt > VERALTET_NACH else "fremd"

    def erwerben(self, erzwingen: bool = False) -> bool:
        zustand = self.zustand()
        if zustand == "eigen":
            return self.auffrischen()
        if zustand == "frei" or erzwingen:
            jetzt = self._jetzt()
            self._schreiben({"kennung": self.kennung, "benutzer": self.benutzer, "pc": self.pc, "seit": jetzt, "aktualisiert": jetzt})
            return self.zustand() == "eigen"
        return False

    def auffrischen(self) -> bool:
        """Aktualisiert die eigene Sperre. False, wenn sie inzwischen jemand anders übernommen hat."""
        info = self.lesen()
        if not info or info.get("kennung") != self.kennung:
            return False
        info["aktualisiert"] = self._jetzt()
        self._schreiben(info)
        return True

    def freigeben(self) -> None:
        if self.zustand() == "eigen":
            try:
                self.pfad.unlink()
            except OSError:
                pass

    def _schreiben(self, info: dict) -> None:
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.pfad.with_name(self.pfad.name + ".tmp")
        tmp.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.pfad)


def _benutzer() -> str:
    try:
        return getpass.getuser()
    except Exception:  # getpass kann je nach Umgebung verschiedene Fehler werfen
        return "unbekannt"
