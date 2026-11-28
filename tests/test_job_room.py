"""Job room (2026-11-27, Jan): the people of a class take its room, their workplaces give it back."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import re

import pytest

from prosper_or_perish_constructor import building_footprint as bf
from prosper_or_perish_constructor import building_shutdown as bs
from prosper_or_perish_constructor import job_room as jr
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"


@pytest.fixture(scope="module")
def vanilla() -> Path:
    return vanilla_root(ROOT, PROJECT)


@pytest.fixture(scope="module")
def targets(vanilla):
    return jr.targets(ROOT, MOD, PROJECT, vanilla)


def test_set_room_writes_one_line_and_takes_it_out_again() -> None:
    body = "\n\tpop_type = burghers\n\tmodifier = {\n\t\tlocal_glass_output_modifier = -0.005\n\t}\n"
    out = jr.set_room(body, "burghers", Decimal("1"))
    assert "\tmodifier = {\n\t\tlocal_burghers_desired_pop = 1 # job_room\n\t\tlocal_glass_output_modifier = -0.005\n\t}\n" in out
    assert "raw_modifier" not in out  # nothing on a building can take room away: its blocks are 0 while it is empty
    assert jr.set_room(out, "burghers", Decimal("1")) == out
    assert jr.set_room(out, None, None) == body
    # a building without the block gets one, and loses it again with the line
    bare = "\n\tpop_type = burghers\n"
    assert jr.set_room(jr.set_room(bare, "burghers", Decimal("0.4")), None, None) == bare


def test_set_room_keeps_its_place_when_later_lines_follow() -> None:
    """Other finalize passes append to the building after this one; writing again must not move the block."""
    out = jr.set_room("\n\tpop_type = burghers\n", "burghers", Decimal("0.8")) + "\tai_construct_weight = { value = 0 }\n"
    assert jr.set_room(out, "burghers", Decimal("0.8")) == out
    assert jr.set_room(out, "burghers", Decimal("0.4")) == out.replace("0.8", "0.4")


def test_set_room_folds_a_line_of_the_same_key_and_gives_it_back() -> None:
    """The engine must not see the key twice in one block (the Trade School's own burgher room)."""
    body = "\n\tmodifier = {\n\t\tlocal_burghers_desired_pop = 0.5\n\t}\n"
    out = jr.set_room(body, "burghers", Decimal("0.2"))
    assert out.count("local_burghers_desired_pop") == 1
    assert "local_burghers_desired_pop = 0.7 # job_room base 0.5" in out
    assert jr.set_room(out, "burghers", Decimal("0.2")) == out
    assert jr.set_room(out, None, None) == body


def test_the_rule() -> None:
    """Engine: room = flat + every job once + the lines. Each person takes k, each filled job gives k back, so people
    at work are always covered and idle people allowed = (flat + unfilled jobs) / (1 + k)."""
    k = Decimal(4)
    flat, jobs = Decimal("0.2"), Decimal("1")
    for working in (Decimal("0"), Decimal("0.5"), Decimal("1")):
        allowed = (flat + jobs - working) / (1 + k)
        for idle in (Decimal("0"), allowed, allowed + Decimal("0.01")):
            people = working + idle
            room = flat + jobs + k * working - k * people
            assert (people <= room) == (idle <= allowed)
    # the town of the design talk: 200 flat places, a guild of 1,000 jobs
    assert [(flat + jobs - w) / (1 + k) for w in (Decimal("1"), Decimal("0.5"), Decimal("0"))] == [
        Decimal("0.04"), Decimal("0.14"), Decimal("0.24")]


def test_the_compiled_buildings_carry_the_line(targets, vanilla) -> None:
    wanted, result = targets
    assert jr.check(ROOT, MOD, PROJECT, vanilla) == [], "run ppc build (job_room)"
    owners = bf.owner_blocks(MOD, vanilla)
    definitions = bf.vanilla_definitions(vanilla)
    values = bf.script_values(vanilla, MOD)
    for key, (pop, room) in wanted.items():
        block = owners[key]
        body = bf._read(block.path)[block.open + 1: block.close]
        inherited = definitions.get(key, "") if block.mode in bf._INJECT_MODES else ""
        tops = bf._depth_zero_text(body) + "\n" + bf._depth_zero_text(inherited)
        # k x the final employment_size (after the employment cut) of the building's own pop type
        assert re.search(rf"^[ \t]*pop_type\s*=\s*{pop}\b", tops, re.MULTILINE), key
        size = re.search(r"^[ \t]*employment_size\s*=\s*([^\s#{}]+)", tops, re.MULTILINE).group(1)
        assert bf._resolve(size, values) * result.room_per_head[pop] == room, key
        _match, open_, close = jr._top_block(body, jr.BLOCK)
        lines = re.findall(rf"local_{pop}_desired_pop\s*=\s*(-?[0-9.]+)[ \t]*# job_room(?: base (-?[0-9.]+))?", body[open_ + 1: close])
        assert len(lines) == 1, key
        value, base = lines[0]
        assert Decimal(value) - Decimal(base or "0") == room, key
        assert len(re.findall(rf"local_{pop}_desired_pop\s*=", body[open_ + 1: close])) == 1, key  # the key once
        assert body.count("# job_room") == 1, key


def test_who_carries_the_line(targets, vanilla) -> None:
    """Every building that employs a listed class, production building or not: a person at work in a building without
    the line would take room and get none back."""
    wanted, result = targets
    config = jr.load_config(PROJECT)
    assert config.room_per_head == {"burghers": Decimal(4), "laborers": Decimal(4)} and config.not_buildings == frozenset()
    assert result.room_per_head == config.room_per_head
    for key in ("glass_guild", "tannery", "printing_press_shop",  # producers
                "marketplace", "fondaco", "hanseatic_kontor",      # trade buildings the mod replaces
                "counting_house", "stock_exchange", "theater",     # vanilla buildings the mod only injects into
                "pp_trade_school"):
        assert wanted[key][0] == "burghers", key
    for key in ("mason", "iron_mine", "charcoal_maker", "tar_kiln", "hired_labor_yard", "cookshop", "sawmill"):
        assert wanted[key][0] == "laborers", key
    for key in ("wheat_farm", "market_village", "pp_village_school"):  # peasants, clergy: not listed
        assert key in result.other_pop and key not in wanted, key
    # worker-less improvements name a class but nobody works there: nothing to give back
    assert result.no_jobs == ["bund", "khmer_baray", "polders", "qanats"]
    assert wanted["mason"] == ("laborers", Decimal("3.2"))             # 4 x 0.8 (1.0 cut to 0.8)
    assert wanted["glass_guild"] == ("burghers", Decimal("1"))        # 4 x 0.25 (0.3 cut to 0.25)
    assert wanted["counting_house"] == ("burghers", Decimal("0.4"))   # 4 x vanilla's 0.1
    # every blueprint building whose pop type is listed and that has jobs
    owners = bf.owner_blocks(MOD, vanilla)
    definitions = bf.vanilla_definitions(vanilla)
    for key in bs.blueprint_rules(ROOT):
        block = owners.get(key)
        if block is None:
            continue
        body = bf._read(block.path)[block.open + 1: block.close]
        inherited = definitions.get(key, "") if block.mode in bf._INJECT_MODES else ""
        pop = jr._POP_RE.search(bf._depth_zero_text(body) + "\n" + bf._depth_zero_text(inherited))
        listed = bool(pop and pop.group("pop") in config.room_per_head)
        assert (key in wanted) == (listed and key not in result.no_jobs), key
    assert len(wanted) > 150


def test_the_pop_type_carries_the_per_person_line(vanilla) -> None:
    """The other half is hand-written in the pop types: pop_percentage_impact is applied at the class's share of the
    location's people and the _scaled room modifier is multiplied by the location's people, so -k there is -k per
    person. The build stops when it does not match [job_room] room_per_head."""
    config = jr.load_config(PROJECT)
    assert jr.pop_type_problems(config, vanilla, MOD) == []
    body = jr.pop_type_bodies(vanilla, MOD)["burghers"]
    _match, open_, close = jr._top_block(body, "pop_percentage_impact")
    assert re.search(r"^\s*local_burghers_desired_pop_scaled = -4\s*$", body[open_ + 1: close], re.MULTILINE)
    laborers = jr.pop_type_bodies(vanilla, MOD)["laborers"]
    _match, open_, close = jr._top_block(laborers, "pop_percentage_impact")
    assert re.search(r"^\s*local_laborers_desired_pop_scaled = -4\s*$", laborers[open_ + 1: close], re.MULTILINE)
    other = jr.Config({"burghers": Decimal(5)}, frozenset())
    assert jr.pop_type_problems(other, vanilla, MOD) == [
        "pop type burghers: pop_percentage_impact needs local_burghers_desired_pop_scaled = -5 ([job_room] room_per_head)"]
    # a class without an equilibrium cannot be listed
    assert any("has no equilibrium" in p for p in jr.pop_type_problems(jr.Config({"peasants": Decimal(1)}, frozenset()), vanilla, MOD))


def _value(text: str, block: str, key: str) -> Decimal:
    """The value of ``key`` inside the first ``block = {`` (or ``:block = {``) of a script text."""
    start = re.search(rf"(?m)^(?:[A-Z_]+:)?{block}\s*=\s*\{{", text)
    assert start, block
    depth, i = 1, start.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    found = re.findall(rf"(?m)^\s*{key}\s*=\s*(-?[0-9.]+)", text[start.end(): i])
    assert len(found) == 1, (block, key, found)  # a key written twice would add up in the engine
    return Decimal(found[0])


def test_flat_room_of_a_listed_class_is_its_old_number_times_one_plus_k(vanilla) -> None:
    """Idle people allowed = (flat room + unfilled jobs) / (1 + k), so every flat room number the mod sets for burghers
    and laborers is the number it had before x (1 + k): the same idle people fit as before."""
    config = jr.load_config(PROJECT)
    five = 1 + config.room_per_head["burghers"]
    assert five == 1 + config.room_per_head["laborers"] == 5
    statics = (MOD / "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt").read_text(encoding="utf-8-sig")
    # an RGO level employs 1,000 laborers and the engine counts no jobs for it: its line is the room of its workers
    # (1), what they take (k) and the old spare half place x (1 + k)
    assert _value(statics, "rgo_level", "local_laborers_desired_pop") == Decimal("1.5") * five
    # location ranks: vanilla's line plus the mod's inject
    vanilla_ranks = "\n".join(bf._read(path) for path in bf.vanilla_files(vanilla, Path("in_game/common/location_ranks")))
    ranks = (MOD / "in_game/common/location_ranks/pp_location_rank_adjustments.txt").read_text(encoding="utf-8-sig")
    for rank, before in (("megalopolis", Decimal("4")), ("city", Decimal("0.5")), ("town", Decimal("0.2"))):
        for pop in ("burghers", "laborers"):
            key = f"local_{pop}_desired_pop"
            assert _value(vanilla_ranks, rank, key) + _value(ranks, rank, key) == before * five, (rank, pop)
    # devastation's cut of the laborers (applied at negative strength), and its upper-class multiplier for the burghers:
    # the multiplier scales the room the workplaces give back too, so a fifth of the old number keeps the old cut
    assert _value(statics, "devastation", "local_laborers_desired_pop") == Decimal("0.4") * five
    assert _value(statics, "devastation", "local_laborers_desired_pop_scaled") == Decimal("0.01") * five
    assert _value(statics, "devastation", "local_upper_class_capacity_modifier") == Decimal("0.5") / five


def test_demotion_follows_the_size_of_the_location(vanilla) -> None:
    """Jan, 2026-11-27: slow demotion. Under the rule one demotion removes (1 + k) times the true excess, up to the
    demotion speed, and people at work go with it. Vanilla demotes a flat 100 people a month per location; here 10 plus
    1 per 1,000 inhabitants."""
    base = "\n".join(bf._read(path) for path in bf.vanilla_files(vanilla, Path("main_menu/common/static_modifiers")))
    inject = (MOD / "in_game/common/static_modifiers/pp_population_growth_and_food_adjustments.txt").read_text(encoding="utf-8-sig")
    statics = (MOD / "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt").read_text(encoding="utf-8-sig")
    assert _value(base, "location_base_values", "local_pop_demotion_speed") + _value(
        inject, "location_base_values", "local_pop_demotion_speed") == Decimal("0.01")
    assert _value(statics, "total_population", "local_pop_demotion_speed") == Decimal("0.001")


def test_no_other_building_carries_a_marked_line(targets, vanilla) -> None:
    wanted, _result = targets
    owners = bf.owner_blocks(MOD, vanilla)
    for key, block in owners.items():
        if key in wanted:
            continue
        assert jr.MARKER not in bf._read(block.path)[block.open + 1: block.close], key


def test_no_negative_line_sits_on_a_building() -> None:
    """The first version (a raw_modifier line of -jobs and a modifier line of +jobs) lost its negative line in an empty
    building: every block of a building is scaled by its input fulfilment, 0 while nobody works there (measured in
    game 2026-11-27). The negative side is on the pop type now; no building carries one."""
    for path in (MOD / "in_game" / "common" / "building_types").glob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        assert not re.search(r"desired_pop\s*=\s*-[0-9.]+[ \t]*# job_room", text), path.name


def test_the_start_step_fills_the_jobs_the_games_own_start_left_empty(vanilla) -> None:
    """When a new game starts the engine sizes every class to its room in one pass, while no building has workers yet:
    nothing is given back, so a listed class is cut to (flat room + jobs) / (1 + k) (in game 2026-11-27: 1.83 M
    burghers on day 0 against 3.88 M without any of this, and a million at work after three years). One step a day
    into a new game fills the open jobs from the peasants, with the culture and religion the engine's own fill gives:
    the class's largest pop in the location, else the owner's for an upper class. Once, no pulse."""
    config = jr.load_config(PROJECT)
    # laborers are listed but need no start step: the pops setup sizes them (test_the_setup_holds_the_laborers...)
    pops = sorted(set(config.room_per_head) - jr.SETUP_SIZED)
    assert pops == ["burghers"] and jr.SETUP_SIZED == {"laborers"}
    upper = jr.upper_pop_types(vanilla, MOD)
    assert {"nobles", "clergy", "burghers"} <= upper and not {"laborers", "soldiers", "peasants"} & upper
    groups = jr.setup_groups(MOD, pops)
    setup, trims = jr.start_laborer_plan(ROOT, PROJECT, vanilla, MOD)
    files = jr.start_files(config, vanilla, MOD, trims)
    assert set(files) == {jr.VALUES, jr.EFFECTS, jr.ON_ACTION}
    for relative, text in files.items():
        assert (MOD / relative).read_text(encoding="utf-8") == text, f"{relative}: run ppc build (job_room)"
    assert jr.start_files(jr.Config({}, frozenset()), vanilla, MOD) == {}  # no class listed: no start step
    values = " ".join(files[jr.VALUES].split())
    effects = " ".join(files[jr.EFFECTS].split())
    on_action = " ".join(files[jr.ON_ACTION].split())
    for pop in pops:
        # the open jobs are read from the buildings in the running game: nothing about sizes is written into the script
        assert (f"pp_job_room_open_{pop} = {{ value = 0 every_buildings_in_location = {{ limit = {{ building_pop_type = {pop} "
                "is_opened = yes } add = { value = building_employment_size_amount subtract = building_employed_amount "
                "min = 0 } } }") in values
        grouped = pop in {g[1] for g in groups}
        note = (f"if = {{ limit = {{ has_variable = pp_job_room_done_{pop} }} subtract = var:pp_job_room_done_{pop} }} "
                if grouped else "")
        assert f"pp_job_room_left_{pop} = {{ value = pp_job_room_open_{pop} {note}min = 0 }}" in values
        assert (f"pp_job_room_share_{pop} = {{ value = pp_job_room_left_{pop} divide = {{ value = num_pop_type:peasants "
                f"min = 0.001 }} min = 0 max = {jr.MAX_SHARE} }}") in values
        assert (f"remove_variable = pp_job_room_done_{pop}" in effects) == grouped  # the note lives for that one step
        block = effects[effects.index(f"# {pop} "):]
        assert f"limit = {{ pp_job_room_share_{pop} > 0 }}" in block
        # into the class's largest pop here, as the engine's own fill does
        assert (f"limit = {{ any_pop = {{ pop_type = pop_type:{pop} }} }} ordered_pop = {{ limit = {{ pop_type = pop_type:{pop} }} "
                "order_by = pop_size max = 1 save_temporary_scope_as = pp_job_room_like }") in block
        assert (f"split_pop = {{ fraction = scope:pp_job_room_share type = pop_type:{pop} culture = scope:pp_job_room_like.culture "
                "religion = scope:pp_job_room_like.religion }") in block
        owner_rule = "culture = scope:pp_job_room_location.owner.culture religion = scope:pp_job_room_location.owner.religion"
        assert (owner_rule in block) == (pop in upper), pop
    # once, at game start, after the game's own sizing; never from a pulse
    assert f"on_game_start = {{ on_actions = {{ delay = {{ days = {jr.START_DELAY_DAYS} }} pp_job_room_start }} }}" in on_action
    assert "every_country = { every_owned_location = { pp_job_room_restore = yes } }" in on_action
    # where the setup gives a class several groups, each comes back at its setup size, the largest first, so it is
    # still the largest when the rest is filled into "the largest" (Stockholm's Swedish and German burghers)
    assert [g for g in groups if g[:2] == ("stockholm", "burghers")] == [
        ("stockholm", "burghers", "swedish", "catholic", "0.91"),
        ("stockholm", "burghers", "holsatian", "catholic", "0.74"),
        ("stockholm", "burghers", "lower_saxon", "catholic", "0.44")]
    assert len(groups) > 800 and {g[1] for g in groups} <= set(pops)
    assert ("location:stockholm = { pp_job_room_group = { pop = burghers culture = swedish religion = catholic size = 0.91 } "
            "pp_job_room_group = { pop = burghers culture = holsatian religion = catholic size = 0.74 } "
            "pp_job_room_group = { pop = burghers culture = lower_saxon religion = catholic size = 0.44 } }") in on_action
    assert on_action.index("location:stockholm = {") < on_action.index("every_country = {")
    group = effects[effects.index("pp_job_room_group = {"):]
    for token in ("$pop$", "$culture$", "$religion$", "$size$"):  # an unused argument makes the call a silent no-op
        assert token in group, token
    for folder in ("in_game/common/on_action", "in_game/common/scripted_effects", "in_game/events"):
        for path in (MOD / folder).glob("*.txt"):
            if path.name in (jr.ON_ACTION.name, jr.EFFECTS.name):
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            assert "pp_job_room_restore" not in text and "pp_job_room_start" not in text, path.name


def test_the_setup_holds_the_laborers_outside_the_buildings(vanilla) -> None:
    """The game's start fills a class up to its room as the room reads with the setup's people. Every laborer takes k
    room and an RGO level gives 1.5 x (1 + k), so a setup with 2 M laborers made 142 M on day 0 (2026-11-27). The pops
    setup therefore holds, per location, 1.5 x the RGO level plus the rank's flat room in laborers (capped by the
    laborers the place had outside its buildings without the rule): the game then adds the building workers itself and
    ends where it did without the rule. Taken from the peasants' own groups, the largest first."""
    from prosper_or_perish_constructor.worldbuilder import start_placement as sp

    config = jr.load_config(PROJECT)
    k = config.room_per_head["laborers"]
    ranks = sp.load_ranks(vanilla, MOD)
    targets, trims = jr.start_laborer_plan(ROOT, PROJECT, vanilla, MOD)
    rows = {}
    with (ROOT / jr.START_LABORERS).open(encoding="utf-8", newline="") as handle:
        import csv
        for row in csv.DictReader(handle):
            rows[row["location"]] = (float(row["rgo_level"]), float(row["free_laborers"]) if float(row["slaves"]) > 0.5 else 1e9)
    assert len(targets) == len(rows) > 13000
    flat = {"rural_settlement": 0.0, "town": 0.2, "city": 0.5, "megalopolis": 4.0}  # the ranks' laborer room / (1 + k)
    for location in ("stockholm", "constantinople", "paris", "patna", "aabenraa"):
        level, free = rows[location]
        assert targets[location] == pytest.approx(min(1.5 * level + flat[ranks.get(location, "rural_settlement")], free), abs=0.001)
    assert targets["patna"] < 0.5 and rows["patna"][0] >= 3  # slaves do the RGO's work there: no laborers to place
    # no slaves: no cap (the setup's laborers plus what the start step gives back are the full 1.5 x level)
    assert rows["longxi"][1] == 1e9
    assert targets["longxi"] + trims.get("longxi", (0.0, 0.0))[0] / float(k) == pytest.approx(1.5 * rows["longxi"][0], abs=0.002)
    # with the setup at the target the start's room is the old one: 7.5 R + J + 5 f - 4 x (1.5 R + f) = 1.5 R + J + f
    level, _free = rows["paris"]
    f = flat[ranks["paris"]]
    jobs = 10.0
    assert (1 + k) * Decimal("1.5") * Decimal(str(level)) + Decimal(jobs) + (1 + k) * Decimal(str(f)) - k * Decimal(str(1.5 * level + f))         == Decimal("1.5") * Decimal(str(level)) + Decimal(jobs) + Decimal(str(f))
    total = sum(targets.values())
    assert 26000 < total < 31000  # thousands: about 28 M of the 45 M laborers a new game has; the rest work in buildings

    # The RGO's own size at game start follows the setup: one level per 10,000 peasants, slaves and tribesmen (in game
    # 2026-11-28: 1,132 RGOs came out a level smaller when the setup first held the laborers). So the setup never takes
    # the lower pops below level x 10,000; the game's start then promotes k x the shortfall too many, and the start
    # step gives exactly that back to the peasants (pp_job_room_trim).
    vanilla_pops = sp.load_pops(vanilla)
    for location, (size, keep) in trims.items():
        level, free = rows[location]
        lower = sum(p.size_k for p in vanilla_pops[location] if p.type in jr.LOWER_POPS)
        # (a few RGOs are larger than their people give: nothing is taken there)
        assert level >= 2 and lower - targets[location] >= min(lower, jr.RGO_PEOPLE_PER_LEVEL * level) - 1e-6, location
        want = min(1.5 * level + flat[ranks.get(location, "rural_settlement")], free)
        assert size == pytest.approx(float(k) * (want - targets[location]), abs=0.002), location
        assert keep == pytest.approx(want, abs=0.002), location  # the laborers outside buildings it was meant to hold
    assert 800 < len(trims) < 1500 and targets["thisted"] < 1.0 and trims["thisted"][0] > 9
    on_action = (MOD / jr.ON_ACTION).read_text(encoding="utf-8")
    assert on_action.count("pp_job_room_trim = { size = ") == len(trims), "run ppc build (job_room)"
    effects = " ".join((MOD / jr.EFFECTS).read_text(encoding="utf-8").split())
    assert ('pp_job_room_trim = { save_temporary_scope_value_as = { name = pp_job_room_spare value = { value = num_pop_type:laborers '
            'subtract = pp_job_room_at_work_laborers subtract = $keep$ min = 0 } } '
            'save_temporary_scope_value_as = { name = pp_job_room_move value = { '
            'value = "unemployed_pops_of_pop_type_in_location(pop_type:laborers)" max = $size$ max = scope:pp_job_room_spare } } '
            'if = { limit = { scope:pp_job_room_move > 0.0005 } '
            'save_temporary_scope_value_as = { name = pp_job_room_share value = { value = scope:pp_job_room_move '
            f'divide = {{ value = num_pop_type:laborers min = 0.001 }} max = {jr.MAX_SHARE} }} }} '
            'every_pop = { limit = { pop_type = pop_type:laborers } split_pop = { fraction = scope:pp_job_room_share '
            'type = pop_type:peasants } } } }') in effects
    assert ("pp_job_room_at_work_laborers = { value = 0 every_buildings_in_location = { limit = { building_pop_type = laborers } "
            "add = building_employed_amount } }") in " ".join((MOD / jr.VALUES).read_text(encoding="utf-8").split())

    # the conversions: the planner's own laborers are replaced, other classes kept, the peasants' groups largest first
    pops = {"a": [sp.Pop("peasants", 10.0, "x", "r"), sp.Pop("peasants", 2.0, "y", "r"), sp.Pop("laborers", 0.5, "x", "r")],
            "b": [sp.Pop("peasants", 1.0, "x", "r")], "c": [sp.Pop("peasants", 5.0, "x", "r")]}
    planner = [sp.PopConversion("a", "peasants", "laborers", 4.0, "x", "r"), sp.PopConversion("a", "peasants", "burghers", 1.0, "x", "r")]
    out = sp.with_setup_laborers(pops, planner, {"a": 11.0, "b": 3.0})
    got = {(c.location, c.to_type, c.culture): c.size_k for c in out}
    assert got[("a", "burghers", "x")] == 1.0
    assert got[("a", "laborers", "x")] == pytest.approx(10.0 * 0.98 - 1.0)   # the largest group first, 98 % of it at most
    assert got[("a", "laborers", "y")] == pytest.approx(11.0 - 0.5 - (10.0 * 0.98 - 1.0))  # then the next; 0.5 were there
    assert got[("b", "laborers", "x")] == pytest.approx(0.98)                # too few peasants: what there is
    assert not any(c.location == "c" for c in out)                           # no target: nothing
    assert sp.with_setup_laborers(pops, planner, {}) == planner              # laborers not listed: the planner's own

    # the written setup holds them
    written = sp.parse_pops((MOD / sp.POPS_SETUP_PATH).read_text(encoding="utf-8-sig"))
    setup_total = sum(p.size_k for groups in written.values() for p in groups if p.type == "laborers")
    assert setup_total == pytest.approx(total, rel=0.01), "run ppc build (the pops setup)"
