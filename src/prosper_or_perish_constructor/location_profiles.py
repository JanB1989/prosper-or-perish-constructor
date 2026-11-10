"""Location Profiles (script side: storage, edits, assignment, the monthly pass). Contract: docs/location_profiles.md.

Branch location-profiles, 2026-11-07, Jan: the player defines profiles (an icon, a colour, ordered build rules) and
assigns them to locations on the map. In a location with a profile the profile's rules build, as a rule group of the
monthly pass (``pp_cplan_run``) with its own budget that saves (its purse); the global Construction Plan rules still
build there what the profile does not set (its rules' targets, the global groups it switches off). Script cannot
create named data while the game runs, so a profile is a generated slot ``k = 1..slots``.

Beside its profile a location carries its marks (Jan, 2026-11-10: "in this location, also expand wheat"): a good
(``location_plan.py``, ``pp_lplan_g_<good>``) or a building (a building type on the location's list ``pp_lplan_b``).
The same pass runs them after the location's profile rules (a location with marks and no profile gets its turn too).
A mark is forced (Jan, the same evening): no payback limit and no market limit; inside one location the marks whose
next level has a profit to measure go first, the best payback first, then the rest in mark order (hand-written
``pp_lplan_location_turn``). A goods mark runs the generated ``pp_lprof_t_<good>`` a profile rule with that target
runs. Marks add: they switch nothing off. This module writes ``pp_lplan_location_marks`` (the goods marks in the
picker's order, numbered), the helpers of a building's mark (``pp_lplan_b_newest``: the newest tier of the marked
building's line the country can build; ``pp_lplan_b_upgrade_here``: an older tier of it stands here, so the
construction is the game's upgrade; ``pp_lplan_b_staff``: its workers) and, for the location window's row "Also build
here", the quick candidates: per good 1 while a building that makes it stands in the location and the good is not
marked (``pp_lplan_quick_<good>``), and the room the row has left for the next chunk of them
(``pp_lplan_quick_room_<n>``).

The Locations group's locations take turns (Jan, 2026-11-10): a number per location, a place on the country where the
last look stopped (hand-written ``pp_lprof_look``, script value ``pp_lprof_turn``).

Cost independent of the slot count (2026-11-07, Jan: up to 100 profiles): every location with a profile carries a copy
of it (icon, colour, each rule's target and payback limit), written on assign and whenever its slot is edited; the
monthly pass and the map badge read only the copy. The editor shows one edit buffer (country variables
``pp_lprof_e_*``, a copy of the slot it edits); its buttons pass the slot flag ``e`` (the buffer's slot). A button
reads its slot into a staged copy (``pp_lprof_s_*``), edits that, writes it back and passes it on (buffer, locations).
Parametrized scripted effects expand where they are called, so the only per-slot script is the slot number of a flag
and the read and write of a slot (each instantiated once per slot, at one place); every edit works on fixed names.

The engine is hand-written in the mod (``scripted_effects/pp_location_profiles.txt``, the scripted GUIs in
``scripted_guis/pp_location_profiles.txt``); this module writes the parts that follow the plan items, the buildings and
``[location_profiles]``:

* ``scripted_effects/pp_location_profiles_generated.txt``: per rule target (a good, market access or a building
  category) the buildings it builds, the dispatch from a rule's stored target to them, the rules of a location in
  order, the slot resolve / read / write, the edits of the staged copy, the copy of a profile and the flag
  declarations;
* ``script_values/pp_location_profiles_generated.txt``: readouts (slot, buffer slot, rule states, first free slot,
  profiles in use) and the pass's helper values;
* ``scripted_triggers/pp_location_profiles_generated.txt``: the category and symbol key checks, "the country has
  profile locations" and the checks the global rules ask before they build in a profile's location (a rule of it
  names this good, a staple food, this building category).

A profile's icon is a good (a goods scope) or a flag: a building category or a symbol (``[location_profiles.symbols]``,
generic pictures such as a city or a harbour that build nothing; flag ``pp_sym_<name>``).

Targets: a good builds its producers (the buildings whose main good it is, as the Construction Plan's goods rules;
``logistics`` = market access builds the logistics buildings in the plan's order), a building category the player-
buildable building types of that category (no foreign, special, estate, organisation or event-only buildings). A
standing building grows highest tier first, while its next level pays back within the rule's limit; where none of the
target's buildings stands, the cheapest one that can be built here starts (its first level has no profit to measure).
Variables carry + 100 (a variable at 0 counts as unset; ``var:x = n`` compares scopes).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import location_plan as lp
from prosper_or_perish_constructor import market_short_weight
from prosper_or_perish_constructor import staple_foods

EFFECTS = Path("in_game/common/scripted_effects/pp_location_profiles_generated.txt")
VALUES = Path("in_game/common/script_values/pp_location_profiles_generated.txt")
TRIGGERS = Path("in_game/common/scripted_triggers/pp_location_profiles_generated.txt")
HAND_EFFECTS = Path("in_game/common/scripted_effects/pp_location_profiles.txt")
SCRIPTED_GUIS = Path("in_game/common/scripted_guis/pp_location_profiles.txt")
LOC = Path("main_menu/localization/english/pp_location_profiles_l_english.yml")
HEADER = "﻿# Generated by ppc finalize (location_profiles.py) from [location_profiles]; do not edit by hand.\n"
LOGISTICS = "logistics"  # the target "market access": the logistics buildings
DEFAULT_ICON = "lumber"  # a new profile's icon
WHY_PROFILE = 105  # the plan ledger's reason code (+ 100) for a construction a profile started
# rule states (+ 100 in pp_lprof_r<r>_st), docs/location_profiles.md; 4 is not used
STATES = {
    1: "started",
    2: "nothing to build",
    3: "a construction under way here",
    4: "no free workers here",
    5: "payback too long (a profile rule; a mark has no payback limit)",
    6: "cannot be built here",
    7: "gold: the Locations group's purse cannot pay it, or the group saves for something before it",
    8: "market lacks the construction goods",
    9: "waiting for an earlier rule's or mark's construction this month",
    10: "the market limit: enough of the good is on the way in its market (a profile rule; a mark is not held by it)",
}
# why a candidate failed, ranked (+ 100 in pp_lprof_fail; the highest rank of a rule's candidates gives its state)
FAIL_STATE = {101: 2, 102: 6, 103: 5, 104: 4, 105: 8, 106: 10, 107: 7}
DIRECTIONS = ("up", "down")
EDITED = "e"  # the pp_slot flag of the editor's buttons: the slot in the edit buffer (pp_lprof_e_k)
NEXT = "next"  # the pp_slot flag of the new profile button: the first slot not in use
SYMBOL_PREFIX = "pp_sym_"  # a symbol's flag, loc key and texture name: pp_sym_<name>
# The global Construction Plan rule groups a profile can switch off in its locations: (copy field, pp_field flag, the
# plan's group). Unset = the group builds there too (Jan 2026-11-09: what a profile does not set, the global rules do;
# a rule of the profile for a target takes that target from them). Businesses = any building that makes goods; country
# = the plan's Towns and Buildings group (construction_plan_country.py reads pp_lprof_xc on the location).
GLOBAL_GROUPS = (("xf", "global_food", "food"), ("xl", "global_logistics", "logistics"),
                 ("xi", "global_improve", "improvements"), ("xg", "global_business", "businesses"),
                 ("xc", "global_country", "country"))
# The location window's row "Also build here" (location_profiles_gui.py): one line of QUICK_ROW tiles, the marked items
# first, then the quick candidates (goods a standing building makes) in chunks of QUICK_CHUNK goods in the picker's
# order. A chunk shows while the marks and the candidates before it leave room for a whole chunk; an exact cut would
# count the candidates before every single tile each frame.
QUICK_ROW = 11
QUICK_CHUNK = 4
BUILDING_MARK_NUMBER = 1000  # pp_lplan_bn of a building's mark (a goods mark's is 100 + its place in the picker)
WHY_MARK_STEP = 0  # the ledger's step (pp_cplan_rs) of a construction a mark started; a profile rule's is its number
BUFFER = "pp_lprof_e"  # the edit buffer's variable prefix (country)
COPY = "pp_lprof"  # a location's copy of its profile (variable prefix)
# A flag is drawn as a frame of one picture strip (location_profiles_gui.render_textures), never through its name: the
# icon flag has its frame number beside it (<prefix>_in), a category rule target too (<prefix>_r<r>_cn), each + 100.


@dataclass(frozen=True)
class Symbol:
    """A generic picture a profile can carry as its icon (builds nothing)."""

    name: str  # the config key (city)
    title: str  # the player-facing name
    texture: str  # its source below gfx/interface/icons (the mod's or vanilla's)

    @property
    def key(self) -> str:
        """The flag, the loc key of its name and the texture's file name."""
        return SYMBOL_PREFIX + self.name


@dataclass(frozen=True)
class Example:
    """A ready profile ([[location_profiles.examples]]): its icon, colour, rules (target, payback limit in years or None
    for any) and the global rule groups it switches off (GLOBAL_GROUPS' plan group names)."""

    icon: str
    color: int
    rules: tuple[tuple[str, int | None], ...] = ()
    off: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    slots: int
    rules: int
    payback_steps: tuple[int, ...]
    colors: tuple[tuple[float, float, float], ...]
    symbols: tuple[Symbol, ...] = ()
    examples: tuple[Example, ...] = ()


@dataclass(frozen=True)
class Candidate:
    """A building a rule target can build, with what the plan's cost formula needs of it."""

    name: str
    demand: str
    category: str
    ipl: float
    pop_type: str = "peasants"  # the workers a level needs (pp_cplan_staff); none = 0 peasants
    workers: float = 0.0

    @property
    def params(self) -> str:
        return (f"type = {self.name} demand = {self.demand} cat = {self.category} ipl = {cp._num(self.ipl)} "
                f"pt = {self.pop_type} sz = {cp._num(self.workers)}")


@dataclass
class Result:
    items: list[lp.Item] = field(default_factory=list)
    targets: dict[str, list[Candidate]] = field(default_factory=dict)  # item key -> buildings, expand order
    categories: dict[str, list[str]] = field(default_factory=dict)
    files_changed: int = 0


def load_symbols(project: Path) -> tuple[Symbol, ...]:
    """``[location_profiles.symbols]``: name = { name = "...", texture = "<folder>/<file>.dds" }, in picker order."""
    data = tomllib.loads(project.read_text(encoding="utf-8"))["location_profiles"].get("symbols", {})
    return tuple(Symbol(name, str(entry["name"]), str(entry["texture"])) for name, entry in data.items())


def load_config(project: Path) -> Config:
    data = tomllib.loads(project.read_text(encoding="utf-8"))["location_profiles"]
    return Config(
        slots=int(data["slots"]),
        rules=int(data["rules"]),
        payback_steps=tuple(int(step) for step in data["payback_steps"]),
        colors=tuple(tuple(float(part) for part in color) for color in data["colors"]),
        symbols=load_symbols(project),
        examples=tuple(
            Example(
                icon=str(row["icon"]),
                color=int(row["color"]),
                rules=tuple((str(rule["target"]), int(rule["payback"]) if "payback" in rule else None)
                            for rule in row.get("rules", [])),
                off=tuple(str(group) for group in row.get("off", [])),
            )
            for row in data.get("examples", [])
        ),
    )


def profile_items(repo: Path, project: Path) -> list[lp.Item]:
    """The plan items (goods by goods category, then the building categories) and market access (the good logistics)."""
    items = lp.plan_items(repo, lp.load_config(project))
    if not any(item.key == LOGISTICS for item in items):
        items.append(lp.Item(LOGISTICS, "good", "market_access"))
    return items


def frame_flags(categories, config: Config) -> list[str]:
    """The flags a profile's icon or rule can hold, in the order of their frames in the picture strip (frame n = the
    n-th; their frame number variables hold n + 100): the building categories, then the symbols."""
    return list(categories) + [symbol.key for symbol in config.symbols]


def fields(config: Config) -> list[str]:
    """The pp_field flags: the icon and the rules."""
    return ["icon"] + [f"r{r}" for r in range(1, config.rules + 1)]


def slot_range(k: int) -> tuple[str, str]:
    """var:pp_lprof bounds of slot k."""
    return f"{100 + k - 0.5:g}", f"{100 + k + 0.5:g}"


def color_value(config: Config, k: int) -> int:
    """A new slot's colour (+ 100): colour k, wrapping after the last (what the script value pp_lprof_new_color
    computes)."""
    return 100 + (k - 1) % len(config.colors) + 1


# ---------------------------------------------------------------------------------------------------------------------
# buildings


def _top_values(body: str, key: str) -> list[str]:
    """Every ``key = scalar`` at the top level of a block body."""
    found: list[str] = []
    depth = 0
    for token in re.finditer(r"\{|\}|\b([A-Za-z0-9_]+)\s*=\s*([A-Za-z0-9_.\-]+)(?!\s*\{)", body):
        if token.group(0) == "{":
            depth += 1
        elif token.group(0) == "}":
            depth -= 1
        elif depth == 0 and token.group(1) == key:
            found.append(token.group(2))
    return found


def tier_depths(database: dict[str, tuple[dict[str, str], str]]) -> dict[str, int]:
    """Tier of every building type: 0 without an ``obsolete`` predecessor, else one more than its highest one."""
    older = {name: [o for o in _top_values(body, "obsolete") if o in database] for name, (_, body) in database.items()}
    memo: dict[str, int] = {}

    def depth(name: str, seen: frozenset[str]) -> int:
        if name in memo:
            return memo[name]
        value = 1 + max((depth(o, seen | {name}) for o in older[name] if o not in seen), default=-1)
        memo[name] = value
        return value

    return {name: depth(name, frozenset()) for name in database}


def _player_buildable(keys: dict[str, str], body: str) -> bool:
    """Building types a player builds in an own location: no foreign, special (unique, event), estate or international
    organisation building, nothing that is never allowed and nothing only for empty land. The rest (rank, potential,
    allow, research) is the game's own can-build check at run time."""
    if keys.get("is_foreign") == "yes" or keys.get("is_special") == "yes":
        return False
    if "estate" in keys or "international_organization_link" in keys or keys.get("in_empty") == "empty":
        return False
    return not re.search(r"\ballow\s*=\s*\{\s*always\s*=\s*no\s*\}", body)


def category_buildings(database: dict[str, tuple[dict[str, str], str]], categories: tuple[str, ...]) -> dict[str, list[str]]:
    """Per building category the player-buildable building types of it."""
    found: dict[str, list[str]] = {category: [] for category in categories}
    for name, (keys, body) in sorted(database.items()):
        category = keys.get("category")
        if category in found and _player_buildable(keys, body):
            found[category].append(name)
    return found


_TARGETS: dict[tuple, tuple[dict[str, list[Candidate]], dict[str, list[str]]]] = {}


def targets(repo: Path, project: Path, mod_root: Path, vanilla_root: Path) -> tuple[dict[str, list[Candidate]], dict[str, list[str]]]:
    """Item key -> the buildings it builds (highest tier first; market access in the plan's logistics order), and the
    category lists. Read once per process and state of the building files: the script side and the GUI side (the quick
    candidates of the location window's row) ask one after the other."""
    stamp = _targets_stamp(repo, project, mod_root, vanilla_root)
    if stamp not in _TARGETS:
        _TARGETS.clear()
        _TARGETS[stamp] = _read_targets(repo, project, mod_root, vanilla_root)
    return _TARGETS[stamp]


def _targets_stamp(repo: Path, project: Path, mod_root: Path, vanilla_root: Path) -> tuple:
    """What targets() reads, by modification time: the config, the goods table and the mod's building, price and
    script value files."""
    files = [project, repo / lp.GOODS_CATEGORIES]
    for folder in ("building_types", "prices", "script_values", "goods"):
        files += sorted((mod_root / "in_game/common" / folder).glob("*.txt"))
    return (repo, project, mod_root, vanilla_root) + tuple((str(path), path.stat().st_mtime_ns) for path in files if path.is_file())


def _read_targets(repo: Path, project: Path, mod_root: Path, vanilla_root: Path) -> tuple[dict[str, list[Candidate]], dict[str, list[str]]]:
    plan = cp.load_config(project)
    database = cp._database(mod_root, vanilla_root, cp.BUILDING_TYPES)
    costs, _ = cp.building_costs(mod_root, vanilla_root, database)
    staff = cp.staffing(database, cp.script_value_numbers(mod_root, vanilla_root))
    depths = tier_depths(database)
    defined = {name for name, (keys, _) in database.items() if "category" in keys}  # DLC-only types carry none here

    def candidate(name: str) -> Candidate:
        cost = costs.get(name, cp.BuildingCost(0.0, cp.DEFAULT_DEMAND, "std"))
        pop_type, workers = staff.get(name, ("peasants", 0.0))
        return Candidate(name, cost.demand, cost.category, cost.ipl, pop_type, workers)

    def ordered(names: list[str]) -> list[Candidate]:
        return [candidate(name) for name in sorted(set(names) & defined, key=lambda name: (-depths[name], name))]

    short = market_short_weight.apply(project, mod_root, vanilla_root, write=False)
    by_good: dict[str, list[str]] = {}
    for building, good in sorted(short.main_good.items()):
        if good in plan.hidden_goods or building in plan.logistics_order:
            continue
        by_good.setdefault(good, []).append(building)
    found: dict[str, list[Candidate]] = {}
    for item in profile_items(repo, project):
        if item.key == LOGISTICS:
            found[item.key] = [candidate(name) for name in plan.logistics_order if name in defined]
        elif item.kind == "good":
            found[item.key] = ordered(by_good.get(item.key, []))
    categories = category_buildings(database, lp.load_config(project).categories)
    for category, names in categories.items():
        found[category] = ordered(names)
    return found, categories


# ---------------------------------------------------------------------------------------------------------------------
# scripted effects


def render_targets(found: dict[str, list[Candidate]]) -> str:
    parts = [
        "\n# ---- Rule targets (location scope, in the monthly pass; scope:pp_lprof_pb = the rule's payback limit + 100) ----\n"
        "# A level under construction of any of the target's buildings here: the rule waits (pp_lprof_st 103). Else a\n"
        "# standing one grows, highest tier first, while its next level pays back within the limit; where none stands,\n"
        "# the cheapest that can be built here starts. Market access tries the logistics buildings in the plan's order,\n"
        "# standing or not. Each candidate that fails ranks its reason in pp_lprof_fail (pp_lprof_finish turns it into\n"
        "# the rule's state).\n"
    ]
    for key, candidates in found.items():
        if not candidates:
            continue
        types = " ".join(f"building_type = building_type:{c.name}" for c in candidates)
        lines = [
            f"\npp_lprof_t_{key} = {{",
            "\tif = {",
            f"\t\tlimit = {{ any_buildings_in_location = {{ building_levels_under_construction > 0 OR = {{ {types} }} }} }}",
            "\t\tset_variable = { name = pp_lprof_st value = 103 }",
            "\t}",
        ]
        if key == LOGISTICS:
            lines += ["\telse = {"] + [f"\t\tpp_lprof_try = {{ {c.params} }}" for c in candidates] + ["\t}"]
        else:
            lines += [
                "\telse_if = {",
                f"\t\tlimit = {{ any_buildings_in_location = {{ building_level > 0 OR = {{ {types} }} }} }}",
            ]
            lines += [f"\t\tpp_lprof_expand = {{ {c.params} }}" for c in candidates]
            lines += ["\t}", "\telse = {"]
            lines += [f"\t\tpp_lprof_start = {{ {c.params} }}" for c in candidates]
            lines += ["\t\tpp_lprof_start_pick = yes", "\t}"]
        lines.append("}")
        parts.append("\n".join(lines) + "\n")
    return "".join(parts)


def render_dispatch(items: list[lp.Item], found: dict[str, list[Candidate]], config: Config) -> str:
    goods = [item.key for item in items if item.kind == "good" and found.get(item.key)]
    categories = [item.key for item in items if item.kind == "category" and found.get(item.key)]
    return (
        "\n# Location scope: the good in the location's variable $v$ (a goods scope, the location's copy of a rule) -> its\n"
        "# target. A good nothing builds leaves the rule without a candidate (state 6).\n"
        "pp_lprof_goods_target = {\n\tswitch = {\n\t\ttrigger = var:$v$\n"
        + "".join(f"\t\tgoods:{good} = {{ pp_lprof_t_{good} = yes }}\n" for good in goods)
        + "\t}\n}\n"
        "\n# Location scope: the building category in the location's variable $v$ (a flag) -> its target.\n"
        "pp_lprof_category_target = {\n\tswitch = {\n\t\ttrigger = var:$v$\n"
        + "".join(f"\t\tflag:{category} = {{ pp_lprof_t_{category} = yes }}\n" for category in categories)
        + "\t}\n}\n"
        "\n# Location scope (in scope:pp_cplan_country's list pp_lprof_locs, owned by it): the rules of its profile in order,\n"
        "# from the location's copy (pp_lprof_r<r>_*); the first rule that starts a construction ends the location for the\n"
        "# month (pp_cplan_hit, cleared per location by pp_lprof_run; the location's marks follow and wait too). No slot is\n"
        "# looked at.\n"
        "pp_lprof_location_rules = {\n"
        + "".join(f"\tpp_lprof_rule = {{ r = {r} }}\n" for r in range(1, config.rules + 1))
        + "}\n"
    )


def mark_items(items: list[lp.Item]) -> list[lp.Item]:
    """The items a location can be marked with in the picker: the goods (without market access, which the plan's
    picker does not offer). A building is marked on its own entry; a building category is a rule target only."""
    return [item for item in lp.mark_items(items) if item.key != LOGISTICS]


def render_marks(items: list[lp.Item], found: dict[str, list[Candidate]]) -> str:
    """The goods marks of a location ("also build this here"): each marked good runs its target, the effect a profile
    rule with that target runs, in the picker's order; n = 100 + its place there (the mark that measured the best
    payback is known by it), lo / hi the bounds around n."""
    lines = [
        "\n# ---- The location's marks (Jan 2026-11-10: \"also build this here\", forced) ----\n"
        "# Location scope (in pp_lplan_location_turn, pp_location_profiles.txt, after the rules of the location's\n"
        "# profile): each marked good in the picker's order (pp_lplan_mark: the pp_lprof_t_<good> a profile rule with that\n"
        "# target runs; no payback limit, no market limit). Run twice a turn: once to measure (scope:pp_lplan_mode 1: the\n"
        "# mark whose next level pays back soonest is built first), once to build and to write the states. The first\n"
        "# construction of the turn in the location, by a rule or a mark, makes the rest wait. The window's ledger\n"
        f"# shows a mark's construction as the profile group's, step {WHY_MARK_STEP} (a profile rule's step is its number).\n"
        "pp_lplan_location_marks = {\n"
    ]
    for number, item in enumerate(mark_items(items), 101):
        if found.get(item.key):
            lines.append(f"\tpp_lplan_mark = {{ v = {item.suffix} do = pp_lprof_t_{item.key} "
                         f"n = {number} lo = {number - 0.5:g} hi = {number + 0.5:g} }}\n")
        else:
            lines.append(f"\tpp_lplan_mark_none = {{ v = {item.suffix} }}\n")
    if len(mark_items(items)) + 101 > BUILDING_MARK_NUMBER:
        raise ValueError("more goods marks than numbers below the building marks' number")
    lines.append("}\n")
    return "".join(lines)


# ---------------------------------------------------------------------------------------------------------------------
# a building's mark: the newest tier of its line, the upgrade, the workers


def line_depth(pairs: list[tuple[str, str]]) -> int:
    """The longest way up a building line: how many steps (older tier -> its successor) the newest tier is away."""
    newer: dict[str, list[str]] = {}
    for older, successor in pairs:
        newer.setdefault(older, []).append(successor)

    def depth(name: str, seen: frozenset[str]) -> int:
        return 1 + max((depth(later, seen | {name}) for later in newer.get(name, ()) if later not in seen), default=-1)

    return max((depth(older, frozenset()) for older in newer), default=0)


def main_chain(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Every building type with a later tier -> its later tiers one by one up the main line: at each step the
    successor with the longest way up (of equals the first in the upgrade rule's order). A skip link (coal_mine ->
    coal_mine_revolutions beside coal_mine -> coal_mine_improved -> coal_mine_revolutions) lies on that line."""
    direct: dict[str, list[str]] = {}
    for old, successor in pairs:
        direct.setdefault(old, []).append(successor)

    def height(name: str, seen: frozenset[str]) -> int:
        return 1 + max((height(later, seen | {name}) for later in direct.get(name, ()) if later not in seen), default=-1)

    out: dict[str, list[str]] = {}
    for start in direct:
        line: list[str] = []
        here, seen = start, {start}
        while True:
            options = [name for name in direct.get(here, ()) if name not in seen]
            if not options:
                break
            here = max(options, key=lambda name: (height(name, frozenset(seen)), -options.index(name)))
            line.append(here)
            seen.add(here)
        out[start] = line
    return out


def newer_tiers(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Every building type with a later tier -> all its later tiers up the line (direct successors first)."""
    direct: dict[str, list[str]] = {}
    for old, successor in pairs:
        direct.setdefault(old, []).append(successor)
    out: dict[str, list[str]] = {}
    for start in direct:
        seen: list[str] = []
        todo = list(direct[start])
        while todo:
            name = todo.pop(0)
            if name != start and name not in seen:
                seen.append(name)
                todo += direct.get(name, [])
        out[start] = seen
    return out


@dataclass(frozen=True)
class MarkMaps:
    """What a building's mark reads of a building type, as global variable maps keyed by the type (filled once per save
    and game data version, pp_lplan_maps_fill): up<k> the k-th later tier on its main line (the top once the line
    ends), dn<k> its k-th direct older tier, wk / wp its workers a level and their pop type (number 101..), ipl / dm /
    ct its cost data (increase per level, construction demand number 101.., efficiency category number 101..)."""

    up: dict[str, list[str]]
    down: dict[str, list[str]]
    staff: dict[str, tuple[str, float]]
    pop_types: tuple[str, ...]
    costs: dict
    demands: tuple[str, ...]
    categories: tuple[str, ...]

    @property
    def depth(self) -> int:
        return max((len(line) for line in self.up.values()), default=0)

    @property
    def older(self) -> int:
        return max((len(olds) for olds in self.down.values()), default=0)


def mark_maps(pairs: list[tuple[str, str]], staff: dict[str, tuple[str, float]], costs: dict) -> MarkMaps:
    down: dict[str, list[str]] = {}
    for old, successor in pairs:
        down.setdefault(successor, []).append(old)
    staffed = {name: value for name, value in staff.items() if value[1] > 0}
    return MarkMaps(
        up=main_chain(pairs), down=down, staff=staffed,
        pop_types=tuple(sorted({pop for pop, _ in staffed.values()})), costs=costs,
        demands=tuple(sorted({c.demand for c in costs.values() if c.demand != cp.DEFAULT_DEMAND})),
        categories=tuple(sorted({c.category for c in costs.values() if c.category != "std"})),
    )


def _map(name: str) -> str:
    return f"pp_lplan_{name}"


def _key(name: str, target: str = "scope:pp_cplan_btype") -> str:
    return f"is_key_in_global_variable_map = {{ name = {_map(name)} target = {target} }}"


def _get(name: str, target: str = "scope:pp_cplan_btype") -> str:
    return f'"global_variable_map({_map(name)}|{target})"'


def _fill_lines(maps: MarkMaps) -> list[str]:
    lines: list[str] = []

    def add(name: str, key: str, value: str) -> None:
        lines.append(f"\tadd_to_global_variable_map = {{ name = {_map(name)} key = building_type:{key} value = {value} }}\n")

    for start, line in maps.up.items():
        for k in range(1, maps.depth + 1):
            add(f"up{k}", start, f"building_type:{line[min(k, len(line)) - 1]}")
    for successor, olds in maps.down.items():
        for k, old in enumerate(olds, 1):
            add(f"dn{k}", successor, f"building_type:{old}")
    for name, (pop_type, workers) in sorted(maps.staff.items()):
        add("wk", name, cp._num(workers))
        add("wp", name, str(101 + maps.pop_types.index(pop_type)))
    for name, cost in sorted(maps.costs.items()):
        if cost.ipl:
            add("ipl", name, cp._num(cost.ipl))
        if cost.demand != cp.DEFAULT_DEMAND:
            add("dm", name, str(101 + maps.demands.index(cost.demand)))
        if cost.category != "std":
            add("ct", name, str(101 + maps.categories.index(cost.category)))
    return lines


def map_names(maps: MarkMaps) -> list[str]:
    return ([f"up{k}" for k in range(1, maps.depth + 1)] + [f"dn{k}" for k in range(1, maps.older + 1)]
            + ["wk", "wp", "ipl", "dm", "ct"])


def maps_version(maps: MarkMaps) -> int:
    """The game data's stamp in the save (global variable pp_lplan_maps_v): another stamp fills the maps afresh."""
    import zlib

    return 100 + zlib.crc32("".join(_fill_lines(maps)).encode()) % 900000


def _chain(value: str, count: int, body, depth: int = 2) -> str:
    """A halving search over a number 101..100+count held in the scope value ``value``: about log2(count) comparisons
    (108 construction demands: 7), then ``body(index)``."""
    tab = "\t" * depth

    def tree(lo: int, hi: int, tab: str) -> str:
        if lo == hi:
            return f"{tab}{body(lo)}\n"
        mid = (lo + hi) // 2
        return (f"{tab}if = {{\n{tab}\tlimit = {{ scope:{value} < {101 + mid + 0.5:g} }}\n" + tree(lo, mid, tab + "\t")
                + f"{tab}}}\n{tab}else = {{\n" + tree(mid + 1, hi, tab + "\t") + f"{tab}}}\n")

    return tree(0, count - 1, tab) if count else ""


def render_building_marks(maps: MarkMaps) -> str:
    """The generated effects of a building's mark (the hand-written pp_lplan_building_mark calls them). Nothing in them
    walks the building types: each reads the global maps (MarkMaps) by the type, a few lookups and comparisons."""
    version = maps_version(maps)
    clear = "".join(
        f"\tif = {{ limit = {{ has_global_variable_map = {_map(name)} }} clear_global_variable_map = {_map(name)} }}\n"
        for name in map_names(maps))
    newest = "".join(
        f"\t\t{'if' if k == maps.depth else 'else_if'} = {{\n"
        f"\t\t\tlimit = {{ scope:pp_cplan_country = {{ can_build_building = {_get(f'up{k}', 'scope:pp_lplan_base')} }} }}\n"
        f"\t\t\t{_get(f'up{k}', 'scope:pp_lplan_base')} = {{ save_scope_as = pp_cplan_btype }}\n\t\t}}\n"
        for k in range(maps.depth, 0, -1))
    staff = _chain("pp_lplan_wt", len(maps.pop_types), lambda i: (
        f"if = {{ limit = {{ NOT = {{ pp_cplan_staff = {{ type = {maps.pop_types[i]} size = scope:pp_lplan_wn }} }} }} "
        "save_temporary_scope_value_as = { name = pp_lplan_sok value = 0 } }"))
    demand = _chain("pp_lplan_dmi", len(maps.demands), lambda i: (
        f"save_temporary_scope_value_as = {{ name = pp_cplan_pf value = pp_cplan_cd_{maps.demands[i]} }} "
        "save_temporary_scope_value_as = { name = pp_cplan_gok value = 1 } "
        f"if = {{ limit = {{ NOT = {{ pp_cplan_goods_here_{maps.demands[i]} = yes }} }} "
        "save_temporary_scope_value_as = { name = pp_cplan_gok value = 0 } }"))
    category = _chain("pp_lplan_cti", len(maps.categories), lambda i: (
        f"save_temporary_scope_value_as = {{ name = pp_cplan_ef value = pp_cplan_eff_{maps.categories[i]} }}"))
    default = cp.DEFAULT_DEMAND
    return (
        "\n# ---- A building's mark (pp_lplan_building_mark, pp_location_profiles.txt; scope:pp_cplan_btype = the building type) ----\n"
        "# What a mark needs of its building type sits in global variable maps keyed by the type (pp_lplan_maps_fill),\n"
        "# so a mark reads a few entries instead of testing the type against every building type.\n"
        f"\n# Any scope: the maps are filled once per save and game data version (stamp {version}).\n"
        "pp_lplan_maps_ready = {\n\tif = {\n\t\tlimit = {\n\t\t\tOR = {\n"
        "\t\t\t\tNOT = { has_global_variable = pp_lplan_maps_v }\n"
        f"\t\t\t\tglobal_var:pp_lplan_maps_v < {version - 0.5:g}\n\t\t\t\tglobal_var:pp_lplan_maps_v > {version + 0.5:g}\n"
        "\t\t\t}\n\t\t}\n\t\tpp_lplan_maps_fill = yes\n\t}\n}\n"
        "\n# Any scope (pp_lplan_maps_ready): up<k> = the k-th later tier on the type's main line (the line's top past its\n"
        "# end), dn<k> = its k-th direct older tier, wk / wp = workers a level and their pop type (101..), ipl / dm / ct =\n"
        "# its cost data (increase per level, construction demand 101.., efficiency category 101..).\n"
        "pp_lplan_maps_fill = {\n" + clear + "".join(_fill_lines(maps))
        + f"\tset_global_variable = {{ name = pp_lplan_maps_v value = {version} }}\n}}\n"
        "\n# Any scope: scope:pp_cplan_btype becomes the newest tier of its main line the country can build (the highest\n"
        f"# of its {maps.depth} later tiers it can build; itself when none). A building the country has made obsolete is not\n"
        "# built any more; its successor is.\n"
        f"pp_lplan_b_newest = {{\n\tif = {{\n\t\tlimit = {{ {_key('up1')} }}\n"
        "\t\tscope:pp_cplan_btype = { save_scope_as = pp_lplan_base }\n" + newest + "\t}\n}\n"
        "\n# Location scope: scope:pp_lplan_sok = 1 where one level of scope:pp_cplan_btype finds its workers here\n"
        "# (pp_cplan_staff with the type's pop type and workers a level; a building without workers always does).\n"
        "pp_lplan_b_staff = {\n\tsave_temporary_scope_value_as = { name = pp_lplan_sok value = 1 }\n"
        f"\tif = {{\n\t\tlimit = {{ {_key('wk')} }}\n"
        f"\t\tsave_temporary_scope_value_as = {{ name = pp_lplan_wn value = {_get('wk')} }}\n"
        f"\t\tsave_temporary_scope_value_as = {{ name = pp_lplan_wt value = {_get('wp')} }}\n" + staff + "\t}\n}\n"
        "\n# Location scope: the build cost data of scope:pp_cplan_btype for pp_cplan_est_* (the values pp_cplan_btype_data\n"
        "# sets, read from the maps).\n"
        "pp_lplan_b_data = {\n\tsave_temporary_scope_value_as = { name = pp_cplan_ipl value = 0 }\n"
        f"\tif = {{ limit = {{ {_key('ipl')} }} save_temporary_scope_value_as = {{ name = pp_cplan_ipl value = {_get('ipl')} }} }}\n"
        f"\tsave_temporary_scope_value_as = {{ name = pp_cplan_pf value = pp_cplan_cd_{default} }}\n"
        "\tsave_temporary_scope_value_as = { name = pp_cplan_gok value = 1 }\n"
        f"\tif = {{ limit = {{ NOT = {{ pp_cplan_goods_here_{default} = yes }} }} save_temporary_scope_value_as = {{ name = pp_cplan_gok value = 0 }} }}\n"
        f"\tif = {{\n\t\tlimit = {{ {_key('dm')} }}\n"
        f"\t\tsave_temporary_scope_value_as = {{ name = pp_lplan_dmi value = {_get('dm')} }}\n" + demand + "\t}\n"
        "\tsave_temporary_scope_value_as = { name = pp_cplan_ef value = pp_cplan_eff_std }\n"
        f"\tif = {{\n\t\tlimit = {{ {_key('ct')} }}\n"
        f"\t\tsave_temporary_scope_value_as = {{ name = pp_lplan_cti value = {_get('ct')} }}\n" + category + "\t}\n}\n"
    )


def render_building_mark_triggers(maps: MarkMaps) -> str:
    """pp_lplan_b_upgrade_here: an older tier of scope:pp_cplan_btype stands here and the country can upgrade it, so
    construct_building with scope:pp_cplan_btype is the game's Upgrade button (in game 2026-11-10); pp_lplan_b_done:
    the marked type or a later tier of its line stands here (the map icon). Both read the maps, no type list."""
    upgrade = "".join(
        f"\t\tAND = {{\n\t\t\t{_key(f'dn{k}')}\n"
        f"\t\t\tany_buildings_in_location = {{ building_type = {_get(f'dn{k}')} pp_cplan_country_upgradable = yes }}\n\t\t}}\n"
        for k in range(1, maps.older + 1))
    line = " ".join(f"building_type = {_get(f'up{k}', 'scope:pp_bt')}" for k in range(1, maps.depth + 1))
    return (
        "\n# Location scope (a building's mark): a tier of the line just below scope:pp_cplan_btype stands here, open, and\n"
        "# the country can upgrade it (pp_cplan_country_upgradable, the Towns and Buildings rule's check): a\n"
        "# construction of scope:pp_cplan_btype here is the game's upgrade of one level of it. Its older tiers: the maps\n"
        "# pp_lplan_dn<k> (pp_lplan_maps_fill).\n"
        "pp_lplan_b_upgrade_here = {\n\tOR = {\n" + upgrade + "\t\talways = no\n\t}\n}\n"
        "\n# Location scope (scope:pp_bt = a marked building type; the Location Plan map icon, scripted GUI pp_lplan_bdone):\n"
        "# a level of it, or of a later tier of its main line (the maps pp_lplan_up<k>), stands here. One walk over the\n"
        "# location's buildings.\n"
        "pp_lplan_b_done = {\n\tOR = {\n"
        f"\t\tAND = {{\n\t\t\t{_key('up1', 'scope:pp_bt')}\n"
        f"\t\t\tany_buildings_in_location = {{ building_level > 0 OR = {{ building_type = scope:pp_bt {line} }} }}\n\t\t}}\n"
        f"\t\tAND = {{\n\t\t\tNOT = {{ {_key('up1', 'scope:pp_bt')} }}\n"
        "\t\t\tany_buildings_in_location = { building_type = scope:pp_bt building_level > 0 }\n\t\t}\n"
        "\t}\n}\n"
    )


_MARK_DATA: dict[tuple, tuple[list[tuple[str, str]], dict[str, tuple[str, float]]]] = {}


def building_mark_data(repo: Path, project: Path, mod_root: Path, vanilla_root: Path) -> tuple[list[tuple[str, str]], dict[str, tuple[str, float]]]:
    """What a building's mark needs of the game's building types: the upgrade pairs (older tier, direct successor;
    the Towns and Buildings rule's list) and the workers a level of each type takes. DLC-only types are left out (the
    mod's script names no DLC-only key)."""
    stamp = _targets_stamp(repo, project, mod_root, vanilla_root)
    if stamp not in _MARK_DATA:
        from prosper_or_perish_constructor import construction_plan_country as cc

        _MARK_DATA.clear()
        database = cp._database(mod_root, vanilla_root, cp.BUILDING_TYPES)
        defined = {name for name, (keys, _) in database.items() if "category" in keys}  # DLC-only types carry none here
        types = cc.database(mod_root, vanilla_root, cc.BUILDING_TYPES)
        pairs = [(older, successor) for older, successor in cc.upgrade_pairs(types)
                 if older in defined and successor in defined]
        staff = {name: value for name, value in cp.staffing(database, cp.script_value_numbers(mod_root, vanilla_root)).items()
                 if name in defined and name in types and not types[name].dlc_only}
        _MARK_DATA[stamp] = (pairs, staff)
    return _MARK_DATA[stamp]


def building_mark_maps(repo: Path, project: Path, mod_root: Path, vanilla_root: Path) -> MarkMaps:
    """The maps of a building's mark: the upgrade pairs and workers (building_mark_data) and the cost data
    pp_cplan_btype_data holds (construction_plan.building_costs, the same table)."""
    pairs, staff = building_mark_data(repo, project, mod_root, vanilla_root)
    costs, _ = cp.building_costs(mod_root, vanilla_root, cp._database(mod_root, vanilla_root, cp.BUILDING_TYPES))
    return mark_maps(pairs, staff, costs)


def quick_goods(items: list[lp.Item], found: dict[str, list[Candidate]]) -> list[lp.Item]:
    """The goods the location window's row offers as quick candidates while a building that makes them stands: every
    markable good a building builds, in the picker's order."""
    return [item for item in mark_items(items) if item.kind == "good" and found.get(item.key)]


def quick_chunks(items: list[lp.Item], found: dict[str, list[Candidate]]) -> list[list[lp.Item]]:
    goods = quick_goods(items, found)
    return [goods[start:start + QUICK_CHUNK] for start in range(0, len(goods), QUICK_CHUNK)]


def render_quick(items: list[lp.Item], found: dict[str, list[Candidate]]) -> str:
    """Script values of the location window's row "Also build here"."""
    parts = [
        "\n# ---- The location window's row \"Also build here\" (location scope; location_profiles_gui.py) ----\n"
        "\n# Quick candidates: 1 while a building that makes the good stands here (what a mark would expand) and the good is\n"
        "# not marked (a marked good has its tile among the marks).\n"
    ]
    for item in quick_goods(items, found):
        types = " ".join(f"has_building = building_type:{c.name}" for c in found[item.key])
        parts.append(
            f"pp_lplan_quick_{item.key} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{\n"
            f"\t\t\tNOT = {{ has_variable = {item.var} }}\n\t\t\tOR = {{ {types} }}\n\t\t}}\n\t\tvalue = 1\n\t}}\n}}\n"
        )
    parts.append(
        f"\n# The row holds {QUICK_ROW} tiles: the marked items, then the quick candidates in chunks of {QUICK_CHUNK} goods. Chunk n\n"
        "# shows while this is above 0: the tiles the row has left after the marks and the candidates of the chunks\n"
        "# before it, minus a whole chunk, plus 1.\n"
    )
    chunks = quick_chunks(items, found)
    for number, _ in enumerate(chunks, 1):
        if number == 1:
            body = f"\tvalue = {QUICK_ROW - QUICK_CHUNK + 1}\n\tsubtract = pp_lplan_planned_n\n"
        else:
            body = f"\tvalue = pp_lplan_quick_room_{number - 1}\n" + "".join(
                f"\tsubtract = pp_lplan_quick_{item.key}\n" for item in chunks[number - 2])
        parts.append(f"pp_lplan_quick_room_{number} = {{\n{body}}}\n")
    return "".join(parts)


def render_slots(config: Config) -> str:
    """The only per-slot script: a slot flag (or the edit buffer's slot, or the first free slot) -> the slot number
    pp_lprof_k, and the copy between slot k's variables and the staged copy (pp_lprof_s_*). Everything else works on
    fixed names."""
    slots = range(1, config.slots + 1)

    def chain(body) -> str:
        return "".join(
            f"\t\t{'if' if k == 1 else 'else_if'} = {{ limit = {{ var:pp_lprof_k < {slot_range(k)[1]} }} {body(k)} }}\n" for k in slots
        )

    return (
        "\n# ---- Slots: the only per-slot script ----\n"
        "\n# Country scope: pp_lprof_k = the slot (+ 100) of the flag scope:pp_slot (s1..sN, or e = the slot in the edit\n"
        "# buffer, pp_lprof_e_k); removed for anything else.\n"
        "pp_lprof_resolve = {\n\tremove_variable = pp_lprof_k\n"
        "\tif = {\n\t\tlimit = { scope:pp_slot = flag:e }\n\t\tpp_cplan_copy_num = { from = pp_lprof_e_k to = pp_lprof_k }\n\t}\n"
        "\telse = {\n\t\tswitch = {\n\t\t\ttrigger = scope:pp_slot\n"
        + "".join(f"\t\t\tflag:s{k} = {{ set_variable = {{ name = pp_lprof_k value = {100 + k} }} }}\n" for k in slots)
        + "\t\t}\n\t}\n}\n"
        "\n# Country scope: pp_lprof_k = the first slot not in use (removed when all are).\n"
        "pp_lprof_resolve_free = {\n\tremove_variable = pp_lprof_k\n"
        + "".join(
            f"\t{'if' if k == 1 else 'else_if'} = {{ limit = {{ NOT = {{ has_variable = pp_lprof_{k}_on }} }} "
            f"set_variable = {{ name = pp_lprof_k value = {100 + k} }} }}\n" for k in slots
        )
        + "}\n"
        "\n# Country scope (scope:pp_lprof_country = it): slot pp_lprof_k's variables -> the staged copy pp_lprof_s_*.\n"
        "pp_lprof_read = {\n\tif = {\n\t\tlimit = { has_variable = pp_lprof_k }\n"
        + chain(lambda k: f"pp_lprof_read_slot = {{ k = {k} }}")
        + "\t}\n}\n"
        "\n# Country scope (scope:pp_lprof_country = it): the staged copy -> slot pp_lprof_k's variables.\n"
        "pp_lprof_write = {\n\tif = {\n\t\tlimit = { has_variable = pp_lprof_k }\n"
        + chain(lambda k: f"pp_lprof_write_slot = {{ k = {k} }}")
        + "\t}\n}\n"
    )


def render_edits(items: list[lp.Item], config: Config, categories: list[str]) -> str:
    rules = range(1, config.rules + 1)
    goods = [item.key for item in items if item.kind == "good"]
    icon_flags = categories + [symbol.key for symbol in config.symbols]
    parts = ["\n# ---- Edits of the staged copy (pp_lprof_s_*, country scope; pp_lprof_edit in pp_location_profiles.txt) ----\n"]

    # set: the item flag -> a goods scope (goods) or the flag itself (categories, symbols)
    parts.append(
        "\n# Any scope: the good named by the flag scope:pp_key as scope:pp_lprof_val (nothing for a category or symbol key).\n"
        "pp_lprof_key_scope = {\n\tswitch = {\n\t\ttrigger = scope:pp_key\n"
        + "".join(f"\t\tflag:{good} = {{ goods:{good} = {{ save_scope_as = pp_lprof_val }} }}\n" for good in goods)
        + "\t}\n}\n"
    )
    parts.append(
        "\n# The icon or a rule target (scope:pp_field) = the item scope:pp_key (a symbol only as the icon).\n"
        "pp_lprof_set_staged = {\n\tswitch = {\n\t\ttrigger = scope:pp_field\n"
        "\t\tflag:icon = { pp_lprof_set_icon = { g = pp_lprof_s_ig c = pp_lprof_s_ic n = pp_lprof_s_in } }\n"
        + "".join(f"\t\tflag:r{r} = {{ pp_lprof_set_target = {{ g = pp_lprof_s_r{r}_g c = pp_lprof_s_r{r}_c n = pp_lprof_s_r{r}_cn }} }}\n"
                  for r in rules)
        + "\t}\n}\n"
    )
    parts.append(
        "\n# The global rule group scope:pp_field (global_food / ...) switched off in the profile's locations, or on again\n"
        "# (unset = on: the group builds there too, except the targets of the profile's rules).\n"
        "pp_lprof_global_staged = {\n\tswitch = {\n\t\ttrigger = scope:pp_field\n"
        + "".join(
            f"\t\tflag:{flag} = {{\n\t\t\tif = {{\n\t\t\t\tlimit = {{ has_variable = pp_lprof_s_{name} }}\n"
            f"\t\t\t\tremove_variable = pp_lprof_s_{name}\n\t\t\t}}\n"
            f"\t\t\telse = {{\n\t\t\t\tset_variable = {{ name = pp_lprof_s_{name} value = 101 }}\n\t\t\t}}\n\t\t}}\n"
            for name, flag, _ in GLOBAL_GROUPS
        )
        + "\t}\n}\n"
    )
    parts.append(
        "\n# The colour scope:pp_col (c1..cN).\npp_lprof_color_staged = {\n\tswitch = {\n\t\ttrigger = scope:pp_col\n"
        + "".join(f"\t\tflag:c{n} = {{ set_variable = {{ name = pp_lprof_s_col value = {100 + n} }} }}\n"
                  for n in range(1, len(config.colors) + 1))
        + "\t}\n}\n"
    )

    # payback steps
    steps = config.payback_steps
    up = "".join(
        f"\t\t\t{'if' if index == 0 else 'else_if'} = {{ limit = {{ var:$var$ < {step + 99.5:g} }} set_variable = {{ name = $var$ value = {step + 100} }} }}\n"
        for index, step in enumerate(steps)
    )
    down = "".join(
        f"\t\telse_if = {{ limit = {{ var:$var$ > {step + 100.5:g} }} set_variable = {{ name = $var$ value = {step + 100} }} }}\n"
        for step in reversed(steps)
    )
    parts.append(
        f"\n# Any scope: steps the payback limit $var$ (years + 100; unset = any) through [location_profiles] payback_steps\n"
        f"# ({', '.join(str(step) for step in steps)}) in the direction scope:pp_dir; up from the last step = any, down from\n"
        "# any = the last step, down from the first stays.\n"
        "pp_lprof_pb_step = {\n\tif = {\n\t\tlimit = { scope:pp_dir = flag:up }\n\t\tif = {\n\t\t\tlimit = { has_variable = $var$ }\n"
        + up
        + "\t\t\telse = { remove_variable = $var$ }\n\t\t}\n\t}\n\telse = {\n"
        f"\t\tif = {{\n\t\t\tlimit = {{ NOT = {{ has_variable = $var$ }} }}\n\t\t\tset_variable = {{ name = $var$ value = {steps[-1] + 100} }}\n\t\t}}\n"
        + down
        + "\t}\n}\n"
    )
    parts.append(
        "\n# The payback limit of rule scope:pp_field (r1..rN), one step in the direction scope:pp_dir.\n"
        "pp_lprof_payback_staged = {\n\tswitch = {\n\t\ttrigger = scope:pp_field\n"
        + "".join(f"\t\tflag:r{r} = {{ pp_lprof_pb_step = {{ var = pp_lprof_s_r{r}_pb }} }}\n" for r in rules)
        + "\t}\n}\n"
    )

    # clear a rule
    parts.append(
        "\n# Rule scope:pp_field emptied, and its states in the slot's locations.\npp_lprof_rule_clear_staged = {\n"
        "\tpp_lprof_save_range = yes\n\tswitch = {\n\t\ttrigger = scope:pp_field\n"
    )
    for r in rules:
        parts.append(
            f"\t\tflag:r{r} = {{\n\t\t\tremove_variable = pp_lprof_s_r{r}_g\n\t\t\tremove_variable = pp_lprof_s_r{r}_c\n"
            f"\t\t\tremove_variable = pp_lprof_s_r{r}_cn\n\t\t\tremove_variable = pp_lprof_s_r{r}_pb\n"
            "\t\t\tevery_in_list = {\n\t\t\t\tvariable = pp_lprof_locs\n"
            "\t\t\t\tlimit = { has_variable = pp_lprof var:pp_lprof > scope:pp_lprof_lo var:pp_lprof < scope:pp_lprof_hi }\n"
            f"\t\t\t\tremove_variable = pp_lprof_r{r}_st\n\t\t\t\tremove_variable = pp_lprof_r{r}_est\n\t\t\t}}\n\t\t}}\n"
        )
    parts.append("\t}\n}\n")

    # move a rule
    parts.append(
        "\n# Rule scope:pp_field swaps places with its neighbour in the direction scope:pp_dir.\npp_lprof_rule_move_staged = {\n"
        "\tswitch = {\n\t\ttrigger = scope:pp_field\n"
    )
    for r in rules:
        branches = []
        if r > 1:
            branches.append(("up", r - 1, r))
        if r < config.rules:
            branches.append(("down", r, r + 1))
        body = "".join(
            f"\t\t\tif = {{\n\t\t\t\tlimit = {{ scope:pp_dir = flag:{direction} }}\n"
            f"\t\t\t\tpp_lprof_swap_rules = {{ a = {a} b = {b} }}\n\t\t\t}}\n"
            for direction, a, b in branches
        )
        parts.append(f"\t\tflag:r{r} = {{\n{body}\t\t}}\n")
    parts.append("\t}\n}\n")

    # the copy of a profile, clearing
    parts.append(
        "\n# ---- Copies of a profile ----\n"
        "\n# Any scope (scope:pp_lprof_country = the profile's country): scope:pp_lprof_country's $from$_* -> this scope's\n"
        "# $to$_* (icon with its frame number, colour, rules; what $from$ lacks goes). A slot is pp_lprof_<k>, the staged\n"
        "# copy pp_lprof_s, the edit buffer pp_lprof_e (country), a location's copy pp_lprof. The rules' category frame\n"
        "# numbers (drawn only in the editor) go separately: pp_lprof_copy_frames.\n"
        "pp_lprof_copy_profile = {\n"
        + "".join(_pull(kind, name) for kind, name in _profile_pulls(config))
        + "}\n"
        "\n# Any scope: the frame numbers of the rules' category targets, scope:pp_lprof_country's $from$_* -> this scope's\n"
        "# $to$_* (slots, the staged copy, the edit buffer; a location's copy needs none).\npp_lprof_copy_frames = {\n"
        + "".join(_pull("n", name) for name in frame_fields(config))
        + "}\n"
        "\n# Any scope: a copy of a profile ($p$_*) removed. The rules' frame numbers exist only on slots, the staged copy\n"
        "# and the edit buffer (pp_lprof_clear_frames): removing a variable never set counts as a use, and on a location\n"
        "# copy logged \"used but never set\" (in game 2026-11-07).\npp_lprof_clear_copies = {\n"
        + "".join(f"\tremove_variable = $p$_{name}\n" for name in profile_fields(config))
        + "}\n"
        "\n# Any scope but a location: the rules' frame numbers of a copy ($p$_*) removed.\npp_lprof_clear_frames = {\n"
        + "".join(f"\tremove_variable = $p$_{name}\n" for name in frame_fields(config))
        + "}\n"
        "\n# Location scope: removes the rule states and the payback notes.\npp_lprof_clear_states = {\n"
        + "".join(f"\tremove_variable = pp_lprof_r{r}_st\n\tremove_variable = pp_lprof_r{r}_est\n" for r in rules)
        + "}\n"
    )

    def pull_flag(name: str, what: str, flags: list[str]) -> str:
        return (
            f"\n# Any scope: the {what} flag in scope:pp_lprof_country's variable $from$ -> this scope's $to$ (removed when\n"
            f"# $from$ holds none). A switch: the flag is compared, never copied as a value.\n{name} = {{\n"
            "\tremove_variable = $to$\n\tif = {\n\t\tlimit = { scope:pp_lprof_country = { has_variable = $from$ } }\n"
            "\t\tswitch = {\n\t\t\ttrigger = scope:pp_lprof_country.var:$from$\n"
            + "".join(f"\t\t\tflag:{flag} = {{ set_variable = {{ name = $to$ value = flag:{flag} }} }}\n" for flag in flags)
            + "\t\t}\n\t}\n}\n"
        )

    parts.append(pull_flag("pp_lprof_pull_icon", "icon (a building category or a symbol)", icon_flags))
    parts.append(pull_flag("pp_lprof_pull_cat", "building category", categories))
    return "".join(parts)


def declared_flags(items: list[lp.Item], config: Config) -> list[str]:
    """Every flag the GUI passes to the scripted GUIs."""
    flags = {f"s{k}" for k in range(1, config.slots + 1)} | {"none", EDITED, NEXT} | set(fields(config)) | set(DIRECTIONS)
    flags |= {flag for _, flag, _ in GLOBAL_GROUPS}
    flags |= {f"c{n}" for n in range(1, len(config.colors) + 1)}
    flags |= {item.key for item in items} | {symbol.key for symbol in config.symbols}
    return sorted(flags)


def _profile_pulls(config: Config) -> list[tuple[str, str]]:
    """(pull kind, field) of pp_lprof_copy_profile: g goods scope, icon / cat flag (a switch), n number."""
    pulls = [("g", "ig"), ("icon", "ic"), ("n", "in"), ("n", "col")]
    for r in range(1, config.rules + 1):
        pulls += [("g", f"r{r}_g"), ("cat", f"r{r}_c"), ("n", f"r{r}_pb")]
    pulls += [("n", name) for name, _, _ in GLOBAL_GROUPS]
    return pulls


def _pull(kind: str, name: str) -> str:
    return f"\tpp_lprof_pull_{kind} = {{ from = $from$_{name} to = $to$_{name} }}\n"


def profile_fields(config: Config) -> list[str]:
    """The fields of a copy of a profile (variable <prefix>_<field>)."""
    return [name for _, name in _profile_pulls(config)]


def frame_fields(config: Config) -> list[str]:
    """The frame numbers of the rules' category targets (slots, staged copy, edit buffer)."""
    return [f"r{r}_cn" for r in range(1, config.rules + 1)]


def copy_names(prefix: str, config: Config, frames: bool = False) -> list[str]:
    """The variables of a copy of a profile (a location's: pp_lprof_*, the edit buffer's: pp_lprof_e_* with frames)."""
    return [f"{prefix}_{name}" for name in profile_fields(config) + (frame_fields(config) if frames else [])]


def gui_only_variables(config: Config) -> list[str]:
    """Variables the script sets and only the GUI reads: a location's icon (and its frame) and colour, the whole edit
    buffer; and the location's Towns and Buildings switch (the badge shows it; the rule group that reads it is
    generated elsewhere, construction_plan_country.py)."""
    location = [f"{COPY}_{name}" for name in ("ig", "ic", "in", "col", "xc")]
    return location + copy_names(BUFFER, config, frames=True)


def render_declarations(items: list[lp.Item], config: Config) -> str:
    reads = "".join(f"\t\t\t\thas_variable = {name}\n" for name in gui_only_variables(config))
    return (
        "\n# Any scope, never run (pp_cplan_run calls it under always = no): declares the flags the GUI passes and reads\n"
        "# the variables only the GUI reads, so the script check logs no 'used but never set' line for them.\n"
        "pp_lprof_declare_flags = {\n"
        + "".join(f"\tset_variable = {{ name = pp_lprof_flag value = flag:{flag} }}\n" for flag in declared_flags(items, config))
        + "\tif = {\n\t\tlimit = {\n\t\t\tOR = {\n\t\t\t\thas_variable = pp_lprof_flag\n"
        + reads
        + "\t\t\t}\n\t\t}\n\t\tremove_variable = pp_lprof_flag\n\t}\n}\n"
    )


def render_examples(items: list[lp.Item], config: Config) -> str:
    """The example profiles ([[location_profiles.examples]]), each made in the next free slot with the buttons' own
    effects (new, then the edit buffer's slot e: icon, colour, rules, payback steps, global groups)."""
    keys = {item.key for item in items}
    symbols = {symbol.key for symbol in config.symbols}
    groups = {group: flag for _, flag, group in GLOBAL_GROUPS}
    steps = config.payback_steps

    def scope(name: str, value: str) -> str:
        return f"\t\tsave_scope_value_as = {{ name = {name} value = flag:{value} }}\n"

    parts = [
        "\n# Country scope (root = the country): the example profiles ([[location_profiles.examples]]), each in the next free\n"
        "# slot (none once all are used), made with the buttons' own effects. The profile editor offers them while the\n"
        "# country has no profile; the test world's setup uses them too.\npp_lprof_examples_do = {\n"
    ]
    for number, example in enumerate(config.examples, 1):
        if example.icon not in keys | symbols:
            raise ValueError(f"example profile {number}: unknown icon {example.icon}")
        if not 1 <= example.color <= len(config.colors):
            raise ValueError(f"example profile {number}: colour {example.color} out of range")
        if len(example.rules) > config.rules:
            raise ValueError(f"example profile {number}: more than {config.rules} rules")
        body = [scope("pp_slot", NEXT), "\t\tpp_lprof_new_do = yes\n", scope("pp_slot", EDITED),
                scope("pp_field", "icon"), scope("pp_key", example.icon), "\t\tpp_lprof_set_do = yes\n",
                scope("pp_col", f"c{example.color}"), "\t\tpp_lprof_color_do = yes\n"]
        for r, (target, payback) in enumerate(example.rules, 1):
            if target not in keys:
                raise ValueError(f"example profile {number}: unknown rule target {target}")
            body += [scope("pp_field", f"r{r}"), scope("pp_key", target), "\t\tpp_lprof_set_do = yes\n"]
            if payback is not None:
                if payback not in steps:
                    raise ValueError(f"example profile {number}: payback {payback} is not one of {steps}")
                # down from any payback: the last step, then one step down each
                body.append(scope("pp_dir", "down"))
                body += ["\t\tpp_lprof_payback_do = yes\n"] * (len(steps) - steps.index(payback))
        for group in example.off:
            if group not in groups:
                raise ValueError(f"example profile {number}: unknown global group {group}")
            body += [scope("pp_field", groups[group]), "\t\tpp_lprof_global_do = yes\n"]
        parts.append(f"\t# example {number}: {example.icon}\n\tif = {{\n\t\tlimit = {{ pp_lprof_first_free > 0 }}\n"
                     + "".join(body) + "\t}\n")
    parts.append("}\n")
    return "".join(parts)


def render_effects(items: list[lp.Item], found: dict[str, list[Candidate]], config: Config, categories: list[str],
                   maps: MarkMaps | None = None) -> str:
    return (
        HEADER
        + render_targets(found)
        + render_dispatch(items, found, config)
        + render_marks(items, found)
        + render_building_marks(maps or mark_maps([], {}, {}))
        + render_slots(config)
        + render_edits(items, config, categories)
        + render_examples(items, config)
        + render_declarations(items, config)
    )


# ---------------------------------------------------------------------------------------------------------------------
# script values and triggers


def _var_n(name: str, var: str, comment: str) -> str:
    return (f"# {comment}\n{name} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {var} }}\n"
            f"\t\tvalue = var:{var}\n\t\tsubtract = 100\n\t}}\n}}\n")


def render_values(config: Config, categories: list[str], items: list[lp.Item] | None = None,
                  found: dict[str, list[Candidate]] | None = None) -> str:
    slots = range(1, config.slots + 1)
    quick = render_quick(items, found) if items is not None and found is not None else ""
    parts = [
        HEADER,
        "\n# Any scope: profile slots and rules per profile ([location_profiles]).\n"
        f"pp_lprof_slots = {{ value = {config.slots} }}\npp_lprof_rule_count = {{ value = {config.rules} }}\n",
        "\n# Country scope: 1 while a location of the country has a profile or a mark (the Locations rule group runs and\n"
        "# its weight counts: pp_cplan_profiles_cw, pp_construction_plan_generated.txt).\n"
        "pp_lprof_group_n = {\n\tvalue = 0\n\tif = {\n\t\tlimit = { pp_lprof_has_locations = yes }\n\t\tvalue = 1\n\t}\n}\n",
        "\n# Location scope, in the pass (scope:pp_cplan_btype and the cost values set): the payback of its next level + 100,\n"
        "# compared with the rule's limit (+ 100); 1 + the build cost, the start picker's key (never 0, which is unset).\n"
        "pp_lprof_payback100 = {\n\tvalue = pp_cplan_est_payback_years\n\tadd = 100\n}\n"
        "pp_lprof_cost1 = {\n\tvalue = pp_cplan_est_cost\n\tadd = 1\n}\n\n",
        _var_n("pp_lprof_n", "pp_lprof", "Location scope: the profile slot (0 none)."),
        _var_n("pp_lprof_e_n", "pp_lprof_e_k", "Country scope: the slot in the editor's buffer (0 none)."),
        "\n# Any scope: the frame (+ 100) of the flag scope:pp_key in the picture strip (pp_profile_symbols.dds: the building\n"
        "# categories, then the symbols), stored beside an icon flag or category rule target; 0 for anything else.\n"
        "pp_lprof_key_frame = {\n\tvalue = 0\n"
        + "".join(f"\t{'if' if index == 1 else 'else_if'} = {{ limit = {{ scope:pp_key = flag:{flag} }} value = {100 + index} }}\n"
                  for index, flag in enumerate(frame_flags(categories, config), 1))
        + "}\n",
        "\n# Country scope (pp_lprof_k = a slot + 100): the var:pp_lprof range of its locations.\n"
        "pp_lprof_k_lo = {\n\tvalue = var:pp_lprof_k\n\tsubtract = 0.5\n}\n"
        "pp_lprof_k_hi = {\n\tvalue = var:pp_lprof_k\n\tadd = 0.5\n}\n",
        f"\n# Country scope (pp_lprof_k = a new slot + 100): its colour + 100, colour k wrapping after the last of the {len(config.colors)}.\n"
        f"pp_lprof_new_color = {{\n\tvalue = var:pp_lprof_k\n\tsubtract = {101 - len(config.colors)}\n\tmodulo = {len(config.colors)}\n\tadd = 101\n}}\n",
        "\n# Country scope: the first slot not in use (0 when all are; the editor offers a new profile while one is free).\n"
        "pp_lprof_first_free = {\n\tvalue = 0\n"
        + "".join(
            f"\t{'if' if k == 1 else 'else_if'} = {{ limit = {{ NOT = {{ has_variable = pp_lprof_{k}_on }} }} value = {k} }}\n"
            for k in slots
        )
        + "}\n"
        "\n# Country scope: the profiles in use.\npp_lprof_used_n = {\n\tvalue = 0\n"
        + "".join(f"\tif = {{ limit = {{ has_variable = pp_lprof_{k}_on }} add = 1 }}\n" for k in slots)
        + "}\n\n",
    ]
    for r in range(1, config.rules + 1):
        parts.append(_var_n(f"pp_lprof_r{r}_st_n", f"pp_lprof_r{r}_st",
                            f"Location scope: the state of rule {r} after the last pass (0 not run yet; 1-10 PP_LPROF_ST_<n>)."))
    return "".join(parts) + quick


def render_triggers(categories: list[str], config: Config, maps: MarkMaps | None = None) -> str:
    return (
        HEADER
        + render_building_mark_triggers(maps or mark_maps([], {}, {}))
        + "\n# Any scope: the flag scope:pp_key names a building category item.\npp_lprof_category_key = {\n\tOR = {\n"
        + "".join(f"\t\tscope:pp_key = flag:{category}\n" for category in categories)
        + "\t}\n}\n"
        "\n# Any scope: the flag scope:pp_key names a symbol ([location_profiles.symbols]; only a profile's icon).\n"
        "pp_lprof_symbol_key = {\n\tOR = {\n"
        + "".join(f"\t\tscope:pp_key = flag:{symbol.key}\n" for symbol in config.symbols)
        + "\t\talways = no\n\t}\n}\n"
        "\n# Country scope (root = this country, in the pass and in the panel): a location the country owns has a profile or\n"
        "# a mark of the Location Plan (the profile rule group has something to run).\n"
        "pp_lprof_has_locations = {\n\tOR = {\n\t\tany_in_list = {\n\t\t\tvariable = pp_lprof_locs\n\t\t\towner ?= root\n"
        "\t\t\thas_variable = pp_lprof\n\t\t}\n\t\tany_in_list = {\n\t\t\tvariable = pp_lplan_locs\n\t\t\towner ?= root\n"
        "\t\t\thas_variable = pp_lplan_n\n\t\t}\n\t}\n}\n"
        "\n# Location scope: a rule of the location's profile has the good $g$ as its target (that good is the profile's here:\n"
        "# the global rules for it stand back; pp_construction_plan.txt's triggers).\n"
        "pp_lprof_has_good = {\n\thas_variable = pp_lprof\n\tOR = {\n"
        + "".join(f"\t\tAND = {{ has_variable = pp_lprof_r{r}_g var:pp_lprof_r{r}_g = goods:$g$ }}\n"
                  for r in range(1, config.rules + 1))
        + "\t}\n}\n"
        "\n# Location scope: a rule of the location's profile has the building category $c$ (a category key such as\n"
        "# trade_category) as its target (that category is the profile's here: the global rules leave its buildings to it).\n"
        "pp_lprof_has_category = {\n\thas_variable = pp_lprof\n\tOR = {\n"
        + "".join(f"\t\tAND = {{ has_variable = pp_lprof_r{r}_c var:pp_lprof_r{r}_c = flag:$c$ }}\n"
                  for r in range(1, config.rules + 1))
        + "\t}\n}\n"
        "\n# Location scope: a rule of the location's profile has a staple food as its target (the profile decides which\n"
        f"# food is made here: the food rule's farm step stands back). Staple foods: {', '.join(staple_foods.staple_foods())}.\n"
        "pp_lprof_food_target = {\n\thas_variable = pp_lprof\n\tOR = {\n"
        + "".join(f"\t\tAND = {{ has_variable = pp_lprof_r{r}_g var:pp_lprof_r{r}_g = {{ {_any_goods(staple_foods.staple_foods())} }} }}\n"
                  for r in range(1, config.rules + 1))
        + "\t}\n}\n"
    )


def _any_goods(goods: tuple[str, ...]) -> str:
    """A trigger in goods scope: this is one of the goods."""
    return "OR = { " + " ".join(f"this = goods:{good}" for good in goods) + " }"


# ---------------------------------------------------------------------------------------------------------------------


def _write(path: Path, text: str, write: bool) -> bool:
    old = path.read_text(encoding="utf-8") if path.is_file() else None
    if old == text:
        return False
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return True


def build(repo: Path, project: Path, mod_root: Path, vanilla_root: Path) -> tuple[Result, dict[Path, str]]:
    config = load_config(project)
    items = profile_items(repo, project)
    found, categories = targets(repo, project, mod_root, vanilla_root)
    result = Result(items=items, targets=found, categories=categories)
    category_keys = [item.key for item in items if item.kind == "category"]
    maps = building_mark_maps(repo, project, mod_root, vanilla_root)
    texts = {
        mod_root / EFFECTS: render_effects(items, found, config, category_keys, maps),
        mod_root / VALUES: render_values(config, category_keys, items, found),
        mod_root / TRIGGERS: render_triggers(category_keys, config, maps),
    }
    return result, texts


def apply(repo: Path, project: Path, mod_root: Path, vanilla_root: Path, write: bool = True) -> int:
    """Writes the generated files; returns how many changed."""
    _, texts = build(repo, project, mod_root, vanilla_root)
    return sum(_write(path, text, write) for path, text in texts.items())
