from datetime import datetime, timedelta

import pytest

from kuerbis.sperre import Sperre, sperrpfad

T0 = datetime(2026, 9, 27, 14, 0)


class Uhr:
    def __init__(self):
        self.jetzt = T0

    def __call__(self):
        return self.jetzt


@pytest.fixture
def uhr():
    return Uhr()


def sperre(tmp_path, uhr, nr):
    return Sperre(tmp_path / "daten.json", kennung=f"id{nr}", benutzer=f"person{nr}", pc=f"PC{nr}", uhr=uhr)


def test_sperrpfad(tmp_path):
    assert sperrpfad(tmp_path / "daten.json") == tmp_path / "daten.json.lock"


def test_erwerben_wenn_frei(tmp_path, uhr):
    a = sperre(tmp_path, uhr, 1)
    assert a.zustand() == "frei"
    assert a.erwerben() is True
    assert a.zustand() == "eigen"
    info = a.lesen()
    assert (info["benutzer"], info["pc"], info["seit"]) == ("person1", "PC1", T0.isoformat(timespec="seconds"))


def test_fremde_sperre_verhindert_erwerben(tmp_path, uhr):
    a, b = sperre(tmp_path, uhr, 1), sperre(tmp_path, uhr, 2)
    a.erwerben()
    assert b.zustand() == "fremd"
    assert b.erwerben() is False
    assert b.lesen()["benutzer"] == "person1"


def test_veraltete_sperre_nach_10_minuten(tmp_path, uhr):
    a, b = sperre(tmp_path, uhr, 1), sperre(tmp_path, uhr, 2)
    a.erwerben()
    uhr.jetzt = T0 + timedelta(minutes=9, seconds=59)
    assert b.zustand() == "fremd"
    uhr.jetzt = T0 + timedelta(minutes=10, seconds=1)
    assert b.zustand() == "veraltet"
    assert b.erwerben() is False  # veraltet wird nur ausdrücklich übernommen
    assert b.erwerben(erzwingen=True) is True
    assert b.zustand() == "eigen"


def test_auffrischen_haelt_sperre_frisch(tmp_path, uhr):
    a, b = sperre(tmp_path, uhr, 1), sperre(tmp_path, uhr, 2)
    a.erwerben()
    uhr.jetzt = T0 + timedelta(minutes=8)
    assert a.auffrischen() is True
    uhr.jetzt = T0 + timedelta(minutes=16)
    assert b.zustand() == "fremd"
    assert a.lesen()["seit"] == T0.isoformat(timespec="seconds")


def test_auffrischen_merkt_uebernahme(tmp_path, uhr):
    a, b = sperre(tmp_path, uhr, 1), sperre(tmp_path, uhr, 2)
    a.erwerben()
    b.erwerben(erzwingen=True)
    assert a.auffrischen() is False
    assert a.zustand() == "fremd"
    assert b.lesen()["benutzer"] == "person2"


def test_freigeben_loescht_nur_eigene_sperre(tmp_path, uhr):
    a, b = sperre(tmp_path, uhr, 1), sperre(tmp_path, uhr, 2)
    a.erwerben()
    b.freigeben()
    assert sperrpfad(tmp_path / "daten.json").exists()
    a.freigeben()
    assert not sperrpfad(tmp_path / "daten.json").exists()


def test_kaputte_sperrdatei_gilt_als_veraltet(tmp_path, uhr):
    sperrpfad(tmp_path / "daten.json").write_text("{kaputt", encoding="utf-8")
    a = sperre(tmp_path, uhr, 1)
    assert a.zustand() == "veraltet"
    assert a.erwerben(erzwingen=True) is True


def test_gleiche_kennung_ist_eigen(tmp_path, uhr):
    a = sperre(tmp_path, uhr, 1)
    a.erwerben()
    wieder = sperre(tmp_path, uhr, 1)  # z. B. nach Neustart des Fensters im selben Prozess
    assert wieder.zustand() == "eigen"
