import copy
from datetime import date

from kuerbis.merge import konflikte_finden, zusammenfuehren
from kuerbis.model import Daten, Saison


def d(**saisons):
    return Daten({int(k[1:]): v for k, v in saisons.items()})


def test_neues_jahr_wird_uebernommen():
    meine = d(j2025=Saison(2025, {date(2025, 9, 1): 10}))
    imp = d(j2024=Saison(2024, {date(2024, 9, 2): 7}))
    assert konflikte_finden(meine, imp) == []
    neu, info = zusammenfuehren(meine, imp, {})
    assert set(neu.saisons) == {2024, 2025}
    assert info["neue_jahre"] == 1
    assert info["neue_tage"] == 1


def test_neuer_tag_und_gleicher_wert():
    meine = d(j2025=Saison(2025, {date(2025, 9, 1): 10}))
    imp = d(j2025=Saison(2025, {date(2025, 9, 1): 10, date(2025, 9, 2): 4}))
    assert konflikte_finden(meine, imp) == []
    neu, info = zusammenfuehren(meine, imp, {})
    assert neu.saisons[2025].eintraege == {date(2025, 9, 1): 10, date(2025, 9, 2): 4}
    assert info["neue_tage"] == 1


def test_nulltag_ist_neuer_eintrag():
    meine = d(j2025=Saison(2025, {date(2025, 9, 1): 10}))
    imp = d(j2025=Saison(2025, {date(2025, 9, 2): 0}))
    neu, info = zusammenfuehren(meine, imp, {})
    assert neu.saisons[2025].eintraege[date(2025, 9, 2)] == 0
    assert info["neue_tage"] == 1


def test_betragskonflikt_mit_wahl():
    meine = d(j2025=Saison(2025, {date(2025, 9, 1): 10, date(2025, 9, 2): 5}))
    imp = d(j2025=Saison(2025, {date(2025, 9, 1): 12, date(2025, 9, 2): 6}))
    konflikte = konflikte_finden(meine, imp)
    assert [(k["datum"], k["mein"], k["import"]) for k in konflikte] == [
        ("2025-09-01", 10, 12),
        ("2025-09-02", 5, 6),
    ]
    wahl = {konflikte[0]["id"]: "import"}  # zweiter fehlt -> mein
    neu, info = zusammenfuehren(meine, imp, wahl)
    assert neu.saisons[2025].eintraege == {date(2025, 9, 1): 12, date(2025, 9, 2): 5}
    assert info["konflikte_import"] == 1
    assert info["konflikte_mein"] == 1


def test_eingaben_bleiben_unveraendert():
    meine = d(j2025=Saison(2025, {date(2025, 9, 1): 10}))
    imp = d(j2025=Saison(2025, {date(2025, 9, 1): 12, date(2025, 9, 3): 1}))
    vorher_m, vorher_i = copy.deepcopy(meine), copy.deepcopy(imp)
    zusammenfuehren(meine, imp, {"betrag:2025-09-01": "import"})
    assert meine == vorher_m
    assert imp == vorher_i
