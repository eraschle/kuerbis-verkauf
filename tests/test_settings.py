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


def test_einstellung_rundlauf_und_standard(tmp_path):
    from kuerbis.settings import einstellung_lesen, einstellung_setzen

    assert einstellung_lesen("vergleich_jahre", 5, tmp_path) == 5
    einstellung_setzen("vergleich_jahre", 8, tmp_path)
    assert einstellung_lesen("vergleich_jahre", 5, tmp_path) == 8


def test_einstellungen_bleiben_gegenseitig_erhalten(tmp_path):
    from kuerbis.settings import einstellung_lesen, einstellung_setzen

    einstellung_setzen("bereich_ausgenommen", [2000], tmp_path)
    datenpfad_setzen(tmp_path / "d.json", tmp_path)
    einstellung_setzen("vergleich_jahre", 3, tmp_path)
    assert einstellung_lesen("bereich_ausgenommen", [], tmp_path) == [2000]
    assert datenpfad_lesen(tmp_path) == tmp_path / "d.json"
