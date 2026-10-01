"""Render the live Tavern / Victualling Yard caps; the offline planner evaluates these same scripts."""

import json

from .buildings import river_size_trigger, write_river_size_triggers


def write(repo, mod_root):
    cfg = json.loads((repo / "config/victuals_logistics.json").read_text())
    write_river_size_triggers(mod_root)
    labels = {
        "BASE": "Local distribution",
        "DEVELOPMENT": "Development",
        "POPULATION": "Settlement size",
        "HARBOR": "Harbor suitability",
        "COAST": "Coastal access",
        "RIVER": "River access",
        "NAVIGABLE": "Navigable waterway",
        "DIFFICULT": "Difficult waterway",
        "MAINTAINED": "Maintained waterway",
        "MARKET": "Market centre",
        "RANK": "Settlement role",
        "RGO": "Food-producing hinterland",
        "FARMLAND": "Cultivated hinterland",
        "TERRAIN": "Land transport difficulty",
        "ROADS": "Roads",
        "HARBOR_CAPACITY": "Harbor capacity",
        "THRESHOLD": "Established harbor trade",
        # Every operation of a cap that shows a breakdown needs a desc, or the tooltip shows a "missing key" line
        # (2026-10-01). No floor = yes: the engine floors max_levels to whole levels itself.
        "MINIMUM": "Minimum",
        "MAXIMUM": "Upper limit",
        "SITE_TAVERN": "Not a town or city that is a province capital",
        "SITE_YARD": "Not a Victualling Yard site",
        "SITE_GRANGE": "Not a province capital, or a Victualling Yard site",
    }

    def add(label, value):
        return f"add = {{ desc = PP_VM_CAP_{label} value = {value} }}"

    def when(condition, label, value):
        return f"if = {{ limit = {{ {condition} }} {add(label, value)} }}"

    def clamp(op, label, value):
        return f"{op} = {{ desc = PP_VM_CAP_{label} value = {value} }}"

    def zero_unless(condition, label):
        return f"if = {{ limit = {{ {condition} }} multiply = {{ desc = PP_VM_CAP_{label} value = 0 }} }}"

    lines = [
        "# Generated from config/victuals_logistics.json. Both the planner and game use these values."
    ]
    for role, spec in ((k, cfg[k]) for k in ("tavern",)):
        body = [
            add("BASE", spec["base"]),
            add("DEVELOPMENT", f"development multiply = {spec['development']}"),
            add("POPULATION", f"population multiply = {spec['population']}"),
            add(
                "HARBOR",
                f"modifier:natural_harbor_suitability max = 3 min = 0 multiply = {spec['harbor']}",
            ),
        ]
        # Coast and waterways. Every location next to a navigation reach is coastal (river and channel banks count as
        # coast; tests/test_victuals_logistics_caps.py), so the three neighbour scans only run on coasts. Navigable and
        # difficult are mutually exclusive baseline classes; a maintained reach (state 4) is one of the navigable
        # states, so its scan only runs where a navigable one was found.
        open_water = "any_neighbor_location = { has_variable = pp_navigation_map_state OR = { var:pp_navigation_map_state = 1 var:pp_navigation_map_state = 4 var:pp_navigation_map_state = 6 } }"
        hard_water = "any_neighbor_location = { has_variable = pp_navigation_map_state OR = { var:pp_navigation_map_state = 2 var:pp_navigation_map_state = 5 } }"
        maintained = "any_neighbor_location = { has_variable = pp_navigation_map_state var:pp_navigation_map_state = 4 }"
        body.append(
            "if = { limit = { is_coastal = yes } "
            + add("COAST", spec["coast"])
            + f" if = {{ limit = {{ {open_water} }} {add('NAVIGABLE', spec['navigable'])}"
            + f" {when(maintained, 'MAINTAINED', spec['maintained'])} }}"
            + f" else_if = {{ limit = {{ {hard_water} }} {add('DIFFICULT', spec['difficult'])} }} }}"
        )
        # A location carries at most one river level: stop at the first match. The size is read as a modifier value
        # (buildings.river_size_trigger): has_location_modifier does not see the engine's own river statics, so this row
        # was missing in game wherever the engine traced the river (EU5 1.4 start: 14 Taverns one level above max).
        for level in range(1, 6):
            keyword = "if" if level == 1 else "else_if"
            body.append(
                f"{keyword} = {{ limit = {{ {river_size_trigger(level)} }} "
                f"{add('RIVER', round(level * spec['river_per_level'], 6))} }}"
            )
        body.append(when("is_market_center = yes", "MARKET", spec["market_center"]))
        for i, (rank, n) in enumerate(spec["rank"].items()):
            # ?= : locations without a rank (unsettled) also evaluate these caps. One rank per location.
            keyword = "if" if i == 0 else "else_if"
            body.append(f"{keyword} = {{ limit = {{ location_rank ?= location_rank:{rank} }} {add('RANK', n)} }}")
        if spec["food_rgo"]:
            body.append(
                when(
                    "OR = { "
                    + " ".join("raw_material = goods:" + g for g in cfg["food_rgos"])
                    + " }",
                    "RGO",
                    spec["food_rgo"],
                )
            )
        if spec["farmland"]:
            body.append(when("vegetation = farmland", "FARMLAND", spec["farmland"]))
        for i, (terrain, n) in enumerate(cfg["terrain_penalties"].items()):
            # one topography per location
            keyword = "if" if i == 0 else "else_if"
            body.append(f"{keyword} = {{ limit = {{ topography = {terrain} }} {add('TERRAIN', n)} }}")
        # Towns and larger that are province capitals only (2026-10-01, as the building's rank flags and potential).
        # Elsewhere 0, so the four-yearly cull clears Taverns an old save left in villages and non-capitals.
        body.append(zero_unless("OR = { is_province_capital = no location_rank ?= location_rank:rural_settlement }", "SITE_TAVERN"))
        body += [clamp("min", "MINIMUM", 0), clamp("max", "MAXIMUM", spec["maximum"])]
        lines.append(
            f"{role}_max_level = {{\n " + "\n ".join(body) + "\n}"
        )
    # The harbour Victualling Yard: harbour capacity (natural harbour + river mouth + docks and shipyards), market centre
    # and development, minus a threshold, at least `minimum` on a Yard site. Elsewhere 0, so the four-yearly cull clears
    # Yards an old save left outside the harbour sites.
    y = cfg["victualling_yard"]
    body = [
        add("HARBOR_CAPACITY", f"modifier:harbor_suitability multiply = {y['harbor_capacity']}"),
        when("is_market_center = yes", "MARKET", y["market_center"]),
        add("DEVELOPMENT", f"development multiply = {y['development']}"),
        add("THRESHOLD", y["threshold"]),
        clamp("min", "MINIMUM", y["minimum"]),
        clamp("max", "MAXIMUM", y["maximum"]),
        zero_unless("NOT = { pp_victualling_yard_site = yes }", "SITE_YARD"),
    ]
    lines.append("victualling_yard_max_level = {\n " + "\n ".join(body) + "\n}")
    # The Grange, the Yard's overland twin at province capitals: base, roads, market centre, development.
    g = cfg["grange"]
    body = [add("BASE", g["base"])]
    for n in range(1, int(g["road_max"] / g["per_road"]) + 1):
        body.append(when(f"num_roads >= {n}", "ROADS", g["per_road"]))
    body += [
        when("is_market_center = yes", "MARKET", g["market_center"]),
        add("DEVELOPMENT", f"development multiply = {g['development']}"),
        zero_unless("OR = { is_province_capital = no pp_victualling_yard_site = yes }", "SITE_GRANGE"),
        clamp("min", "MINIMUM", 0),
        clamp("max", "MAXIMUM", g["maximum"]),
    ]
    lines.append("grange_max_level = {\n " + "\n ".join(body) + "\n}")
    path = mod_root / "in_game/common/script_values/pp_victuals_logistics.txt"
    path.write_text("\ufeff" + "\n\n".join(lines) + "\n", encoding="utf-8")
    # Victualling Yard sites: good harbours on the sea coast (pp_wb_coastal marks the World Builder's sea coast, river
    # ports excluded) or very good harbours anywhere, never in cold climates. The engine's harbour value includes the
    # river-mouth bonus, so a great river alone (river size 5 = +0.25) cannot pass the second tier.
    site = cfg["yard_site"]
    cold = " ".join(f"climate = {c}" for c in site["cold_climates"])
    trigger = (
        "# Generated from config/victuals_logistics.json (yard_site).\n"
        "pp_victualling_yard_site = {\n"
        "\tis_port = yes\n"
        f"\tNOR = {{ {cold} }}\n"
        "\tOR = {\n"
        f"\t\tAND = {{ has_location_modifier = pp_wb_coastal modifier:natural_harbor_suitability >= {site['sea_harbor']} }}\n"
        f"\t\tmodifier:natural_harbor_suitability >= {site['any_harbor']}\n"
        "\t}\n"
        "}\n"
    )
    trigger_path = mod_root / "in_game/common/scripted_triggers/pp_victuals_site_triggers.txt"
    trigger_path.write_text("\ufeff" + trigger, encoding="utf-8")
    loc = (
        mod_root / "main_menu/localization/english/pp_victuals_logistics_l_english.yml"
    )
    loc.write_text(
        "\ufeffl_english:\n"
        + "\n".join(f' PP_VM_CAP_{k}: "{v}"' for k, v in labels.items())
        + "\n",
        encoding="utf-8",
    )
