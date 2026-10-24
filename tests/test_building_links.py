"""Every building a player-facing text names is a link (Jan, 2026-10-24): hovering the name shows the building.

A building in localization is ``[ShowBuildingTypeName('<key>')|e]``, never ``$<key>$`` (plain name), never
``[ShowBuildingTypeName('<key>')]`` without ``|e`` and never ``ShowBuildingTypeNameWithNoTooltip``. Slot titles and price
labels never type a building's name ("Beer Workshop Work", "Incamisana Price"); building_links.py links them in the
blueprints. Concepts are linked the same way (``[location|e]``); the generators that name buildings or attributes
are tested where they are written.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import building_links, cap_tooltips

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
_ENTRY = re.compile(r'^\s*([\w.]+):\d*\s*"(.*)"\s*$')
_REFERENCE = re.compile(r"\$(\w+)(?:\|[^$]*)?\$")
_UNLINKED = re.compile(r"ShowBuildingTypeNameWithNoTooltip\(|ShowBuildingTypeName\('\w+'\)\]")


@pytest.fixture(scope="module")
def vanilla() -> Path:
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    root = cap_tooltips.game_root(vanilla_root(ROOT, ROOT / "constructor.toml"))
    if not (root / "in_game/common/building_types").is_dir():
        pytest.skip("no vanilla game files")
    return root


@pytest.fixture(scope="module")
def buildings(vanilla: Path) -> set[str]:
    return building_links.building_keys([vanilla, MOD_ROOT])


@pytest.fixture(scope="module")
def names(vanilla: Path) -> dict[str, str]:
    return building_links.building_names(vanilla, MOD_ROOT)


def unlinked(text: str, buildings: set[str]) -> list[str]:
    """The building mentions in one localization string that are not links."""
    return [f"${ref}$" for ref in _REFERENCE.findall(text) if ref in buildings] + _UNLINKED.findall(text)


def english_entries():
    for path in sorted(MOD_ROOT.rglob("*.yml")):
        if "english" in path.parts:
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if entry := _ENTRY.match(line):
                    yield path.name, entry[1], entry[2]


def test_the_check_finds_every_unlinked_form() -> None:
    known = {"tavern", "granary"}
    assert unlinked("The $tavern$ feeds the town", known) == ["$tavern$"]
    assert unlinked("$tavern|Y$ and [ShowBuildingTypeName('granary')]", known) == ["$tavern$", "ShowBuildingTypeName('granary')]"]
    assert unlinked("[ShowBuildingTypeNameWithNoTooltip('granary')] Max Level", known) == ["ShowBuildingTypeNameWithNoTooltip("]
    assert unlinked("[ShowBuildingTypeName('granary')|e] in this [location|e], $other_key$", known) == []


def test_typed_names_link_to_their_building() -> None:
    names = {"brewery": "Brewery", "brewery_mill": "Brewery Mill", "cloth_manufactory": "Textile Works", "farm": "Farm"}
    link = building_links.link
    # the building's own name, by its game name or its key in words; the longest name wins (Brewery Mill, not Brewery)
    assert building_links.linked("Brewery Mill Work", "brewery_mill", names) == f"{link('brewery_mill')} Work"
    assert building_links.linked("Cloth Manufactory Work", "cloth_manufactory", names) == f"{link('cloth_manufactory')} Work"
    assert building_links.linked("Brewery Price", "brewery", names) == f"{link('brewery')} Price"
    # links stay as they are, other words too; a word inside a longer word is not a name
    assert building_links.linked(f"{link('farm')} Farmland Market", None, names) == f"{link('farm')} Farmland Market"
    assert building_links.typed_names("Cloth Manufactory Work", "cloth_manufactory", names) == ["Cloth Manufactory"]
    assert building_links.typed_names(f"{link('brewery')} Price", "brewery", names) == []


def test_apply_links_typed_names_in_every_blueprint_entry(tmp_path: Path) -> None:
    names = {"brewery": "Brewery", "grange": "Grange", "farm": "Farm"}
    link = building_links.link
    folder = tmp_path / building_links.BLUEPRINTS
    folder.mkdir(parents=True)
    blueprint = folder / "brewery.yml"
    blueprint.write_bytes((
        "building:\r\n  key: brewery\r\n  body: |\r\n    pp_brewery_ale: Brewery Ale\r\n"   # not an entry: left alone
        "localization:\r\n  entries:\r\n    brewery: Brewery\r\n    brewery_slot_0: Brewery Work\r\n"
        "    pp_brewery_ale: Brewery Ale\r\n"
        "    brewery_desc: 'Brews what the Grange sends: ale # and more'\r\n"
        "    farm: Farm\r\n"
    ).encode("utf-8"))
    # every entry links, except a building's own name; line endings stay as they were (CRLF here)
    assert building_links.apply(tmp_path, names, write=False) == ["brewery_slot_0", "pp_brewery_ale", "brewery_desc"]
    assert blueprint.read_bytes().count(b"Brewery Ale") == 2   # write=False leaves the file alone
    building_links.apply(tmp_path, names)
    text = blueprint.read_bytes().decode("utf-8")
    assert "\n" not in text.replace("\r\n", "")
    data = building_links.yaml_io.safe_load(text)
    assert data["building"]["body"] == "pp_brewery_ale: Brewery Ale\n"
    entries = data["localization"]["entries"]
    assert entries["brewery"] == "Brewery" and entries["farm"] == "Farm"
    assert entries["pp_brewery_ale"] == f"{link('brewery')} Ale"
    assert entries["brewery_desc"] == f"Brews what the {link('grange')} sends: ale # and more"
    assert building_links.apply(tmp_path, names, write=False) == []
    # a multi-line entry is linked by hand
    blueprint.write_text("building:\n  key: brewery\nlocalization:\n  entries:\n    brewery_desc: >-\n      The Grange\n",
                         encoding="utf-8")
    with pytest.raises(ValueError, match="link it by hand"):
        building_links.apply(tmp_path, names, write=False)


def test_every_building_named_in_the_mod_text_is_a_link(buildings: set[str]) -> None:
    offenders = [f"{name}: {key}: {', '.join(found)}" for name, key, text in english_entries() if (found := unlinked(text, buildings))]
    assert offenders == [], f"{len(offenders)} texts name a building without linking it:\n" + "\n".join(offenders[:30])


def test_slot_titles_and_price_labels_type_no_building_name(buildings: set[str], names: dict[str, str]) -> None:
    owner: dict[str, str] = {}   # price key -> its building, from the building definitions the game loads
    for path in (MOD_ROOT / "in_game/common/building_types").glob("*.txt"):
        current = None
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if (start := re.match(r"^(?:[A-Z_]+:)?(\w+)\s*=\s*\{", line)) and start[1] in buildings:
                current = start[1]
            elif current and (price := re.match(r"^\s*price\s*=\s*(\w+)", line)):
                owner[price[1]] = current
    offenders = []
    for name, key, text in english_entries():
        slot = re.fullmatch(r"(\w+)_slot_\d+", key)
        building = slot[1] if slot and slot[1] in buildings else owner.get(key)
        if building and (found := building_links.typed_names(text, building, names)):
            offenders.append(f"{name}: {key}: {text} ({', '.join(found)})")
    assert offenders == [], f"{len(offenders)} slot titles or price labels type a building's name:\n" + "\n".join(offenders[:30])


def test_no_text_types_a_building_name(buildings: set[str], names: dict[str, str]) -> None:
    """Method names, modifier names, descriptions, Europedia: a building's game name is never plain text. Only the
    building's own name entry holds it."""
    offenders = [f"{name}: {key}: {', '.join(found)}" for name, key, text in english_entries()
                 if key not in buildings and (found := building_links.typed_names(text, None, names))]
    assert offenders == [], f"{len(offenders)} texts type a building's name:\n" + "\n".join(offenders[:40])


def test_the_blueprints_hold_no_typed_building_names_in_slot_titles_or_price_labels(names: dict[str, str]) -> None:
    assert building_links.apply(ROOT, names, write=False) == []   # fix: uv run python -m prosper_or_perish_constructor.building_links
