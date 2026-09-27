import json

import pytest

from kuerbis.api import Api
from kuerbis.excel_io import json_exportieren
from kuerbis.model import Daten, Saison
from datetime import date


@pytest.fixture
def api(tmp_path):
    return Api(tmp_path / "daten.json", einstellungen_basis=tmp_path / "einst")


def test_status_leer(api, tmp_path):
    st = api.status()
    assert st["jahre"] == []
    assert st["datenpfad"] == str(tmp_path / "daten.json")


def test_neue_saison_und_betrag(api, tmp_path):
    assert api.neue_saison(2025, "2025-08-25")["jahr"] == 2025
    res = api.betrag_setzen(2025, "2025-08-26", "12,5")
    assert res["statistik"]["total"] == 12.5
    gespeichert = json.loads((tmp_path / "daten.json").read_text(encoding="utf-8"))
    assert gespeichert["saisons"]["2025"]["eintraege"] == {"2025-08-26": 12.5}
    assert api.status()["jahre"] == [2025]


def test_betrag_loeschen(api):
    api.neue_saison(2025, "2025-08-25")
    api.betrag_setzen(2025, "2025-08-26", "10")
    res = api.betrag_setzen(2025, "2025-08-26", "")
    assert res["statistik"]["total"] == 0


def test_ungueltiger_betrag(api):
    api.neue_saison(2025, "2025-08-25")
    assert "fehler" in api.betrag_setzen(2025, "2025-08-26", "-3")
    assert "fehler" in api.betrag_setzen(2025, "2025-08-26", "abc")


def test_saison_doppelt(api):
    api.neue_saison(2025, "2025-08-25")
    assert "fehler" in api.neue_saison(2025, "2025-08-25")


def test_start_aendern_und_loeschen(api):
    api.neue_saison(2025, "2025-08-25")
    assert api.start_aendern(2025, "2025-09-01")["start"] == "2025-09-01"
    api.saison_loeschen(2025)
    assert api.status()["jahre"] == []


def test_vergleich_und_uebersicht(api):
    api.neue_saison(2024, "2024-08-26")
    api.betrag_setzen(2024, "2024-08-27", 10)
    api.neue_saison(2025, "2025-08-25")
    v = api.vergleich()
    assert [j["jahr"] for j in v["jahre"]] == [2024, 2025]
    assert v["jahre"][0]["kumuliert"] == [0, 10]
    u = api.uebersicht()
    assert u["max_wochen"] == 16
    assert [z["jahr"] for z in u["zeilen"]] == [2025, 2024]  # neuestes zuerst
    assert u["zeilen"][1]["wochen"][0] == 10


def test_import_mit_konflikt(api, tmp_path):
    api.neue_saison(2025, "2025-08-25")
    api.betrag_setzen(2025, "2025-08-26", 10)
    datei = tmp_path / "fremd.json"
    json_exportieren(datei, Daten({2025: Saison(2025, date(2025, 8, 25), {date(2025, 8, 26): 12, date(2025, 8, 27): 3})}))
    vor = api.import_vorbereiten(str(datei))
    assert len(vor["konflikte"]) == 1
    assert vor["neue_tage"] == 1
    info = api.import_abschliessen({vor["konflikte"][0]["id"]: "import"})
    assert info["konflikte_import"] == 1
    assert api.saison(2025)["statistik"]["total"] == 15


def test_import_fehler(api, tmp_path):
    datei = tmp_path / "x.txt"
    datei.write_text("x", encoding="utf-8")
    assert "fehler" in api.import_vorbereiten(str(datei))


def test_import_abschliessen_ohne_vorbereitung(api):
    assert "fehler" in api.import_abschliessen({})


def test_speicherort_verschieben(api, tmp_path):
    api.neue_saison(2025, "2025-08-25")
    ziel = tmp_path / "anders" / "k.json"
    assert api.speicherort_verschieben(str(ziel), False)["datenpfad"] == str(ziel)
    assert ziel.exists()
    # Einstellung gemerkt
    neu = Api.aus_einstellungen(tmp_path / "einst")
    assert neu.status()["datenpfad"] == str(ziel)


def test_speicherort_verschieben_ziel_existiert(api, tmp_path):
    ziel = tmp_path / "vorhanden.json"
    json_exportieren(ziel, Daten())
    assert api.speicherort_verschieben(str(ziel), False) == {"existiert": True}
    assert api.speicherort_verschieben(str(ziel), True)["datenpfad"] == str(ziel)


def test_speicherort_oeffnen(api, tmp_path):
    ziel = tmp_path / "andere.json"
    json_exportieren(ziel, Daten({2020: Saison(2020, date(2020, 8, 31), {date(2020, 9, 1): 5})}))
    res = api.speicherort_oeffnen(str(ziel))
    assert res["jahre"] == [2020]


def test_kaputte_datendatei(tmp_path):
    pfad = tmp_path / "daten.json"
    pfad.write_text("{kaputt", encoding="utf-8")
    a = Api(pfad, einstellungen_basis=tmp_path)
    assert "fehler" in a.status()
    # Schreiben wird verweigert, damit die Datei nicht überschrieben wird
    assert "fehler" in a.neue_saison(2025, "2025-08-25")
    assert pfad.read_text(encoding="utf-8") == "{kaputt"


def test_export(api, tmp_path):
    api.neue_saison(2025, "2025-08-25")
    assert api.export_nach(str(tmp_path / "e.xlsx"), "excel") == {"ok": True}
    assert api.export_nach(str(tmp_path / "e.json"), "json") == {"ok": True}
    assert (tmp_path / "e.xlsx").exists()


def test_dateifilter_sind_fuer_pywebview_gueltig():
    from webview.util import parse_file_type

    from kuerbis.api import DATEIFILTER

    for filter_liste in DATEIFILTER.values():
        for f in filter_liste:
            parse_file_type(f)  # wirft ValueError bei ungültigem Filter


def test_null_betrag_zaehlt_als_verkaufstag(api):
    api.neue_saison(2025, "2025-08-25")
    api.betrag_setzen(2025, "2025-08-26", "10")
    res = api.betrag_setzen(2025, "2025-08-27", "0")
    assert res["statistik"] == {"min": 0, "max": 10, "mittel": 5, "tage": 2, "total": 10}
    res = api.betrag_setzen(2025, "2025-08-27", "")  # leer = Eintrag entfernen
    assert res["statistik"]["tage"] == 1
