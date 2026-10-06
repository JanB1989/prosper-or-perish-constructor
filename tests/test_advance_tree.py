"""The merged advance tree (vanilla + Prosper or Perish) stays valid across game updates.

Pins what an EU5 update can silently break in the mod's advance patches: patch targets that vanilla renamed or removed,
`requires` that no longer resolve, unlocks of buildings or production methods that are gone, modifier keys the game no
longer defines, duplicate keys after an inject, and vanilla changes to advances the mod replaces whole (a REPLACE drops
every vanilla change, so each difference from the current vanilla block must be one the mod made on purpose).
"""

from __future__ import annotations

from collections import Counter
from functools import cache
from pathlib import Path

from eu5_mod_orchestrator.blueprints import enabled_manifest_entries
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList, Value
from eu5gameparser.load_order import MergedEntry, load_merged_directory, load_profile
from prosper_or_perish_constructor import yaml_io


ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
MOD_ADVANCES = MOD_ROOT / "in_game" / "common" / "advances"
BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted"
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"
GENERATED_REDIRECTS = "pp_rgo_building_cost_redirects.txt"

AGES = (
    "age_1_traditions",
    "age_2_renaissance",
    "age_3_discovery",
    "age_4_reformation",
    "age_5_absolutism",
    "age_6_revolutions",
)
# Keys of an advance that are not modifiers.
STRUCTURAL_KEYS = {
    "age", "icon", "requires", "for", "research_cost", "depth", "potential", "allow", "ai_weight",
    "starting_technology_level", "in_tree_of", "government", "country_type", "content_priority",
    "ai_preference_tags", "allow_children", "modifier_while_progressing", "pure_tooltip_entry",
}
# Keys an advance holds once; a second copy after an inject is a bug (modifier keys add up and may repeat).
SINGLE_KEYS = {
    "age", "icon", "for", "research_cost", "depth", "potential", "allow", "ai_weight", "starting_technology_level",
    "in_tree_of", "government", "country_type", "content_priority", "allow_children",
}
# A vanilla advance may unlock a vanilla production method of a building the mod replaces with its own `pp_*`
# methods (paper guild, paper mill, Scottish whisky, Bavarian beer, Mesoamerican copper and obsidian). That vanilla
# line no longer reaches anything, so the same advance must unlock the mod's copy (`pp_<building>_<vanilla method>`,
# a TRY_INJECT advancement in the building's blueprint); otherwise the copy is available without the research.
# unlock_* key -> collection holding its targets (checked for advances the mod touches).
UNLOCK_COLLECTIONS = {
    "unlock_building": "building_types",
    "unlock_unit": "unit_types",
    "unlock_government_reform": "government_reforms",
    "unlock_cabinet_action": "cabinet_actions",
    "unlock_estate_privilege": "estate_privileges",
    "unlock_town_rights": "town_rights",
    "unlock_levy": "levies",
    "unlock_road_type": "road_types",
    "unlock_subject_type": "subject_types",
    "unlock_casus_belli": "casus_belli",
    "unlock_law": "laws",
}
# Every difference between a mod REPLACE and the current vanilla advance, as (dropped vanilla lines, added mod lines).
# A vanilla update that changes a replaced advance shows up here: merge the change into the REPLACE unless the mod
# overrides that line on purpose, then update this table.
DELIBERATE_REPLACE_DIFFERENCES: dict[str, tuple[set[str], set[str]]] = {
    # Public Health (2026-10-05): growth comes only from food, so growth -> disease resistance + population capacity
    "sanitation_advance": (
        {"global_disease_resistance = 0.07", "global_population_growth = 0.001"},
        {"global_disease_resistance = 0.1", "global_population_capacity_modifier = 0.05"},
    ),
    "vaccination_advance": (
        {"global_disease_resistance = 0.07", "global_population_growth = 0.002"},
        {"global_disease_resistance = 0.12", "global_population_capacity_modifier = 0.08"},
    ),
    # institution spread (2026-10-04): research speed instead of max literacy, Print Culture growth halved
    # trade (2026-10-07, Jan): a little cheaper merchants for the printing countries
    "printing_press_advance": (
        {"global_max_literacy = 10"},
        {"research_speed_modifier = 0.05", "merchant_maintenance_efficiency = 0.1"},
    ),
    # trade (2026-10-07, Jan): Global Trade countries' long hauls use a bit less merchant capacity
    "global_trade_advance": (set(), {"trade_sea_efficiency = 0.15", "trade_range_modifier = 0.1"}),
    "print_culture": ({"global_institution_growth_modifier = 0.2"}, {"global_institution_growth_modifier = 0.1"}),
    # New World branch (2026-10-04): Christian Iberian countries skip the institution gate, AI weight for them
    "new_world_advance": (
        {"allow = {has_embraced_institution=institution:new_world}"},
        {
            "allow = {OR={has_embraced_institution=institution:new_world AND={culture={has_culture_group="
            "culture_group:iberian_group} religion.group=religion_group:christian}}}",
            "ai_weight = {if={limit={culture={has_culture_group=culture_group:iberian_group} "
            "religion.group=religion_group:christian} add=100}}",
        },
    ),
    "explorer_commisions_advance": (
        set(),
        {
            "ai_weight = {if={limit={culture={has_culture_group=culture_group:iberian_group} "
            "religion.group=religion_group:christian} add=100}}",
        },
    ),
    "advanced_mining": (set(), {"unlock_building = alum_quarry", "unlock_building = saltpeter_beds"}),
    "efficient_mining": ({"global_iron_output_modifier = 0.1"}, set()),
    "new_currency_demands": (
        {"global_copper_output_modifier = 0.25", "global_tin_output_modifier = 0.1"},
        {"unlock_building = copper_mine_adit", "unlock_building = tin_stamping_mill"},
    ),
    "green_vitriol": (set(), {"unlock_building = alum_works"}),
    "renaissance_sculptures": (
        set(),
        {"global_marble_output_modifier = 0.1", "unlock_building = marble_saw_yard"},
    ),
    "blast_furnace": (
        {"global_iron_output_modifier = 0.75", "requires = plantation_buildings_advance"},
        {"requires = pike_and_shot_advance", "unlock_building = bog_iron_smelter_blast_furnace"},
    ),
    "pan_amalgamation_advance": ({"global_mercury_output_modifier = 0.1"}, set()),
    "slitting_mills": (
        {"global_iron_output_modifier = 0.66"},
        {
            "unlock_building = iron_mine_deep",
            "unlock_production_method = pp_bog_iron_smelter_blast_furnace_finery",
            "unlock_production_method = pp_iron_mine_improved_slitting_dressed_ore",
        },
    ),
    "foreign_mining_techniques": (set(), {"unlock_building = gem_sluice"}),
    "coke_blast_furnace": (
        {"global_iron_output_modifier = 1.0"},
        {"unlock_building = bog_iron_smelter_coke_blast_furnace"},
    ),
    "hot_blast_furnace": (
        {"global_iron_output_modifier = 0.5"},
        {"unlock_production_method = pp_bog_iron_smelter_hot_blast_refining_maintenance"},
    ),
    # The mod keeps the 1.3 coal output (+0.33); EU5 1.4 raised vanilla's to +0.75.
    "coal_improvements_absolutism": (
        {"global_coal_output_modifier = 0.75"},
        {
            "global_coal_output_modifier = 0.33",
            "unlock_building = coal_mine_improved",
            "unlock_production_method = pp_engineered_brine_saltworks_mineral_fired_pans",
        },
    ),
    "coal_improvements_revolutions": (
        {"global_coal_output_modifier = 1.0"},
        {"unlock_building = coal_mine_revolutions"},
    ),
    "saiger_process_discovery": (
        {"global_lead_output_modifier = 0.2", "global_silver_output_modifier = 0.2"},
        {"unlock_building = silver_mine_improved"},
    ),
    "lead_ore_dressing": ({"global_lead_output_modifier = 1.0"}, {"global_lead_output_modifier = 0.25"}),
    "bole_smelting": ({"global_lead_output_modifier = 1.0"}, {"unlock_building = lead_mine_bole_smelting"}),
    "cupola_smelting": ({"global_lead_output_modifier = 1.0"}, {"unlock_building = lead_mine_cupola_smelting"}),
    "lumber_improvements_discovery": (
        {"global_lumber_output_modifier = 0.5"},
        {"ai_weight = {add=150}", "global_lumber_output_modifier = 0.2"},
    ),
    "lumber_improvements_reformation": (
        {
            "global_lumber_output_modifier = 0.5",
            "icon = rudimentary_coastal_ship_repair",
            "requires = bole_smelting",
        },
        {
            "ai_weight = {add=150}",
            "icon = water_sawmill",
            "requires = global_trade_advance",
            "unlock_building = water_sawmill",
        },
    ),
    "lumber_improvements_absolutism": (
        {"global_lumber_output_modifier = 0.5", "icon = rudimentary_coastal_ship_repair"},
        {"ai_weight = {add=150}", "icon = lumber_mill_improved", "unlock_building = lumber_mill_improved"},
    ),
}
# The mod keeps devastation recovery from these advances small (sticky devastation). EU5 1.4 halved the vanilla
# bonus to +0.0025, so the injects were re-netted; the merged value must stay positive.
DEVASTATION_RECOVERY_NET = {
    "recovery_efforts": 0.00025,
    "mother_of_russian_cities": 0.001,
    "wake_of_the_mongol_horde": 0.001,
    "hidden_cities": 0.001,
    "four_noble_truths": 0.001,
    "thrive_under_persecution": 0.001,
    "paschal_cycle": 0.001,
}


@cache
def _profile(name: str):
    return load_profile(name, LOAD_ORDER)


@cache
def _merged(collection: str, scope: str = "in_game", profile: str = "constructor") -> dict[str, MergedEntry]:
    return {entry.key: entry for entry in load_merged_directory(_profile(profile), collection, scope=scope).entries}


def _advances() -> dict[str, MergedEntry]:
    return _merged("advances")


def _mod_touched(entry: MergedEntry) -> bool:
    return any(record.mod_name for record in entry.source_history)


def _scalar(value: Value) -> str:
    return str(value)


def _render(value: Value) -> str:
    if isinstance(value, CList):
        parts = [f"{entry.key}{entry.op}{_render(entry.value)}" for entry in value.entries]
        parts.extend(_render(item) for item in value.items)
        return "{" + " ".join(parts) + "}"
    return str(value)


def _age(entry: MergedEntry) -> str | None:
    ages = entry.value.values("age") if isinstance(entry.value, CList) else []
    return _scalar(ages[-1]) if ages else None


@cache
def _production_methods() -> frozenset[str]:
    methods = set(_merged("production_methods"))
    for building in _merged("building_types").values():
        if not isinstance(building.value, CList):
            continue
        for slot in building.value.values("unique_production_methods"):
            if isinstance(slot, CList):
                methods.update(method.key for method in slot.entries)
    return frozenset(methods)


def _mod_advance_files() -> list[Path]:
    return sorted(path for path in MOD_ADVANCES.glob("*.txt"))


def test_mod_advance_patches_target_existing_vanilla_advances() -> None:
    vanilla = _merged("advances", profile="vanilla")
    offenders: list[str] = []
    created: dict[str, str] = {}
    for path in _mod_advance_files():
        for entry in parse_file(path).entries:
            mode, _, key = entry.key.rpartition(":")
            if mode and key not in vanilla:
                offenders.append(f"{path.name}: {entry.key} patches an advance vanilla no longer has")
            elif not mode and key in vanilla:
                offenders.append(f"{path.name}: {key} redefines a vanilla advance without REPLACE")
            elif not mode and key in created:
                offenders.append(f"{path.name}: {key} is also defined in {created[key]}")
            elif not mode:
                created[key] = path.name
    assert not offenders, "\n".join(offenders)


def test_every_advance_requirement_resolves_in_the_same_or_an_earlier_age() -> None:
    advances = _advances()
    offenders: list[str] = []
    for key, entry in advances.items():
        assert isinstance(entry.value, CList), key
        age = _age(entry)
        if age not in AGES:
            offenders.append(f"{key}: unknown age {age}")
            continue
        for required in map(_scalar, entry.value.values("requires")):
            if required not in advances:
                offenders.append(f"{key} requires missing advance {required}")
            elif _age(advances[required]) not in AGES[: AGES.index(age) + 1]:
                offenders.append(f"{key} ({age}) requires {required} of a later age ({_age(advances[required])})")
    assert not offenders, "\n".join(offenders)


def test_advance_requirements_have_no_cycles() -> None:
    advances = _advances()
    graph = {
        key: [_scalar(value) for value in entry.value.values("requires") if _scalar(value) in advances]
        for key, entry in advances.items()
        if isinstance(entry.value, CList)
    }
    done: set[str] = set()
    for root in graph:
        if root in done:
            continue
        on_path: set[str] = set()
        stack: list[tuple[str, int]] = [(root, 0)]
        while stack:
            node, index = stack.pop()
            if index == 0:
                if node in on_path:
                    raise AssertionError(f"requires cycle through {node}")
                on_path.add(node)
            children = graph.get(node, [])
            if index < len(children):
                stack.append((node, index + 1))
                child = children[index]
                if child in on_path:
                    raise AssertionError(f"requires cycle: {node} -> {child}")
                if child not in done:
                    stack.append((child, 0))
            else:
                on_path.discard(node)
                done.add(node)


def test_advance_unlocks_reach_existing_buildings_and_methods() -> None:
    advances = _advances()
    buildings = _merged("building_types")
    methods = _production_methods()
    vanilla = _merged("advances", profile="vanilla")
    offenders: list[str] = []
    for key, entry in advances.items():
        unlocked_methods = {_scalar(item.value) for item in entry.value.entries if item.key == "unlock_production_method"}
        vanilla_entry = vanilla.get(key)
        vanilla_methods = {
            _scalar(item.value)
            for item in (vanilla_entry.value.entries if vanilla_entry is not None else [])
            if item.key == "unlock_production_method"
        }
        for item in entry.value.entries:
            target = _scalar(item.value)
            if item.key == "unlock_building" and target not in buildings:
                offenders.append(f"{key}: unlock_building = {target} does not exist")
            elif item.key == "unlock_production_method" and target not in methods:
                copies = {
                    method
                    for method in unlocked_methods & methods
                    if method.startswith("pp_") and method.endswith(f"_{target}")
                }
                if target in vanilla_methods and copies:
                    continue  # vanilla's line for a method the mod renamed; the same advance gates the pp_* copy
                if target in vanilla_methods:
                    offenders.append(
                        f"{key}: vanilla unlock_production_method = {target} reaches no method and no pp_* copy is "
                        "gated by the same advance"
                    )
                else:
                    offenders.append(f"{key}: unlock_production_method = {target} does not exist")
            elif item.key in UNLOCK_COLLECTIONS and _mod_touched(entry):
                if target not in _merged(UNLOCK_COLLECTIONS[item.key]):
                    offenders.append(f"{key}: {item.key} = {target} does not exist")
    assert not offenders, "\n".join(offenders)


def test_advance_modifier_keys_are_defined_modifier_types() -> None:
    modifier_types = _merged("modifier_type_definitions", scope="main_menu")
    offenders = sorted(
        f"{key}: {item.key}"
        for key, entry in _advances().items()
        for item in entry.value.entries
        if not isinstance(item.value, CList)
        and item.key not in STRUCTURAL_KEYS
        and not item.key.startswith(("unlock_", "can_", "allow_"))
        and item.key not in modifier_types
    )
    assert not offenders, "\n".join(offenders)


def test_mod_touched_advances_hold_single_keys_once() -> None:
    offenders = [
        f"{key}: {name} x{count}"
        for key, entry in _advances().items()
        if _mod_touched(entry)
        for name, count in Counter(item.key for item in entry.value.entries).items()
        if name in SINGLE_KEYS and count > 1
    ]
    assert not offenders, "\n".join(offenders)


def test_replaced_advances_differ_from_vanilla_only_where_the_mod_means_to() -> None:
    vanilla = _merged("advances", profile="vanilla")
    actual: dict[str, tuple[set[str], set[str]]] = {}
    for path in _mod_advance_files():
        if path.name == GENERATED_REDIRECTS:
            continue
        for entry in parse_file(path).entries:
            mode, _, key = entry.key.rpartition(":")
            if "REPLACE" not in mode:
                continue
            ours = {f"{item.key} = {_render(item.value)}" for item in entry.value.entries}
            theirs = {f"{item.key} = {_render(item.value)}" for item in vanilla[key].value.entries}
            actual[key] = (theirs - ours, ours - theirs)
    assert actual == DELIBERATE_REPLACE_DIFFERENCES


def test_devastation_recovery_advances_keep_a_small_positive_net() -> None:
    advances = _advances()
    for key, expected in DEVASTATION_RECOVERY_NET.items():
        total = sum(
            float(item.value)
            for item in advances[key].value.entries
            if item.key == "global_devastation_recovery"
        )
        assert abs(total - expected) < 1e-9, f"{key}: net global_devastation_recovery {total}"


def test_blueprint_upgrade_chain_unlock_advances_exist() -> None:
    manifest = yaml_io.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = [
        BLUEPRINT_ROOT / entry
        for entry in enabled_manifest_entries(manifest.get("enabled", []), source=MANIFEST_PATH)
        if str(entry).startswith("buildings/")
    ]
    blueprints = [yaml_io.safe_load(path.read_text(encoding="utf-8")) for path in enabled]
    known = set(_advances())
    for raw in blueprints:
        known.update(advancement["key"] for advancement in raw.get("advancements") or [])
    offenders = [
        f"{raw['tag']}: unlock_advance {(raw.get('upgrade_chain') or {}).get('unlock_advance')}"
        for raw in blueprints
        if (raw.get("upgrade_chain") or {}).get("unlock_advance") not in (None, *known)
    ]
    assert not offenders, "\n".join(offenders)
