"""Sicheres Speichern: fremde Änderungen nicht überschreiben, Sperre / Nur-Ansicht, offene Eingaben."""

from datetime import date

import pytest

from kuerbis import storage
from kuerbis.api import Api
from kuerbis.sperre import sperrpfad


@pytest.fixture
def api(tmp_path):
    return Api(tmp_path / "daten.json", einstellungen_basis=tmp_path / "einst")


def zweite_instanz(tmp_path):
    return Api(tmp_path / "daten.json", einstellungen_basis=tmp_path / "einst2")


def fremd_aendern(pfad, jahr, datum, betrag):
    """Simuliert eine Änderung durch jemand anders (z. B. über OneDrive synchronisiert)."""
    d = storage.laden(pfad)
    if betrag is None:
        d.saisons[jahr].eintraege.pop(date.fromisoformat(datum), None)
    else:
        d.saisons[jahr].eintraege[date.fromisoformat(datum)] = betrag
    storage.speichern(pfad, d)


# ---- Massnahme 1: fremde Änderungen nicht überschreiben ----


def test_fremde_aenderung_bleibt_erhalten(api, tmp_path):
    pfad = tmp_path / "daten.json"
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-09-05", "10")
    fremd_aendern(pfad, 2025, "2025-09-06", 5)
    res = api.betrag_setzen(2025, "2025-09-07", "7", "")
    assert res["extern_geaendert"] is True
    gespeichert = storage.laden(pfad).saisons[2025].eintraege
    assert gespeichert == {date(2025, 9, 5): 10, date(2025, 9, 6): 5, date(2025, 9, 7): 7}


def test_konflikt_wenn_derselbe_tag_fremd_geaendert_wurde(api, tmp_path):
    pfad = tmp_path / "daten.json"
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-09-05", "10")
    fremd_aendern(pfad, 2025, "2025-09-05", 12)
    res = api.betrag_setzen(2025, "2025-09-05", "15", "10")
    assert res["konflikt"] == {"datum": "2025-09-05", "erwartet": 10, "aktuell": 12, "neu": 15}
    assert storage.laden(pfad).saisons[2025].eintraege[date(2025, 9, 5)] == 12  # nichts überschrieben
    # Bestätigt: mit dem aktuellen Wert als Erwartung wird gespeichert
    res = api.betrag_setzen(2025, "2025-09-05", "15", "12")
    assert "konflikt" not in res
    assert storage.laden(pfad).saisons[2025].eintraege[date(2025, 9, 5)] == 15


def test_konflikt_auch_beim_neuen_tag(api, tmp_path):
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-09-05", "10")
    fremd_aendern(tmp_path / "daten.json", 2025, "2025-09-06", 3)
    res = api.betrag_setzen(2025, "2025-09-06", "4", "")  # Zeile "Neu": erwartet leer
    assert res["konflikt"]["aktuell"] == 3


def test_gleicher_wert_ist_kein_konflikt(api, tmp_path):
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-09-05", "10")
    fremd_aendern(tmp_path / "daten.json", 2025, "2025-09-05", 15)
    assert "konflikt" not in api.betrag_setzen(2025, "2025-09-05", "15", "10")


def test_pruefen_erkennt_fremde_aenderung(api, tmp_path):
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-09-05", "10")
    assert api.pruefen()["geaendert"] is False
    fremd_aendern(tmp_path / "daten.json", 2025, "2025-09-06", 5)
    assert api.pruefen()["geaendert"] is True
    assert api.saison(2025)["statistik"]["total"] == 15
    assert api.pruefen()["geaendert"] is False


def test_verschwundene_datei_wird_nicht_als_leer_behandelt(api, tmp_path):
    api.neue_saison(2025)
    api.betrag_setzen(2025, "2025-09-05", "10")
    (tmp_path / "daten.json").unlink()
    assert "fehler" in api.betrag_setzen(2025, "2025-09-06", "5", "")
    assert not (tmp_path / "daten.json").exists()


# ---- Massnahme 2: Sperre / nur Ansicht ----


def test_zweite_instanz_ist_nur_ansicht(api, tmp_path):
    api.neue_saison(2025)
    assert api.status()["nur_ansicht"] is False
    zweite = zweite_instanz(tmp_path)
    st = zweite.status()
    assert st["nur_ansicht"] is True
    assert st["sperre"]["pc"]
    assert st["sperre_veraltet"] is False
    assert "fehler" in zweite.betrag_setzen(2025, "2025-09-05", "10", "")
    assert "fehler" in zweite.neue_saison(2026)
    assert zweite.saison(2025)["jahr"] == 2025  # Ansehen geht weiterhin


def test_sperre_uebernehmen_und_verlieren(api, tmp_path):
    api.neue_saison(2025)
    zweite = zweite_instanz(tmp_path)
    assert zweite.sperre_uebernehmen()["nur_ansicht"] is False
    assert "konflikt" not in zweite.betrag_setzen(2025, "2025-09-05", "10", "")
    # Die erste Instanz merkt beim nächsten Prüfen, dass sie die Sperre verloren hat
    assert api.pruefen()["nur_ansicht"] is True
    assert "fehler" in api.betrag_setzen(2025, "2025-09-06", "1", "")


def test_freie_sperre_wird_beim_pruefen_uebernommen(api, tmp_path):
    zweite = zweite_instanz(tmp_path)
    assert zweite.status()["nur_ansicht"] is True
    api.beenden()  # gibt die Sperre frei
    assert zweite.pruefen()["nur_ansicht"] is False


def test_beenden_gibt_sperre_frei(api, tmp_path):
    assert sperrpfad(tmp_path / "daten.json").exists()
    api.beenden()
    assert not sperrpfad(tmp_path / "daten.json").exists()


def test_speicherort_wechsel_nimmt_sperre_mit(api, tmp_path):
    api.neue_saison(2025)
    ziel = tmp_path / "anders" / "k.json"
    api.speicherort_verschieben(str(ziel), False)
    assert not sperrpfad(tmp_path / "daten.json").exists()
    assert sperrpfad(ziel).exists()


def test_speicherort_verschieben_auf_fremd_gesperrte_datei(api, tmp_path):
    ziel = tmp_path / "geteilt.json"
    fremd = Api(ziel, einstellungen_basis=tmp_path / "einst3")  # hält die Sperre am Ziel
    fremd.neue_saison(2020)
    assert "fehler" in api.speicherort_verschieben(str(ziel), True)
    assert 2020 in storage.laden(ziel).saisons  # nicht überschrieben


# ---- Ungespeicherte Eingaben beim Schliessen ----


def test_offene_eingaben_verhindern_schliessen(api):
    assert api.darf_schliessen() is True
    api.offen_melden(2)
    assert api.darf_schliessen() is False
    api.offen_melden(0)
    assert api.darf_schliessen() is True


def test_beenden_erlaubt_schliessen_trotz_offener_eingaben(api):
    api.offen_melden(1)
    api.beenden()
    assert api.darf_schliessen() is True
