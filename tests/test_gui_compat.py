from prosper_or_perish_constructor import gui_compat


def _mod(tmp_path):
    gui = tmp_path / "in_game/gui"
    gui.mkdir(parents=True)
    (gui / "location_window.gui").write_text(
        "types T {\n\ttype location_card = hbox {\n\t\ttext = \"pop/cap\" # { brace in a comment\n\t}\n}\n"
        "window = {\n\tlocation_card = {\n\t}\n}\n")
    (gui / "location_production_lateralview.gui").write_text("w = {\n\t\tlocation_card = {}\n}\n")
    (gui / "food_production_lateralview.gui").write_text(
        "types F {\n\ttype food_production_province = widget {\n\t}\n}\nw = {\n\tfood_production_province = {}\n}\n")
    return gui


def test_mod_windows_use_protected_copies_and_protect_is_idempotent(tmp_path):
    gui = _mod(tmp_path)
    assert gui_compat.protect(tmp_path) == {"location_card": 2, "food_production_province": 1}
    first = {p.name: p.read_text(encoding="utf-8-sig") for p in gui.iterdir()}
    window = first["location_window.gui"]
    assert "type location_card = hbox" in window and "type pp_location_card = hbox" in window
    assert "\tpp_location_card = {" in window and "\tlocation_card = {\n" not in window.split("window = {")[1]
    assert "pp_location_card = {}" in first["location_production_lateralview.gui"]
    gui_compat.protect(tmp_path)
    assert {p.name: p.read_text(encoding="utf-8-sig") for p in gui.iterdir()} == first
    gui_compat.strip(tmp_path)
    assert "pp_" not in (gui / "location_window.gui").read_text(encoding="utf-8-sig")
