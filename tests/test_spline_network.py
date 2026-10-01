import re
import struct
from pathlib import Path

import pytest

from prosper_or_perish_constructor.worldbuilder import spline_network as sn
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "mod/Prosper or Perish (Population Growth & Food Rework)"


def _network(points, strips, connections):
    head = struct.pack("<HHHi", 0xEE, 1, 0x0C, 4) + struct.pack("<HHH", 0x45A, 1, 3)
    head += struct.pack("<HiHiHi", 0x0C, len(points), 0x0C, len(strips), 0x0C, len(connections)) + struct.pack("<H", 4)
    body = struct.pack("<HHH", 0x5F4, 1, 3) + b"".join(sn._point(i, x, y) for i, x, y in points) + struct.pack("<H", 4)
    body += struct.pack("<HHH", 0x5F5, 1, 3) + b"".join(sn._strip(i, p) for i, p in strips) + struct.pack("<H", 4)
    body += struct.pack("<HHH", 0x5F6, 1, 3) + b"".join(sn._connection(k, s) for k, s in connections) + struct.pack("<H", 4)
    return head + body


def _read(data):
    counts = struct.unpack_from("<xxixxixxi", data, 16)
    start = 42
    ids = [struct.unpack_from("<I", data, start + i * 34 + 8)[0] for i in range(counts[0])]
    return counts, ids


VANILLA = _network(
    points=[(1, 0.0, 0.0), (2, 10.0, 0.0), (sn.CONTROL | 1, 5.0, 0.0)],
    strips=[(0, [1, sn.CONTROL | 1, 2])],
    connections=[(sn.connection_key(2, 1), [0])],
)


def test_navigation_pairs_get_straight_strips_and_sorted_anchors():
    order = ["a", "b", "lake", "nav"]
    positions = {"a": (0.0, 0.0), "b": (10.0, 0.0), "lake": (0.0, 10.0), "nav": (0.0, 20.0)}
    data, report = sn.extend(VANILLA, order, positions, [("nav", "lake"), ("lake", "nav"), ("a", "b")])

    assert report == {"anchors_added": 2, "control_points_added": 1, "strips_added": 1, "connections_added": 1}
    counts, ids = _read(data)
    assert counts == (6, 2, 2)
    # new anchors 3 and 4 sit before the control points; new control ids continue past vanilla's
    assert ids == [1, 2, 3, 4, sn.CONTROL | 1, sn.CONTROL | 2]
    assert data.endswith(sn._connection(sn.connection_key(4, 3), [1 << 8]) + struct.pack("<H", 4))
    assert sn._strip(1 << 8, [4, sn.CONTROL | 2, 3]) in data


def test_a_pair_inside_the_vanilla_id_range_is_merged_in_sorted_order():
    vanilla = _network(
        points=[(1, 0.0, 0.0), (2, 10.0, 0.0), (3, 0.0, 10.0), (4, 10.0, 10.0), (sn.CONTROL | 1, 5.0, 0.0), (sn.CONTROL | 2, 5.0, 10.0)],
        strips=[(0, [1, sn.CONTROL | 1, 2]), (1 << 8, [3, sn.CONTROL | 2, 4])],
        connections=[(sn.connection_key(2, 1), [0]), (sn.connection_key(4, 3), [1 << 8])],
    )
    order = ["a", "b", "c", "d"]
    positions = {"a": (0.0, 0.0), "b": (10.0, 0.0), "c": (0.0, 10.0), "d": (10.0, 10.0)}
    added = []
    data, report = sn.extend(vanilla, order, positions, [("c", "a"), ("a", "b")], added)
    assert added == [("c", "a")] and report["connections_added"] == 1
    connections = sn.read_connections(data)
    assert list(connections) == sorted(connections) == [sn.connection_key(2, 1), sn.connection_key(3, 1), sn.connection_key(4, 3)]
    assert connections[sn.connection_key(3, 1)] == {1, 3}


def test_a_pair_already_in_the_network_needs_no_locator():
    data, report = sn.extend(VANILLA, ["a", "b"], {}, [("b", "a")])
    assert data == VANILLA and report["connections_added"] == 0


def test_unknown_location_is_an_error():
    with pytest.raises(ValueError, match="without index or locator"):
        sn.extend(VANILLA, ["a", "b"], {"a": (0.0, 0.0), "b": (1.0, 0.0)}, [("a", "ghost")])


def test_location_order_follows_definitions_leaves(tmp_path):
    path = tmp_path / "definitions.txt"
    path.write_text("europe = { north = { sweden = { stockholm norrtalje } # x\n lake_area = { malaren } } }\n")
    assert sn.location_order(path) == ["stockholm", "norrtalje", "malaren"]


def test_location_order_skips_scalar_settings(tmp_path):
    # EU5 1.4 puts `not_eligible_for_dynamic_country_name = yes` on areas and provinces; counting `yes` as a
    # location shifted every later anchor index and the engine found none of the navigation strips.
    path = tmp_path / "definitions.txt"
    path.write_text(
        "europe = { finland_area = { not_eligible_for_dynamic_country_name = yes\n"
        " tavastland = { not_eligible_for_dynamic_country_name = yes hollola lohja } }\n"
        " other = { x = 0.5 abo } }\n"
    )
    assert sn.location_order(path) == ["hollola", "lohja", "abo"]


def test_order_check_rejects_non_locations():
    sn.check_order(["a", "b"], {"a", "b"})
    with pytest.raises(ValueError, match="no location: yes"):
        sn.check_order(["a", "yes", "b"], {"a", "b"})
    with pytest.raises(ValueError, match="missing"):
        sn.check_order(["a"], {"a", "b"})


def test_read_connections_returns_strip_ends():
    data, _ = sn.extend(VANILLA, ["a", "b", "lake", "nav"], {"a": (0.0, 0.0), "b": (10.0, 0.0), "lake": (0.0, 10.0), "nav": (0.0, 20.0)}, [("nav", "lake")])
    assert sn.read_connections(data) == {sn.connection_key(2, 1): {1, 2}, sn.connection_key(4, 3): {3, 4}}


ROAD = re.compile(r"location:([A-Za-z0-9_\-]+)\s*=\s*\{\s*add_road_to\s*=\s*\{\s*target\s*=\s*location:([A-Za-z0-9_\-]+)")


def test_shipped_network_has_a_strip_for_every_road():
    """Every road the mod or the vanilla setup creates has a type-0 strip between the right anchors.

    The engine looks a road's strip up by the two locations' 1-based index in ``definitions.txt`` and logs
    ``Could not find spline network strip`` on every road redraw when it is missing (EU5 1.4: ~600 lines a second).
    """
    network = MOD / sn.RELATIVE_PATH
    if not network.is_file():
        pytest.skip("mod not built")
    order = sn.location_order(MOD / "in_game/map_data/definitions.txt")
    sn.check_order(order, sn.template_locations(MOD / "in_game/map_data/location_templates.txt"))
    index = {tag: i for i, tag in enumerate(order, 1)}
    pairs = set()
    for path in (MOD / "in_game/common").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if "add_road_to" in text:
            pairs.update(ROAD.findall(text))
    assert len(pairs) > 3000, "navigation roads not found in the built mod"
    root = vanilla_root(REPO, REPO / "constructor.toml")
    vanilla = root / "game/main_menu/setup/1337/09_roads.txt"
    if vanilla.is_file():
        text = re.sub(r"#[^\n]*", "", vanilla.read_text(encoding="utf-8-sig"))
        pairs.update(re.findall(r"([A-Za-z0-9_\-]+)\s*=\s*([A-Za-z0-9_\-]+)", text.split("{", 1)[1]))
        # every land adjacency of the mod's map: a player or the AI may build a road there later
        pairs.update(sn.land_pairs(MOD, root, REPO / "artifacts/data/worldbuilder/land_adjacency.json"))
    connections = sn.read_connections(network.read_bytes())
    unknown = sorted({t for pair in pairs for t in pair if t not in index})
    assert unknown == []
    missing = sorted(
        (a, b) for a, b in pairs if a != b and not {index[a], index[b]} <= connections.get(sn.connection_key(index[a], index[b]), set())
    )
    assert missing == [], f"{len(missing)} roads without a strip, e.g. {missing[:5]}"
