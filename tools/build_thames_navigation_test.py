"""Build a small, artificial Thames navigation experiment from vanilla map data.

Run through ``uv run python tools/build_thames_navigation_test.py --output ...``.
Output must be an empty staging directory, never a live mod. No main-mod sync.
Reference designs: Navigable Rivers (Steam 3778399034), River_Barriers and
Elevation_Friction by mikejaklitsch. This generator is independent of their code.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from eu5gameparser.clausewitz.parser import parse_file


BOX = (7600, 1740, 7750, 1880)
ZONES = {
    "pp_thames_barrier": (7642, 7660, 0x123AF1),
    "pp_thames_upper": (7660, 7680, 0x123AF2),
    "pp_thames_lower": (7680, 7701, 0x123AF3),
}
TITLES = {
    "pp_thames_barrier": "Thames: Permanent Barrier",
    "pp_thames_upper": "Thames: Upper Reach",
    "pp_thames_lower": "Thames: London Reach",
}


def encode(a):
    return (a[..., 0].astype(np.uint32) << 16) | (a[..., 1].astype(np.uint32) << 8) | a[..., 2]


def pairs(a):
    result = set()
    for x, y in [(a[:, :-1], a[:, 1:]), (a[:-1, :], a[1:, :])]:
        mask = x != y
        result.update(tuple(sorted((int(u), int(v)))) for u, v in zip(x[mask], y[mask]))
    return result


def insert_list(text, key, items):
    match = re.search(r"\b" + key + r"\s*=\s*\{", text)
    assert match, key
    return text[:match.end()] + "\n\t# Thames navigation experiment\n\t" + " ".join(items) + "\n" + text[match.end():]


def build(game: Path, output: Path):
    assert not output.exists() or not any(output.iterdir()), "Use an empty staging directory"
    output.mkdir(parents=True, exist_ok=True)
    written = []

    def write(rel, text, bom=False):
        p = output / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8-sig" if bom else "utf-8", newline="\n")
        written.append(rel)

    def source(rel):
        return (game / rel).read_text(encoding="utf-8-sig")

    md = "in_game/map_data/"
    names_text = source(md + "named_locations/00_default.txt")
    colors = {name: int(c, 16) for name, c in re.findall(r"(\w+)\s*=\s*([0-9a-fA-F]+)", names_text)}
    names = {c: n for n, c in colors.items()}
    for name, (_, _, color) in ZONES.items():
        assert color not in names and name not in colors
    defaults = parse_file(game / md / "default.map")
    groups = {e.key: set(e.value.items) for e in defaults.entries if hasattr(e.value, "items")}
    nonland = set.union(*(groups[k] for k in ["sea_zones", "lakes", "impassable_mountains", "non_ownable"]))
    land_colors = {c for n, c in colors.items() if n not in nonland}
    Image.MAX_IMAGE_PIXELS = None
    original_image = Image.open(game / md / "locations.png").convert("RGB")
    height = original_image.height
    original = encode(np.array(original_image.crop(BOX)))
    after = original.copy()
    river = np.array(Image.open(game / md / "rivers.png").crop(BOX))
    assert river.ndim == 2, "Expected indexed vanilla river raster"
    yy, xx = np.indices(river.shape)
    xx += BOX[0]
    mask = ndimage.binary_dilation((river < 254) & (xx >= 7642) & (xx <= 7700), iterations=2)
    mask &= (xx >= 7642) & (xx <= 7700)
    for name, (lo, hi, c) in ZONES.items():
        after[mask & (xx >= lo) & (xx < hi)] = c
        colors[name] = c
        names[c] = name

    # Repair the tiny fragments cut off from the main land location. Assign them
    # to an adjoining land bank, never join two banks back across the channel.
    repairs = []
    for c in sorted(set(np.unique(original[mask])) & land_colors):
        labels, count = ndimage.label(after == c)
        assert ndimage.label(original == c)[1] == 1
        sizes = np.bincount(labels.ravel()); sizes[0] = 0
        main = int(sizes.argmax())
        for label in range(1, count + 1):
            if label == main:
                continue
            fragment = labels == label
            assert int(fragment.sum()) < 40
            ring = ndimage.binary_dilation(fragment) & ~fragment
            choices = [int(v) for v in after[ring] if int(v) in land_colors and int(v) != c]
            assert choices, f"No adjoining bank for {names[c]} fragment"
            target = max(set(choices), key=choices.count)
            after[fragment] = target
            repairs.append({"from": names[c], "to": names[target], "pixels": int(fragment.sum())})

    report = {"artificial_test": True, "crop": BOX, "fragment_repairs": repairs, "zones": {}, "ports": [], "crossings": [], "locator_moves": []}
    affected = set(int(x) for x in np.unique(original[after != original])) & land_colors
    for c in affected:
        assert ndimage.label(after == c)[1] == 1, names[c]
        assert (after == c).sum() >= 100, names[c]
    for name, (_, _, c) in ZONES.items():
        assert (after == c).sum() >= 100 and ndimage.label(after == c)[1] == 1, name
        report["zones"][name] = {"pixels": int((after == c).sum()), "impassable": name == "pp_thames_barrier"}
    adjacency = pairs(after)
    chain = ["thames", "pp_thames_lower", "pp_thames_upper", "pp_thames_barrier"]
    for a, b in zip(chain, chain[1:]):
        assert tuple(sorted((colors[a], colors[b]))) in adjacency, (a, b)
    assert tuple(sorted((colors["thames"], colors["pp_thames_upper"]))) not in adjacency

    crop_rgb = np.stack(((after >> 16) & 255, (after >> 8) & 255, after & 255), axis=-1).astype(np.uint8)
    original_image.paste(Image.fromarray(crop_rgb), BOX[:2])
    p = output / md / "locations.png"; p.parent.mkdir(parents=True, exist_ok=True)
    original_image.save(p, compress_level=7)
    written.append(md + "locations.png")
    write(md + "named_locations/pp_thames_test.txt", "\n".join(f"{n} = {c:06x}" for n, (_, _, c) in ZONES.items()) + "\n")
    text = insert_list(source(md + "default.map"), "sea_zones", ZONES)
    text = insert_list(text, "impassable_mountains", ["pp_thames_barrier"])
    write(md + "default.map", text)
    hierarchy = "pp_thames_waterways = { pp_thames_subcontinent = { pp_thames_region = { pp_thames_area = {\n pp_thames_province = { pp_thames_lower pp_thames_upper }\n pp_thames_barrier_province = { pp_thames_barrier }\n} } } }\n"
    write(md + "definitions.txt", source(md + "definitions.txt").rstrip() + "\n\n" + hierarchy, bom=True)
    templates = source(md + "location_templates.txt")
    for n in ZONES:
        templates += f"\n{n} = {{ topography = {'ocean_wasteland' if n == 'pp_thames_barrier' else 'narrows'} climate = oceanic }}\n"
    write(md + "location_templates.txt", templates, bom=True)
    write("main_menu/setup/templates/expl_western_europe.txt", insert_list(source("main_menu/setup/templates/expl_western_europe.txt"), "discovered_areas", ["pp_thames_area"]), bom=True)

    # One port per land location, on a cardinally adjacent water pixel. Retain
    # existing assignments where their sea is still adjacent; add new river ports.
    rows = source(md + "ports.csv").splitlines()
    existing = {r.split(";")[0]: r for r in rows[1:] if ";" in r}
    new_ports = {}
    for land in sorted(affected):
        name = names[land]
        neighbours = {b if a == land else a for a, b in adjacency if land in (a, b)}
        candidates = [colors[n] for n in ["pp_thames_lower", "pp_thames_upper"] if colors[n] in neighbours]
        if not candidates:
            continue
        old = existing.get(name)
        if old and name != "london":
            old_sea = old.split(";")[1]
            if colors.get(old_sea) in neighbours:
                # Keep the original port only if its exact pixel survives too.
                fields = old.split(";"); px, py = int(fields[2]), height - int(fields[3])
                if not (BOX[0] <= px < BOX[2] and BOX[1] <= py < BOX[3]) or after[py-BOX[1], px-BOX[0]] == colors[old_sea]:
                    continue
        sea = candidates[0]
        shore = ndimage.binary_dilation(after == land) & (after == sea)
        ys, xs = np.where(shore)
        center = np.array(np.where(after == land)).mean(axis=1)
        k = int(np.argmin((ys-center[0])**2 + (xs-center[1])**2))
        px, py = int(xs[k]+BOX[0]), int(ys[k]+BOX[1])
        new_ports[name] = (names[sea], px, py)
        report["ports"].append({"land": name, "sea": names[sea], "x": px, "y": py})
    assert new_ports["london"][0] == "pp_thames_lower"
    assert {v[0] for v in new_ports.values()} == {"pp_thames_lower", "pp_thames_upper"}
    rows = [r for r in rows if r.split(";")[0] not in new_ports]
    rows += [f"{n};{s};{x};{height-y};x" for n, (s, x, y) in new_ports.items()]
    write(md + "ports.csv", "\n".join(rows) + "\n")

    # Restore every land adjacency severed by carving, with one explicit strait
    # crossing through a single river zone. Coordinates use the game's Y axis.
    lost = {p for p in pairs(original) - adjacency if p[0] in land_colors and p[1] in land_colors}
    cross_candidates = {}
    for y, x in zip(*np.where(np.isin(after, list(affected)))):
        a = int(after[y, x])
        for dy, dx in [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
            through = None
            for distance in range(1, 14):
                by, bx = y + dy*distance, x + dx*distance
                if not (0 <= by < after.shape[0] and 0 <= bx < after.shape[1]): break
                b = int(after[by, bx])
                if b in {z[2] for z in ZONES.values()}:
                    if through is not None and through != b: break
                    through = b
                    continue
                pair = tuple(sorted((a, b)))
                if through is not None and pair in lost:
                    candidate = (distance, names[a], names[b], names[through], x+BOX[0], y+BOX[1], bx+BOX[0], by+BOX[1])
                    if pair not in cross_candidates or candidate < cross_candidates[pair]: cross_candidates[pair] = candidate
                break
    assert set(cross_candidates) == lost, f"Unrestored crossings: {lost-set(cross_candidates)}"
    rows = source(md + "adjacencies.csv").rstrip().splitlines()
    for _, a, b, through, x, y, bx, by in cross_candidates.values():
        rows.append(f"{a};{b};sea;{through};{x};{height-y};{bx};{height-by};Thames test crossing")
        report["crossings"].append({"from": a, "to": b, "through": through})
    write(md + "adjacencies.csv", "\n".join(rows) + "\n")

    # Preserve vanilla ordering/rotations. Move only anchors that were painted
    # out of their own location; supply ship/combat anchors in the new sea zones.
    locator_pattern = re.compile(r"\{\s*id\s*=\s*(\w+)\s+position\s*=\s*\{([^}]+)\}[^{}]*rotation\s*=\s*\{[^}]*\}[^{}]*scale\s*=\s*\{[^}]*\}\s*\}")
    def center(c):
        dist = ndimage.distance_transform_edt(after == c)
        y, x = np.unravel_index(dist.argmax(), dist.shape)
        return float(x+BOX[0]+0.5), float(height-y-BOX[1]-0.5)

    for kind in ["city", "combat", "unit_stack", "dock"]:
        rel = f"in_game/gfx/map/map_objects/generated_map_object_locators_{kind}.txt"
        text = source(rel)
        seen = set()
        def replace(m):
            n = m.group(1); seen.add(n)
            block = m.group(0)
            if kind == "dock":
                if n not in new_ports: return block
                _, x, y = new_ports[n]; pos = (x+0.5, height-y-0.5)
            else:
                if colors.get(n) not in affected: return block
                x, h, z = map(float, m.group(2).split()); px, py = int(x), int(height-z)
                if not (BOX[0] <= px < BOX[2] and BOX[1] <= py < BOX[3]) or after[py-BOX[1], px-BOX[0]] == colors[n]: return block
                pos = center(colors[n])
            report["locator_moves"].append({"kind": kind, "location": n})
            return re.sub(r"position\s*=\s*\{[^}]+\}", f"position={{ {pos[0]:.6f} 0.000000 {pos[1]:.6f} }}", block)
        text = locator_pattern.sub(replace, text)
        additions = []
        if kind in ["combat", "unit_stack"]:
            entries = {n: center(c) for n, (_, _, c) in ZONES.items()}
        elif kind == "dock":
            entries = {n: (x+0.5, height-y-0.5) for n, (_, x, y) in new_ports.items() if n not in seen}
        else: entries = {}
        for n, (x, z) in entries.items():
            additions.append(f"\n\t\t{{ id={n} position={{ {x} 0 {z} }} rotation={{ 0 0 0 1 }} scale={{ 1 1 1 }} }}\n")
        close = text.rfind("}", 0, text.rfind("}"))
        assert close >= 0 and len(seen) > 1000
        write(rel, text[:close] + "".join(additions) + text[close:])

    road_types = [("pp_river_obstructed", 8, 99.0, 15.0), ("pp_river_barrier", 9, 2.0, 15.0), ("pp_river_navigable", 10, -0.5, -0.6)]
    text = "# Positive costs are penalties, not a hard pathfinding prohibition.\n# The barrier's static map classification supplies actual impassability.\n"
    for name, level, movement, market in road_types:
        text += f"""{name} = {{
 level = {level}
 enabled = {{ always = no }}
 movement_cost = {movement}
 market_access = {market}
 pop_movement = 0
 proximity = 0
 build_time_per_unit_distance = 20
 price_per_unit_distance = pp_test_canal_price
 construction_demand = build_gravel_road_demand
 maintenance_demand = maintain_gravel_road_demand
 color = map_paved_road
 spline_style_id = 1
}}
"""
    write("in_game/common/road_types/pp_thames_navigation_test.txt", text)
    # Declare shore connections only from water scopes to adjacent land scopes.
    # The effect has no documented one-way parameter: reverse queries below
    # diagnose engine behavior without creating any reverse road declaration.
    shore_types = {
        "pp_thames_lower": "pp_river_navigable",
        "pp_thames_upper": "pp_river_obstructed",
        "pp_thames_barrier": "pp_river_barrier",
    }
    shore_edges = []
    for water, road in shore_types.items():
        c = colors[water]
        neighbours = {b if a == c else a for a, b in adjacency if c in (a, b)}
        shore_edges.extend((water, names[land], road) for land in sorted(neighbours & land_colors))
    assert shore_edges and len(shore_edges) == len(set(shore_edges))
    report["shore_roads"] = [{"from": w, "to": l, "type": r} for w, l, r in shore_edges]

    def shore_effect(name, edges):
        blocks = [name + " = {\n"]
        for water, land, road in edges:
            blocks.append(f""" location:{water} = {{
  add_road_to = {{ target = location:{land} type = {road} }}
  if = {{
   limit = {{ has_road_of_type_to = {{ target = location:{land} type = road_type:{road} }} }}
   debug_log = "PP_THAMES_SHORE {water} -> {land}: {road} stored"
  }}
  else = {{ debug_log = "PP_THAMES_SHORE {water} -> {land}: {road} NOT stored" }}
 }}
 location:{land} = {{
  if = {{
   limit = {{ has_road_of_type_to = {{ target = location:{water} type = road_type:{road} }} }}
   debug_log = "PP_THAMES_SHORE reverse query {land} -> {water}: present without reverse creation"
  }}
  else = {{ debug_log = "PP_THAMES_SHORE reverse query {land} -> {water}: absent" }}
 }}
""")
        return "".join(blocks) + "}\n"

    text = shore_effect("pp_thames_seed_shore_roads", shore_edges)
    text += shore_effect("pp_thames_upgrade_shore_roads", [
        (water, land, "pp_river_navigable") for water, land, _ in shore_edges if water == "pp_thames_upper"
    ])
    write("in_game/common/scripted_effects/pp_thames_shore_roads.txt", text)
    # Remove the old Dover startup probe by overriding that same test-mod file.
    write("in_game/common/on_action/pp_test_shipping_start.txt", "# Previous Dover/Calais startup probe disabled for the Thames experiment.\n")
    write("in_game/common/on_action/pp_thames_navigation_test.txt", """on_game_start = { on_actions = { pp_thames_navigation_start } }
pp_thames_navigation_start = {
 effect = {
  pp_thames_seed_shore_roads = yes
  location:thames = { add_road_to = { target = location:pp_thames_lower type = pp_river_navigable } }
  location:pp_thames_lower = { add_road_to = { target = location:pp_thames_upper type = pp_river_obstructed } }
  location:pp_thames_upper = { add_road_to = { target = location:pp_thames_barrier type = pp_river_barrier } }
  location:london.owner = { research_advance = advance_type:pp_thames_navigation_engineering }
  location:pp_thames_lower = {
   if = {
    limit = { has_road_of_type_to = { target = location:pp_thames_upper type = road_type:pp_river_obstructed } }
    debug_log = "PP_THAMES_TEST obstructed river connection stored"
   }
   else = { debug_log = "PP_THAMES_TEST ERROR obstructed river connection missing" }
  }
  location:thames = {
   if = {
    limit = { has_road_of_type_to = { target = location:pp_thames_lower type = road_type:pp_river_navigable } }
    debug_log = "PP_THAMES_TEST open river connection stored"
   }
   else = { debug_log = "PP_THAMES_TEST ERROR open river connection missing" }
  }
  location:pp_thames_upper = {
   if = {
    limit = { has_road_of_type_to = { target = location:pp_thames_barrier type = road_type:pp_river_barrier } }
    debug_log = "PP_THAMES_TEST barrier road stored; static sea impassability still needs fleet test"
   }
   else = { debug_log = "PP_THAMES_TEST barrier road refused; inspect static sea impassability with fleet"
   }
  }
 }
}
""")
    write("in_game/common/advances/pp_thames_navigation_test.txt", """pp_thames_navigation_engineering = {
 age = age_1_traditions
 icon = road_building
 research_cost = 0.1
 unlock_building = pp_thames_navigation_works
}
""")
    write("in_game/common/building_types/pp_thames_navigation_test.txt", """pp_thames_navigation_works = {
 is_foreign = no
 max_levels = 1
 pop_type = laborers
 employment_size = 0.001
 category = trade_category
 icon = marketplace
 rural_settlement = yes
 town = yes
 city = yes
 megalopolis = yes
 forbidden_for_estates = yes
 automation_build_allowed = no
 location_potential = { this = location:london }
 allow = { owner = scope:actor }
 price = pp_test_canal_works_price
 build_time = 30
 construction_demand = town_building_construction
 possible_production_methods = { pp_test_canal_upkeep }
 on_built = {
  pp_thames_upgrade_shore_roads = yes
  location:pp_thames_lower = {
   add_road_to = { target = location:pp_thames_upper type = pp_river_navigable }
   if = {
    limit = { has_road_of_type_to = { target = location:pp_thames_upper type = road_type:pp_river_navigable } }
    debug_log = "PP_THAMES_TEST navigation works upgraded river connection"
   }
   else = { debug_log = "PP_THAMES_TEST ERROR upgrade connection missing" }
   if = {
    limit = { has_road_of_type_to = { target = location:pp_thames_upper type = road_type:pp_river_obstructed } }
    debug_log = "PP_THAMES_TEST WARNING original obstructed type still reported after upgrade"
   }
  }
 }
}
""")
    price_keys = ["pp_test_canal_price", "pp_test_lock_canal_price", "pp_test_canal_works_price", "pp_test_canal_locks_price"]
    write("main_menu/common/modifier_type_definitions/pp_test_canal_prices.txt", "".join(
        f"{key}_cost_modifier = {{ color = bad percent = yes game_data = {{ category = country }} }}\n" for key in price_keys
    ))
    loc = {
        **TITLES,
        "pp_thames_waterways": "Thames Waterways", "pp_thames_subcontinent": "Thames Waterways",
        "pp_thames_region": "Thames Waterways", "pp_thames_area": "Thames Waterways",
        "pp_thames_province": "Navigable Thames", "pp_thames_barrier_province": "Upper Thames Barrier",
        "pp_river_navigable": "Navigable River", "pp_river_obstructed": "Obstructed River",
        "pp_river_barrier": "Permanent River Barrier",
        "pp_thames_navigation_engineering": "Thames Navigation Engineering",
        "pp_thames_navigation_engineering_desc": "Allows navigation works at London to improve passage along the upper Thames.",
        "pp_thames_navigation_works": "Thames Navigation Works",
        "pp_thames_navigation_works_desc": "Clears obstructions between the London and Upper Reaches, improving ship movement and market access. The permanent upstream barrier remains impassable.",
    }
    for key, title in zip(price_keys, ["Canal Construction Cost", "Lock Canal Construction Cost", "Navigation Works Cost", "Canal Locks Cost"]):
        loc[key + "_cost_modifier"] = title
    write("in_game/localization/english/pp_thames_navigation_test_l_english.yml", "l_english:\n" + "".join(f' {k}:0 "{v}"\n' for k, v in loc.items()), bom=True)

    # Syntax validation does not substitute for engine loading and fleet testing.
    for rel in written:
        if rel.endswith(".txt") and "named_locations/" not in rel:
            parse_file(output / rel)
    parsed = parse_file(output / md / "default.map")
    actual = {e.key: set(e.value.items) for e in parsed.entries if hasattr(e.value, "items")}
    assert actual["sea_zones"] - groups["sea_zones"] == set(ZONES)
    assert actual["impassable_mountains"] - groups["impassable_mountains"] == {"pp_thames_barrier"}
    report["files"] = list(written)
    report["validation"] = "PASS: syntax, connected zones, minimum areas, preserved land connectivity, edge chain, crossing restoration, port shore pixels"
    write("THAMES_TEST_REPORT.json", json.dumps(report, indent=2) + "\n")
    preview_rgb = crop_rgb.copy()
    for name, color in zip(ZONES, [(65, 70, 85), (195, 125, 35), (0, 165, 220)]):
        preview_rgb[after == colors[name]] = color
    preview = Image.fromarray(preview_rgb).resize((1200, 1120), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(preview)
    for name in ["london", "kingston", "harrow", "windsor", "wycombe", "thames", *ZONES]:
        ys, xs = np.where(after == colors[name])
        if len(xs):
            label = TITLES.get(name, name.title())
            draw.text((int(np.median(xs))*8, int(np.median(ys))*8), label, fill="white", stroke_width=1, stroke_fill="black")
    preview.save(output / "THAMES_TEST_MAP.png")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = tomllib.loads((Path(__file__).resolve().parents[1] / "constructor.load_order.toml").read_text())
    root = config["paths"]["vanilla_root"]
    if re.match(r"^[A-Za-z]:\\", root):
        root = "/mnt/" + root[0].lower() + "/" + root[3:].replace("\\", "/")
    build(Path(root) / "game", args.output)
