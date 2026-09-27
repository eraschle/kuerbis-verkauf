from datetime import date

import pytest

from kuerbis.model import (
    Daten,
    Saison,
    achsentag,
    betrag_normalisieren,
    daten_aus_dict,
    daten_zu_dict,
    kw,
    naechster_tag,
    statistik,
    tageszeilen,
    vergleichsreihe,
    vorgeschlagener_start,
    wochentotale,
)


def saison(**tage):
    """tage: 'mmdd' -> Betrag, z. B. saison(m0905=45) für den 5. September 2025."""
    return Saison(2025, {date(2025, int(k[1:3]), int(k[3:5])): v for k, v in tage.items()})


def test_kw_ist_iso_kalenderwoche():
    assert kw(2025, date(2025, 9, 1)) == 36  # Montag
    assert kw(2025, date(2025, 9, 7)) == 36  # Sonntag
    assert kw(2025, date(2025, 9, 8)) == 37


def test_kw_zaehlt_ende_dezember_weiter():
    # 29.12.2025 gehört nach ISO zu KW 1/2026 – in der Saison 2025 zählt sie als KW 53
    assert kw(2025, date(2025, 12, 29)) == 53


def test_achsentag_gleicher_wochentag_gleiche_position():
    samstag_kw37_2025 = date(2025, 9, 13)
    samstag_kw37_2024 = date(2024, 9, 14)
    assert achsentag(2025, samstag_kw37_2025) == achsentag(2024, samstag_kw37_2024) == 36 * 7 + 5


def test_leere_saison_hat_keine_zeilen():
    assert tageszeilen(saison()) == []
    assert wochentotale(saison()) == {}


def test_zeilen_nur_vom_ersten_bis_letzten_tag():
    zeilen = tageszeilen(saison(m0905=45, m0908=10))  # Freitag bis Montag
    assert [z["datum"] for z in zeilen] == ["2025-09-05", "2025-09-06", "2025-09-07", "2025-09-08"]
    assert [z["betrag"] for z in zeilen] == [45, None, None, 10]
    assert zeilen[0]["wochentag"] == "Freitag"
    assert [z["kw"] for z in zeilen] == [36, 36, 36, 37]


def test_wochenstart_am_montag_und_in_erster_zeile():
    zeilen = tageszeilen(saison(m0905=45, m0908=10))
    assert [z["wochenstart"] for z in zeilen] == [True, False, False, True]


def test_laufendes_total_nur_an_tagen_mit_eintrag():
    zeilen = tageszeilen(saison(m0905=45, m0907=5))
    assert [z["laufend"] for z in zeilen] == [45, None, 50]


def test_wochentotal_am_sonntag_und_am_letzten_tag():
    zeilen = tageszeilen(saison(m0905=45, m0907=5, m0909=3))
    wt = [z["wochentotal"] for z in zeilen]
    # Fr 5., Sa 6., So 7. | Mo 8., Di 9. (letzter Tag, Woche noch offen)
    assert wt == [None, None, 50, None, 3]


def test_woche_ohne_eintrag_zeigt_kein_wochentotal():
    zeilen = tageszeilen(saison(m0905=1, m0915=2))
    sonntag_14 = next(z for z in zeilen if z["datum"] == "2025-09-14")
    assert sonntag_14["wochentotal"] is None


def test_wochentotale_pro_kw():
    assert wochentotale(saison(m0905=45, m0907=5, m0909=3, m0922=1)) == {36: 50, 37: 3, 38: 0, 39: 1}


def test_statistik():
    st = statistik(saison(m0901=10, m0902=20, m0906=30))
    assert st == {"min": 10, "max": 30, "mittel": 20, "tage": 3, "total": 60}


def test_statistik_leer():
    assert statistik(saison()) == {"min": None, "max": None, "mittel": None, "tage": 0, "total": 0}


def test_null_ist_ein_verkaufstag():
    s = saison(m0901=10, m0902=0, m0908=0)
    assert statistik(s) == {"min": 0, "max": 10, "mittel": 3.33, "tage": 3, "total": 10}
    zeilen = tageszeilen(s)
    assert zeilen[1]["betrag"] == 0
    assert zeilen[1]["laufend"] == 10
    assert zeilen[-1]["wochentotal"] == 0  # Woche nur mit 0-Tag zeigt 0
    assert zeilen[6]["wochentotal"] == 10


def test_vergleichsreihe():
    r = vergleichsreihe(saison(m0905=45, m0907=5))
    assert r == {"erster_tag": achsentag(2025, date(2025, 9, 5)), "erstes_datum": "2025-09-05", "kumuliert": [45, 45, 50]}
    assert vergleichsreihe(saison()) == {"erster_tag": None, "erstes_datum": None, "kumuliert": []}


def test_naechster_tag():
    assert naechster_tag(saison(m0905=45), heute=date(2026, 1, 1)) == date(2025, 9, 6)
    assert naechster_tag(saison(), heute=date(2025, 9, 20)) == date(2025, 9, 20)  # heute im Saisonjahr
    assert naechster_tag(saison(), heute=date(2026, 3, 1)) == vorgeschlagener_start(2025)


def test_naechster_tag_bleibt_im_jahr():
    assert naechster_tag(saison(m1231=1), heute=date(2026, 1, 5)) == date(2025, 12, 31)


@pytest.mark.parametrize(
    "eingabe, erwartet",
    [("12,5", 12.5), ("12.50", 12.5), ("40", 40), (40.0, 40), (7, 7), ("", None), (None, None), ("0", 0), (0, 0), (" ", None)],
)
def test_betrag_normalisieren(eingabe, erwartet):
    ergebnis = betrag_normalisieren(eingabe)
    assert ergebnis == erwartet
    if isinstance(erwartet, int):
        assert isinstance(ergebnis, int)


@pytest.mark.parametrize("eingabe", ["-1", "abc", -3])
def test_betrag_normalisieren_ungueltig(eingabe):
    with pytest.raises(ValueError):
        betrag_normalisieren(eingabe)


def test_rundlauf_dict():
    d = Daten({2025: saison(m0901=10, m0904=12.5, m0905=0), 2026: Saison(2026, {})})
    obj = daten_zu_dict(d)
    assert obj["format"] == "kuerbisverkauf"
    assert obj["version"] == 2
    assert "start" not in obj["saisons"]["2025"]
    assert obj["saisons"]["2025"]["eintraege"]["2025-09-04"] == 12.5
    assert daten_aus_dict(obj) == d


def test_version_1_mit_startdatum_wird_gelesen():
    obj = {
        "format": "kuerbisverkauf",
        "version": 1,
        "saisons": {"2025": {"start": "2025-08-25", "eintraege": {"2025-09-01": 10}}},
    }
    assert daten_aus_dict(obj) == Daten({2025: saison(m0901=10)})


def test_daten_aus_dict_falsches_format():
    with pytest.raises(ValueError):
        daten_aus_dict({"irgendwas": 1})


def test_vorgeschlagener_start_letzter_montag_im_august():
    assert vorgeschlagener_start(2025) == date(2025, 8, 25)
    assert vorgeschlagener_start(2026) == date(2026, 8, 31)


def test_min_max_jahre_nur_abgeschlossene():
    from kuerbis.model import min_max_jahre

    d = Daten(
        {
            2023: Saison(2023, {date(2023, 9, 1): 100}),
            2024: Saison(2024, {date(2024, 9, 1): 300}),
            2025: Saison(2025, {date(2025, 9, 1): 50}),
            2026: Saison(2026, {date(2026, 9, 1): 999}),  # laufendes Jahr zählt nicht
            2022: Saison(2022, {}),  # ohne Einträge zählt nicht
        }
    )
    assert min_max_jahre(d, aktuelles_jahr=2026) == {"min": 2025, "max": 2024}
    assert min_max_jahre(d, aktuelles_jahr=2026, ausgenommen=[2025]) == {"min": 2023, "max": 2024}
    assert min_max_jahre(d, aktuelles_jahr=2023) == {"min": None, "max": None}
