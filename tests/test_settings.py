from kuerbis.settings import datenpfad_lesen, datenpfad_setzen, standard_datenpfad


def test_ohne_einstellung_standardpfad(tmp_path):
    assert datenpfad_lesen(tmp_path) == standard_datenpfad()


def test_rundlauf(tmp_path):
    ziel = tmp_path / "irgendwo" / "meine-daten.json"
    datenpfad_setzen(ziel, tmp_path)
    assert datenpfad_lesen(tmp_path) == ziel


def test_kaputte_einstellung_ergibt_standard(tmp_path):
    (tmp_path / "einstellungen.json").write_text("xx", encoding="utf-8")
    assert datenpfad_lesen(tmp_path) == standard_datenpfad()


def test_standardpfad_name():
    assert standard_datenpfad().name == "kuerbis-daten.json"
