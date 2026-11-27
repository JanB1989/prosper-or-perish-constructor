"""Job room (2026-11-27, Jan): a production building's room for its workers' class follows its staffing."""

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


def test_set_room_writes_one_line_per_block_and_takes_them_out_again() -> None:
    body = "\n\tpop_type = burghers\n\tmodifier = {\n\t\tlocal_glass_output_modifier = -0.005\n\t}\n"
    out = jr.set_room(body, "burghers", Decimal("0.25"))
    assert "\tmodifier = {\n\t\tlocal_burghers_desired_pop = 0.25 # job_room\n\t\tlocal_glass_output_modifier = -0.005\n\t}\n" in out
    assert "\traw_modifier = {\n\t\tlocal_burghers_desired_pop = -0.25 # job_room\n\t}\n" in out
    assert jr.set_room(out, "burghers", Decimal("0.25")) == out
    assert jr.set_room(out, None, None) == body


def test_set_room_keeps_its_place_when_later_lines_follow() -> None:
    """Other finalize passes append to the building after this one; writing again must not move the blocks."""
    out = jr.set_room("\n\tpop_type = laborers\n", "laborers", Decimal("0.8")) + "\tai_construct_weight = { value = 0 }\n"
    assert jr.set_room(out, "laborers", Decimal("0.8")) == out
    assert jr.set_room(out, "laborers", Decimal("0.4")) == out.replace("0.8", "0.4")


def test_set_room_folds_a_line_of_the_same_key_and_gives_it_back() -> None:
    """The engine must not see the key twice in one block."""
    body = "\n\tmodifier = {\n\t\tlocal_laborers_desired_pop = 0.003\n\t}\n\traw_modifier = {\n\t\tfree_building_levels = 1\n\t}\n"
    out = jr.set_room(body, "laborers", Decimal("0.8"))
    assert out.count("local_laborers_desired_pop") == 2
    assert "local_laborers_desired_pop = 0.803 # job_room base 0.003" in out
    assert "local_laborers_desired_pop = -0.8 # job_room\n" in out
    assert jr.set_room(out, "laborers", Decimal("0.8")) == out
    assert jr.set_room(out, None, None) == body


def test_room_is_the_filled_jobs() -> None:
    """jobs - f x raw + f x staffing x modifier with both lines at the job count: the jobs when full, the staffed share
    when the inputs are supplied, never more than the jobs."""
    jobs = Decimal("0.25")
    for fulfilment in (Decimal("1"), Decimal("0.5"), Decimal("0")):
        for staffing in (Decimal("0"), Decimal("0.4"), Decimal("1")):
            room = jobs - fulfilment * jobs + fulfilment * staffing * jobs
            assert room <= jobs
            if staffing == 1:
                assert room == jobs
            if fulfilment == 1:
                assert room == jobs * staffing


def test_the_compiled_buildings_carry_the_lines(targets, vanilla) -> None:
    wanted, result = targets
    assert jr.check(ROOT, MOD, PROJECT, vanilla) == [], "run ppc build (job_room)"
    assert len(wanted) > 150
    owners = bf.owner_blocks(MOD, vanilla)
    for key, (pop, employment) in wanted.items():
        block = owners[key]
        body = bf._read(block.path)[block.open + 1: block.close]
        tops = bf._depth_zero_text(body)
        # the final employment_size (after the employment cut) of the building's own pop type
        assert re.search(rf"^[ \t]*pop_type\s*=\s*{pop}\b", tops, re.MULTILINE), key
        size = re.search(r"^[ \t]*employment_size\s*=\s*([^\s#{}]+)", tops, re.MULTILINE).group(1)
        assert bf._resolve(size, bf.script_values(vanilla, MOD)) == employment, key
        for name, sign in jr.BLOCKS:
            _match, open_, close = jr._top_block(body, name)
            lines = re.findall(rf"local_{pop}_desired_pop\s*=\s*(-?[0-9.]+)[ \t]*# job_room(?: base (-?[0-9.]+))?", body[open_ + 1: close])
            assert len(lines) == 1, (key, name)
            value, base = lines[0]
            assert Decimal(value) - Decimal(base or "0") == employment * sign, (key, name)
            # the key appears once in the block
            assert len(re.findall(rf"local_{pop}_desired_pop\s*=", body[open_ + 1: close])) == 1, (key, name)
        assert body.count("# job_room") == 2, key  # the two room lines and nothing else


def test_who_carries_the_lines(targets, vanilla) -> None:
    """Every production building whose workers' class has an equilibrium, food makers included (Jan, 2026-11-27: "they
    can still be subsidized. Same logic. We can just apply it to everything")."""
    wanted, result = targets
    assert jr.load_config(PROJECT).not_buildings == frozenset()
    # the classes people promote into: all but peasants, tribesmen and slaves (has_cap in the pop types)
    assert result.pop_types == ["burghers", "clergy", "laborers", "nobles", "soldiers"]
    assert jr.capped_pop_types(vanilla, MOD) == set(result.pop_types)
    for key in ("glass_guild", "tannery", "mason", "charcoal_maker", "tar_kiln", "iron_mine", "hired_labor_yard", "scriptorium"):
        assert key in wanted, key
    for key in ("cookshop", "public_kitchen", "tavern", "grange", "victualling_yard", "ocean_fishery"):
        assert key in wanted, key
    # buildings worked by peasants or slaves have no equilibrium to follow
    for key in ("wheat_farm", "market_village", "rural_daywork_yard", "sugar_plantation"):
        assert key in result.other_pop and key not in wanted, key
    # only producers, and every producer is in exactly one group
    producers = set(bs.producers(ROOT, MOD, vanilla))
    groups = [set(wanted), set(result.other_pop), set(result.excluded)]
    assert set().union(*groups) == producers
    assert sum(len(group) for group in groups) == len(producers)
    assert len(wanted) > 190


def test_the_size_follows_the_buildings_employment(targets, vanilla) -> None:
    """Nothing is stored: the lines are the building's final employment_size, read at every build, so a change of a
    building's employment (or of the employment cut) moves them by itself."""
    wanted, _result = targets
    sizes = {employment for _pop, employment in wanted.values()}
    assert len(sizes) > 3  # buildings of different sizes carry different lines
    assert wanted["glass_guild"] == ("burghers", Decimal("0.25"))  # 0.3 cut to 0.25 ([building_scaling.employment_cut])
    assert wanted["mason"] == ("laborers", Decimal("0.8"))  # 1.0 cut to 0.8
    assert jr.set_room("\n\tpop_type = laborers\n", "laborers", Decimal("0.6")).count("0.6 # job_room") == 2


def test_no_other_building_carries_a_marked_line(targets, vanilla) -> None:
    wanted, _result = targets
    owners = bf.owner_blocks(MOD, vanilla)
    for key, block in owners.items():
        if key in wanted:
            continue
        assert jr.MARKER not in bf._read(block.path)[block.open + 1: block.close], key


def test_a_building_that_cannot_be_closed_is_what_makes_this_work(targets, vanilla) -> None:
    """A closed building applies neither block and keeps its jobs in the equilibrium, so every building with the lines
    must be one nobody can close."""
    wanted, _result = targets
    owners = bf.owner_blocks(MOD, vanilla)
    for key in wanted:
        block = owners[key]
        tops = bf._depth_zero_text(bf._read(block.path)[block.open + 1: block.close])
        assert bs._ANY_FLAG_RE["can_close"].search(tops).group("value") == "no", key


def test_the_start_step_fills_the_jobs_the_games_own_fill_left_empty(targets, vanilla) -> None:
    """When a new game starts the engine employs the setup's pops and then fills every class up to its room from the
    peasants. A production building nobody works in yet gives no room, so nothing was made for its jobs (in game
    2026-11-27, against a control game: burghers 1.54 M on day 0 instead of 3.88 M, laborers 34.0 M instead of 45.3 M).
    One step a day into a new game fills the open jobs from the peasants, with the culture and religion the engine's
    own fill gives: the class's largest pop in the location, else the owner's for an upper class. Once, no pulse."""
    wanted, _result = targets
    pops = sorted({pop for pop, _employment in wanted.values()})
    assert {"burghers", "laborers"} <= set(pops)
    upper = jr.upper_pop_types(vanilla, MOD)
    assert {"nobles", "clergy", "burghers"} <= upper and not {"laborers", "soldiers", "peasants"} & upper
    groups = jr.setup_groups(MOD, pops)
    files = jr.support_files(pops, upper, groups)
    for relative, text in files.items():
        assert (MOD / relative).read_text(encoding="utf-8") == text, f"{relative}: run ppc build (job_room)"
    for relative in jr.STALE:
        assert not (MOD / relative).exists(), relative
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
        # a class without setup groups never sets the note, so nothing reads or removes it (the game logs a variable
        # that is read and never set)
        assert (f"pp_job_room_done_{pop}" in values + effects.replace("$pop$", "")) == grouped or grouped
        assert (f"pp_job_room_share_{pop} = {{ value = pp_job_room_left_{pop} divide = {{ value = num_pop_type:peasants "
                f"min = 0.001 }} min = 0 max = {jr.MAX_SHARE} }}") in values
        assert (f"remove_variable = pp_job_room_done_{pop}" in effects) == grouped  # the note lives for that one step
        block = effects[effects.index(f"# {pop} "):]
        block = block[: block.index(" # ", 3)] if " # " in block[3:] else block
        assert f"limit = {{ pp_job_room_share_{pop} > 0 }}" in block
        # into the class's largest pop here, as the engine's own fill does
        assert (f"limit = {{ any_pop = {{ pop_type = pop_type:{pop} }} }} ordered_pop = {{ limit = {{ pop_type = pop_type:{pop} }} "
                "order_by = pop_size max = 1 save_temporary_scope_as = pp_job_room_like }") in block
        assert (f"split_pop = {{ fraction = scope:pp_job_room_share type = pop_type:{pop} culture = scope:pp_job_room_like.culture "
                "religion = scope:pp_job_room_like.religion }") in block
        owner_rule = "culture = scope:pp_job_room_location.owner.culture religion = scope:pp_job_room_location.owner.religion"
        assert (owner_rule in block) == (pop in upper), pop
        assert f"split_pop = {{ fraction = scope:pp_job_room_share type = pop_type:{pop} }}" in block
        assert block.count("limit = { pop_type = pop_type:peasants }") == (3 if pop in upper else 2)  # only peasants give
    assert "save_temporary_scope_as = pp_job_room_location" in effects
    # once, at game start, after the game's own fill; never from a pulse
    assert f"on_game_start = {{ on_actions = {{ delay = {{ days = {jr.START_DELAY_DAYS} }} pp_job_room_start }} }}" in on_action
    assert "every_country = { every_owned_location = { pp_job_room_restore = yes } }" in on_action
    # where the setup gives a class several groups, each comes back at its setup size, the largest first, so it is
    # still the largest when the rest is filled into "the largest" (Stockholm's Swedish and German burghers)
    stockholm = [g for g in groups if g[:2] == ("stockholm", "burghers")]
    assert stockholm == [("stockholm", "burghers", "swedish", "catholic", "0.91"),
                         ("stockholm", "burghers", "holsatian", "catholic", "0.74"),
                         ("stockholm", "burghers", "lower_saxon", "catholic", "0.44")]
    assert len(groups) > 1500 and {g[1] for g in groups} <= set(pops)
    assert "laborers" not in {g[1] for g in groups}  # the setup gives laborers one group per location
    assert ("location:stockholm = { pp_job_room_group = { pop = burghers culture = swedish religion = catholic size = 0.91 } "
            "pp_job_room_group = { pop = burghers culture = holsatian religion = catholic size = 0.74 } "
            "pp_job_room_group = { pop = burghers culture = lower_saxon religion = catholic size = 0.44 } }") in on_action
    assert on_action.index("location:stockholm = {") < on_action.index("every_country = {")
    group = effects[effects.index("pp_job_room_group = {"):]
    for token in ("$pop$", "$culture$", "$religion$", "$size$"):  # an unused argument makes the call a silent no-op
        assert token in group, token
    assert "limit = { pp_job_room_left_$pop$ > 0 }" in group and "max = pp_job_room_left_$pop$" in group
    assert "value = { value = $size$ subtract = pop_size min = 0 }" in group
    assert ("split_pop = { fraction = scope:pp_job_room_share type = pop_type:$pop$ culture = culture:$culture$ "
            "religion = religion:$religion$ }") in group
    assert "change_variable = { name = pp_job_room_done_$pop$ add = scope:pp_job_room_move }" in group
    for folder in ("in_game/common/on_action", "in_game/common/scripted_effects", "in_game/events"):
        for path in (MOD / folder).glob("*.txt"):
            if path.name in (jr.ON_ACTION.name, jr.EFFECTS.name):
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            assert "pp_job_room_restore" not in text and "pp_job_room_start" not in text, path.name
