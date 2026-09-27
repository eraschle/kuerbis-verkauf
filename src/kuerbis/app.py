"""Programmstart: öffnet das Fenster mit der Oberfläche."""

from __future__ import annotations

import sys
from pathlib import Path

import webview

from kuerbis.api import Api


def web_ordner() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "kuerbis" / "web"
    return Path(__file__).resolve().parent / "web"


def main() -> None:
    api = Api.aus_einstellungen()
    fenster = webview.create_window(
        "Kürbisverkauf",
        str(web_ordner() / "index.html"),
        js_api=api,
        width=1280,
        height=860,
        min_size=(980, 640),
        text_select=True,
    )
    api.fenster_setzen(fenster)
    # Die .exe liefert ihr Symbol selbst; im Entwicklungsmodus aus der .ico-Datei
    webview.start(icon=str(web_ordner() / "kuerbis.ico"))


if __name__ == "__main__":
    main()
