"""Command surface for the Prosper or Perish constructor workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT_MARKER = "constructor.toml"
CONSTRUCTOR_PROFILE = "constructor"
CONSTRUCTOR_LOAD_ORDER = Path("constructor.load_order.toml")
SAVEGAME_DATASET = Path("graphs/dataset")
SAVEGAME_NOTEBOOK_DATA = Path("graphs/savegame_notebooks/data")
SAVEGAME_NOTEBOOK_EXPORTS = Path("graphs/savegame_notebooks/exports")
SAVEGAME_LEGACY_DATASETS = (
    Path("graphs/dataset_v2"),
    Path("graphs/savegame_progression_dataset"),
    Path("artifacts/data/savegame_progression"),
    Path("graphs/dashboard_benchmark_report.json"),
)
SAVEGAME_ARTIFACT_DIR = Path("artifacts/data/savegame")
SYNC_STATE_PATH = Path("artifacts/sync/state.json")
GOODS_FLOW_EXPLORER = Path("graphs/goods_flow_explorer.html")
SAVEGAME_EXPLORER = Path("graphs/savegame_explorer.html")
SAVEGAME_PROGRESSION_EXPLORER = Path("graphs/savegame_progression.html")
PUBLISHED_SAVEGAME_EXPLORER = Path("docs/examples/savegame_explorer.html")
EUROPEDIA_EXPORT = Path("graphs/europedia.html")
EUROPEDIA_ENTRIES = Path("graphs/europedia_entries.json")
PUBLISHED_GRAPH_EXAMPLES = (
    GOODS_FLOW_EXPLORER.name,
    SAVEGAME_EXPLORER.name,
    EUROPEDIA_EXPORT.name,
    EUROPEDIA_ENTRIES.name,
)
# The World Builder stage patches blueprints, so it runs before the render stage (as in `ppc build`).
SYNC_STAGES = ("worldbuilder", "blueprints")
# Everything `ppc worldbuilder apply` reads besides the project TOML, the handover and the blueprints: the code it
# runs (stage.py's import closure and the scripts it executes), repo data, and the mod folders it parses through
# the constructor load order (scripts, setup, map data).
WORLDBUILDER_CODE_AND_DATA = (
    "src/prosper_or_perish_constructor/worldbuilder",
    "src/prosper_or_perish_constructor/building_footprint.py",
    "src/prosper_or_perish_constructor/free_building_levels.py",
    "src/prosper_or_perish_constructor/location_baseline.py",
    "src/prosper_or_perish_constructor/location_status.py",
    "src/prosper_or_perish_constructor/rural_capacity.py",
    "src/prosper_or_perish_constructor/yaml_io.py",
    "scripts/generate_rural_capacity_values.py",
    "scripts/generate_raw_material_local_map_modes.py",
    "tools/map_mode_styles.py",
    "config",
    "data",
)
WORLDBUILDER_MOD_INPUTS = (
    "in_game/common",
    "in_game/map_data",
    "main_menu/common",
    "main_menu/setup",
    "loading_screen/common",
)
SAVEGAME_PURGE_PATHS = (
    SAVEGAME_ARTIFACT_DIR,
    SAVEGAME_EXPLORER,
    SAVEGAME_PROGRESSION_EXPLORER,
    PUBLISHED_SAVEGAME_EXPLORER,
    SAVEGAME_DATASET,
    SAVEGAME_NOTEBOOK_DATA,
    SAVEGAME_NOTEBOOK_EXPORTS,
    *SAVEGAME_LEGACY_DATASETS,
)
BOM_TEXT_RELATIVE_PATHS = (
    Path("main_menu/common/game_concepts/pp_location_potential.txt"),
    Path("main_menu/common/game_concepts/pp_fish_capacity.txt"),
    Path("main_menu/common/game_concepts/pp_forest_capacity.txt"),
    Path("main_menu/common/game_concepts/pp_population_capacity.txt"),
    Path("main_menu/common/static_modifiers/pp_capacity_pressure_effects.txt"),
    Path("main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt"),
    Path("main_menu/common/static_modifiers/pp_location_modifiers.txt"),
    Path("in_game/common/climates/pp_climate_changes.txt"),
    Path("in_game/common/vegetation/pp_vegetation_changes.txt"),
    Path("in_game/common/topography/pp_topography_changes.txt"),
    Path("in_game/common/static_modifiers/pp_rgo_static_bonuses.txt"),
    Path("in_game/common/estate_privileges/pp_estate_privilege_adjustments.txt"),
    Path("in_game/common/societal_values/pp_societal_value_adjustments.txt"),
    Path("in_game/common/location_ranks/pp_location_rank_adjustments.txt"),
    Path("in_game/common/advances/pp_local_resource_productivity_advances.txt"),
    Path("in_game/common/advances/pp_prosperity_advances_adjustments.txt"),
    Path("in_game/common/building_types/pp_mercury_patio_adjustments.txt"),
    Path("in_game/common/script_values/pp_building_capacity_values.txt"),
    Path("in_game/common/scripted_effects/pp_capacity_precalc.txt"),
    Path("in_game/common/scripted_effects/pp_capacity_culling_effects.txt"),
    Path("in_game/gfx/map/map_modes/pp_local_output_modifier_map_modes.txt"),
    Path("in_game/common/on_action/pp_apply_location_modifiers.txt"),
    Path("in_game/common/on_action/pp_building_capacity_culling_v2.txt"),
)
GAME_LOADED_TEXT_ROOTS = ("main_menu", "in_game")
GAME_LOADED_TEXT_SUFFIXES = {".asset", ".gfx", ".gui", ".info", ".txt", ".yml"}
EU5_USER_DATA_SUFFIX = Path("Documents/Paradox Interactive/Europa Universalis V")
GAME_RULE_PRESET_RELATIVE_PATH = Path("player/game_rules/presets.txt")
OBSOLETE_MOD_GAME_RULE_SETTING_KEYS = {
    "pp_ai_building_maintenance_normal",
    "pp_ai_building_maintenance_neg_025",
    "pp_ai_building_maintenance_neg_050",
    "pp_ai_building_maintenance_neg_075",
}
PRICE_MODIFIER_TYPE_DEFINITIONS = Path(
    "main_menu/common/modifier_type_definitions/pp_modifier_types.txt"
)
PRICE_MODIFIER_ICONS = Path("main_menu/common/modifier_icons/pp_price_modifier_icons.txt")
PRICE_MODIFIER_LOCALIZATION = Path("main_menu/localization/english/pp_modifier_types_l_english.yml")
FARMING_CAPACITY_RAW_MODIFIER_BRIDGES = Path(
    "in_game/common/building_types/zzzz_pp_farming_capacity_raw_modifier_bridges.txt"
)
FARMING_CAPACITY_MODIFIER_TYPES = Path(
    "main_menu/common/modifier_type_definitions/pp_farming_capacity_modifier_types.txt"
)
FARMING_CAPACITY_MODIFIER_ICONS = Path(
    "main_menu/common/modifier_icons/pp_farming_capacity_modifier_icons.txt"
)
FARMING_CAPACITY_MODIFIER_LOCALIZATION = Path(
    "main_menu/localization/english/pp_farming_capacity_modifier_types_l_english.yml"
)
PROVINCE_FOOD_SALES_MODIFIER_KEY = "local_province_food_sales_output_modifier"
PROVINCE_FOOD_SALES_PRICE_SCENARIO_SCALE = 0.25
PROVINCE_FOOD_SALES_PRICE_CAP_SCALE = 0.5
PROVINCE_FOOD_SALES_CHEAP_CAP_TARGET = -0.450
PROVINCE_FOOD_SALES_EXPENSIVE_CAP_TARGET = 0.124
PROVINCE_FOOD_SALES_STARVING_TARGET = 0.080
PROVINCE_FOOD_SALES_TOTAL_MODIFIER_MIN = -0.4
PROVINCE_FOOD_SALES_TOTAL_MODIFIER_MAX = 0.4
PROVINCE_FOOD_SALES_GROWTH_CAP_TARGET = 2.0
PROVINCE_FOOD_SALES_TOLERANCE = 0.000001
PROVINCE_FOOD_SALES_PROFITABILITY_BLUEPRINT = Path("buildings/victuals_market_export.yml")
PROVINCE_FOOD_SALES_PROFITABILITY_METHOD = "pp_province_food_to_market"
PROVINCE_FOOD_SALES_STATIC_TARGETS = {
    "cheap_food_in_location": -0.900,
    "expensive_food_in_location": 0.248,
    "province_starving": PROVINCE_FOOD_SALES_STARVING_TARGET,
}
PROVINCE_FOOD_SALES_EDGE_PRICE_TARGETS = {
    "cheap_cap_0x": PROVINCE_FOOD_SALES_CHEAP_CAP_TARGET,
    "base_100": 0.0,
    "expensive_cap_2x": PROVINCE_FOOD_SALES_EXPENSIVE_CAP_TARGET,
}
PROVINCE_FOOD_SALES_EDGE_STARVING_TARGETS = {
    "no": 0.0,
    "yes": PROVINCE_FOOD_SALES_STARVING_TARGET,
}
PROVINCE_FOOD_SALES_MATRIX_TARGETS = {
    ("rural_settlement", "cheap_cap_0x", "full", "no"): -0.4,
    ("rural_settlement", "base_100", "full", "no"): 0.050,
    ("megalopolis", "expensive_cap_2x", "empty", "yes"): 0.4,
}
PROVINCE_FOOD_SALES_STORAGE_TARGET_EDGE = ("rural_settlement", "cheap_cap_0x", "full", "no")
PROVINCE_FOOD_SALES_RANK_TARGETS = {
    "rural_settlement": 0.136,
    "town": 0.156,
    "city": 0.176,
    "megalopolis": 0.196,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args, extra = parser.parse_known_args(argv)

    repo = _resolve_repo(args.repo)
    project = repo / args.project

    try:
        return args.handler(args, extra, repo, project)
    except KeyboardInterrupt:
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ppc",
        description="Prosper or Perish constructor workflow commands.",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Repository root. Defaults to the nearest parent containing constructor.toml.",
    )
    parser.add_argument(
        "--project",
        default=ROOT_MARKER,
        help="Project TOML path relative to --repo. Defaults to constructor.toml.",
    )

    subcommands = parser.add_subparsers(dest="command", required=True)

    _add_command(
        subcommands,
        "setup",
        "Install dev dependencies, then inspect the constructor project.",
        _setup,
    )
    _add_command(
        subcommands,
        "finalize",
        "Finalize generated mod text, metadata, and UTF-8 BOM encodings.",
        _finalize,
    )
    worldbuilder = _add_command(
        subcommands,
        "worldbuilder",
        "Consume the World Builder handover: geography, attribute rows, improvement buildings, farm land, setup.",
        _worldbuilder,
    )
    worldbuilder.add_argument(
        "action",
        choices=("apply", "export-development", "check", "food-check"),
        help="apply writes the mod inputs; export-development writes the vanilla development table; check reports the fit of the written setup; food-check compares the start-food model with the exported save.",
    )
    worldbuilder.add_argument(
        "--save",
        type=Path,
        default=None,
        help="food-check only: export this .eu5 save first (otherwise the existing artifacts/data/savegame export is used).",
    )
    footprint = _add_command(
        subcommands,
        "footprint",
        "Write each building's footprint population capacity (blueprint footprint class x employment) into the mod.",
        _footprint,
    )
    footprint.add_argument(
        "action",
        choices=("apply", "check"),
        help="apply writes the capacity lines into the compiled mod (ppc build does this too); check validates the classes.",
    )
    labour = _add_command(
        subcommands,
        "labour",
        "Set each producing production method's manual labor share (blueprint labour class) in the accepted blueprints.",
        _labour,
    )
    labour.add_argument(
        "action",
        choices=("apply", "check"),
        help="apply rewrites the method inputs in blueprints/accepted; check lists untagged methods and methods off their class.",
    )
    labour.add_argument(
        "--verbose",
        action="store_true",
        help="check: also list every method apply would change.",
    )
    clean_game_rule_presets = _add_command(
        subcommands,
        "clean-game-rule-presets",
        "Remove this mod's custom game-rule settings from local EU5 saved presets.",
        _clean_game_rule_presets,
    )
    clean_game_rule_presets.add_argument(
        "--user-data-root",
        type=Path,
        default=None,
        help="EU5 user data root. Defaults to the local Documents/Paradox Interactive/Europa Universalis V folder.",
    )
    clean_game_rule_presets.add_argument(
        "--preset",
        type=Path,
        default=None,
        help="Explicit presets.txt path. Overrides --user-data-root.",
    )
    _add_command(
        subcommands,
        "inspect",
        "Inspect the configured constructor project.",
        _orchestrator("inspect"),
    )
    farming_village_unlocks = _add_command(
        subcommands,
        "farming-village-unlocks",
        "Check or regenerate data-driven farming-village RGO unlock advances.",
        _farming_village_unlocks,
    )
    farming_village_unlocks_mode = farming_village_unlocks.add_mutually_exclusive_group()
    farming_village_unlocks_mode.add_argument(
        "--check",
        action="store_true",
        help="Fail if farming_village.yml unlock advances are stale. This is the default.",
    )
    farming_village_unlocks_mode.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the farming_village.yml unlock advances from current location data.",
    )
    _add_command(
        subcommands,
        "test",
        "Run pytest. Extra args are passed to pytest.",
        _test,
    )
    _add_command(
        subcommands,
        "analyze",
        "Export static parser tables and refresh the goods-flow docs example.",
        _analyze,
    )
    update_audit = _add_command(
        subcommands,
        "update-audit",
        "Audit Prosper or Perish vanilla data dependencies across two EU5 refs.",
        _update_audit,
    )
    update_audit.add_argument(
        "--old-ref",
        required=True,
        help="Older vanilla EU5 Git ref, for example eu5-1.1.10.",
    )
    update_audit.add_argument(
        "--new-ref",
        required=True,
        help="Newer vanilla EU5 Git ref, for example eu5-1.2.3.",
    )
    update_audit.add_argument(
        "--load-order",
        type=Path,
        default=CONSTRUCTOR_LOAD_ORDER,
        help="Load-order TOML path relative to --repo. Defaults to constructor.load_order.toml.",
    )
    update_audit.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Report output directory. Defaults to reports/eu5_update_audit/<old>..<new>.",
    )
    output_modifiers = _add_command(
        subcommands,
        "output-modifiers",
        "Print cumulative global output modifiers by good and age.",
        _output_modifiers,
    )
    output_modifiers.add_argument(
        "--include-specific",
        action="store_true",
        help="Include output modifiers from advancements with potential-specific gates.",
    )
    output_modifiers.add_argument(
        "--load-order",
        type=Path,
        default=CONSTRUCTOR_LOAD_ORDER,
        help="Load-order TOML path relative to --repo. Defaults to constructor.load_order.toml.",
    )
    output_modifiers.add_argument(
        "--profile",
        default=CONSTRUCTOR_PROFILE,
        help="Parser profile from the load-order TOML. Defaults to constructor.",
    )
    province_food_sales_check = _add_command(
        subcommands,
        "province-food-sales-check",
        "Check parsed Province Food Sales modifier edge conditions.",
        _province_food_sales_check,
    )
    province_food_sales_check.add_argument(
        "--load-order",
        type=Path,
        default=CONSTRUCTOR_LOAD_ORDER,
        help="Load-order TOML path relative to --repo. Defaults to constructor.load_order.toml.",
    )
    province_food_sales_check.add_argument(
        "--profile",
        default=CONSTRUCTOR_PROFILE,
        help="Parser profile from the load-order TOML. Defaults to constructor.",
    )
    province_food_sales_check.add_argument(
        "--tolerance",
        type=float,
        default=PROVINCE_FOOD_SALES_TOLERANCE,
        help=f"Allowed absolute difference for checks. Defaults to {PROVINCE_FOOD_SALES_TOLERANCE:g}.",
    )
    production_throughput = _add_command(
        subcommands,
        "production-throughput",
        "Print best building production throughput by good and age.",
        _production_throughput,
    )
    production_throughput.add_argument(
        "--include-specific",
        action="store_true",
        help="Include production methods with potential-specific gates.",
    )
    production_throughput.add_argument(
        "--load-order",
        type=Path,
        default=CONSTRUCTOR_LOAD_ORDER,
        help="Load-order TOML path relative to --repo. Defaults to constructor.load_order.toml.",
    )
    production_throughput.add_argument(
        "--profile",
        default=CONSTRUCTOR_PROFILE,
        help="Parser profile from the load-order TOML. Defaults to constructor.",
    )
    production_profit = _add_command(
        subcommands,
        "production-profit",
        "Report and optionally convert vanilla output-producing building blueprint stubs.",
        _production_profit,
    )
    production_profit.add_argument(
        "--include-specific",
        action="store_true",
        help="Include production methods with potential-specific gates in the profit report.",
    )
    production_profit.add_argument(
        "--load-order",
        type=Path,
        default=CONSTRUCTOR_LOAD_ORDER,
        help="Load-order TOML path relative to --repo. Defaults to constructor.load_order.toml.",
    )
    production_profit.add_argument(
        "--profile",
        default=CONSTRUCTOR_PROFILE,
        help="Parser profile from the load-order TOML. Defaults to constructor.",
    )
    production_profit.add_argument(
        "--vanilla-profile",
        default="vanilla",
        help="Parser profile used to identify vanilla production buildings. Defaults to vanilla.",
    )
    production_profit.add_argument(
        "--write-blueprints",
        action="store_true",
        help="Convert cost-only vanilla production stubs into full REPLACE blueprints.",
    )
    production_profit.add_argument(
        "--import-missing",
        action="store_true",
        help="Create faithful REPLACE/CREATE blueprints for production buildings missing from the manifest.",
    )
    production_profit.add_argument(
        "--dry-run",
        action="store_true",
        help="With --write-blueprints or --import-missing, report changes without writing files.",
    )
    _add_command(
        subcommands,
        "savegame",
        "Export latest savegame facts and the savegame explorer.",
        _savegame,
    )
    _add_command(
        subcommands,
        "europedia",
        "Export the custom Prosper or Perish Europedia into the docs examples.",
        _europedia,
    )
    savegame_purge = _add_command(
        subcommands,
        "savegame-purge",
        "Delete generated savegame analysis artifacts and notebook datasets.",
        _savegame_purge,
    )
    savegame_purge.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated savegame paths that would be deleted without deleting them.",
    )
    _add_command(
        subcommands,
        "publish-docs",
        "Copy generated graph outputs into docs/examples.",
        _publish_docs,
    ).add_argument(
        "examples",
        nargs="*",
        help="Optional graph HTML files to publish. Defaults to all examples.",
    )
    _add_command(
        subcommands,
        "build",
        "Build accepted blueprints into the constructor mod copy with --overwrite.",
        _build,
    )
    sync = _add_command(
        subcommands,
        "sync",
        "RISKY: incrementally build and mirror the constructor mod into the live Paradox mod folder.",
        _sync,
    )
    sync.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation for live mod folder mirroring.",
    )
    sync.add_argument(
        "--force-build",
        action="store_true",
        help="Run smart sync generator stages even when their fingerprints are unchanged.",
    )
    sync.add_argument(
        "--force-deploy",
        action="store_true",
        help="Copy all built mod files to the live target even when they look unchanged.",
    )
    sync.add_argument(
        "--full-build",
        action="store_true",
        help="Use the previous full eu5-orchestrator build workflow before deploy.",
    )
    sync.add_argument(
        "--while-running",
        action="store_true",
        help="Deploy even while EU5 is running (its debug-mode filewatcher then hot-reloads the mod).",
    )
    vanilla_mirror = _add_command(
        subcommands,
        "vanilla-mirror",
        "Copy the game's data files to the local disk and point the load order at the copy "
        "(re-run after a game update).",
        _vanilla_mirror,
    )
    vanilla_mirror.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Directory for the copy. Defaults to ~/.cache/eu5-vanilla.",
    )

    blueprint = subcommands.add_parser(
        "blueprint",
        help="Run blueprint list, parity, evaluate, ratios, tag, good, or build workflows.",
        description="Blueprint workflow commands. Extra args are passed to eu5-orchestrator.",
    )
    blueprint_subcommands = blueprint.add_subparsers(dest="blueprint_command", required=True)
    _add_command(blueprint_subcommands, "list", "List accepted blueprints.", _blueprint("list"))
    _add_command(
        blueprint_subcommands,
        "parity",
        "Check blueprint output parity against generated mod files.",
        _blueprint("parity"),
    )
    _add_command(
        blueprint_subcommands,
        "evaluate",
        "Evaluate accepted blueprint economics and balance rules.",
        _blueprint("evaluate"),
    )
    ratios = _add_command(
        blueprint_subcommands,
        "ratios",
        "Show a combined modifier ratio table for accepted blueprints.",
        _blueprint_ratios,
    )
    ratios.add_argument(
        "tag",
        nargs="?",
        help="Optional building key, blueprint tag, custom tag, or filename stem.",
    )
    tag = _add_command(
        blueprint_subcommands,
        "tag",
        "Evaluate accepted blueprints matching a tag.",
        _blueprint_tag,
    )
    tag.add_argument(
        "tag",
        help="Building key, blueprint tag, custom tag, or filename stem, for example farming_capacity.",
    )
    good = _add_command(
        blueprint_subcommands,
        "good",
        "Compare production methods that produce one trade good.",
        _blueprint_good,
    )
    good.add_argument("good", help="Trade good id, for example coal or victuals.")
    _add_command(
        blueprint_subcommands,
        "build",
        "Build accepted blueprints into the constructor mod copy with --overwrite.",
        _build,
    )

    savegame_notebooks = subcommands.add_parser(
        "savegame-notebooks",
        help="Build RAM-efficient parquet data for savegame notebooks.",
        description="Savegame notebook commands using the constructor profile and load order.",
    )
    savegame_notebooks_subcommands = savegame_notebooks.add_subparsers(
        dest="savegame_notebooks_command",
        required=True,
    )
    savegame_notebooks_build = _add_savegame_notebooks_command(
        savegame_notebooks_subcommands,
        "build",
        "Ingest savegames, then write notebook-ready parquet data.",
        _savegame_notebooks_build,
    )
    savegame_notebooks_build.add_argument(
        "--save-dir",
        type=Path,
        default=None,
        help="Directory containing .eu5 saves. Defaults to auto-detecting the EU5 documents save folder.",
    )
    savegame_notebooks_build.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel save parser workers. Defaults to 4.",
    )
    savegame_notebooks_build.add_argument(
        "--no-ingest",
        action="store_true",
        help="Only rebuild notebook parquet from an existing graphs/dataset.",
    )
    savegame_notebooks_build.set_defaults(extended=False)
    savegame_notebooks_build.add_argument(
        "--extended",
        action="store_true",
        help="Include full slower legacy tables such as population, provinces, and characters.",
    )
    savegame_notebooks_build.add_argument(
        "--no-extended",
        action="store_false",
        dest="extended",
        help=argparse.SUPPRESS,
    )
    savegame_notebooks_build.add_argument(
        "--force",
        action="store_true",
        help="Rebuild notebook parquet even when existing output metadata is current.",
    )
    savegame_notebooks_build.add_argument(
        "--no-webp",
        action="store_true",
        help="Skip the standard global WebP map animation exports.",
    )
    return parser


def _add_command(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
    handler,
) -> argparse.ArgumentParser:
    command = subcommands.add_parser(
        name,
        help=help_text,
        description=f"{help_text} Use '--' before extra tool arguments when needed.",
    )
    command.set_defaults(handler=handler)
    return command


def _resolve_repo(repo: Path | None) -> Path:
    if repo is not None:
        resolved = repo.expanduser().resolve()
        _require_project_root(resolved)
        return resolved

    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ROOT_MARKER).is_file():
            return candidate

    raise SystemExit(
        f"Could not find {ROOT_MARKER}. Run from the repo or pass --repo /path/to/repo."
    )


def _require_project_root(repo: Path) -> None:
    if not (repo / ROOT_MARKER).is_file():
        raise SystemExit(f"{repo} does not look like this constructor repo; missing {ROOT_MARKER}.")


def _run(command: Sequence[str | os.PathLike[str]], repo: Path) -> int:
    printable = " ".join(str(part) for part in command)
    print(f"$ {printable}", flush=True)
    completed = subprocess.run([str(part) for part in command], cwd=repo, check=False)
    return completed.returncode


def _run_collecting_output(
    command: Sequence[str | os.PathLike[str]],
    repo: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[int, str]:
    printable = " ".join(str(part) for part in command)
    print(f"$ {printable}", flush=True)
    process = subprocess.Popen(
        [str(part) for part in command],
        cwd=repo,
        env=dict(env) if env is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output: list[str] = []
    if process.stdout is not None:
        for line in process.stdout:
            output.append(line)
            print(line, end="", flush=True)
    return process.wait(), "".join(output)


def _orchestrator(action: str):
    def handler(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
        return _run(["eu5-orchestrator", action, "--project", project, *extra], repo)

    return handler


def _blueprint(action: str):
    def handler(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
        result = _run(["eu5-orchestrator", "blueprint", action, "--project", project, *extra], repo)
        if result == 0 and action == "build":
            _finalize_constructor_mod(repo, project)
        return result

    return handler


def _blueprint_good(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    return _run(
        ["eu5-orchestrator", "blueprint", "good", "--project", project, "--good", args.good, *extra],
        repo,
    )


def _blueprint_ratios(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    return _run_blueprint_ratios(args.tag, extra, repo, project)


def _blueprint_tag(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    return _run(
        [
            "eu5-orchestrator",
            "blueprint",
            "evaluate",
            "--project",
            project,
            "--building",
            args.tag,
            *extra,
        ],
        repo,
    )


def _run_blueprint_ratios(
    tag: str | None, extra: Sequence[str], repo: Path, project: Path
) -> int:
    command: list[str | os.PathLike[str]] = [
        "eu5-orchestrator",
        "blueprint",
        "ratios",
        "--project",
        project,
    ]
    if tag is not None:
        command.append(tag)
    command.extend(extra)
    return _run(command, repo)


def _setup(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit("setup does not accept extra arguments.")

    sync_code = _run(["uv", "sync", "--dev"], repo)
    if sync_code != 0:
        return sync_code
    return _run(["eu5-orchestrator", "inspect", "--project", project], repo)


def _finalize(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit("finalize does not accept extra arguments.")

    _finalize_constructor_mod(repo, project)
    return 0


def _clean_game_rule_presets(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    if extra:
        raise SystemExit("clean-game-rule-presets does not accept extra arguments.")

    mod_root = _project_mod_root(repo, project)
    setting_keys = _mod_game_rule_setting_keys(mod_root) | OBSOLETE_MOD_GAME_RULE_SETTING_KEYS
    if not setting_keys:
        print("mod_game_rule_settings=0", flush=True)
        return 0

    preset = args.preset
    if preset is None:
        user_data_root = args.user_data_root or _default_eu5_user_data_root()
        preset = user_data_root / GAME_RULE_PRESET_RELATIVE_PATH
    if not preset.is_file():
        print(f"missing={preset}", flush=True)
        return 0

    removed = _remove_game_rule_settings_from_preset(preset, setting_keys)
    print(f"preset={preset}", flush=True)
    print(f"removed_game_rule_settings={removed}", flush=True)
    return 0


def _test(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    # Parallel workers come from [tool.pytest.ini_options] addopts; pass -n0 for a serial run.
    return _run([sys.executable, "-m", "pytest", *extra], repo)


def _vanilla_mirror(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit("vanilla-mirror does not accept extra arguments.")
    from prosper_or_perish_constructor import vanilla_mirror

    result = vanilla_mirror.mirror(repo / CONSTRUCTOR_LOAD_ORDER, args.target or vanilla_mirror.DEFAULT_TARGET)
    print(
        f"Game data copied from {result['source']} (build {result['buildid']}) to {result['target']}; "
        f"{result['override']} now points vanilla_root at the copy.",
        flush=True,
    )
    return 0


def _farming_village_unlocks(
    args: argparse.Namespace,
    extra: Sequence[str],
    repo: Path,
    project: Path,
) -> int:
    if extra:
        raise SystemExit("farming-village-unlocks does not accept extra arguments.")

    from prosper_or_perish_constructor.farming_village_unlocks import (
        check_blueprint_advancements,
        write_blueprint_advancements,
    )

    if args.write:
        changed = write_blueprint_advancements(repo, project)
        print(
            "farming_village_unlocks=updated" if changed else "farming_village_unlocks=unchanged",
            flush=True,
        )
        return 0

    check = check_blueprint_advancements(repo, project)
    if check.ok:
        print("farming_village_unlocks=ok", flush=True)
        return 0
    print("farming_village_unlocks=stale", flush=True)
    diff = check.unified_diff()
    if diff:
        print(diff, flush=True)
    print("Run: uv run ppc farming-village-unlocks --write", flush=True)
    return 1



def _worldbuilder_apply_on_build(project: Path) -> bool:
    with project.open("rb") as handle:
        config = tomllib.load(handle)
    section = config.get("worldbuilder")
    return bool(isinstance(section, dict) and section.get("apply_on_build", True))


def _worldbuilder_apply(repo: Path, project: Path) -> dict[str, object]:
    from prosper_or_perish_constructor.worldbuilder.stage import apply

    report = apply(repo, project, _project_mod_root(repo, project))
    print(
        "World Builder stage applied: "
        f"{report.get('class_injects')} class injects, "
        f"{(report.get('static_modifiers') or {}).get('static_modifiers')} static modifiers, "
        f"{(report.get('setup') or {}).get('rows')} starting building rows, "
        f"development for {(report.get('development') or {}).get('locations')} locations.",
        flush=True,
    )
    return report


def _worldbuilder(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit("worldbuilder does not accept extra arguments.")
    from prosper_or_perish_constructor.worldbuilder import stage

    if args.action == "apply":
        report = _worldbuilder_apply(repo, project)
        print(json.dumps({k: v for k, v in report.items() if k != "blueprints_patched"}, indent=2, default=str))
        return 0
    if args.action == "export-development":
        print(json.dumps(stage.export_development(repo, project), indent=2))
        return 0
    if args.action == "check":
        print(json.dumps(stage.check(repo, project, _project_mod_root(repo, project)), indent=2))
        return 0
    if args.action == "food-check":
        if args.save is not None:
            result = _run(["eu5-orchestrator", "savegame", "--project", project, "--save", args.save], repo)
            if result != 0:
                return result
        from prosper_or_perish_constructor.worldbuilder import food_check

        print(json.dumps(food_check.run(repo, project, _project_mod_root(repo, project)), indent=2, default=str))
        return 0
    raise SystemExit(f"unknown worldbuilder action {args.action!r}")


def _footprint(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit("footprint does not accept extra arguments.")
    from prosper_or_perish_constructor import building_footprint
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    if args.action == "check":
        errors = building_footprint.validate(repo, building_footprint.load_config(project), vanilla_root(repo, project))
        for error in errors:
            print(error)
        print("building footprint: " + (f"{len(errors)} problems" if errors else "every building has a footprint class"))
        return 1 if errors else 0
    _apply_building_footprint(repo, project, _project_mod_root(repo, project))
    return 0


def _labour(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit("labour does not accept extra arguments.")
    from prosper_or_perish_constructor import production_labour

    result = production_labour.apply(repo, project, write=args.action == "apply")
    for problem in result.problems:
        print(problem)
    if args.action == "check":
        if args.verbose:
            for plan in result.changed:
                print(f"{plan.method.blueprint.name}: {plan.method.name} ({plan.labour_class}) -> {plan.amounts}")
        print(
            f"production labour: {len(result.plans)} methods, {len(result.changed)} off their class, "
            f"{len(result.problems)} problems"
        )
        return 1 if result.problems or result.changed else 0
    if result.problems:
        print(f"production labour: {len(result.problems)} problems, nothing written")
        return 1
    print(
        f"production labour: {len(result.changed)} methods rewritten in {result.files_changed} blueprints; "
        f"report {production_labour.REPORT_RELATIVE_PATH}."
    )
    return 0


def _print_labour_check(repo: Path, project: Path) -> None:
    """Build-time summary; problems are printed, not fatal (tag new producing methods with ppc labour check)."""
    from prosper_or_perish_constructor import production_labour

    try:
        result = production_labour.apply(repo, project, write=False)
    except Exception as exc:  # noqa: BLE001 - the build must not fail on the advisory check
        print(f"Production labour check skipped: {exc}", flush=True)
        return
    for problem in result.problems:
        print(f"Production labour: {problem}", flush=True)
    print(
        f"Production labour: {len(result.plans)} methods tagged, {len(result.changed)} off their class "
        f"(run ppc labour apply), {len(result.problems)} problems.",
        flush=True,
    )


def _apply_building_footprint(repo: Path, project: Path, mod_root: Path) -> None:
    from prosper_or_perish_constructor import building_footprint
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    result = building_footprint.apply(repo, mod_root, project, vanilla_root(repo, project))
    print(
        f"Building footprint: population capacity written for {result.buildings_written} buildings "
        f"({result.buildings_ignored} ignored, {len(result.not_in_mod)} not in the mod) across "
        f"{result.files_changed} changed files; report {building_footprint.REPORT_RELATIVE_PATH}.",
        flush=True,
    )


def _build(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if _worldbuilder_apply_on_build(project):
        _worldbuilder_apply(repo, project)
    if _has_farming_village_blueprint(repo):
        unlock_code = _farming_village_unlocks(
            argparse.Namespace(write=False, check=True),
            (),
            repo,
            project,
        )
        if unlock_code != 0:
            return unlock_code
    build_code = _run(["eu5-orchestrator", "build", "--project", project, "--overwrite", *extra], repo)
    if build_code != 0:
        return build_code
    _finalize_constructor_mod(repo, project)
    _print_labour_check(repo, project)
    return 0


def _has_farming_village_blueprint(repo: Path) -> bool:
    from prosper_or_perish_constructor.farming_village_unlocks import BLUEPRINT_RELATIVE_PATH

    return (repo / BLUEPRINT_RELATIVE_PATH).is_file()


def _finalize_constructor_mod(repo: Path, project: Path) -> None:
    from prosper_or_perish_constructor.building_scaling import (
        apply_increase_per_level_cost_multiplier,
    )
    from prosper_or_perish_constructor.free_building_levels import (
        compile_free_building_level_modifiers,
        local_free_building_levels_sheet_csv_path,
    )
    from prosper_or_perish_constructor.food_storage_gui import (
        FOOD_STORAGE_GUI_DIVISOR_COUNTS,
        compile_food_storage_gui,
    )
    from prosper_or_perish_constructor.rgo_cost_redirects import write_rgo_cost_redirects

    from prosper_or_perish_constructor import profit_margins

    mod_root = _project_mod_root(repo, project)
    increase_cost_result = apply_increase_per_level_cost_multiplier(repo, mod_root, project)
    print(
        "Applied increase_per_level_cost multiplier "
        f"{increase_cost_result.multiplier} to {increase_cost_result.entries_scaled} "
        f"building entries across {increase_cost_result.files_changed} changed files.",
        flush=True,
    )
    _apply_building_footprint(repo, project, mod_root)
    if local_free_building_levels_sheet_csv_path(repo).is_file():
        compile_free_building_level_modifiers(repo, mod_root)
    _ensure_farming_capacity_raw_modifier_bridges(repo, mod_root)
    load_order_path = repo / CONSTRUCTOR_LOAD_ORDER
    if load_order_path.is_file():
        redirect_result = write_rgo_cost_redirects(
            repo=repo,
            mod_root=mod_root,
            load_order_path=load_order_path,
            profile_name=CONSTRUCTOR_PROFILE,
        )
        print(
            "Generated RGO cost redirects for "
            f"{len(redirect_result.assignments)} active expand_rgo cost entries, "
            f"{len(redirect_result.classification.priced_targets)} priced building targets, "
            f"and {len(redirect_result.classification.unpriced_buildings)} unpriced classified buildings.",
            flush=True,
        )
    _ensure_price_cost_modifier_assets(mod_root)
    from prosper_or_perish_constructor import gui_compat

    gui_compat.strip(mod_root)   # the food-storage compile counts its gauge lines per file
    food_storage_gui_result = compile_food_storage_gui(
        repo=repo,
        mod_root=mod_root,
        profile=CONSTRUCTOR_PROFILE,
        load_order_path=repo / CONSTRUCTOR_LOAD_ORDER,
    )
    if not food_storage_gui_result.skipped:
        localization_status = (
            "updated" if food_storage_gui_result.localization_changed else "unchanged"
        )
        print(
            "Compiled "
            f"{food_storage_gui_result.replacements} province-food GUI divisors "
            f"across {len(FOOD_STORAGE_GUI_DIVISOR_COUNTS)} files to "
            f"{food_storage_gui_result.divisor_literal} months from "
            f"{food_storage_gui_result.max_years:g} configured years; "
            f"{food_storage_gui_result.files_changed} GUI files changed and "
            "the food-storage map scale was "
            f"{'updated' if food_storage_gui_result.map_mode_changed else 'unchanged'}, "
            "while "
            "the food-storage localization was "
            f"{localization_status}.",
            flush=True,
        )
    protected = gui_compat.protect(mod_root)
    print(f"Protected GUI types from other mods' vanilla copies: {protected}.", flush=True)
    if load_order_path.is_file():
        from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

        margins = profit_margins.apply(
            mod_root, vanilla_root(repo, project), profit_margins.goods_prices(load_order_path, CONSTRUCTOR_PROFILE)
        )
        print(
            f"Profit margins: debug_max_profit kept at the base-price profit on {margins.methods_written} production "
            f"methods ({margins.files_changed} mod files changed, {len(margins.vanilla_replaced)} vanilla shared "
            f"methods replaced); still flagged: {len(margins.mod_losing)} mod methods that lose money at base "
            f"prices and {len(margins.vanilla_unchanged)} vanilla methods (see profit_margins.py).",
            flush=True,
        )
    _ensure_constructor_text_boms(mod_root)


def _project_mod_root(repo: Path, project: Path) -> Path:
    with project.open("rb") as handle:
        config = tomllib.load(handle)
    try:
        configured = config["project"]["mod_root"]
    except KeyError as error:
        raise SystemExit(f"Missing [project].mod_root in {project}") from error
    if not isinstance(configured, str):
        raise SystemExit(f"[project].mod_root must be a string in {project}")
    mod_root = Path(configured)
    return mod_root if mod_root.is_absolute() else repo / mod_root


def _resolve_repo_relative_path(repo: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo / path


def _ensure_farming_capacity_raw_modifier_bridges(repo: Path, mod_root: Path) -> None:
    from eu5gameparser.domain.building_types import load_building_type_data

    from prosper_or_perish_constructor.rural_capacity import (
        FARM_WATER_CONTROL_BUILDINGS,
        LAND_FARM_BUILDINGS,
        farm_capacity_modifier_for_building,
    )

    data = load_building_type_data(
        profile=CONSTRUCTOR_PROFILE,
        load_order_path=repo / CONSTRUCTOR_LOAD_ORDER,
    )
    building_keys = sorted(str(key) for key in data.building_types["name"].to_list())
    accepted_blueprint_keys = {
        path.stem
        for path in (repo / "blueprints" / "accepted" / "buildings").glob("*.yml")
    }
    land_farms = set(LAND_FARM_BUILDINGS)
    water_controls = dict(FARM_WATER_CONTROL_BUILDINGS)
    fallback_building_keys = [
        building for building in building_keys if building not in accepted_blueprint_keys
    ]

    bridge_lines = [
        "# Prosper or Perish - generated farming-capacity raw modifier fallbacks.",
        "# Accepted building blueprints own their raw_modifier entries directly.",
        "# Generated by ppc finalize; do not edit by hand.",
        "",
    ]
    generated_bridge_count = 0
    for building in fallback_building_keys:
        updates: dict[str, str] = {}
        if building in land_farms:
            updates[farm_capacity_modifier_for_building(building)] = "-1"
        if building in water_controls:
            updates[farm_capacity_modifier_for_building(building)] = water_controls[building]
        if not updates:
            continue
        generated_bridge_count += 1
        bridge_lines.append(f"TRY_INJECT:{building} = {{")
        bridge_lines.append("\traw_modifier = {")
        for key, value in updates.items():
            bridge_lines.append(f"\t\t{key} = {value}")
        bridge_lines.append("\t}")
        bridge_lines.append("}")
        bridge_lines.append("")

    _write_text_if_changed(
        mod_root / FARMING_CAPACITY_RAW_MODIFIER_BRIDGES,
        "\n".join(bridge_lines).rstrip() + "\n",
        encoding="utf-8-sig",
    )

    capacity_modifier_keys = [
        *(farm_capacity_modifier_for_building(building) for building, _ in FARM_WATER_CONTROL_BUILDINGS),
        *(farm_capacity_modifier_for_building(building) for building in LAND_FARM_BUILDINGS),
    ]
    _write_farming_capacity_modifier_types(mod_root, capacity_modifier_keys)
    _write_farming_capacity_modifier_icons(
        mod_root,
        building_modifiers={
            **{farm_capacity_modifier_for_building(building): building for building, _ in FARM_WATER_CONTROL_BUILDINGS},
            **{farm_capacity_modifier_for_building(building): building for building in LAND_FARM_BUILDINGS},
        },
    )
    _write_farming_capacity_modifier_localization(
        mod_root,
        building_modifiers={
            **{farm_capacity_modifier_for_building(building): building for building, _ in FARM_WATER_CONTROL_BUILDINGS},
            **{farm_capacity_modifier_for_building(building): building for building in LAND_FARM_BUILDINGS},
        },
    )
    print(
        "Generated farming capacity raw modifier fallbacks for "
        f"{generated_bridge_count} non-blueprint building types.",
        flush=True,
    )


def _write_farming_capacity_modifier_types(mod_root: Path, modifier_keys: Sequence[str]) -> None:
    lines = [
        "# Prosper or Perish - generated farming-capacity bridge modifier types.",
        "# Generated by ppc finalize; do not edit by hand.",
        "",
    ]
    for key in modifier_keys:
        lines.extend(
            (
                f"{key} = {{",
                "\tdecimals = 2",
                "\tgame_data = {",
                "\t\tcategory = location",
                "\t}",
                "}",
                "",
            )
        )
    _write_text_if_changed(
        mod_root / FARMING_CAPACITY_MODIFIER_TYPES,
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8-sig",
    )


def _write_farming_capacity_modifier_icons(
    mod_root: Path,
    *,
    building_modifiers: Mapping[str, str],
) -> None:
    lines = [
        "# Prosper or Perish - generated farming-capacity bridge modifier icons.",
        "# Generated by ppc finalize; do not edit by hand.",
        "",
    ]
    for modifier_key, building in building_modifiers.items():
        icon = f"gfx/interface/icons/buildings/{building}.dds"
        lines.extend(
            (
                f"{modifier_key} = {{",
                f'\tpositive = "{icon}"',
                f'\tnegative = "{icon}"',
                "}",
                "",
            )
        )
    _write_text_if_changed(
        mod_root / FARMING_CAPACITY_MODIFIER_ICONS,
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8-sig",
    )


def _write_farming_capacity_modifier_localization(
    mod_root: Path,
    *,
    building_modifiers: Mapping[str, str],
) -> None:
    lines = [
        "l_english:",
        "  # Farming-capacity bridge modifier localization (generated by ppc finalize)",
    ]
    for modifier_key, building in building_modifiers.items():
        building_link = f"[ShowBuildingTypeName('{building}')|e]"
        lines.append(f'  MODIFIER_TYPE_NAME_{modifier_key}: "Farming Capacity from {building_link}"')
        lines.append(
            f'  MODIFIER_TYPE_DESC_{modifier_key}: "Shows how {building_link} changes Farming Capacity in this location."'
        )
    _write_text_if_changed(
        mod_root / FARMING_CAPACITY_MODIFIER_LOCALIZATION,
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8-sig",
    )


def _ensure_price_cost_modifier_assets(mod_root: Path) -> None:
    modifier_keys = [f"{price_key}_cost_modifier" for price_key in _pp_price_keys(mod_root)]
    if not modifier_keys:
        return

    _upsert_price_cost_modifier_types(mod_root, modifier_keys)
    _prune_stale_price_cost_modifier_icons(mod_root, set(modifier_keys))
    _write_price_cost_modifier_icons(mod_root, modifier_keys)
    _append_missing_price_cost_modifier_localization(mod_root, modifier_keys)


def _pp_price_keys(mod_root: Path) -> list[str]:
    prices_root = mod_root / "in_game" / "common" / "prices"
    if not prices_root.is_dir():
        return []

    keys: set[str] = set()
    pattern = re.compile(r"(?m)^\s*(pp_[A-Za-z0-9_]+_price)\s*=\s*\{")
    for path in sorted(prices_root.glob("pp_*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        keys.update(pattern.findall(text))
    return sorted(keys)


def _upsert_price_cost_modifier_types(mod_root: Path, modifier_keys: Sequence[str]) -> None:
    path = mod_root / PRICE_MODIFIER_TYPE_DEFINITIONS
    if path.is_file():
        text = path.read_text(encoding="utf-8-sig").rstrip()
    else:
        text = ""
        path.parent.mkdir(parents=True, exist_ok=True)

    text = _prune_stale_price_cost_modifier_blocks(text, set(modifier_keys)).rstrip()
    existing = _top_level_keys(text)
    missing = [key for key in modifier_keys if key not in existing]
    blocks = [_price_cost_modifier_type_block(key) for key in missing]
    updated = "\n\n".join(part for part in (text, "\n\n".join(blocks)) if part).rstrip() + "\n"
    _write_text_if_changed(path, updated, encoding="utf-8-sig")


def _prune_stale_price_cost_modifier_blocks(text: str, allowed_keys: set[str]) -> str:
    if not text:
        return text

    parts: list[str] = []
    last = 0
    pattern = re.compile(
        r"(?m)^\ufeff?(?P<key>pp_[A-Za-z0-9_]+_price_cost_modifier)\s*=\s*\{"
    )
    for match in pattern.finditer(text):
        block_end = _balanced_clausewitz_block_end(text, match.end() - 1)
        if block_end is None:
            continue
        if match.group("key") in allowed_keys:
            continue
        parts.append(text[last : match.start()])
        last = block_end

    if last == 0:
        return text

    parts.append(text[last:])
    return re.sub(r"\n{3,}", "\n\n", "".join(parts)).strip()


def _balanced_clausewitz_block_end(text: str, open_brace_index: int) -> int | None:
    depth = 0
    in_string = False
    index = open_brace_index
    while index < len(text):
        char = text[index]
        if in_string:
            if char == '"' and (index == 0 or text[index - 1] != "\\"):
                in_string = False
            index += 1
            continue
        if char == "#":
            next_newline = text.find("\n", index)
            if next_newline == -1:
                return None
            index = next_newline + 1
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def _price_cost_modifier_type_block(modifier_key: str) -> str:
    return "\n".join(
        (
            f"{modifier_key}={{",
            "\tcolor=bad",
            "\tpercent=yes",
            "\tgame_data={",
            "\t\tcategory=country",
            "\t}",
            "}",
        )
    )


def _write_price_cost_modifier_icons(mod_root: Path, modifier_keys: Sequence[str]) -> None:
    path = mod_root / PRICE_MODIFIER_ICONS
    path.parent.mkdir(parents=True, exist_ok=True)
    keys_defined_elsewhere = _modifier_icon_keys(mod_root, exclude=path)
    keys = [key for key in modifier_keys if key not in keys_defined_elsewhere]
    if not keys and not path.exists():
        return

    lines = [
        "# Prosper or Perish - generated building price cost modifier icons.",
        "# Generated from in_game/common/prices/pp_*.txt by the ppc finalizer.",
        "",
    ]
    for key in keys:
        lines.extend(
            (
                f"{key} = {{",
                '\tpositive = "gfx/interface/icons/modifier_types/_default.dds"',
                "}",
            )
        )
    _write_text_if_changed(path, "\n".join(lines).rstrip() + "\n", encoding="utf-8-sig")


def _prune_stale_price_cost_modifier_icons(mod_root: Path, allowed_keys: set[str]) -> None:
    icons_root = mod_root / "main_menu" / "common" / "modifier_icons"
    if not icons_root.is_dir():
        return

    for path in sorted(icons_root.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        had_price_cost_modifier_asset = _has_price_cost_modifier_reference(text)
        updated = _prune_stale_price_cost_modifier_blocks(text, allowed_keys)
        if (
            had_price_cost_modifier_asset
            and not _top_level_keys(updated)
            and not _has_non_comment_text(updated)
        ):
            path.unlink()
            continue
        if updated != text:
            _write_text_if_changed(path, updated.rstrip() + "\n", encoding="utf-8-sig")


def _has_price_cost_modifier_reference(text: str) -> bool:
    return "price cost modifier" in text.lower() or bool(
        re.search(r"pp_[A-Za-z0-9_]+_price_cost_modifier", text)
    )


def _has_non_comment_text(text: str) -> bool:
    return any(
        stripped and not stripped.startswith("#")
        for stripped in (line.strip() for line in text.splitlines())
    )


def _modifier_icon_keys(mod_root: Path, *, exclude: Path) -> set[str]:
    icons_root = mod_root / "main_menu" / "common" / "modifier_icons"
    if not icons_root.is_dir():
        return set()

    keys: set[str] = set()
    for path in sorted(icons_root.glob("*.txt")):
        if path == exclude:
            continue
        keys.update(_top_level_keys(path.read_text(encoding="utf-8-sig")))
    return keys


def _append_missing_price_cost_modifier_localization(
    mod_root: Path,
    modifier_keys: Sequence[str],
) -> None:
    localization_root = mod_root / "main_menu" / "localization" / "english"
    localization_root.mkdir(parents=True, exist_ok=True)
    existing_name_keys: set[str] = set()
    existing_desc_keys: set[str] = set()
    for path in sorted(localization_root.glob("*.yml")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        existing_name_keys.update(re.findall(r"(?m)^\s*MODIFIER_TYPE_NAME_([A-Za-z0-9_]+):", text))
        existing_desc_keys.update(re.findall(r"(?m)^\s*MODIFIER_TYPE_DESC_([A-Za-z0-9_]+):", text))

    target = mod_root / PRICE_MODIFIER_LOCALIZATION
    if target.is_file():
        text = _prune_stale_price_cost_modifier_localization_lines(
            target.read_text(encoding="utf-8-sig"),
            set(modifier_keys),
        ).rstrip()
    else:
        text = "l_english:"

    lines: list[str] = []
    for modifier_key in modifier_keys:
        building_key = modifier_key.removeprefix("pp_").removesuffix("_price_cost_modifier")
        display_name = _title_from_key(building_key)
        if modifier_key not in existing_desc_keys:
            lines.append(
                f'  MODIFIER_TYPE_DESC_{modifier_key}: "Affects the cost of building [ShowBuildingTypeName(\'{building_key}\')|e]."'
            )
        if modifier_key not in existing_name_keys:
            lines.append(f'  MODIFIER_TYPE_NAME_{modifier_key}: "{display_name} Cost"')

    if not lines:
        if target.is_file():
            _write_text_if_changed(target, text.rstrip() + "\n", encoding="utf-8-sig")
        return
    updated = text + "\n" + "\n".join(lines) + "\n"
    _write_text_if_changed(target, updated, encoding="utf-8-sig")


def _prune_stale_price_cost_modifier_localization_lines(text: str, allowed_keys: set[str]) -> str:
    if not text:
        return text

    pattern = re.compile(
        r"(?m)^\s*MODIFIER_TYPE_(?:DESC|NAME)_"
        r"(?P<key>pp_[A-Za-z0-9_]+_price_cost_modifier):.*(?:\n|$)"
    )
    updated = pattern.sub(
        lambda match: match.group(0) if match.group("key") in allowed_keys else "",
        text,
    )
    return re.sub(r"\n{3,}", "\n\n", updated).rstrip()


def _title_from_key(key: str) -> str:
    return " ".join(part.capitalize() for part in key.split("_"))


def _top_level_keys(text: str) -> set[str]:
    return set(re.findall(r"(?m)^\ufeff?([A-Za-z0-9_]+)\s*=\s*\{", text))


def _ensure_constructor_text_boms(mod_root: Path) -> None:
    explicit_paths = {mod_root / relative_path for relative_path in BOM_TEXT_RELATIVE_PATHS}
    for path in sorted({*_iter_game_loaded_text_files(mod_root), *explicit_paths}):
        if path.is_file():
            if _is_setup_start_file(mod_root, path):
                _ensure_utf8_without_bom(path)
            else:
                _ensure_utf8_bom(path)


def _is_setup_start_file(mod_root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(mod_root)
    except ValueError:
        return False
    parts = relative.parts
    return len(parts) >= 4 and parts[0] in GAME_LOADED_TEXT_ROOTS and parts[1:3] == (
        "setup",
        "start",
    )


def _iter_game_loaded_text_files(mod_root: Path) -> list[Path]:
    paths: list[Path] = []
    for root_name in GAME_LOADED_TEXT_ROOTS:
        root = mod_root / root_name
        if not root.is_dir():
            continue
        paths.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in GAME_LOADED_TEXT_SUFFIXES
        )
    return paths


def _ensure_utf8_bom(path: Path) -> bool:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
        text = payload.decode("cp1252", errors="replace")
    if raw.startswith(b"\xef\xbb\xbf") and text.encode("utf-8") == raw[3:]:
        return False
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        handle.write(text)
    return True


def _ensure_utf8_without_bom(path: Path) -> bool:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
        text = payload.decode("cp1252", errors="replace")
    if not raw.startswith(b"\xef\xbb\xbf") and text.encode("utf-8") == raw:
        return False
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return True


def _mod_game_rule_setting_keys(mod_root: Path) -> set[str]:
    game_rules_root = mod_root / "main_menu" / "common" / "game_rules"
    if not game_rules_root.is_dir():
        return set()

    keys: set[str] = set()
    key_block = re.compile(r"^\s*(?P<key>[A-Za-z0-9_]+)\s*=\s*\{")
    for path in sorted(game_rules_root.glob("*.txt")):
        depth = 0
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            match = key_block.match(line)
            if match and depth == 1:
                keys.add(match.group("key"))
            depth += line.count("{") - line.count("}")
    return keys


def _default_eu5_user_data_root() -> Path:
    candidates: list[Path] = []
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidates.append(Path(user_profile) / "Documents" / "Paradox Interactive" / "Europa Universalis V")
    candidates.append(Path.home() / EU5_USER_DATA_SUFFIX)
    users_root = Path("/mnt/c/Users")
    if users_root.is_dir():
        candidates.extend(path / EU5_USER_DATA_SUFFIX for path in sorted(users_root.iterdir()))

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def _remove_game_rule_settings_from_preset(preset: Path, setting_keys: set[str]) -> int:
    with preset.open("r", encoding="utf-8-sig", newline="") as handle:
        text = handle.read()

    removed = 0

    def replace_setting(match: re.Match[str]) -> str:
        nonlocal removed
        tokens = match.group("body").split()
        kept = [token for token in tokens if token not in setting_keys]
        removed += len(tokens) - len(kept)
        return f"{match.group('prefix')}{' '.join(kept)}{match.group('suffix')}"

    updated = re.sub(
        r"(?P<prefix>\bsetting\s*=\s*\{\s*)(?P<body>[^}]*)"
        r"(?P<suffix>\s*\})",
        replace_setting,
        text,
    )
    if updated != text:
        with preset.open("w", encoding="utf-8-sig", newline="") as handle:
            handle.write(updated)
    return removed


def _read_text_preserving_newlines(path: Path, *, encoding: str = "utf-8") -> str:
    with path.open("r", encoding=encoding, newline="") as handle:
        return handle.read()


def _write_text_if_changed(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    newline: str | None = None,
) -> bool:
    wants_bom = encoding.replace("_", "-").lower() == "utf-8-sig"
    if path.exists():
        with path.open("r", encoding=encoding, newline=newline) as handle:
            existing = handle.read()
        has_required_bom = not wants_bom or path.read_bytes().startswith(b"\xef\xbb\xbf")
        if existing == text and has_required_bom:
            return False
    with path.open("w", encoding=encoding, newline=newline) as handle:
        handle.write(text)
    return True


def _analyze(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    result = _run(["eu5-orchestrator", "analyze", "--project", project, *extra], repo)
    if result != 0:
        return result
    return _publish_graph_examples(repo, [GOODS_FLOW_EXPLORER.name])


def _update_audit(
    args: argparse.Namespace,
    extra: Sequence[str],
    repo: Path,
    project: Path,
) -> int:
    if extra:
        raise SystemExit("update-audit does not accept extra arguments.")

    from prosper_or_perish_constructor.update_audit import run_update_audit

    output_dir = None if args.output_dir is None else _resolve_repo_relative_path(repo, args.output_dir)
    summary = run_update_audit(
        repo=repo,
        project=project,
        load_order_path=_resolve_repo_relative_path(repo, args.load_order),
        old_ref=args.old_ref,
        new_ref=args.new_ref,
        output_dir=output_dir,
    )
    print(f"dependencies={summary.dependency_count}", flush=True)
    print(
        "impacted="
        f"{summary.changed_count + summary.added_count + summary.removed_count} "
        f"(changed={summary.changed_count}, added={summary.added_count}, removed={summary.removed_count})",
        flush=True,
    )
    print(f"unchanged={summary.unchanged_count}", flush=True)
    if summary.missing_both_count:
        print(f"missing_both={summary.missing_both_count}", flush=True)
    if summary.warning_count:
        print(f"warnings={summary.warning_count}", flush=True)
    print(f"html={summary.index_html}", flush=True)
    print(f"changed_csv={summary.changed_csv}", flush=True)
    print(f"all_csv={summary.all_csv}", flush=True)
    print(f"changed_json={summary.changed_json}", flush=True)
    return 0


def _output_modifiers(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    if extra:
        raise SystemExit("output-modifiers does not accept extra arguments.")

    goods, modifiers, ages = _load_output_modifier_inputs(
        profile=args.profile,
        load_order_path=_repo_path(repo, args.load_order),
    )
    rows = _cumulative_output_modifier_rows(
        goods,
        modifiers,
        ages,
        include_specific=args.include_specific,
    )
    print(_format_output_modifier_table(rows, ages), flush=True)
    return 0


def _province_food_sales_check(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    if extra:
        raise SystemExit("province-food-sales-check does not accept extra arguments.")
    if args.tolerance < 0:
        raise SystemExit("--tolerance must be >= 0.")

    inputs = _load_province_food_sales_check_inputs(
        profile=args.profile,
        load_order_path=_repo_path(repo, args.load_order),
        project=project,
    )
    report = _province_food_sales_check_report(inputs, tolerance=args.tolerance)
    print(_format_province_food_sales_check_report(report), flush=True)
    return 0 if not report["failures"] else 1


def _load_province_food_sales_check_inputs(
    *,
    profile: str,
    load_order_path: Path,
    project: Path,
) -> dict[str, Any]:
    from eu5gameparser.domain.defines import load_define_data
    from eu5gameparser.domain.location_ranks import load_location_rank_data
    from eu5gameparser.domain.static_modifiers import load_static_modifier_data

    static_data = load_static_modifier_data(profile=profile, load_order_path=load_order_path)
    rank_data = load_location_rank_data(profile=profile, load_order_path=load_order_path)
    define_data = load_define_data(profile=profile, load_order_path=load_order_path)
    growth_cap = define_data.numeric_value("NEconomy", "GROWTH_FROM_FOOD_MULTIPLIER_MAX")
    if growth_cap is None:
        raise SystemExit("Missing parsed define NEconomy.GROWTH_FROM_FOOD_MULTIPLIER_MAX.")

    static_values = {
        name: static_data.modifier_baseline(name, None, PROVINCE_FOOD_SALES_MODIFIER_KEY)
        for name in (
            "cheap_food_in_location",
            "expensive_food_in_location",
            "positive_province_food_growth",
            "province_starving",
        )
    }
    rank_values = {
        name: rank_data.modifier_baseline(name, "rank_modifier", PROVINCE_FOOD_SALES_MODIFIER_KEY)
        for name in PROVINCE_FOOD_SALES_RANK_TARGETS
    }
    return {
        "growth_cap": float(growth_cap),
        "static": static_values,
        "ranks": rank_values,
        "profitability_rows": _load_province_food_sales_profitability_rows(
            project=project,
            profile=profile,
            load_order_path=load_order_path,
        ),
        "warnings": [
            *static_data.warnings,
            *rank_data.warnings,
            *define_data.warnings,
        ],
    }


def _load_province_food_sales_profitability_rows(
    *,
    project: Path,
    profile: str,
    load_order_path: Path,
) -> list[dict[str, Any]]:
    from eu5_mod_orchestrator.adapters.building_pipeline import evaluate_building_blueprint_data
    from eu5_mod_orchestrator.adapters.parser import (
        load_balance_prices,
        load_food_cost_context,
        load_global_building_unlock_ages,
        load_global_unlock_ages,
        load_raw_material_goods,
        load_script_values,
    )
    from eu5_mod_orchestrator.config import load_project_config

    config = load_project_config(project)
    blueprint_path = config.accepted_blueprints_dir / PROVINCE_FOOD_SALES_PROFITABILITY_BLUEPRINT
    if not blueprint_path.is_file():
        raise SystemExit(f"Missing Province Food Sales profitability blueprint: {blueprint_path}")

    evaluation = evaluate_building_blueprint_data(
        blueprint_path,
        config,
        price_by_good={
            **load_balance_prices(profile=profile, load_order_path=load_order_path),
            **config.blueprint_evaluation.price_overrides,
        },
        raw_material_goods=load_raw_material_goods(
            profile=profile,
            load_order_path=load_order_path,
        ),
        script_values=load_script_values(profile=profile, load_order_path=load_order_path),
        global_unlock_age_by_method=load_global_unlock_ages(
            profile=profile,
            load_order_path=load_order_path,
        ),
        global_unlock_age_by_building=load_global_building_unlock_ages(
            profile=profile,
            load_order_path=load_order_path,
        ),
        food_cost_context=load_food_cost_context(profile=profile, load_order_path=load_order_path),
    )
    for method in evaluation.methods:
        if method.name == PROVINCE_FOOD_SALES_PROFITABILITY_METHOD:
            return _province_food_sales_profitability_rows_from_method(method)
    raise SystemExit(
        f"Missing Province Food Sales profitability method {PROVINCE_FOOD_SALES_PROFITABILITY_METHOD} "
        f"in {blueprint_path}"
    )


def _province_food_sales_profitability_rows_from_method(method: object) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in getattr(method, "food_cost_scenarios", ()):
        scenario_name = str(getattr(scenario, "scenario", ""))
        input_gold = _province_food_sales_float(getattr(scenario, "input_gold", None))
        output_gold = _province_food_sales_float(getattr(scenario, "output_gold", None))
        output_multiplier = _province_food_sales_float(getattr(scenario, "output_multiplier", None))
        actual_output_modifier = (
            output_multiplier - 1.0 if math.isfinite(output_multiplier) else math.nan
        )
        profit_gold = _province_food_sales_float(getattr(scenario, "profit_gold", None))
        worker_food_gold = _province_food_sales_float(getattr(scenario, "worker_food_gold", None))
        goods_input_gold = input_gold - worker_food_gold if math.isfinite(worker_food_gold) else math.nan
        base_output_gold = (
            output_gold / output_multiplier
            if math.isfinite(output_gold)
            and math.isfinite(output_multiplier)
            and output_multiplier > 0.0
            else math.nan
        )
        required_output_multiplier = (
            input_gold / base_output_gold
            if math.isfinite(input_gold)
            and math.isfinite(base_output_gold)
            and base_output_gold > 0.0
            else math.nan
        )
        required_output_modifier = required_output_multiplier - 1.0
        rows.append(
            {
                "scenario": scenario_name,
                "food_price": _province_food_sales_scenario_price_label(scenario_name),
                "input_gold": input_gold,
                "goods_input_gold": goods_input_gold,
                "worker_food_gold": worker_food_gold,
                "base_output_gold": base_output_gold,
                "required_output_modifier": required_output_modifier,
                "actual_output_modifier": actual_output_modifier,
                "modifier_margin": actual_output_modifier - required_output_modifier,
                "output_gold": output_gold,
                "profit_gold": profit_gold,
                "profitable": math.isfinite(profit_gold) and profit_gold >= 0.0,
            }
        )
    return rows


def _province_food_sales_rank_profitability_rows(
    rank_rows: Sequence[Mapping[str, Any]],
    profitability_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    base_row = next(
        (row for row in profitability_rows if row.get("scenario") == "base_100"),
        None,
    )
    if base_row is None:
        return []

    input_gold = _province_food_sales_float(base_row.get("input_gold"))
    goods_input_gold = _province_food_sales_float(base_row.get("goods_input_gold"))
    base_output_gold = _province_food_sales_float(base_row.get("base_output_gold"))
    if not math.isfinite(base_output_gold):
        return []

    rows: list[dict[str, Any]] = []
    for row in rank_rows:
        modifier = _province_food_sales_float(row.get("base_full_storage"))
        output_gold = base_output_gold * (1.0 + modifier)
        profit_gold = output_gold - input_gold if math.isfinite(input_gold) else math.nan
        profit_ex_food = (
            output_gold - goods_input_gold
            if math.isfinite(goods_input_gold)
            else math.nan
        )
        rows.append(
            {
                "rank": row.get("rank"),
                "modifier": modifier,
                "output_gold": output_gold,
                "profit_gold": profit_gold,
                "profit_ex_food": profit_ex_food,
                "profitable": math.isfinite(profit_gold) and profit_gold >= 0.0,
            }
        )
    return rows


def _province_food_sales_scenario_price_label(scenario: str) -> str:
    return {
        "cheap_50": "50%",
        "base_100": "100%",
        "expensive_150": "150%",
    }.get(scenario, scenario)


def _province_food_sales_solve_component_target(
    *,
    total_modifier: float,
    known_modifiers: Sequence[float],
) -> float:
    total = _province_food_sales_float(total_modifier)
    if not math.isfinite(total):
        return math.nan

    known_total = 0.0
    for modifier in known_modifiers:
        value = _province_food_sales_float(modifier)
        if not math.isfinite(value):
            return math.nan
        known_total += value
    return total - known_total


def _province_food_sales_storage_full_target_for_edge(
    edge: tuple[str, str, str, str],
    *,
    matrix_targets: Mapping[tuple[str, str, str, str], float],
    rank_targets: Mapping[str, float],
    price_targets: Mapping[str, float],
    starving_targets: Mapping[str, float],
) -> float:
    rank, price, storage, starving = edge
    if storage != "full":
        raise ValueError("storage target edge must use full storage")
    return _province_food_sales_solve_component_target(
        total_modifier=_province_food_sales_float(matrix_targets.get(edge)),
        known_modifiers=(
            _province_food_sales_float(rank_targets.get(rank)),
            _province_food_sales_float(price_targets.get(price)),
            _province_food_sales_float(starving_targets.get(starving)),
        ),
    )


def _province_food_sales_storage_raw_target_for_edge(
    edge: tuple[str, str, str, str],
    *,
    growth_cap: float,
    matrix_targets: Mapping[tuple[str, str, str, str], float],
    rank_targets: Mapping[str, float],
    price_targets: Mapping[str, float],
    starving_targets: Mapping[str, float],
) -> float:
    cap = _province_food_sales_float(growth_cap)
    if not math.isfinite(cap) or cap == 0.0:
        return math.nan
    return _province_food_sales_storage_full_target_for_edge(
        edge,
        matrix_targets=matrix_targets,
        rank_targets=rank_targets,
        price_targets=price_targets,
        starving_targets=starving_targets,
    ) / cap


def _province_food_sales_check_report(
    inputs: Mapping[str, Any],
    *,
    tolerance: float,
) -> dict[str, Any]:
    static_values = dict(inputs.get("static") or {})
    rank_values = dict(inputs.get("ranks") or {})
    growth_cap = _province_food_sales_float(inputs.get("growth_cap"))
    storage_raw = _province_food_sales_float(static_values.get("positive_province_food_growth"))
    cheap_raw = _province_food_sales_float(static_values.get("cheap_food_in_location"))
    expensive_raw = _province_food_sales_float(static_values.get("expensive_food_in_location"))
    starving = _province_food_sales_float(static_values.get("province_starving"))

    component_rows: list[dict[str, Any]] = []
    component_rows.append(
        _province_food_sales_check_row(
            "growth storage cap",
            growth_cap,
            PROVINCE_FOOD_SALES_GROWTH_CAP_TARGET,
            tolerance,
        )
    )
    component_rows.append(
        _province_food_sales_check_row(
            "cheap raw modifier",
            cheap_raw,
            PROVINCE_FOOD_SALES_STATIC_TARGETS["cheap_food_in_location"],
            tolerance,
        )
    )
    component_rows.append(
        _province_food_sales_check_row(
            "cheap cap effect (food price 0x)",
            cheap_raw * PROVINCE_FOOD_SALES_PRICE_CAP_SCALE,
            PROVINCE_FOOD_SALES_CHEAP_CAP_TARGET,
            tolerance,
        )
    )
    component_rows.append(
        _province_food_sales_check_row(
            "cheap scenario effect (food price 50%)",
            cheap_raw * PROVINCE_FOOD_SALES_PRICE_SCENARIO_SCALE,
            PROVINCE_FOOD_SALES_STATIC_TARGETS["cheap_food_in_location"]
            * PROVINCE_FOOD_SALES_PRICE_SCENARIO_SCALE,
            tolerance,
        )
    )
    component_rows.append(
        _province_food_sales_check_row("base scenario effect (food price 100%)", 0.0, 0.0, tolerance)
    )
    component_rows.append(
        _province_food_sales_check_row(
            "expensive scenario effect (food price 150%)",
            expensive_raw * PROVINCE_FOOD_SALES_PRICE_SCENARIO_SCALE,
            PROVINCE_FOOD_SALES_STATIC_TARGETS["expensive_food_in_location"]
            * PROVINCE_FOOD_SALES_PRICE_SCENARIO_SCALE,
            tolerance,
        )
    )
    component_rows.append(
        _province_food_sales_check_row(
            "expensive cap effect (food price 2x)",
            expensive_raw * PROVINCE_FOOD_SALES_PRICE_CAP_SCALE,
            PROVINCE_FOOD_SALES_EXPENSIVE_CAP_TARGET,
            tolerance,
        )
    )
    component_rows.append(
        _province_food_sales_check_row(
            "expensive raw modifier",
            expensive_raw,
            PROVINCE_FOOD_SALES_STATIC_TARGETS["expensive_food_in_location"],
            tolerance,
        )
    )
    storage_full_target = _province_food_sales_storage_full_target_for_edge(
        PROVINCE_FOOD_SALES_STORAGE_TARGET_EDGE,
        matrix_targets=PROVINCE_FOOD_SALES_MATRIX_TARGETS,
        rank_targets=PROVINCE_FOOD_SALES_RANK_TARGETS,
        price_targets=PROVINCE_FOOD_SALES_EDGE_PRICE_TARGETS,
        starving_targets=PROVINCE_FOOD_SALES_EDGE_STARVING_TARGETS,
    )
    storage_raw_target = _province_food_sales_storage_raw_target_for_edge(
        PROVINCE_FOOD_SALES_STORAGE_TARGET_EDGE,
        growth_cap=growth_cap,
        matrix_targets=PROVINCE_FOOD_SALES_MATRIX_TARGETS,
        rank_targets=PROVINCE_FOOD_SALES_RANK_TARGETS,
        price_targets=PROVINCE_FOOD_SALES_EDGE_PRICE_TARGETS,
        starving_targets=PROVINCE_FOOD_SALES_EDGE_STARVING_TARGETS,
    )
    component_rows.append(
        _province_food_sales_check_row(
            "stored-food raw modifier",
            storage_raw,
            storage_raw_target,
            tolerance,
        )
    )
    component_rows.append(
        _province_food_sales_check_row(
            "stored-food full effect",
            storage_raw * growth_cap,
            storage_full_target,
            tolerance,
        )
    )
    component_rows.append(
        _province_food_sales_check_row(
            "starving boost",
            starving,
            PROVINCE_FOOD_SALES_STARVING_TARGET,
            tolerance,
        )
    )
    for rank, target in PROVINCE_FOOD_SALES_RANK_TARGETS.items():
        component_rows.append(
            _province_food_sales_check_row(
                f"rank baseline {rank}",
                _province_food_sales_float(rank_values.get(rank)),
                target,
                tolerance,
            )
        )

    price_rows = [
        {
            "scenario": "cheap_50",
            "modifier": cheap_raw * PROVINCE_FOOD_SALES_PRICE_SCENARIO_SCALE,
        },
        {"scenario": "base_100", "modifier": 0.0},
        {
            "scenario": "expensive_150",
            "modifier": expensive_raw * PROVINCE_FOOD_SALES_PRICE_SCENARIO_SCALE,
        },
        {"scenario": "cheap_cap_0x", "modifier": cheap_raw * PROVINCE_FOOD_SALES_PRICE_CAP_SCALE},
        {
            "scenario": "expensive_cap_2x",
            "modifier": expensive_raw * PROVINCE_FOOD_SALES_PRICE_CAP_SCALE,
        },
    ]
    for row in price_rows:
        row["output_multiplier"] = 1.0 + row["modifier"]

    storage_full = storage_raw * growth_cap
    cheap_cap = cheap_raw * PROVINCE_FOOD_SALES_PRICE_CAP_SCALE
    expensive_cap = expensive_raw * PROVINCE_FOOD_SALES_PRICE_CAP_SCALE
    profitability_rows = list(inputs.get("profitability_rows") or [])
    rank_rows = []
    for rank in PROVINCE_FOOD_SALES_RANK_TARGETS:
        baseline = _province_food_sales_float(rank_values.get(rank))
        rank_rows.append(
            {
                "rank": rank,
                "base_full_storage": baseline + storage_full,
                "cheap_cap_full_storage": baseline + cheap_cap + storage_full,
                "expensive_cap_empty": baseline + expensive_cap,
                "expensive_cap_starving": baseline + expensive_cap + starving,
            }
        )

    edge_price_rows = [
        {"price": "cheap_cap_0x", "modifier": cheap_cap},
        {"price": "base_100", "modifier": 0.0},
        {"price": "expensive_cap_2x", "modifier": expensive_cap},
    ]
    edge_storage_rows = [
        {"storage": "empty", "modifier": 0.0},
        {"storage": "full", "modifier": storage_full},
    ]
    edge_starving_rows = [
        {"starving": "no", "modifier": 0.0},
        {"starving": "yes", "modifier": starving},
    ]
    matrix_rows = []
    for rank in PROVINCE_FOOD_SALES_RANK_TARGETS:
        rank_modifier = _province_food_sales_float(rank_values.get(rank))
        for price_row in edge_price_rows:
            for storage_row in edge_storage_rows:
                for starving_row in edge_starving_rows:
                    total_modifier = (
                        rank_modifier
                        + price_row["modifier"]
                        + storage_row["modifier"]
                        + starving_row["modifier"]
                    )
                    matrix_rows.append(
                        {
                            "rank": rank,
                            "price": price_row["price"],
                            "storage": storage_row["storage"],
                            "starving": starving_row["starving"],
                            "rank_modifier": rank_modifier,
                            "price_modifier": price_row["modifier"],
                            "storage_modifier": storage_row["modifier"],
                            "starving_modifier": starving_row["modifier"],
                            "total_modifier": total_modifier,
                            "in_band": (
                                PROVINCE_FOOD_SALES_TOTAL_MODIFIER_MIN - tolerance
                                <= total_modifier
                                <= PROVINCE_FOOD_SALES_TOTAL_MODIFIER_MAX + tolerance
                            ),
                            "output_multiplier": 1.0 + total_modifier,
                        }
                    )

    matrix_by_key = {
        (
            str(row["rank"]),
            str(row["price"]),
            str(row["storage"]),
            str(row["starving"]),
        ): row
        for row in matrix_rows
    }
    for key, target in PROVINCE_FOOD_SALES_MATRIX_TARGETS.items():
        row = matrix_by_key.get(key)
        parsed = math.nan if row is None else _province_food_sales_float(row["total_modifier"])
        component_rows.append(
            _province_food_sales_check_row(
                f"matrix {' '.join(key)} total",
                parsed,
                target,
                tolerance,
            )
        )

    matrix_band_failures = [row for row in matrix_rows if not row["in_band"]]
    failures = [
        *[row for row in component_rows if not row["ok"]],
        *matrix_band_failures,
    ]
    return {
        "growth_cap": growth_cap,
        "component_rows": component_rows,
        "price_rows": price_rows,
        "rank_rows": rank_rows,
        "matrix_rows": matrix_rows,
        "profitability_rows": profitability_rows,
        "rank_profitability_rows": _province_food_sales_rank_profitability_rows(
            rank_rows,
            profitability_rows,
        ),
        "matrix_band_failures": matrix_band_failures,
        "failures": failures,
        "warnings": list(inputs.get("warnings") or []),
    }


def _province_food_sales_check_row(
    name: str,
    parsed: float,
    target: float,
    tolerance: float,
) -> dict[str, Any]:
    delta = parsed - target
    ok = math.isfinite(parsed) and math.isfinite(target) and abs(delta) <= tolerance
    return {
        "name": name,
        "parsed": parsed,
        "target": target,
        "delta": delta,
        "ok": ok,
    }


def _province_food_sales_float(value: object) -> float:
    if isinstance(value, bool) or value is None:
        return math.nan
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def _format_province_food_sales_check_report(report: Mapping[str, Any]) -> str:
    lines = ["Province Food Sales parsed edge check"]
    warnings = list(report.get("warnings") or [])
    if warnings:
        lines.append(f"parser_warnings={len(warnings)}")
    lines.append("")
    lines.append("component checks:")
    component_rows = list(report.get("component_rows") or [])
    name_width = max(len("check"), *(len(str(row["name"])) for row in component_rows))
    lines.append(
        "  ".join(
            [
                "check".ljust(name_width),
                "parsed".rjust(8),
                "target".rjust(8),
                "delta".rjust(8),
                "status",
            ]
        )
    )
    lines.append(
        "  ".join(
            [
                "-" * name_width,
                "-" * 8,
                "-" * 8,
                "-" * 8,
                "------",
            ]
        )
    )
    for row in component_rows:
        lines.append(
            "  ".join(
                [
                    str(row["name"]).ljust(name_width),
                    _format_province_food_sales_value(row["parsed"]).rjust(8),
                    _format_province_food_sales_value(row["target"]).rjust(8),
                    _format_province_food_sales_value(row["delta"]).rjust(8),
                    "ok" if row["ok"] else "FAIL",
                ]
            )
        )

    lines.append("")
    lines.append("price scenario output modifiers and multipliers:")
    lines.append("scenario           modifier  output_mult")
    lines.append("-----------------  --------  -------------")
    for row in report.get("price_rows") or []:
        lines.append(
            "  ".join(
                [
                    str(row["scenario"]).ljust(17),
                    _format_province_food_sales_value(row["modifier"]).rjust(8),
                    f"{row['output_multiplier']:.3f}".rjust(11),
                ]
            )
        )

    lines.append("")
    lines.append("rank edge totals:")
    lines.append(
        "rank              base+stored  cheap_cap+stored  expensive_cap  expensive_cap+starving"
    )
    lines.append(
        "----------------  -----------  ----------------  -------------  ----------------------"
    )
    for row in report.get("rank_rows") or []:
        lines.append(
            "  ".join(
                [
                    str(row["rank"]).ljust(16),
                    _format_province_food_sales_value(row["base_full_storage"]).rjust(11),
                    _format_province_food_sales_value(row["cheap_cap_full_storage"]).rjust(16),
                    _format_province_food_sales_value(row["expensive_cap_empty"]).rjust(13),
                    _format_province_food_sales_value(row["expensive_cap_starving"]).rjust(22),
                ]
            )
        )

    profitability_rows = list(report.get("profitability_rows") or [])
    if profitability_rows:
        lines.append("")
        lines.append("victuals market base-condition profitability:")
        lines.append(
            "scenario       food_price  input  base_out  req_mod  actual_mod  margin_mod  output  profit  status"
        )
        lines.append(
            "-------------  ----------  -----  --------  -------  ----------  ----------  ------  ------  ------"
        )
        for row in profitability_rows:
            lines.append(
                "  ".join(
                    [
                        str(row["scenario"]).ljust(13),
                        str(row["food_price"]).rjust(10),
                        _format_province_food_sales_unsigned(row["input_gold"]).rjust(5),
                        _format_province_food_sales_unsigned(row["base_output_gold"]).rjust(8),
                        _format_province_food_sales_value(row["required_output_modifier"]).rjust(7),
                        _format_province_food_sales_value(row["actual_output_modifier"]).rjust(10),
                        _format_province_food_sales_value(row["modifier_margin"]).rjust(10),
                        _format_province_food_sales_unsigned(row["output_gold"]).rjust(6),
                        _format_province_food_sales_value(row["profit_gold"]).rjust(6),
                        "profit" if row["profitable"] else "loss",
                    ]
                )
            )

    rank_profitability_rows = list(report.get("rank_profitability_rows") or [])
    if rank_profitability_rows:
        lines.append("")
        lines.append("victuals market base price + full storage profitability by rank:")
        lines.append("rank              total_mod  output  profit  profit_ex_food  status")
        lines.append("----------------  ---------  ------  ------  --------------  ------")
        for row in rank_profitability_rows:
            lines.append(
                "  ".join(
                    [
                        str(row["rank"]).ljust(16),
                        _format_province_food_sales_value(row["modifier"]).rjust(9),
                        _format_province_food_sales_unsigned(row["output_gold"]).rjust(6),
                        _format_province_food_sales_value(row["profit_gold"]).rjust(6),
                        _format_province_food_sales_value(row["profit_ex_food"]).rjust(14),
                        "profit" if row["profitable"] else "loss",
                    ]
                )
            )

    matrix_rows = list(report.get("matrix_rows") or [])
    lines.append("")
    lines.append(f"full edge matrix ({len(matrix_rows)} rows):")
    lines.append(
        "rank              price             storage  starving  rank_mod  price_mod  storage_mod  starving_mod  total_mod  output_mult  status"
    )
    lines.append(
        "----------------  ----------------  -------  --------  --------  ---------  -----------  ------------  ---------  -----------  ------"
    )
    for row in matrix_rows:
        lines.append(
            "  ".join(
                [
                    str(row["rank"]).ljust(16),
                    str(row["price"]).ljust(16),
                    str(row["storage"]).ljust(7),
                    str(row["starving"]).ljust(8),
                    _format_province_food_sales_value(row["rank_modifier"]).rjust(8),
                    _format_province_food_sales_value(row["price_modifier"]).rjust(9),
                    _format_province_food_sales_value(row["storage_modifier"]).rjust(11),
                    _format_province_food_sales_value(row["starving_modifier"]).rjust(12),
                    _format_province_food_sales_value(row["total_modifier"]).rjust(9),
                    f"{row['output_multiplier']:.3f}".rjust(11),
                    "ok" if row["in_band"] else "FAIL",
                ]
            )
        )

    matrix_band_failures = list(report.get("matrix_band_failures") or [])
    if matrix_band_failures:
        lines.append("")
        lines.append(
            "matrix band failures: "
            f"{len(matrix_band_failures)} rows outside "
            f"[{PROVINCE_FOOD_SALES_TOTAL_MODIFIER_MIN:+.3f}, "
            f"{PROVINCE_FOOD_SALES_TOTAL_MODIFIER_MAX:+.3f}]"
        )

    failures = list(report.get("failures") or [])
    lines.append("")
    if failures:
        lines.append(f"result=fail failures={len(failures)}")
    else:
        lines.append("result=ok")
    return "\n".join(lines)


def _format_province_food_sales_value(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "nan"
    if not math.isfinite(number):
        return "nan"
    if abs(number) < 0.0000000001:
        number = 0.0
    return f"{number:+.3f}"


def _format_province_food_sales_unsigned(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "nan"
    if not math.isfinite(number):
        return "nan"
    if abs(number) < 0.0000000001:
        number = 0.0
    return f"{number:.3f}"


def _load_output_modifier_inputs(
    *,
    profile: str,
    load_order_path: Path,
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    from eu5gameparser.domain.advancements import load_advancement_data
    from eu5gameparser.domain.availability import AGE_ORDER
    from eu5gameparser.domain.goods import load_goods_data

    goods_data = load_goods_data(profile=profile, load_order_path=load_order_path)
    advancement_data = load_advancement_data(profile=profile, load_order_path=load_order_path)
    goods = sorted(str(row["name"]) for row in goods_data.goods.to_dicts())
    modifiers = _output_modifier_entries(advancement_data.advancements.to_dicts(), list(AGE_ORDER))
    return goods, modifiers, list(AGE_ORDER)


def _output_modifier_entries(
    advancement_rows: Sequence[dict[str, Any]],
    ages: Sequence[str],
) -> list[dict[str, Any]]:
    age_set = set(ages)
    entries: list[dict[str, Any]] = []
    for row in advancement_rows:
        age = row.get("age")
        if age not in age_set:
            continue
        try:
            modifiers = json.loads(row.get("modifiers") or "{}")
        except json.JSONDecodeError:
            continue
        for key, value in modifiers.items():
            if not key.startswith("global_") or not key.endswith("_output_modifier"):
                continue
            if not isinstance(value, int | float) or isinstance(value, bool):
                continue
            entries.append(
                {
                    "good": key.removeprefix("global_").removesuffix("_output_modifier"),
                    "age": age,
                    "value": float(value),
                    "has_potential": bool(row.get("has_potential")),
                }
            )
    return entries


def _cumulative_output_modifier_rows(
    goods: Sequence[str],
    modifiers: Sequence[dict[str, Any]],
    ages: Sequence[str],
    *,
    include_specific: bool,
) -> list[dict[str, Any]]:
    totals = {good: {age: 0.0 for age in ages} for good in goods}
    known_goods = set(goods)
    age_set = set(ages)
    for modifier in modifiers:
        good = str(modifier.get("good") or "")
        age = str(modifier.get("age") or "")
        if not good or age not in age_set:
            continue
        if modifier.get("has_potential") and not include_specific:
            continue
        if good not in totals:
            totals[good] = {known_age: 0.0 for known_age in ages}
            known_goods.add(good)
        totals[good][age] += float(modifier.get("value") or 0.0)

    rows: list[dict[str, Any]] = []
    for good in sorted(known_goods):
        cumulative = 0.0
        row_values: dict[str, float] = {}
        for age in ages:
            cumulative += totals[good][age]
            row_values[age] = cumulative
        rows.append({"good": good, "values": row_values})

    last_age = ages[-1]
    return sorted(rows, key=lambda row: (-row["values"][last_age], row["good"]))


def _format_output_modifier_table(rows: Sequence[dict[str, Any]], ages: Sequence[str]) -> str:
    headers = ["good", *ages]
    formatted_rows = [
        [str(row["good"]), *[_format_modifier_total(row["values"][age]) for age in ages]]
        for row in rows
    ]
    widths = [
        max(len(header), *(len(row[index]) for row in formatted_rows))
        for index, header in enumerate(headers)
    ]
    lines = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    lines.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in formatted_rows
    )
    return "\n".join(lines)


def _format_modifier_total(value: float) -> str:
    if abs(value) < 0.0000000001:
        value = 0.0
    return f"{value:.2f}"


def _production_throughput(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    if extra:
        raise SystemExit("production-throughput does not accept extra arguments.")

    goods, methods, ages = _load_production_throughput_inputs(
        profile=args.profile,
        load_order_path=_repo_path(repo, args.load_order),
        include_specific=args.include_specific,
    )
    rows = _production_throughput_rows(
        goods,
        methods,
        ages,
        include_specific=args.include_specific,
    )
    print(_format_production_throughput_table(rows, ages), flush=True)
    return 0


def _load_production_throughput_inputs(
    *,
    profile: str,
    load_order_path: Path,
    include_specific: bool,
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    from eu5gameparser.domain.availability import AGE_ORDER, annotate_building_data_availability
    from eu5gameparser.domain.eu5 import load_eu5_data

    data = load_eu5_data(profile=profile, load_order_path=load_order_path)
    annotated = annotate_building_data_availability(
        data.building_data,
        data.advancements,
        include_specific_unlocks=include_specific,
    )
    goods = sorted(str(row["name"]) for row in data.goods.to_dicts())
    return goods, annotated.production_methods.to_dicts(), list(AGE_ORDER)


def _production_throughput_rows(
    goods: Sequence[str],
    methods: Sequence[dict[str, Any]],
    ages: Sequence[str],
    *,
    include_specific: bool,
) -> list[dict[str, Any]]:
    age_index = {age: index for index, age in enumerate(ages)}
    known_goods = {str(good) for good in goods if str(good)}
    values = {good: {age: 0.0 for age in ages} for good in known_goods}

    for age in ages:
        building_slots: dict[tuple[str, str], dict[object, tuple[float, str]]] = {}
        for method in methods:
            good = str(method.get("produced") or "")
            building = str(method.get("building") or "")
            if not good or not building:
                continue
            if not _production_method_available_by_age(
                method,
                age,
                age_index,
                include_specific=include_specific,
            ):
                continue
            throughput = _production_method_throughput(method)
            if throughput is None:
                continue

            known_goods.add(good)
            values.setdefault(good, {known_age: 0.0 for known_age in ages})
            slot = _production_method_slot(method)
            method_name = str(method.get("name") or "")
            slots = building_slots.setdefault((good, building), {})
            existing = slots.get(slot)
            if (
                existing is None
                or throughput > existing[0]
                or (throughput == existing[0] and method_name < existing[1])
            ):
                slots[slot] = (throughput, method_name)

        best_by_good: dict[str, tuple[float, str]] = {}
        for (good, building), slots in building_slots.items():
            total = sum(throughput for throughput, _name in slots.values())
            existing = best_by_good.get(good)
            if (
                existing is None
                or total > existing[0]
                or (total == existing[0] and building < existing[1])
            ):
                best_by_good[good] = (total, building)

        for good, (total, _building) in best_by_good.items():
            values[good][age] = total

    rows = [{"good": good, "values": values[good]} for good in sorted(known_goods)]
    last_age = ages[-1]
    return sorted(rows, key=lambda row: (-row["values"][last_age], row["good"]))


def _production_method_available_by_age(
    method: dict[str, Any],
    age: str,
    age_index: dict[str, int],
    *,
    include_specific: bool,
) -> bool:
    kind = str(
        method.get("effective_availability_kind")
        or method.get("availability_kind")
        or ""
    )
    if kind == "available_by_default":
        return True
    if kind == "specific_only" and not include_specific:
        return False

    unlock_age = method.get("effective_unlock_age")
    if unlock_age is None:
        unlock_age = method.get("unlock_age")
    unlock_index = age_index.get(str(unlock_age))
    current_index = age_index.get(age)
    return unlock_index is not None and current_index is not None and unlock_index <= current_index


def _production_method_throughput(method: dict[str, Any]) -> float | None:
    if not method.get("input_goods") or not method.get("input_amounts"):
        return None

    input_cost = _positive_float(method.get("input_cost"))
    output_value = _positive_float(method.get("output_value"))
    if input_cost is None or output_value is None:
        return None
    return input_cost + output_value


def _positive_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def _production_method_slot(method: dict[str, Any]) -> object:
    slot = method.get("production_method_group_index")
    if slot is not None:
        return slot
    return method.get("production_method_group") or "__slotless__"


def _format_production_throughput_table(
    rows: Sequence[dict[str, Any]], ages: Sequence[str]
) -> str:
    return _format_output_modifier_table(rows, ages)


def _production_profit(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    if extra:
        raise SystemExit("production-profit does not accept extra arguments.")

    from prosper_or_perish_constructor.production_profit import (
        convert_vanilla_production_stubs,
        import_missing_production_buildings,
        production_profit_report,
    )

    load_order_path = _repo_path(repo, args.load_order)
    if args.write_blueprints or getattr(args, "import_missing", False):
        from prosper_or_perish_constructor.building_scaling import load_building_scaling_config

        scaling = load_building_scaling_config(project)
        burgher_employment_size = float(scaling.burgher_building_employment_size)
        if getattr(args, "import_missing", False):
            results = import_missing_production_buildings(
                repo,
                profile=args.profile,
                vanilla_profile=args.vanilla_profile,
                load_order_path=load_order_path,
                dry_run=args.dry_run,
                burgher_employment_size=burgher_employment_size,
            )
            changed = sum(1 for result in results if result.changed)
            mode = "dry_run" if args.dry_run else "written"
            print(
                f"imported_blueprints={len(results)} changed={changed} mode={mode}",
                flush=True,
            )
            if not results:
                print("  none", flush=True)
            for result in results:
                relative = result.path.relative_to(repo)
                state = "changed" if result.changed else "unchanged"
                print(
                    f"  {result.building}: {relative} "
                    f"slots={result.slot_count} methods={result.method_count} {state}",
                    flush=True,
                )
            if not args.write_blueprints:
                return 0
        results = convert_vanilla_production_stubs(
            repo,
            profile=args.profile,
            vanilla_profile=args.vanilla_profile,
            load_order_path=load_order_path,
            dry_run=args.dry_run,
            burgher_employment_size=burgher_employment_size,
        )
        changed = sum(1 for result in results if result.changed)
        mode = "dry_run" if args.dry_run else "written"
        print(
            f"converted_blueprints={len(results)} changed={changed} mode={mode}",
            flush=True,
        )
        for result in results:
            relative = result.path.relative_to(repo)
            state = "changed" if result.changed else "unchanged"
            print(
                f"  {result.building}: {relative} "
                f"slots={result.slot_count} methods={result.method_count} {state}",
                flush=True,
            )
        return 0

    print(
        production_profit_report(
            repo,
            profile=args.profile,
            vanilla_profile=args.vanilla_profile,
            load_order_path=load_order_path,
            include_specific=args.include_specific,
        ),
        flush=True,
    )
    return 0


def _savegame(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    save_args: list[str | os.PathLike[str]] = []
    if not _has_option(extra, "--save") and not _has_option(extra, "--save-dir"):
        save_args.extend(["--save-dir", _resolve_save_dir(repo, None)])
    result = _run(["eu5-orchestrator", "savegame", "--project", project, *save_args, *extra], repo)
    if result != 0:
        return result
    return _publish_graph_examples(repo, [SAVEGAME_EXPLORER.name])


def _europedia(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit("europedia does not accept extra arguments.")

    from prosper_or_perish_constructor.europedia import (
        EuropediaExportError,
        write_europedia_export,
    )

    mod_root = _project_mod_root(repo, project)
    try:
        html_path, json_path = write_europedia_export(
            mod_root,
            repo / EUROPEDIA_EXPORT,
            repo / EUROPEDIA_ENTRIES,
        )
    except EuropediaExportError as error:
        raise SystemExit(str(error)) from error

    print(f"Exported Europedia HTML: {html_path}", flush=True)
    print(f"Exported Europedia JSON: {json_path}", flush=True)
    return _publish_graph_examples(repo, [EUROPEDIA_EXPORT.name, EUROPEDIA_ENTRIES.name])


def _has_option(args: Sequence[str], option: str) -> bool:
    return any(arg == option or arg.startswith(f"{option}=") for arg in args)


def _savegame_purge(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit("savegame-purge does not accept extra arguments.")

    for path in SAVEGAME_PURGE_PATHS:
        target = _repo_path(repo, path)
        if args.dry_run:
            print(f"Would delete: {target}", flush=True)
            continue
        if target.is_dir():
            shutil.rmtree(target)
            print(f"Deleted directory: {target}", flush=True)
        elif target.exists():
            target.unlink()
            print(f"Deleted file: {target}", flush=True)
        else:
            print(f"Already absent: {target}", flush=True)
    return 0


def _publish_docs(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    if extra:
        raise SystemExit("publish-docs accepts examples as positional arguments, not extra args.")

    return _publish_graph_examples(repo, args.examples or PUBLISHED_GRAPH_EXAMPLES)


def _publish_graph_examples(repo: Path, examples: Sequence[str]) -> int:
    graphs_dir = repo / "graphs"
    examples_dir = repo / "docs" / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)

    for example in examples:
        source = graphs_dir / example
        destination = examples_dir / example
        if not source.is_file():
            raise SystemExit(f"Missing generated docs output: {source}")
        _copy_published_example(source, destination, repo)
        print(f"Updated docs/examples/{example}", flush=True)

    graph_assets_dir = graphs_dir / "assets"
    if graph_assets_dir.is_dir():
        example_assets_dir = examples_dir / "assets"
        shutil.copytree(graph_assets_dir, example_assets_dir, dirs_exist_ok=True)
        print("Updated docs/examples/assets", flush=True)
    return 0


def _copy_published_example(source: Path, destination: Path, repo: Path) -> None:
    if source.suffix not in {".html", ".json"}:
        shutil.copy2(source, destination)
        return

    text = source.read_text(encoding="utf-8")
    destination.write_text(_portable_published_text(text, repo), encoding="utf-8")


def _portable_published_text(text: str, repo: Path) -> str:
    resolved = repo.resolve()
    replacements = {
        resolved.as_posix(),
        str(resolved),
        str(resolved).replace("\\", "\\\\"),
    }
    for raw in sorted(replacements, key=len, reverse=True):
        if not raw:
            continue
        text = text.replace(f"{raw}/", "<constructor-repo>/")
        text = text.replace(raw, "<constructor-repo>")
    return text


def _extract_report_count(output: str, key: str) -> int | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(\d+)\s*$", output)
    return int(match.group(1)) if match else None


def _native_temp_subprocess_env(repo: Path) -> dict[str, str]:
    """Return an env with temp files on native Linux storage for worker sockets."""

    temp_dir = repo / "artifacts" / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    temp_text = str(temp_dir)
    env["TMPDIR"] = temp_text
    env["TMP"] = temp_text
    env["TEMP"] = temp_text
    return env


def _export_savegame_notebook_global_webps(
    *,
    repo: Path,
    dataset: Path,
    load_order: Path,
    profile: str,
) -> None:
    from prosper_or_perish_constructor import savegame_notebook

    print("global webp exports: rendering", flush=True)
    started_at = time.perf_counter()
    output = savegame_notebook.export_global_map_outputs(
        repo=repo,
        data_root=dataset,
        load_order_path=load_order,
        profile=profile,
    )
    elapsed = time.perf_counter() - started_at
    for export in output.animations:
        print(
            f"global webp: {_display_path(repo, export.path)} "
            f"({_format_file_size(export.path)})",
            flush=True,
        )
    print(f"global viewer: {_display_path(repo, output.viewer.path)}", flush=True)
    print(f"global webp exports: completed in {_format_elapsed_seconds(elapsed)}", flush=True)


def _display_path(repo: Path, path: Path) -> Path:
    try:
        return path.relative_to(repo)
    except ValueError:
        return path


def _format_file_size(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return "size unknown"
    if size >= 1_000_000:
        return f"{size / 1_000_000:.1f} MB"
    if size >= 1_000:
        return f"{size / 1_000:.1f} KB"
    return f"{size} B"


def _format_elapsed_seconds(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, remainder = divmod(total, 60)
    if minutes:
        return f"{minutes}m {remainder:02d}s"
    return f"{remainder}s"


def _print_savegame_notebook_dataset_status(
    repo: Path,
    dataset: Path,
    *,
    output: Path,
    force: bool,
    active_save_dir: Path | None,
    require_manifest: bool,
) -> None:
    manifest = dataset / "manifest.parquet"
    if force:
        print("--force ignored: notebooks now read the raw dataset directly.", flush=True)
    if output != repo / SAVEGAME_NOTEBOOK_DATA:
        print(f"--output ignored: notebooks now read {dataset}", flush=True)
    print(f"raw dataset: {dataset}", flush=True)
    print(f"notebook data: {dataset}", flush=True)
    print("notebook rewrite: skipped (not required)", flush=True)
    if not manifest.is_file():
        message = f"raw dataset manifest not found: {manifest}"
        if require_manifest:
            raise SystemExit(message)
        print(message, flush=True)
        return

    try:
        import polars as pl
    except ModuleNotFoundError as exc:
        raise SystemExit(f"Cannot read raw dataset status; missing dependency: {exc.name}") from exc

    frame = pl.read_parquet(manifest)
    total = frame.height
    active = total
    if active_save_dir is not None and not frame.is_empty():
        path_column = (
            "path"
            if "path" in frame.columns
            else "source_path"
            if "source_path" in frame.columns
            else None
        )
        if path_column is not None:
            active = sum(
                1
                for value in frame.get_column(path_column).to_list()
                if _save_path_is_under_active_dir(value, active_save_dir)
            )
    print(f"snapshots: {active}", flush=True)
    if active != total:
        print(f"stale_snapshots_ignored: {total - active}", flush=True)
    table_root = dataset / "tables"
    if table_root.is_dir():
        for table_dir in sorted(path for path in table_root.iterdir() if path.is_dir()):
            count = len(list(table_dir.rglob("*.parquet")))
            if count:
                print(f"{table_dir.name}: {count} parquet file(s)", flush=True)


def _save_path_is_under_active_dir(value: object, active_save_dir: Path) -> bool:
    if value is None:
        return False
    path = Path(str(value)).expanduser()
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if not resolved.is_file():
        return False
    try:
        resolved.relative_to(active_save_dir.expanduser().resolve())
    except ValueError:
        return False
    return True


def _repo_path(repo: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo / path


def _resolve_save_dir(repo: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return _repo_path(repo, explicit).expanduser()

    checked: list[Path] = []
    for candidate in _savegame_dir_candidates():
        expanded = candidate.expanduser()
        if expanded in checked:
            continue
        checked.append(expanded)
        if expanded.is_dir() and any(expanded.glob("*.eu5")):
            return expanded

    checked_text = "\n".join(f"  - {path}" for path in checked)
    raise SystemExit(
        "Could not auto-detect an EU5 save folder containing .eu5 files. Checked:\n"
        f"{checked_text}\n"
        "Pass --save-dir /path/to/save-games if the save folder is somewhere else."
    )


def _savegame_dir_candidates() -> list[Path]:
    candidates: list[Path] = []
    suffix = Path("Documents/Paradox Interactive/Europa Universalis V/save games")

    for value in (
        os.environ.get("USERPROFILE"),
        _windows_userprofile_from_cmd(),
        Path.home(),
    ):
        if value:
            candidates.append(Path(value) / suffix)

    for base in _wsl_windows_user_dirs():
        candidates.append(base / suffix)
        candidates.append(base / "OneDrive" / suffix)

    return candidates


def _wsl_windows_user_dirs() -> list[Path]:
    users = Path("/mnt/c/Users")
    if not users.is_dir():
        return []
    ignored = {"All Users", "Default", "Default User", "Public", "desktop.ini"}
    return sorted(path for path in users.iterdir() if path.is_dir() and path.name not in ignored)


def _windows_userprofile_from_cmd() -> str | None:
    if shutil.which("cmd.exe") is None:
        return None
    # /u makes cmd write piped output as UTF-16LE; without it the output is in the OEM codepage
    # (cp850 on German hosts), which is not UTF-8 and garbles non-ASCII user names.
    completed = subprocess.run(
        ["cmd.exe", "/d", "/u", "/c", "echo %USERPROFILE%"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.decode("utf-16-le").strip()
    if not value or "%" in value:
        return None
    if shutil.which("wslpath") is None:
        return value
    converted = subprocess.run(
        ["wslpath", "-u", value],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if converted.returncode != 0:
        return value
    return converted.stdout.strip()


def _sync_stage_fingerprints(repo: Path, project: Path) -> dict[str, str]:
    return {stage: _sync_stage_fingerprint(repo, project, stage) for stage in SYNC_STAGES}


def _sync_stage_fingerprint(repo: Path, project: Path, stage: str) -> str:
    config = _project_config(project)
    if stage == "blueprints":
        return _fingerprint_paths(_blueprint_fingerprint_paths(repo, project, config))
    from eu5gameparser.load_order import local_load_order_path

    from prosper_or_perish_constructor.vanilla_mirror import installed_build_id

    load_order = repo / CONSTRUCTOR_LOAD_ORDER
    digest = hashlib.sha256(
        _fingerprint_paths(
            [
                *_worldbuilder_fingerprint_paths(repo, project, config),
                *_blueprint_fingerprint_paths(repo, project, config),
                load_order,
                local_load_order_path(load_order),
            ],
            file_filter=_is_fingerprint_input,
        ).encode()
    )
    # The game data itself is too large to hash; its Steam build stands in for it.
    digest.update(f"game build {installed_build_id(load_order)}".encode())
    return digest.hexdigest()


def _worldbuilder_fingerprint_paths(repo: Path, project: Path, config: dict[str, Any]) -> list[Path]:
    section = _mapping(config.get("worldbuilder", {}))
    paths: list[Path] = [project]
    for key in ("handover", "geography_export"):
        raw = section.get(key)
        if not raw:
            continue
        root = Path(str(raw))
        root = root if root.is_absolute() else (repo / root)
        # contract.json pins every handover file by SHA-256.
        for name in ("contract.json", "ha1300-build.json"):
            candidate = root / name
            if candidate.is_file():
                paths.append(candidate)
    paths.extend(repo / relative for relative in WORLDBUILDER_CODE_AND_DATA)
    mod_root = _project_mod_root(repo, project)
    paths.extend(mod_root / relative for relative in WORLDBUILDER_MOD_INPUTS)
    return paths


def _is_fingerprint_input(path: Path) -> bool:
    return "__pycache__" not in path.parts and path.suffix != ".pyc"


def _blueprint_fingerprint_paths(repo: Path, project: Path, config: dict[str, Any]) -> list[Path]:
    blueprints = _mapping(config.get("building_blueprints", {}))
    manifest = _config_path(repo, blueprints.get("manifest")) or repo / "blueprints" / "buildings.manifest.yml"
    return [project, manifest, repo / "blueprints" / "accepted"]


def _validation_fingerprint(repo: Path, project: Path) -> str:
    mod_root = _project_mod_root(repo, project)
    return _fingerprint_paths(
        [project, repo / CONSTRUCTOR_LOAD_ORDER, mod_root],
        file_filter=_is_validation_input,
    )


def _is_validation_input(path: Path) -> bool:
    return path.suffix.lower() in {".txt", ".yml", ".yaml", ".gui"}


def _fingerprint_paths(paths: Sequence[Path], *, file_filter=None) -> str:
    digest = hashlib.sha256()
    for path in sorted({item.resolve() if item.exists() else item for item in paths}, key=str):
        _fingerprint_path(digest, path, path, file_filter=file_filter)
    return digest.hexdigest()


def _fingerprint_path(digest, path: Path, root: Path, *, file_filter=None) -> None:
    if path.is_dir():
        files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
        for candidate in files:
            if file_filter is not None and not file_filter(candidate):
                continue
            _fingerprint_file(digest, candidate, candidate.relative_to(root))
        return
    if not path.is_file():
        digest.update(f"missing:{path}\n".encode("utf-8", errors="surrogateescape"))
        return
    if file_filter is None or file_filter(path):
        _fingerprint_file(digest, path, Path(path.name))


def _fingerprint_file(digest, path: Path, label: Path) -> None:
    digest.update(str(label).replace(os.sep, "/").encode("utf-8", errors="surrogateescape"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")


def _project_config(project: Path) -> dict[str, Any]:
    with project.open("rb") as handle:
        return tomllib.load(handle)


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _config_path(repo: Path, value: object) -> Path | None:
    if value in (None, ""):
        return None
    return _resolve_config_path(repo, value)


def _resolve_config_path(base: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else (base / path).resolve()


def _load_sync_state(repo: Path) -> dict[str, str]:
    path = repo / SYNC_STATE_PATH
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if isinstance(value, str)}


def _save_sync_state(repo: Path, state: dict[str, str]) -> None:
    path = repo / SYNC_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record_current_sync_state(repo: Path, project: Path) -> None:
    state = _sync_stage_fingerprints(repo, project)
    state["validation"] = _validation_fingerprint(repo, project)
    _save_sync_state(repo, state)


GAME_PROCESS = "eu5.exe"


def _game_running() -> bool:
    """Whether EU5 runs on the Windows host (checked through tasklist.exe from WSL)."""
    try:
        result = subprocess.run(
            ["tasklist.exe", "/FI", f"IMAGENAME eq {GAME_PROCESS}", "/FO", "CSV", "/NH"],
            capture_output=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    # tasklist prints localized text in the OEM codepage (not UTF-8); the image name is ASCII, so match the raw bytes.
    return GAME_PROCESS.lower().encode("ascii") in result.stdout.lower()


def _deploy_built_mod(repo: Path, project: Path, *, force: bool, while_running: bool = False) -> int:
    # With -debug_mode the game's filewatcher reloads changed script files. Reloading building types that
    # the mod REPLACEs re-adds vanilla's production methods, so error.log fills with thousands of false
    # "duplicated production method name" and "Unexpected token" lines and the running game is left
    # in a mixed state. Deploy only while the game is closed.
    if not while_running and _game_running():
        print(
            "EU5 is running: the build is ready but NOT deployed, because the game would hot-reload the mod "
            "and log false duplicate/unexpected-token errors. Close the game and re-run `uv run ppc sync --yes` "
            "(the smart sync then only deploys), or pass --while-running.",
            flush=True,
        )
        return 3
    command: list[str | os.PathLike[str]] = ["eu5-orchestrator", "deploy", "--project", project, "--clean"]
    if force:
        command.append("--force")
    return _run(command, repo)


def _smart_sync(args: argparse.Namespace, repo: Path, project: Path) -> int:
    state = _load_sync_state(repo)
    ran_generator = False
    for stage in SYNC_STAGES:
        # Taken when the stage is reached: the World Builder stage patches blueprints the render stage reads.
        if not args.force_build and state.get(stage) == _sync_stage_fingerprint(repo, project, stage):
            print(f"Smart sync: {stage} inputs unchanged; skipping.", flush=True)
            continue
        if stage == "worldbuilder":
            _worldbuilder_apply(repo, project)
        else:
            result = _run(["eu5-orchestrator", "render", "--project", project, "--overwrite"], repo)
            if result != 0:
                return result
        ran_generator = True
    _finalize_constructor_mod(repo, project)
    # The stages rewrite blueprints and mod files they also read, so the inputs are recorded as this sync
    # leaves them; the next sync reruns a stage only if something changed them since.
    state.update(_sync_stage_fingerprints(repo, project))
    validation_before = _validation_fingerprint(repo, project)
    if ran_generator or args.force_build or state.get("validation") != validation_before:
        result = _run(["eu5-orchestrator", "validate", "--project", project], repo)
        if result != 0:
            return result
        state["validation"] = _validation_fingerprint(repo, project)
    else:
        print("Smart sync: validation inputs unchanged; skipping validation.", flush=True)
    _save_sync_state(repo, state)
    return _deploy_built_mod(repo, project, force=args.force_deploy, while_running=args.while_running)


def _sync(args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit("sync does not accept extra arguments.")
    if not args.yes:
        raise SystemExit(
            "Refusing to mirror into the live Paradox mod folder without explicit confirmation. "
            "Re-run `uv run ppc sync --yes` only when you intend to update the live mod."
        )
    if not (repo / "constructor.local.toml").is_file():
        raise SystemExit(
            "Refusing to sync: constructor.local.toml is missing. Configure [deploy].target first."
        )
    if args.full_build:
        build_result = _build(args, (), repo, project)
        if build_result != 0:
            return build_result
        _record_current_sync_state(repo, project)
        return _deploy_built_mod(repo, project, force=args.force_deploy, while_running=args.while_running)
    return _smart_sync(args, repo, project)




if __name__ == "__main__":
    raise SystemExit(main())


def _add_savegame_notebooks_command(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
    handler,
) -> argparse.ArgumentParser:
    command = subcommands.add_parser(name, help=help_text, description=help_text)
    command.add_argument(
        "--dataset",
        type=Path,
        default=SAVEGAME_DATASET,
        help="Raw savegame parquet dataset directory relative to --repo. Defaults to graphs/dataset.",
    )
    command.add_argument(
        "--output",
        type=Path,
        default=SAVEGAME_NOTEBOOK_DATA,
        help=(
            "Deprecated. Notebooks now read the raw --dataset parquet directory directly; "
            "this option is ignored."
        ),
    )
    command.add_argument(
        "--load-order",
        type=Path,
        default=CONSTRUCTOR_LOAD_ORDER,
        help="Load-order TOML path relative to --repo. Defaults to constructor.load_order.toml.",
    )
    command.add_argument(
        "--profile",
        default=CONSTRUCTOR_PROFILE,
        help="Parser profile from the load-order TOML. Defaults to constructor.",
    )
    command.set_defaults(handler=handler)
    return command


def _savegame_notebooks_build(
    args: argparse.Namespace, extra: Sequence[str], repo: Path, project: Path
) -> int:
    if extra:
        raise SystemExit("savegame-notebooks build does not accept extra arguments.")

    active_save_dir: Path | None = None
    if not args.no_ingest:
        save_dir = _resolve_save_dir(repo, args.save_dir)
        active_save_dir = save_dir
        saves = sorted(save_dir.glob("*.eu5")) if save_dir.is_dir() else []
        if not saves:
            raise SystemExit(
                f"No .eu5 saves found in {save_dir}. "
                "Pass --save-dir /path/to/save-games if the EU5 save folder is somewhere else."
            )
        print(f"Found {len(saves)} .eu5 saves in {save_dir}", flush=True)
        ingest_code, ingest_output = _run_collecting_output(
            [
                "uv",
                "run",
                "eu5parse",
                "savegame",
                "ingest",
                "--save-dir",
                save_dir,
                "--output",
                _repo_path(repo, args.dataset),
                "--profile",
                args.profile,
                "--load-order",
                _repo_path(repo, args.load_order),
                "--workers",
                str(args.workers),
                *(["--extended"] if args.extended else []),
            ],
            repo,
            env=_native_temp_subprocess_env(repo),
        )
        if ingest_code != 0:
            return ingest_code
        processed = _extract_report_count(ingest_output, "processed")
        skipped = _extract_report_count(ingest_output, "skipped")
        if processed == 0:
            suffix = f" ({skipped} already digested)" if skipped is not None else ""
            print(f"raw ingest skipped: no new saves processed{suffix}", flush=True)
        elif processed is not None:
            print(f"raw ingest processed: {processed} new save(s)", flush=True)
    elif args.save_dir is not None:
        active_save_dir = _repo_path(repo, args.save_dir).expanduser()

    dataset = _repo_path(repo, args.dataset)
    _print_savegame_notebook_dataset_status(
        repo,
        dataset,
        output=_repo_path(repo, args.output),
        force=args.force,
        active_save_dir=active_save_dir,
        require_manifest=args.no_ingest,
    )
    if not args.no_webp:
        if (dataset / "manifest.parquet").is_file():
            _export_savegame_notebook_global_webps(
                repo=repo,
                dataset=dataset,
                load_order=_repo_path(repo, args.load_order),
                profile=args.profile,
            )
        else:
            print("global webp exports: skipped (raw dataset manifest missing)", flush=True)
    return 0
