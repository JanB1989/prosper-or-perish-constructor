"""World Builder classes and river channels in the terrain biomes: parents widened, own biomes for vegetation classes."""
from pathlib import Path

import pytest

from prosper_or_perish_constructor.worldbuilder import biomes

VANILLA_BIOMES = """﻿## Vegetation : desert - sparse - grasslands - woods - forest- jungle
#climate = climate_key (defined in game/common/climate)

000 =
{
\tbiome = default_biome
}

101 =
{
\tclimate = continental
\tclimate = oceanic
\ttopography = flatland
\tvegetation = forest
\tvegetation = jungle
\tbiome = oceanic_flatland_forest_jungle_biome
}

102 =
{
\tclimate = continental
\tclimate = oceanic
\ttopography = hills
\tvegetation = forest
\tvegetation = jungle
\tbiome = oceanic_hills_forest_jungle_biome
}

103 =
{
\tclimate = continental
\tclimate = oceanic
\ttopography = wetlands
\tvegetation = forest
\tvegetation = jungle
\tbiome = oceanic_wetlands_forest_jungle_biome
}

104 =
{
\tclimate = continental
\tclimate = oceanic
\ttopography = mountains
\tvegetation = forest
\tvegetation = jungle
\tbiome = oceanic_mountains_forest_jungle_biome
}

157 =
{
\tclimate = oceanic
\tclimate = continental
\ttopography = narrows
\tbiome = oceanic_narrows
}
"""


def _palette(fill):
    return "\n".join(f"\t\t\t{m}" for m in ["sand"] * 6 + ["river", "border", "tveg", "tclim"] + fill)


VANILLA_MATERIALS = "﻿materials = {\n" + "".join(
    f'\t{{\n\t\tname = \t\t"{n}"\n\t\tdiffuse =\t"textures/{n}_diffuse.dds"\n\t\tnormal =\t"textures/{n}_normal.dds"\n'
    f'\t\tproperties =\t"textures/{n}_properties.dds"\n\t}}\n'
    for n in ["fallback_material", "sand", "river", "border", "tveg", "tclim", "rock", "grass", "dense", "scatter", "wood01", "wood02"]
) + "}\nbiomes = {\n" + "".join(
    f"\t{{\n\t\tname = {b}\n\t\tmaterials = {{\n{_palette(fill)}\n\t\t}}\n\t}}\n"
    for b, fill in [("default_biome", []), ("oceanic_flatland_forest_jungle_biome", ["grass"] * 6),
                    ("oceanic_hills_forest_jungle_biome", ["rock"] * 6), ("oceanic_wetlands_forest_jungle_biome", ["grass"] * 6),
                    ("oceanic_mountains_forest_jungle_biome", ["rock"] * 3), ("oceanic_narrows", ["grass"] * 3)]
) + "}"

FAMILIES = {"vegetation": {"forest": ["ha1300_veg_coniferous_forest"]}, "topography": {"flatland": ["ha1300_topo_valleys"]},
            "climate": {"continental": ["ha1300_climate_continental_monsoon"]}}

TEMPLATES = """allenstein = { topography = flatland vegetation = ha1300_veg_coniferous_forest climate = continental }
nidzica = { topography = ha1300_topo_valleys vegetation = ha1300_veg_coniferous_forest climate = ha1300_climate_continental_monsoon }
lyck = { topography = flatland vegetation = ha1300_veg_coniferous_forest climate = oceanic }
hill = { topography = hills vegetation = ha1300_veg_coniferous_forest climate = continental }
alps = { topography = mountains vegetation = ha1300_veg_coniferous_forest climate = continental }
osterode = { topography = flatland vegetation = forest climate = continental }
channel = { topography = pp_river_channel climate = continental }
mystery = { topography = flatland vegetation = forest climate = ha1300_climate_new }
"""

DESIGN = """
[general]
own_biomes = true
own_biome_minimum_locations = 2
max_total_biomes = 20
[climate_groups.temperate]
climates = ["continental", "oceanic"]
neighbours = []
[tones.temperate]
DENSE = "dense"
SCATTER = "scatter"
[terrain]
flatland = "flat"
wetlands = "wet"
hills = "rough"
[terrain_base]
flat = "flatland"
wet = "wetlands"
rough = "hills"
[classes]
ha1300_veg_coniferous_forest = ["wood02", "wood02", "DENSE", "pp_new", "wood02", "SCATTER"]
[materials.pp_new]
diffuse = "textures/pp_new_diffuse.dds"
normal = "textures/pp_new_normal.dds"
properties = "textures/pp_new_properties.dds"
"""


def test_children_follow_their_parent_line():
    text, added = biomes.widen(VANILLA_BIOMES, biomes.with_channels(FAMILIES, ["pp_river_channel"]))
    assert "\tvegetation = forest\n\tvegetation = ha1300_veg_coniferous_forest\n" in text
    assert "\ttopography = narrows\n\ttopography = pp_river_channel\n" in text
    assert "#climate = climate_key" in text and added == 4 + 5 + 1 + 1          # forest x4, continental x5, flatland, narrows


def test_vegetation_children_skip_the_terrains_with_own_definitions():
    text, _ = biomes.widen(VANILLA_BIOMES, FAMILIES, skip_vegetation_in={"flatland", "hills", "wetlands"})
    blocks = {name: keys for name, keys, _ in biomes.definitions(text)}
    assert "ha1300_veg_coniferous_forest" not in blocks["101"]["vegetation"]
    assert "ha1300_veg_coniferous_forest" in blocks["104"]["vegetation"]          # mountains keep the parent


@pytest.fixture
def written(tmp_path: Path):
    vanilla, mod = tmp_path / "vanilla", tmp_path / "mod"
    for rel, text in ((biomes.RELATIVE_PATH, VANILLA_BIOMES), (biomes.MATERIALS_PATH, VANILLA_MATERIALS)):
        (vanilla / "game" / rel).parent.mkdir(parents=True, exist_ok=True)
        (vanilla / "game" / rel).write_text(text, encoding="utf-8")
    for kind in ("diffuse", "normal", "properties"):
        path = vanilla / "game" / biomes.TEXTURE_ROOT / f"textures/pp_new_{kind}.dds"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"DDS ")
    (mod / "in_game/map_data").mkdir(parents=True)
    (mod / "in_game/map_data/location_templates.txt").write_text(TEMPLATES, encoding="utf-8")
    (tmp_path / "design.toml").write_text(DESIGN, encoding="utf-8")
    report = biomes.write(vanilla, mod, FAMILIES, ["pp_river_channel"], biomes.load_design(tmp_path / "design.toml"))
    out_biomes = (mod / biomes.RELATIVE_PATH).read_text(encoding="utf-8-sig")
    out_materials = (mod / biomes.MATERIALS_PATH).read_text(encoding="utf-8-sig")
    return report, out_biomes, out_materials


def _biome_of(text, attrs):
    defs = biomes.definitions(text)
    hits = biomes.matching(defs, attrs)
    assert len(hits) <= 1, hits
    return next((b for n, _, b in defs if hits and n == hits[0]), "default_biome")


def test_vegetation_class_gets_its_own_biome(written):
    report, out_biomes, out_materials = written
    assert report["own_biomes"] == 1 and report["plain_locations"] == 1 and report["plain_sample"] == ["mystery"]
    flat = {"climate": "continental", "vegetation": "ha1300_veg_coniferous_forest", "topography": "flatland"}
    assert _biome_of(out_biomes, flat) == "pp_coniferous_forest_temperate_flat_biome"
    # climate and topography children reach the class's biome too
    assert _biome_of(out_biomes, {**flat, "topography": "ha1300_topo_valleys", "climate": "ha1300_climate_continental_monsoon"}) \
        == "pp_coniferous_forest_temperate_flat_biome"
    # a rare terrain borrows the class's own biome; mountains keep the vanilla parent
    assert _biome_of(out_biomes, {**flat, "topography": "hills"}) == "pp_coniferous_forest_temperate_flat_biome"
    assert _biome_of(out_biomes, {**flat, "topography": "mountains"}) == "oceanic_mountains_forest_jungle_biome"
    assert _biome_of(out_biomes, {"climate": "continental", "topography": "pp_river_channel"}) == "oceanic_narrows"
    assert _biome_of(out_biomes, {**flat, "vegetation": "forest"}) == "oceanic_flatland_forest_jungle_biome"


def test_own_palette_keeps_the_coasts_and_follows_the_class_pattern(written):
    _, _, out_materials = written
    names, palettes = biomes.parse_materials(out_materials)
    assert "pp_new" in names and names.count("pp_new") == 1
    palette = palettes["pp_coniferous_forest_temperate_flat_biome"]
    assert palette[:10] == ["sand"] * 6 + ["river", "border", "tveg", "tclim"]
    assert palette[10:] == ["wood02", "wood02", "dense", "pp_new", "wood02", "scatter"]
    assert out_materials.startswith("# Generated by ppc worldbuilder apply")


def test_rough_and_wet_keep_part_of_their_base():
    design_rows = biomes.Design(1, 20, True, {"temperate": ["continental", "oceanic"]}, {"temperate": []},
                                {"temperate": {"DENSE": "dense", "SCATTER": "scatter"}},
                                {"flatland": "flat", "wetlands": "wet", "hills": "rough"},
                                {"flat": "flatland", "wet": "wetlands", "rough": "hills"},
                                {"ha1300_veg_coniferous_forest": ["wood02"] * 6}, {})
    templates = "a = { topography = hills vegetation = ha1300_veg_coniferous_forest climate = continental }\n" \
                "b = { topography = wetlands vegetation = ha1300_veg_coniferous_forest climate = continental }\n"
    _, palettes = biomes.parse_materials(VANILLA_MATERIALS)
    plan = biomes.plan(design_rows, VANILLA_BIOMES, palettes, FAMILIES, templates)
    assert plan.palettes["pp_coniferous_forest_temperate_rough_biome"][10:] == ["wood02", "wood02", "rock"] * 2
    assert plan.palettes["pp_coniferous_forest_temperate_wet_biome"][10:] == ["wood02", "grass", "wood02"] * 2


def test_check_rejects_a_missing_material():
    broken = VANILLA_MATERIALS.replace("\t\t\triver\n", "\t\t\tno_such_material\n", 1)
    with pytest.raises(ValueError, match="no_such_material"):
        biomes.check(VANILLA_BIOMES, broken, TEMPLATES)


def test_parent_only_keeps_vanilla_definitions_and_drops_a_stale_materials_override(written, tmp_path):
    # EU5 1.4 stops at game start with "Too many biomes" above its limit: parent-only adds no biome and no definition
    vanilla, mod = tmp_path / "vanilla", tmp_path / "mod"
    assert (mod / biomes.MATERIALS_PATH).is_file()                     # written by the own-biome run in the fixture
    report = biomes.write(vanilla, mod, FAMILIES, ["pp_river_channel"], None)
    out = (mod / biomes.RELATIVE_PATH).read_text(encoding="utf-8-sig")
    assert report["mode"] == "parent_only" and report["removed_materials_override"]
    assert not (mod / biomes.MATERIALS_PATH).exists()
    assert len(biomes.definitions(out)) == len(biomes.definitions(VANILLA_BIOMES))
    flat = {"climate": "continental", "vegetation": "ha1300_veg_coniferous_forest", "topography": "flatland"}
    assert _biome_of(out, flat) == "oceanic_flatland_forest_jungle_biome"


def test_the_shipped_config_adds_no_biome():
    design = biomes.load_design(Path(__file__).resolve().parents[1] / "config/terrain_biomes.toml")
    assert not design.own_biomes and design.max_total <= 191
