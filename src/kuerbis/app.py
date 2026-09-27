"""Programmstart: öffnet das Fenster mit der Oberfläche."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import webview

from kuerbis.api import Api

SPERRE_TAKT_SEKUNDEN = 60


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

    def beim_schliessen():
        # Läuft im GUI-Thread: kein evaluate_js hier (würde blockieren) – die Rückfrage übernimmt die Oberfläche.
        if api.darf_schliessen():
            api.beenden(fenster_schliessen=False)  # schliesst ohnehin gerade
            return True
        threading.Thread(target=lambda: fenster.evaluate_js("schliessenAnfragen()"), daemon=True).start()
        return False  # Schliessen abbrechen, bis die Rückfrage beantwortet ist

    fenster.events.closing += beim_schliessen

    # Sperre regelmässig auffrischen, auch wenn die Oberfläche (z. B. minimiert) gedrosselt läuft
    stopp = threading.Event()

    def takt():
        while not stopp.wait(SPERRE_TAKT_SEKUNDEN):
            api.sperre_auffrischen()

    threading.Thread(target=takt, daemon=True).start()
    try:
        # Die .exe liefert ihr Symbol selbst; im Entwicklungsmodus aus der .ico-Datei
        webview.start(icon=str(web_ordner() / "kuerbis.ico"))
    finally:
        stopp.set()
        api.beenden(fenster_schliessen=False)  # Sperre sicher freigeben


if __name__ == "__main__":
    main()
