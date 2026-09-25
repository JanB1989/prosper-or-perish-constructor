"""Render the live Tavern / Victualling Yard caps; the offline planner evaluates these same scripts."""

import json


def write(repo, mod_root):
    cfg = json.loads((repo / "config/victuals_logistics.json").read_text())
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
    }

    def add(label, value):
        return f"add = {{ desc = PP_VM_CAP_{label} value = {value} }}"

    def when(condition, label, value):
        return f"if = {{ limit = {{ {condition} }} {add(label, value)} }}"

    lines = [
        "# Generated from config/victuals_logistics.json. Both the planner and game use these values."
    ]
    for role, spec in ((k, cfg[k]) for k in ("tavern", "victualling_yard")):
        body = [
            add("BASE", spec["base"]),
            add("DEVELOPMENT", f"development multiply = {spec['development']}"),
            add("POPULATION", f"population multiply = {spec['population']}"),
            add(
                "HARBOR",
                f"modifier:natural_harbor_suitability max = 3 min = 0 multiply = {spec['harbor']}",
            ),
            when("is_coastal = yes", "COAST", spec["coast"]),
        ]
        for level in range(1, 6):
            body.append(
                when(
                    f"has_location_modifier = river_flowing_through_{level}",
                    "RIVER",
                    round(level * spec["river_per_level"], 6),
                )
            )
        # Mutually exclusive baseline classes; a maintained reach keeps its better class.
        open_water = "any_neighbor_location = { has_variable = pp_navigation_map_state OR = { var:pp_navigation_map_state = 1 var:pp_navigation_map_state = 4 var:pp_navigation_map_state = 6 } }"
        hard_water = "any_neighbor_location = { has_variable = pp_navigation_map_state OR = { var:pp_navigation_map_state = 2 var:pp_navigation_map_state = 5 } }"
        body += [
            when(open_water, "NAVIGABLE", spec["navigable"]),
            f"else_if = {{ limit = {{ {hard_water} }} {add('DIFFICULT', spec['difficult'])} }}",
            when(
                "any_neighbor_location = { has_variable = pp_navigation_map_state var:pp_navigation_map_state = 4 }",
                "MAINTAINED",
                spec["maintained"],
            ),
            when("is_market_center = yes", "MARKET", spec["market_center"]),
        ]
        for rank, n in spec["rank"].items():
            body.append(when(f"location_rank = location_rank:{rank}", "RANK", n))
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
        for terrain, n in cfg["terrain_penalties"].items():
            body.append(when("topography = " + terrain, "TERRAIN", n))
        body += ["min = 0", f"max = {spec['maximum']}", "floor = yes"]
        lines.append(
            f"{role}_max_level = {{\n " + "\n ".join(body) + "\n}"
        )
    path = mod_root / "in_game/common/script_values/pp_victuals_logistics.txt"
    path.write_text("\ufeff" + "\n\n".join(lines) + "\n", encoding="utf-8")
    loc = (
        mod_root / "main_menu/localization/english/pp_victuals_logistics_l_english.yml"
    )
    loc.write_text(
        "\ufeffl_english:\n"
        + "\n".join(f' PP_VM_CAP_{k}: "{v}"' for k, v in labels.items())
        + "\n",
        encoding="utf-8",
    )
