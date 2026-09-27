from datetime import date, timedelta

import pytest

from kuerbis.model import (
    Daten,
    Saison,
    anzahl_wochen,
    betrag_normalisieren,
    daten_aus_dict,
    daten_zu_dict,
    kumuliert_pro_tag,
    statistik,
    tageszeilen,
    vorgeschlagener_start,
    wochentotale,
)

START = date(2025, 8, 25)  # Montag


def saison(**tage):
    """tage: Offset in Tagen -> Betrag, z. B. saison(d0=10, d7=5)."""
    return Saison(2025, START, {START + timedelta(int(k[1:])): v for k, v in tage.items()})


def test_woche_1_umfasst_die_ersten_7_tage():
    zeilen = tageszeilen(saison())
    assert zeilen[0]["woche"] == 1
    assert zeilen[6]["woche"] == 1
    assert zeilen[7]["woche"] == 2
    assert zeilen[0]["wochentag"] == "Montag"
    assert zeilen[0]["datum"] == "2025-08-25"


def test_saison_hat_mindestens_16_wochen():
    s = saison()
    assert anzahl_wochen(s) == 16
    assert len(tageszeilen(s)) == 16 * 7


def test_saison_waechst_mit_spaeten_eintraegen():
    s = saison(d120=5)  # Tag 121 -> Woche 18
    assert anzahl_wochen(s) == 18


def test_laufendes_total_nur_an_tagen_mit_betrag():
    zeilen = tageszeilen(saison(d0=10, d2=5))
    assert zeilen[0]["laufend"] == 10
    assert zeilen[1]["laufend"] is None
    assert zeilen[1]["betrag"] is None
    assert zeilen[2]["laufend"] == 15


def test_wochentotal_am_letzten_tag_der_woche():
    zeilen = tageszeilen(saison(d0=10, d6=5, d7=3))
    assert zeilen[6]["wochentotal"] == 15
    assert zeilen[5]["wochentotal"] is None
    assert zeilen[13]["wochentotal"] == 3
    assert zeilen[20]["wochentotal"] is None  # Woche 3 ohne Umsatz


def test_wochentotale_liste():
    w = wochentotale(saison(d0=10, d6=5, d7=3))
    assert w[:3] == [15, 3, 0]
    assert len(w) == 16


def test_statistik():
    st = statistik(saison(d0=10, d1=20, d5=30))
    assert st == {"min": 10, "max": 30, "mittel": 20, "tage": 3, "total": 60}


def test_statistik_leer():
    assert statistik(saison()) == {"min": None, "max": None, "mittel": None, "tage": 0, "total": 0}


def test_kumuliert_pro_tag():
    assert kumuliert_pro_tag(saison(d0=10, d2=5)) == [10, 10, 15]
    assert kumuliert_pro_tag(saison()) == []


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
    d = Daten({2025: saison(d0=10, d3=12.5)})
    obj = daten_zu_dict(d)
    assert obj["format"] == "kuerbisverkauf"
    assert obj["saisons"]["2025"]["start"] == "2025-08-25"
    assert obj["saisons"]["2025"]["eintraege"]["2025-08-28"] == 12.5
    assert daten_aus_dict(obj) == d


def test_daten_aus_dict_falsches_format():
    with pytest.raises(ValueError):
        daten_aus_dict({"irgendwas": 1})


def test_vorgeschlagener_start_letzter_montag_im_august():
    assert vorgeschlagener_start(2025) == date(2025, 8, 25)
    assert vorgeschlagener_start(2026) == date(2026, 8, 31)


def test_null_ist_ein_verkaufstag():
    s = saison(d0=10, d1=0, d7=0)
    st = statistik(s)
    assert st == {"min": 0, "max": 10, "mittel": 3.33, "tage": 3, "total": 10}
    zeilen = tageszeilen(s)
    assert zeilen[1]["betrag"] == 0
    assert zeilen[1]["laufend"] == 10
    assert zeilen[13]["wochentotal"] == 0  # Woche nur mit 0-Tag zeigt 0
    assert zeilen[20]["wochentotal"] is None  # Woche ohne Eintrag bleibt leer
    assert anzahl_wochen(s) == 16


def test_null_bleibt_im_rundlauf():
    d = Daten({2025: saison(d1=0)})
    assert daten_aus_dict(daten_zu_dict(d)) == d
