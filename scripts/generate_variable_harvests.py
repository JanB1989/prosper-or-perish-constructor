from __future__ import annotations

import math
import re
import tomllib
from pathlib import Path
from typing import Any

from eu5gameparser.savegame.hierarchy import load_location_hierarchy

from prosper_or_perish_constructor import staple_foods

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "variable_harvests.toml"
LOAD_ORDER_PATH = ROOT / "constructor.load_order.toml"
PROFILE = "constructor"

SEVERITIES = (
    "abysmal",
    "very_poor",
    "poor",
    "normal",
    "good",
    "very_good",
    "bountiful",
)
ACTIVE_SEVERITIES = tuple(severity for severity in SEVERITIES if severity != "normal")
BAD_MEMORY_MARKERS = ("abysmal", "very_poor", "poor")
GOOD_MEMORY_MARKERS = ("good", "very_good", "bountiful")
SEVERITY_LABELS = {
    "abysmal": "Failed Harvest",
    "very_poor": "Bad Harvest",
    "poor": "Weak Harvest",
    "good": "Strong Harvest",
    "very_good": "Excellent Harvest",
    "bountiful": "Exceptional Harvest",
}
SEVERITY_DESCRIPTIONS = {
    "abysmal": "A disastrous harvest has struck",
    "very_poor": "A poor harvest has spread through",
    "poor": "A weak harvest is affecting",
    "good": "A strong harvest is helping",
    "very_good": "An excellent harvest is lifting",
    "bountiful": "An exceptional harvest is blessing",
}
POSITIVE_SEVERITY_TO_BASE = {
    "good": "poor",
    "very_good": "very_poor",
    "bountiful": "abysmal",
}
NEGATIVE_SEVERITY_TO_BASE = {
    "poor": "poor",
    "very_poor": "very_poor",
    "abysmal": "abysmal",
}
PROFILE_BY_SHOCK_AND_MEMORY = {
    "bad": {
        "previous_bad": "bad_persistent",
        "previous_good": "neutral",
        "none": "shock_bad",
    },
    "neutral": {
        "previous_bad": "memory_bad",
        "previous_good": "memory_good",
        "none": "neutral",
    },
    "good": {
        "previous_bad": "neutral",
        "previous_good": "good_persistent",
        "none": "shock_good",
    },
}
LAND_SUPER_REGIONS = {"africa", "america", "asia", "europe", "oceania"}


def main() -> int:
    config = _load_config()
    hierarchy = load_location_hierarchy(profile=PROFILE, load_order_path=LOAD_ORDER_PATH)
    region_map = _regions_by_subcontinent(config, hierarchy)
    location_values = _read_location_output_values(ROOT / config["paths"]["location_modifiers"])
    tiers = _derive_family_tiers(config, hierarchy, location_values)
    output_scale = _derive_output_scale(config, tiers)

    _write_static_modifiers(config, tiers, output_scale)
    _write_scripted_effects(config, region_map)
    _write_localization(config)

    print(
        "Generated regional variable harvests for "
        f"{len(region_map)} subcontinents and {sum(len(v) for v in region_map.values())} regions."
    )
    return 0


def _load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _regions_by_subcontinent(
    config: dict[str, Any],
    hierarchy: dict[str, dict[str, str | None]],
) -> dict[str, list[str]]:
    allowed = set(config["subcontinents"])
    regions: dict[str, set[str]] = {subcontinent: set() for subcontinent in allowed}
    for row in hierarchy.values():
        if row.get("super_region") not in LAND_SUPER_REGIONS:
            continue
        subcontinent = row.get("macro_region")
        region = row.get("region")
        if subcontinent in allowed and region:
            regions[subcontinent].add(region)
    return {key: sorted(value) for key, value in sorted(regions.items()) if value}


def _read_location_output_values(path: Path) -> dict[str, dict[str, float]]:
    location_values: dict[str, dict[str, float]] = {}
    current: str | None = None
    values: dict[str, float] = {}
    block_re = re.compile(r"^(pp_loc_[A-Za-z0-9_]+)\s*=\s*\{\s*$")
    modifier_re = re.compile(r"^\s*local_([A-Za-z0-9_]+)_output_modifier\s*=\s*(-?\d+(?:\.\d+)?)\s*$")

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if current is None:
            match = block_re.match(line)
            if match:
                current = match.group(1).removeprefix("pp_loc_")
                values = {}
            continue

        if line.strip() == "}":
            location_values[current] = values
            current = None
            values = {}
            continue

        match = modifier_re.match(line)
        if match:
            values[match.group(1)] = float(match.group(2))

    return location_values


def _derive_family_tiers(
    config: dict[str, Any],
    hierarchy: dict[str, dict[str, str | None]],
    location_values: dict[str, dict[str, float]],
) -> dict[str, dict[str, str]]:
    families = config["families"]
    derivation = config["derivation"]
    overrides = config.get("reviewed_tier_overrides", {})
    values_by_subcontinent: dict[str, dict[str, list[float]]] = {
        subcontinent: {family: [] for family in families}
        for subcontinent in config["subcontinents"]
    }

    for location, row in hierarchy.items():
        subcontinent = row.get("macro_region")
        if subcontinent not in values_by_subcontinent:
            continue
        output_values = location_values.get(location)
        if output_values is None:
            output_values = location_values.get(f"{location}_pp", {})
        for family, family_config in families.items():
            for good in family_config["goods"]:
                values_by_subcontinent[subcontinent][family].append(output_values.get(good, 0.0))

    tiers: dict[str, dict[str, str]] = {}
    for subcontinent in config["subcontinents"]:
        tiers[subcontinent] = {}
        for family in families:
            values = values_by_subcontinent[subcontinent][family]
            positive_share = (
                sum(1 for value in values if value > 0) / len(values)
                if values
                else 0.0
            )
            p90 = _percentile(values, 0.90)
            if (
                positive_share >= derivation["high_positive_share"]
                or p90 >= derivation["high_p90"]
            ):
                tier = "high"
            elif (
                positive_share >= derivation["standard_positive_share"]
                or p90 >= derivation["standard_p90"]
            ):
                tier = "standard"
            else:
                tier = "low"
            tiers[subcontinent][family] = overrides.get(subcontinent, {}).get(family, tier)

    return tiers


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = math.ceil(percentile * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _derive_output_scale(config: dict[str, Any], tiers: dict[str, dict[str, str]]) -> float:
    target = config.get("output_scaling", {}).get("max_abs_output_modifier")
    if target is None:
        return 1.0

    max_abs = 0.0
    for subcontinent in config["subcontinents"]:
        for family, family_config in config["families"].items():
            multiplier = config["tier_multipliers"][tiers[subcontinent][family]]
            for severity in ACTIVE_SEVERITIES:
                for good in family_config["goods"]:
                    value = abs(_raw_modifier_value_for_good(good, severity, multiplier, config))
                    max_abs = max(max_abs, value)

    if max_abs == 0:
        return 1.0
    return float(target) / max_abs


def _write_static_modifiers(
    config: dict[str, Any],
    tiers: dict[str, dict[str, str]],
    output_scale: float,
) -> None:
    path = ROOT / config["paths"]["static_modifiers"]
    lines: list[str] = [
        "# Generated by scripts/generate_variable_harvests.py; do not edit by hand.",
        "# Active harvest modifiers are combined by subcontinent and severity for readable UI.",
        "",
    ]

    lines.append("# Combined active harvest modifiers.")
    for subcontinent in config["subcontinents"]:
        lines.append(f"# {subcontinent}")
        for severity in ACTIVE_SEVERITIES:
            lines.extend(_combined_modifier_lines(subcontinent, severity, tiers, config, output_scale))

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8-sig")


def _combined_modifier_lines(
    subcontinent: str,
    severity: str,
    tiers: dict[str, dict[str, str]],
    config: dict[str, Any],
    output_scale: float,
) -> list[str]:
    lines = [
        f"{_active_harvest_modifier(subcontinent, severity)} = {{",
        "\tgame_data = { category = location }",
    ]
    food_consumption = config["food_consumption"].get(severity)
    if food_consumption is not None:
        lines.append(f"\tlocal_peasants_food_consumption = {_format_number(food_consumption)}")
    exempt = exempt_goods(config)
    for family, family_config in config["families"].items():
        tier = tiers[subcontinent][family]
        multiplier = config["tier_multipliers"][tier]
        for good in family_config["goods"]:
            if good in exempt:
                continue
            value = _modifier_value_for_good(good, severity, multiplier, config, output_scale)
            lines.append(f"\tlocal_{good}_output_modifier = {_format_number(value)}")
    lines.extend(["}", ""])
    return lines


def exempt_goods(config: dict[str, Any]) -> frozenset[str]:
    """Goods the harvests leave alone: every good of the staple groups in ``[exempt] staple_groups`` (2026-10-04, Jan:
    the staple animals). They still count toward their family's tier, so the other goods' tiers do not move."""
    groups = config.get("exempt", {}).get("staple_groups", [])
    return frozenset(good for group in groups for good in staple_foods.goods_in_group(str(group)))


def _modifier_value_for_good(
    good: str,
    severity: str,
    tier_multiplier: float,
    config: dict[str, Any],
    output_scale: float = 1.0,
) -> float:
    return round(_raw_modifier_value_for_good(good, severity, tier_multiplier, config) * output_scale, 2)


def _raw_modifier_value_for_good(
    good: str,
    severity: str,
    tier_multiplier: float,
    config: dict[str, Any],
) -> float:
    sensitivity = config["goods"][good]["sensitivity"]
    if severity in NEGATIVE_SEVERITY_TO_BASE:
        base_key = NEGATIVE_SEVERITY_TO_BASE[severity]
        sign = -1.0
    else:
        base_key = POSITIVE_SEVERITY_TO_BASE[severity]
        sign = 1.0
    value = config["sensitivity_values"][sensitivity][base_key] * tier_multiplier
    return sign * value


def _write_scripted_effects(config: dict[str, Any], region_map: dict[str, list[str]]) -> None:
    path = ROOT / config["paths"]["scripted_effects"]
    lines: list[str] = [
        "# Generated by scripts/generate_variable_harvests.py; do not edit by hand.",
        "",
        "apply_regional_harvest_effect = {",
    ]
    for subcontinent in config["subcontinents"]:
        if subcontinent not in region_map:
            continue
        lines.extend(
            [
                f"\tsub_continent:{subcontinent} = {{",
                "\t\trandom_list = {",
            ]
        )
        for shock, weight in config["shock_weights"].items():
            lines.extend(
                [
                    f"\t\t\t{weight} = {{",
                    f"\t\t\t\tpp_apply_{subcontinent}_harvest_shock_{shock} = yes",
                    "\t\t\t}",
                ]
            )
        lines.extend(["\t\t}", "\t}", ""])
    lines.extend(["}", ""])

    for subcontinent, regions in region_map.items():
        for shock in config["shock_weights"]:
            lines.append(f"pp_apply_{subcontinent}_harvest_shock_{shock} = {{")
            for region in regions:
                lines.extend(
                    [
                        f"\tregion:{region} = {{",
                        f"\t\tpp_roll_region_harvest_for_{shock}_shock = {{ subcontinent = {subcontinent} }}",
                        "\t}",
                    ]
                )
            lines.extend(["}", ""])

    for shock in config["shock_weights"]:
        lines.extend(_shock_router_lines(shock))

    for profile in config["profiles"]:
        lines.extend(_profile_roll_lines(profile, config))

    lines.extend(_apply_outcome_lines(config))
    lines.extend(_clear_lines(config))

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8-sig")


def _shock_router_lines(shock: str) -> list[str]:
    route = PROFILE_BY_SHOCK_AND_MEMORY[shock]
    return [
        f"pp_roll_region_harvest_for_{shock}_shock = {{",
        "\tif = {",
        "\t\tlimit = {",
        *_memory_trigger_lines(BAD_MEMORY_MARKERS, 3),
        "\t\t}",
        f"\t\tpp_roll_region_harvest_{route['previous_bad']} = {{ subcontinent = $subcontinent$ }}",
        "\t}",
        "\telse_if = {",
        "\t\tlimit = {",
        *_memory_trigger_lines(GOOD_MEMORY_MARKERS, 3),
        "\t\t}",
        f"\t\tpp_roll_region_harvest_{route['previous_good']} = {{ subcontinent = $subcontinent$ }}",
        "\t}",
        "\telse = {",
        f"\t\tpp_roll_region_harvest_{route['none']} = {{ subcontinent = $subcontinent$ }}",
        "\t}",
        "}",
        "",
    ]


def _memory_trigger_lines(markers: tuple[str, ...], tabs: int) -> list[str]:
    indent = "\t" * tabs
    child = "\t" * (tabs + 1)
    grandchild = "\t" * (tabs + 2)
    lines = [f"{indent}any_location_in_region = {{", f"{child}OR = {{"]
    for marker in markers:
        lines.append(f"{grandchild}has_location_modifier = pp_harvest_$subcontinent$_{marker}")
    lines.extend([f"{child}}}", f"{indent}}}"])
    return lines


def _profile_roll_lines(profile: str, config: dict[str, Any]) -> list[str]:
    lines = [
        f"pp_roll_region_harvest_{profile} = {{",
        "\trandom_list = {",
    ]
    for severity in SEVERITIES:
        weight = config["profiles"][profile][severity]
        lines.append(f"\t\t{weight} = {{")
        if severity == "normal":
            lines.append(
                "\t\t\tclear_variable_harvest_effects_in_region = { subcontinent = $subcontinent$ }"
            )
        else:
            lines.append(
                "\t\t\tpp_apply_region_harvest_outcome = { "
                f"subcontinent = $subcontinent$ severity = {severity} }}"
            )
        lines.append("\t\t}")
    lines.extend(["\t}", "}", ""])
    return lines


def _apply_outcome_lines(config: dict[str, Any]) -> list[str]:
    lines = [
        "pp_apply_region_harvest_outcome = {",
        "\tclear_variable_harvest_effects_in_region = { subcontinent = $subcontinent$ }",
        "\tevery_location_in_region = {",
        "\t\tlimit = {",
        "\t\t\tis_ownable = yes",
        "\t\t\tprovince ?= {",
        "\t\t\t\tNOT = { has_province_modifier = russian_famine }",
        "\t\t\t}",
        "\t\t}",
        "\t\tadd_location_modifier = {",
        "\t\t\tmodifier = pp_harvest_$subcontinent$_$severity$",
        "\t\t\tmonths = 13",
        "\t\t\tmode = replace",
        "\t\t}",
    ]
    lines.extend(["\t}", "}", ""])
    return lines


def _clear_lines(config: dict[str, Any]) -> list[str]:
    lines = [
        "clear_variable_harvest_effects_in_region = {",
        "\tevery_location_in_region = {",
        "\t\tlimit = { is_ownable = yes }",
    ]
    for severity in ACTIVE_SEVERITIES:
        lines.append(f"\t\tremove_location_modifier = pp_harvest_$subcontinent$_{severity}")
    lines.extend(["\t}", "}", ""])
    return lines


def _format_number(value: float) -> str:
    if abs(value) < 0.005:
        return "0"
    return f"{value:.2f}"


def _active_harvest_modifier(subcontinent: str, severity: str) -> str:
    return f"pp_harvest_{subcontinent}_{severity}"


def _write_localization(config: dict[str, Any]) -> None:
    path = ROOT / config["paths"]["modifier_localization"]
    lines = [
        "l_english:",
        "  # Generated by scripts/generate_variable_harvests.py; do not edit by hand.",
    ]
    for subcontinent in config["subcontinents"]:
        label = _display_name(subcontinent)
        for severity in ACTIVE_SEVERITIES:
            modifier = _active_harvest_modifier(subcontinent, severity)
            lines.append(f'  STATIC_MODIFIER_NAME_{modifier}: "{SEVERITY_LABELS[severity]}: {label}"')
            lines.append(
                f'  STATIC_MODIFIER_DESC_{modifier}: "{SEVERITY_DESCRIPTIONS[severity]} '
                f"{label}. This location's harvest modifier shows the affected goods; "
                'an average harvest leaves no harvest modifier."'
            )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8-sig")


def _display_name(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_"))


if __name__ == "__main__":
    raise SystemExit(main())
