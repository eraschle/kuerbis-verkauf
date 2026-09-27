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
    assert api.neue_saison(2025)["jahr"] == 2025
    res = api.betrag_setzen(2025, "2025-08-26", "12,5")
    assert res["statistik"]["total"] == 12.5
    gespeichert = json.loads((tmp_path / "daten.json").read_text(encoding="utf-8"))
    assert gespeichert["saisons"]["2025"]["eintraege"] == {"2025-08-26": 12.5}
    assert api.status()["jahre"] == [2025]


def test_betrag_loeschen(api):
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-08-26", "10")
    res = api.betrag_setzen(2025, "2025-08-26", "")
    assert res["statistik"]["total"] == 0


def test_ungueltiger_betrag(api):
    api.neue_saison(2025)
    assert "fehler" in api.betrag_setzen(2025, "2025-08-26", "-3")
    assert "fehler" in api.betrag_setzen(2025, "2025-08-26", "abc")


def test_saison_doppelt(api):
    api.neue_saison(2025)
    assert "fehler" in api.neue_saison(2025)


def test_saison_loeschen(api):
    api.neue_saison(2025)
    api.saison_loeschen(2025)
    assert api.status()["jahre"] == []


def test_neue_saison_ist_leer_mit_vorschlag(api):
    res = api.neue_saison(2025)
    assert res["zeilen"] == []
    assert res["naechster_tag"].startswith("2025-")


def test_tabelle_waechst_mit_eintraegen(api):
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-09-05", 45)
    res = api.betrag_setzen(2025, "2025-09-07", 5)
    assert [z["datum"] for z in res["zeilen"]] == ["2025-09-05", "2025-09-06", "2025-09-07"]
    assert res["naechster_tag"] == "2025-09-08"
    res = api.betrag_setzen(2025, "2025-09-07", "")  # letzten Tag entfernen -> Tabelle schrumpft
    assert [z["datum"] for z in res["zeilen"]] == ["2025-09-05"]


def test_datum_ausserhalb_des_jahres(api):
    api.neue_saison(2025)
    assert "fehler" in api.betrag_setzen(2025, "2026-01-02", 5)
    assert "fehler" in api.betrag_setzen(2025, "kein-datum", 5)


def test_vergleich_und_uebersicht(api):
    api.neue_saison(2024)
    api.betrag_setzen(2024, "2024-09-07", 10)  # Samstag KW 36
    api.betrag_setzen(2024, "2024-09-08", 5)
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-09-06", 7)  # Samstag KW 36
    v = api.vergleich()
    assert [j["jahr"] for j in v["jahre"]] == [2024, 2025]
    j24, j25 = v["jahre"]
    assert j24["erster_tag"] == j25["erster_tag"]  # gleicher Wochentag, gleiche Position
    assert j24["kumuliert"] == [10, 15]
    assert j24["erstes_datum"] == "2024-09-07"
    u = api.uebersicht()
    assert u["kws"] == [36]
    assert [z["jahr"] for z in u["zeilen"]] == [2025, 2024]  # neuestes zuerst
    assert u["zeilen"][1]["wochen"] == [15]  # Sa 7. + So 8.9.2024 = KW 36
    assert u["zeilen"][0]["wochen"] == [7]
    assert (u["zeilen"][1]["erster_tag"], u["zeilen"][1]["letzter_tag"]) == ("2024-09-07", "2024-09-08")
    api.betrag_setzen(2025, "2025-09-15", 1)  # KW 38 -> Lücke KW 37 wird aufgefüllt
    u = api.uebersicht()
    assert u["kws"] == [36, 37, 38]
    assert u["zeilen"][0]["wochen"] == [7, 0, 1]
    assert u["zeilen"][1]["wochen"] == [15, None, None]


def test_import_mit_konflikt(api, tmp_path):
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-08-26", 10)
    datei = tmp_path / "fremd.json"
    json_exportieren(datei, Daten({2025: Saison(2025, {date(2025, 8, 26): 12, date(2025, 8, 27): 3})}))
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
    api.neue_saison(2025)
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
    json_exportieren(ziel, Daten({2020: Saison(2020, {date(2020, 9, 1): 5})}))
    res = api.speicherort_oeffnen(str(ziel))
    assert res["jahre"] == [2020]


def test_kaputte_datendatei(tmp_path):
    pfad = tmp_path / "daten.json"
    pfad.write_text("{kaputt", encoding="utf-8")
    a = Api(pfad, einstellungen_basis=tmp_path)
    assert "fehler" in a.status()
    # Schreiben wird verweigert, damit die Datei nicht überschrieben wird
    assert "fehler" in a.neue_saison(2025)
    assert pfad.read_text(encoding="utf-8") == "{kaputt"


def test_export(api, tmp_path):
    api.neue_saison(2025)
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
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-08-26", "10")
    res = api.betrag_setzen(2025, "2025-08-27", "0")
    assert res["statistik"] == {"min": 0, "max": 10, "mittel": 5, "tage": 2, "total": 10}
    res = api.betrag_setzen(2025, "2025-08-27", "")  # leer = Eintrag entfernen
    assert res["statistik"]["tage"] == 1


def test_vergleich_mit_bereich_und_einstellungen(tmp_path):
    a = Api(tmp_path / "daten.json", einstellungen_basis=tmp_path / "einst", heute=date(2026, 9, 27))
    for jahr, betrag in [(2024, 300), (2025, 50), (2026, 999), (2000, 5)]:
        a.neue_saison(jahr)
        a.betrag_setzen(jahr, f"{jahr}-09-05", betrag)
    v = a.vergleich()
    assert v["bereich"] == {"min": 2000, "max": 2024}
    assert v["anzahl_jahre"] == 5
    assert v["ausgenommen"] == []
    assert [j["jahr"] for j in v["abgeschlossen"]] == [2025, 2024, 2000]
    assert v["aktuelles_jahr"] == 2026

    a.vergleich_einstellen(3, [2000])
    v = a.vergleich()
    assert v["bereich"] == {"min": 2025, "max": 2024}
    assert v["anzahl_jahre"] == 3
    assert v["ausgenommen"] == [2000]
    # gemerkt für den nächsten Start
    b = Api(tmp_path / "daten.json", einstellungen_basis=tmp_path / "einst", heute=date(2026, 9, 27))
    assert b.vergleich()["anzahl_jahre"] == 3
    assert b.uebersicht()["bereich"] == {"min": 2025, "max": 2024}


def test_vergleich_einstellen_prueft_werte(api):
    assert "fehler" in api.vergleich_einstellen(0, [])
    assert "fehler" in api.vergleich_einstellen(11, [])
