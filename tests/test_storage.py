import json
from datetime import date

import pytest

from kuerbis.model import Daten, Saison
from kuerbis.storage import DatenFehler, laden, speichern


def beispiel(betrag=10):
    return Daten({2025: Saison(2025, date(2025, 8, 25), {date(2025, 9, 1): betrag})})


def test_fehlende_datei_ergibt_leere_daten(tmp_path):
    assert laden(tmp_path / "gibtsnicht.json") == Daten()


def test_rundlauf(tmp_path):
    pfad = tmp_path / "daten.json"
    speichern(pfad, beispiel())
    assert laden(pfad) == beispiel()


def test_backup_enthaelt_vorherigen_stand(tmp_path):
    pfad = tmp_path / "daten.json"
    speichern(pfad, beispiel(10))
    speichern(pfad, beispiel(20))
    assert laden(pfad) == beispiel(20)
    assert laden(pfad.with_name("daten.json.bak")) == beispiel(10)


def test_kaputte_datei_gibt_fehler_und_bleibt_unveraendert(tmp_path):
    pfad = tmp_path / "daten.json"
    pfad.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(DatenFehler):
        laden(pfad)
    assert pfad.read_text(encoding="utf-8") == "{kaputt"


def test_ordner_wird_angelegt(tmp_path):
    pfad = tmp_path / "neu" / "daten.json"
    speichern(pfad, beispiel())
    assert json.loads(pfad.read_text(encoding="utf-8"))["format"] == "kuerbisverkauf"
