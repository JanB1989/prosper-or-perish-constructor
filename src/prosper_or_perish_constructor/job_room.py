"""Job room: a production building's room for its workers' class follows its staffing (2026-11-27, Jan).

The engine counts a building's jobs (employment_size x level) in its pop type's equilibrium whether the jobs are
offered or not: a building that laid its workers off, or that never found any, still lets people promote into the
class, and they sit idle (run b18a10d6, 1837: 1.5 M burghers and 15.9 M laborers unemployed next to unfilled jobs in
open buildings). Jan: "If a building is full, it should give ... just what its employment size is. But if it's empty,
it should give not what its employment size is ... I want surplus to demote."

Two lines per level do that, both for the building's own pop type and both the size of its jobs E:

    raw_modifier = { local_<pop>_desired_pop = -E }   # x input fulfilment
    modifier     = { local_<pop>_desired_pop =  E }   # x input fulfilment x staffing

Jobs and flat desired pop go into one sum in the engine, so the building's room is E x (1 - f + f x staffing), f the
average input fulfilment of its method slots: E when fully staffed, E x staffing when its inputs are supplied, and
never more than E. A new building opens no room of its own; it hires from the spare room the location already has
(the location ranks give burghers and laborers flat room) and brings its own room in as it fills. The AI counts both
lines in full, so they cancel in its score, and it values burgher and laborer room at zero anyway.

A closed building applies neither block and keeps all its jobs in the equilibrium, which is why production buildings
cannot be closed any more (building_shutdown.py). Read from the 1.4.9 code and private notes, not tested in game.

Written at finalize, after the employment cut: the size is read from the building's final employment_size at every
build, so it follows any change of a building's employment by itself. Every blueprint building with a goods output
carries the lines when its pop type has an equilibrium (``has_cap = yes`` in the pop type: nobles, clergy, burghers,
laborers, soldiers; peasants, tribesmen and slaves have none), food makers included (Jan, 2026-11-27: "they can
still be subsidized. Same logic. We can just apply it to everything"; the first version of that day left them out).
``[job_room] not_buildings`` takes single buildings out. The lines carry a marker comment; a building that leaves the
set loses them again. A line of the same key the building already has in that block is folded into ours (the engine
would otherwise see the key twice) and comes back when ours goes.

Game start (2026-11-27, three test games and a control game the same day): when a new game starts the engine first
employs the pops the setup defines and then fills every class up to its room from the peasants. The setup defines few
of them (2.4 M burghers, 2.0 M laborers); the rest of day 0 (3.9 M burghers, 45.3 M laborers in the control) is made by
that fill. With the two lines a building nobody works in yet gives no room, so the fill made nothing for it: per
location the loss was either all of the producers' jobs or none (burghers 2.34 M of 3.22 M producer jobs in 675
locations, laborers 11.3 M of 12.3 M), and the class does not come back by itself (a typical town promotes one burgher
a month). ``pp_job_room_start`` (on_game_start, a day in, once; never a pulse) does the fill for those jobs: per owned
location and class, the jobs of its open buildings that nobody fills (``pp_job_room_open_<pop>``, read from the
buildings in the running game) are filled from the peasants, every peasant pop giving the same share. The people get
the culture and religion the engine's own fill gives them (measured in the control game): those of the class's largest
pop in the location (98-100 % of the game-made people join it); where the class has no pop there, the owner's culture
and religion for an upper class, the peasants' own otherwise.

Setup groups first: where the setup gives a class several groups in a location (Stockholm's Swedish, Holsatian and
Lower Saxon burghers), the engine's start trimmed them all alike to the smaller room, and filling everything into the
largest would lose the others (third test game: the 604 burgher groups beside the largest held 106k people against
151k in the control). So the step first brings each group of such a class and location back to its setup size, the largest
first (``pp_job_room_group``, one generated line per group, read from the mod's pops setup at every build), within the
class's open jobs, and only then fills the rest into the largest. The largest has to be among them: in the fourth test
game only the others were brought back, Stockholm's Holsatians then outnumbered its trimmed Swedes and took the rest. The location variable ``pp_job_room_done_<pop>`` carries what the
groups took, for that one step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
import re
import tomllib

from prosper_or_perish_constructor import building_footprint as bf
from prosper_or_perish_constructor import building_shutdown as bs

CONFIG_SECTION = "job_room"
MARKER = "# job_room"
BLOCKS = (("raw_modifier", -1), ("modifier", 1))  # block -> sign of the line
POP_TYPES = Path("in_game/common/pop_types")
START_DELAY_DAYS = 1  # after the game's own fill of the classes, before the first monthly tick
VALUES = Path("in_game/common/script_values/pp_job_room_values.txt")
EFFECTS = Path("in_game/common/scripted_effects/pp_job_room_effects.txt")
ON_ACTION = Path("in_game/common/on_action/pp_job_room.txt")
HEADER = "\ufeff# Generated by ppc finalize (job_room.py); do not edit by hand.\n"
MAX_SHARE = "0.9"  # of a location's peasants, the most the start step moves into one class

_POP_RE = re.compile(r"^[ \t]*pop_type\s*=\s*(?P<pop>[A-Za-z_0-9]+)", re.MULTILINE)
_EMPLOYMENT_RE = re.compile(r"^[ \t]*employment_size\s*=\s*(?P<value>[^\s#{}]+)", re.MULTILINE)
_MARKED_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>local_[a-z_0-9]+_desired_pop|local_pp_job_room_[a-z_0-9]+)\s*=\s*\S+[ \t]*#\s*job_room(?:[ \t]+base[ \t]+(?P<base>-?[0-9.]+))?[^\n]*\n?",
    re.MULTILINE,
)
_HAS_CAP_RE = re.compile(r"^[ \t]*has_cap\s*=\s*(?P<value>yes|no)", re.MULTILINE)
_UPPER_RE = re.compile(r"^[ \t]*upper\s*=\s*(?P<value>yes|no)", re.MULTILINE)


@dataclass(frozen=True)
class Config:
    not_buildings: frozenset[str]
    enabled: bool = True  # false: no building carries the lines (control builds for in-game comparisons)


@dataclass
class Result:
    written: list[str] = field(default_factory=list)
    pop_types: list[str] = field(default_factory=list)  # the pop types with an equilibrium
    other_pop: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    files_changed: int = 0


def load_config(project: Path) -> Config:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig")).get(CONFIG_SECTION)
    if not isinstance(raw, dict) or not isinstance(raw.get("not_buildings"), list):
        raise ValueError(f"{project}: [{CONFIG_SECTION}] needs not_buildings (a list of building keys, may be empty)")
    return Config(frozenset(raw["not_buildings"]), bool(raw.get("enabled", True)))


def capped_pop_types(vanilla_root: Path, mod_root: Path) -> frozenset[str]:
    """The pop types with an equilibrium (``has_cap = yes``)."""
    return _flagged_pop_types(vanilla_root, mod_root, _HAS_CAP_RE)


def upper_pop_types(vanilla_root: Path, mod_root: Path) -> frozenset[str]:
    """The upper classes (``upper = yes``): a pop of theirs the game makes at game start gets the owner's culture."""
    return _flagged_pop_types(vanilla_root, mod_root, _UPPER_RE)


def _flagged_pop_types(vanilla_root: Path, mod_root: Path, _HAS_CAP_RE: re.Pattern[str]) -> frozenset[str]:
    """The pop types whose definition sets a yes / no key to yes: vanilla's definitions, then the mod's (a REPLACE is
    the whole definition, an INJECT adds to vanilla's)."""
    capped: dict[str, bool] = {}
    for path in bf.vanilla_files(vanilla_root, POP_TYPES):
        text = bf._read(path)
        for block in bf.blocks(path, text):
            match = _HAS_CAP_RE.search(bf._depth_zero_text(text[block.open + 1: block.close]))
            capped[block.key] = bool(match and match.group("value") == "yes")
    for path in sorted((mod_root / POP_TYPES).glob("*.txt")):
        text = bf._read(path)
        for block in bf.blocks(path, text):
            match = _HAS_CAP_RE.search(bf._depth_zero_text(text[block.open + 1: block.close]))
            if block.mode in bf._INJECT_MODES:
                if match:
                    capped[block.key] = match.group("value") == "yes"
            else:
                capped[block.key] = bool(match and match.group("value") == "yes")
    return frozenset(name for name, value in capped.items() if value)


def fmt(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in ("-0", "") else text


def _top_block(body: str, name: str) -> tuple[re.Match[str], int, int] | None:
    """The first top-level ``name = { ... }`` of the body: (match, open, close)."""
    zero = bf._depth_zero_opens(body)
    pairs = bf._brace_pairs(body)
    for match in re.finditer(rf"^(?P<indent>[ \t]*){name}\s*=\s*\{{", body, re.MULTILINE):
        if match.end() - 1 in zero:
            return match, match.end() - 1, pairs[match.end() - 1]
    return None


def _clear(body: str, drop_empty: bool) -> str:
    """Take our marked lines out of the top-level modifier blocks: a folded line comes back at its base value. A block
    left empty goes with ``drop_empty`` (the building leaves the set); otherwise it stays where it is, so writing the
    lines again puts them back in the same place whatever later passes appended to the building."""
    for name, _sign in BLOCKS:
        found = _top_block(body, name)
        if found is None:
            continue
        match, open_, close = found
        inner = body[open_ + 1: close]
        if MARKER not in inner:
            continue

        def restore(m: re.Match[str]) -> str:
            return f"{m.group('indent')}{m.group('key')} = {m.group('base')}\n" if m.group("base") is not None else ""

        inner = _MARKED_RE.sub(restore, inner)
        if inner.strip() or not drop_empty:
            body = body[: open_ + 1] + inner + body[close:]
        else:
            end = close + 1 + (body[close + 1: close + 2] == "\n")
            body = body[: match.start()] + body[end:]
    return body


def set_room(body: str, pop: str | None, employment: Decimal | None) -> str:
    """The body with the two job room lines of ``pop`` at ``employment`` (None: without them)."""
    body = _clear(body, drop_empty=pop is None or employment is None)
    if pop is None or employment is None:
        return body
    key = f"local_{pop}_desired_pop"
    own = re.compile(rf"^[ \t]*{key}\s*=\s*(?P<value>-?[0-9.]+)[^\n]*\n?", re.MULTILINE)
    for name, sign in BLOCKS:
        value = employment * sign
        found = _top_block(body, name)
        if found is None:
            indent = bf._body_indent(body)
            block = f"{indent}{name} = {{\n{indent}{bf._step(indent)}{key} = {fmt(value)} {MARKER}\n{indent}}}\n"
            head = body.rstrip(" \t")
            body = head + ("" if head.endswith("\n") or not head else "\n") + block
            continue
        match, open_, close = found
        indent = match.group("indent")
        inner = body[open_ + 1: close]
        note = MARKER
        existing = own.search(inner)
        if existing:
            base = Decimal(existing.group("value"))
            value += base
            note = f"{MARKER} base {fmt(base)}"
            inner = inner[: existing.start()] + inner[existing.end():]
        line = f"\n{indent}{bf._step(indent)}{key} = {fmt(value)} {note}"
        if not inner.strip():
            body = body[: open_ + 1] + line + f"\n{indent}" + body[close:]
        else:
            body = body[: open_ + 1] + line + ("" if inner.startswith("\n") else "\n") + inner + body[close:]
    return body


SetupGroup = tuple[str, str, str, str, str]  # location, pop type, culture, religion, size in thousands


def setup_groups(mod_root: Path, pop_types: list[str]) -> list[SetupGroup]:
    """The setup's groups of a class in a location where it has several, the largest first, for the classes that
    carry the lines (the mod's pops setup, written by the World Builder stage)."""
    from prosper_or_perish_constructor.worldbuilder import start_placement as sp

    path = mod_root / sp.POPS_SETUP_PATH
    if not path.is_file():
        return []
    out: list[SetupGroup] = []
    for location, pops in sorted(sp.parse_pops(path.read_text(encoding="utf-8-sig")).items()):
        for pop in pop_types:
            sizes: dict[tuple[str, str], Decimal] = {}
            for entry in pops:
                if entry.type == pop and entry.culture and entry.religion:
                    key = (entry.culture, entry.religion)
                    sizes[key] = sizes.get(key, Decimal(0)) + Decimal(str(entry.size_k))
            if len(sizes) < 2:
                continue
            out += [(location, pop, culture, religion, fmt(sizes[(culture, religion)]))
                    for culture, religion in sorted(sizes, key=lambda key: (-sizes[key], key))]
    return out


def support_files(pop_types: list[str], upper: frozenset[str], groups: list[SetupGroup] = ()) -> dict[Path, str]:
    """The one-off start step for the pop types that carry the lines: script values, effects and on_action."""
    values = HEADER + (
        "# Location scope. pp_job_room_open_<class>: the jobs for the class in the open buildings here that nobody fills,\n"
        "# in thousands. pp_job_room_left_<class>: those the start step has not filled yet (the setup's groups come\n"
        "# first). pp_job_room_share_<class>: the share of the location's peasants that fills them, at most "
        f"{MAX_SHARE}.\n"
    )
    steps = ""
    grouped = {group[1] for group in groups}  # only these classes ever set pp_job_room_done_<class>
    for pop in pop_types:
        values += (
            f"pp_job_room_open_{pop} = {{\n\tvalue = 0\n\tevery_buildings_in_location = {{\n"
            f"\t\tlimit = {{ building_pop_type = {pop} is_opened = yes }}\n"
            "\t\tadd = { value = building_employment_size_amount subtract = building_employed_amount min = 0 }\n\t}\n}\n"
            f"pp_job_room_left_{pop} = {{\n\tvalue = pp_job_room_open_{pop}\n"
            + (f"\tif = {{\n\t\tlimit = {{ has_variable = pp_job_room_done_{pop} }}\n"
               f"\t\tsubtract = var:pp_job_room_done_{pop}\n\t}}\n" if pop in grouped else "")
            + "\tmin = 0\n}\n"
            f"pp_job_room_share_{pop} = {{\n\tvalue = pp_job_room_left_{pop}\n"
            f"\tdivide = {{ value = num_pop_type:peasants min = 0.001 }}\n\tmin = 0\n\tmax = {MAX_SHARE}\n}}\n"
        )

        def move(extra: str, tabs: str) -> str:
            return (f"{tabs}every_pop = {{\n{tabs}\tlimit = {{ pop_type = pop_type:peasants }}\n"
                    f"{tabs}\tsplit_pop = {{ fraction = scope:pp_job_room_share type = pop_type:{pop}{extra} }}\n{tabs}}}\n")

        like = " culture = scope:pp_job_room_like.culture religion = scope:pp_job_room_like.religion"
        owner = " culture = scope:pp_job_room_location.owner.culture religion = scope:pp_job_room_location.owner.religion"
        steps += (
            f"\t# {pop}\n\tif = {{\n\t\tlimit = {{ pp_job_room_share_{pop} > 0 }}\n"
            f"\t\tsave_temporary_scope_value_as = {{ name = pp_job_room_share value = pp_job_room_share_{pop} }}\n"
            f"\t\tif = {{\n\t\t\tlimit = {{ any_pop = {{ pop_type = pop_type:{pop} }} }}\n"
            f"\t\t\tordered_pop = {{\n\t\t\t\tlimit = {{ pop_type = pop_type:{pop} }}\n\t\t\t\torder_by = pop_size\n"
            "\t\t\t\tmax = 1\n\t\t\t\tsave_temporary_scope_as = pp_job_room_like\n\t\t\t}\n"
            + move(like, "\t\t\t") + "\t\t}\n"
        )
        if pop in upper:
            steps += "\t\telse_if = {\n\t\t\tlimit = { exists = owner }\n" + move(owner, "\t\t\t") + "\t\t}\n"
        steps += "\t\telse = {\n" + move("", "\t\t\t") + "\t\t}\n\t}\n"
        if pop in grouped:
            steps += f"\tremove_variable = pp_job_room_done_{pop}\n"
    effects = HEADER + (
        "# Location scope, once, a day into a new game (on_action/pp_job_room.txt). When a new game starts the engine fills\n"
        "# every class up to its room from the peasants, but a production building nobody works in yet gives no room\n"
        "# (job_room.py), so nothing was made for its jobs. This does that fill: per class, the open jobs of the\n"
        "# location's buildings are filled from its peasants, every peasant pop giving the same share (read one class\n"
        "# after the other, each over the peasants left). Culture and religion as in the engine's own fill: those of the\n"
        "# class's largest pop here; where it has none, the owner's for an upper class, the peasants' own otherwise.\n"
        "pp_job_room_restore = {\n\tsave_temporary_scope_as = pp_job_room_location\n" + steps + "}\n\n"
        "# Location scope, before pp_job_room_restore: one group of a class the setup defines here beside the class's\n"
        "# largest. The engine's start trimmed the setup's groups alike; this brings the group back to its setup size from\n"
        "# the peasants, within the class's open jobs, and notes what it took (pp_job_room_done_<class>).\n"
        "pp_job_room_group = {\n"
        "\tif = {\n\t\tlimit = { pp_job_room_left_$pop$ > 0 }\n"
        "\t\tsave_temporary_scope_value_as = { name = pp_job_room_want value = $size$ }\n"
        "\t\trandom_pop = {\n"
        "\t\t\tlimit = { pop_type = pop_type:$pop$ culture = culture:$culture$ religion = religion:$religion$ }\n"
        "\t\t\tsave_temporary_scope_value_as = { name = pp_job_room_want value = { value = $size$ subtract = pop_size min = 0 } }\n"
        "\t\t}\n"
        "\t\tsave_temporary_scope_value_as = { name = pp_job_room_move value = { value = scope:pp_job_room_want max = pp_job_room_left_$pop$ } }\n"
        "\t\tif = {\n\t\t\tlimit = { scope:pp_job_room_move > 0.0005 }\n"
        "\t\t\tsave_temporary_scope_value_as = { name = pp_job_room_share value = { value = scope:pp_job_room_move "
        f"divide = {{ value = num_pop_type:peasants min = 0.001 }} max = {MAX_SHARE} }} }}\n"
        "\t\t\tevery_pop = {\n\t\t\t\tlimit = { pop_type = pop_type:peasants }\n"
        "\t\t\t\tsplit_pop = { fraction = scope:pp_job_room_share type = pop_type:$pop$ culture = culture:$culture$ religion = religion:$religion$ }\n"
        "\t\t\t}\n"
        "\t\t\tif = {\n\t\t\t\tlimit = { has_variable = pp_job_room_done_$pop$ }\n"
        "\t\t\t\tchange_variable = { name = pp_job_room_done_$pop$ add = scope:pp_job_room_move }\n\t\t\t}\n"
        "\t\t\telse = {\n\t\t\t\tset_variable = { name = pp_job_room_done_$pop$ value = scope:pp_job_room_move }\n\t\t\t}\n"
        "\t\t}\n\t}\n}\n"
    )
    rows = ""
    by_location: dict[str, list[SetupGroup]] = {}
    for group in groups:
        by_location.setdefault(group[0], []).append(group)
    for location, items in sorted(by_location.items()):
        rows += f"\t\tlocation:{location} = {{\n" + "".join(
            f"\t\t\tpp_job_room_group = {{ pop = {pop} culture = {culture} religion = {religion} size = {size} }}\n"
            for _location, pop, culture, religion, size in items) + "\t\t}\n"
    on_action = HEADER + (
        f"# Once, {START_DELAY_DAYS} day into a new game: after the game's own fill of the classes, before the first monthly tick.\n"
        "on_game_start = {\n\ton_actions = {\n"
        f"\t\tdelay = {{ days = {START_DELAY_DAYS} }}\n\t\tpp_job_room_start\n\t}}\n}}\n\n"
        "pp_job_room_start = {\n\teffect = {\n"
        "\t\t# where the setup gives a class several groups in a location: each back to its setup size, the largest first\n" + rows +
        "\t\t# then the open jobs left, into the class's largest group\n"
        "\t\tevery_country = {\n\t\t\tevery_owned_location = {\n"
        "\t\t\t\tpp_job_room_restore = yes\n\t\t\t}\n\t\t}\n\t}\n}\n"
    )
    return {VALUES: values, EFFECTS: effects, ON_ACTION: on_action}


STALE = (Path("main_menu/common/modifier_type_definitions/pp_job_room_modifier_types.txt"),
         Path("main_menu/common/modifier_icons/pp_job_room_modifier_icons.txt"),
         Path("main_menu/localization/english/pp_job_room_l_english.yml"))  # the counter of the first start step


def targets(repo: Path, mod_root: Path, project: Path, vanilla_root: Path) -> tuple[dict[str, tuple[str, Decimal]], Result]:
    """Building key -> (pop type, employment per level) for the buildings that carry the lines, and who was left out."""
    config = load_config(project)
    owners = bf.owner_blocks(mod_root, vanilla_root)
    vanilla = bf.vanilla_definitions(vanilla_root)
    values = bf.script_values(vanilla_root, mod_root)
    capped = capped_pop_types(vanilla_root, mod_root)
    result = Result(pop_types=sorted(capped))
    out: dict[str, tuple[str, Decimal]] = {}
    unresolved: list[str] = []
    for key in bs.producers(repo, mod_root, vanilla_root) if config.enabled else ():
        block = owners[key]
        text = bf._read(block.path)
        body = text[block.open + 1: block.close]
        inherited = vanilla.get(key, "") if block.mode in bf._INJECT_MODES else ""
        if key in config.not_buildings:
            result.excluded.append(key)
            continue
        tops = bf._depth_zero_text(body) + "\n" + (bf._depth_zero_text(inherited) if inherited else "")
        pop = _POP_RE.search(tops)
        if not pop or pop.group("pop") not in capped:
            result.other_pop.append(key)
            continue
        size = _EMPLOYMENT_RE.search(tops)
        employment = bf._resolve(size.group("value"), values) if size else None
        if employment is None or employment <= 0:
            unresolved.append(f"{key}: employment_size {size.group('value') if size else '(none)'}")
            continue
        if block.mode in bf._INJECT_MODES:
            unresolved.append(f"{key}: an INJECT cannot add to the vanilla modifier blocks; make the blueprint a REPLACE")
            continue
        out[key] = (pop.group("pop"), employment)
    if unresolved:
        raise ValueError("job room:\n" + "\n".join(f"- {u}" for u in unresolved))
    result.written = sorted(out)
    return out, result


def apply(repo: Path, mod_root: Path, project: Path, vanilla_root: Path) -> Result:
    wanted, result = targets(repo, mod_root, project, vanilla_root)
    owners = bf.owner_blocks(mod_root, vanilla_root)
    edits: dict[Path, list[tuple[bf.Block, tuple[str, Decimal] | None]]] = {}
    for key, _rule in bs.blueprint_rules(repo).items():
        block = owners.get(key)
        if block is not None and block.mode not in bf._INJECT_MODES:
            edits.setdefault(block.path, []).append((block, wanted.get(key)))
    for path, items in edits.items():
        original = bf._read(path)
        text = original
        for block, target in sorted(items, key=lambda item: -item[0].open):
            body = text[block.open + 1: block.close]
            if target is None and MARKER not in body:
                continue
            new = set_room(body, *(target if target else (None, None)))
            text = text[: block.open + 1] + new + text[block.close:]
        if text != original:
            path.write_text(text, encoding="utf-8-sig", newline="\n")
            result.files_changed += 1
    upper = upper_pop_types(vanilla_root, mod_root)
    pops = sorted({pop for pop, _employment in wanted.values()})
    for relative, text in support_files(pops, upper, setup_groups(mod_root, pops)).items():
        path = mod_root / relative
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            result.files_changed += 1
    for relative in STALE:
        if (mod_root / relative).exists():
            (mod_root / relative).unlink()
            result.files_changed += 1
    return result


def check(repo: Path, mod_root: Path, project: Path, vanilla_root: Path) -> list[str]:
    """Buildings whose compiled definition does not carry exactly the two lines it should (run ppc build / sync)."""
    wanted, _result = targets(repo, mod_root, project, vanilla_root)
    owners = bf.owner_blocks(mod_root, vanilla_root)
    problems: list[str] = []
    for key, _rule in sorted(bs.blueprint_rules(repo).items()):
        block = owners.get(key)
        if block is None or block.mode in bf._INJECT_MODES:
            continue
        text = bf._read(block.path)
        body = text[block.open + 1: block.close]
        target = wanted.get(key)
        if set_room(body, *(target if target else (None, None))) != body:
            problems.append(f"{key}: job room lines not written (run ppc build)")
    upper = upper_pop_types(vanilla_root, mod_root)
    pops = sorted({pop for pop, _employment in wanted.values()})
    for relative, text in support_files(pops, upper, setup_groups(mod_root, pops)).items():
        path = mod_root / relative
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            problems.append(f"{relative}: not current (run ppc build)")
    return problems


def summary(result: Result) -> str:
    return (
        f"Job room: {len(result.written)} production buildings give room for their class only as far as they are staffed "
        f"(classes with an equilibrium: {', '.join(result.pop_types)}; {len(result.other_pop)} buildings of other pop types left out"
        + (f", {len(result.excluded)} excluded by name" if result.excluded else "")
        + f"), {result.files_changed} files changed."
    )
