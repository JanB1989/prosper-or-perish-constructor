"""Extend the vanilla road spline network with strips for the navigation roads.

The engine draws every road from pre-baked strips in ``spline_network.splnet`` (binary Clausewitz).
A road between two anchors without a strip logs ``Could not find spline network strip`` on every
road redraw, which for the ~8,000 navigation connections floods ``error.log`` in bursts. This module
copies the vanilla file and appends one straight strip per navigation connection.

Layout (reverse-engineered from EU5 1.3): a header with the three section counts, then

* points ``{ id = u32  pos = { f32 f32 } }`` sorted by id: anchors use the 1-based location index in
  ``definitions.txt`` order (unchanged in EU5 1.4: every 1337 setup road has its strip under that order),
  control points carry ``CONTROL`` in the id; fixed 34-byte entries;
* strips ``{ id = u64 (index << 8 | spline type)  points = { u32 ... } }`` with contiguous indices;
* connections ``{ id = u64 (a << 35 | b << 6 | spline type), a > b  strips = { u64 ... } }`` sorted by id.
"""

from __future__ import annotations

import json
import math
import re
import struct
from pathlib import Path

RELATIVE_PATH = Path("in_game/gfx/map/spline_network/spline_network.splnet")
CONTROL = 0x10000000
ROAD_TYPE = 0  # spline type ``road1``: every road type draws with it
STEP = 5.0  # control point spacing in map pixels, as in the vanilla strips

_KEY_POINTS, _KEY_STRIPS, _KEY_CONNECTIONS = 0x5F4, 0x5F5, 0x5F6
_KEY_ID, _KEY_POS, _KEY_STRIP_POINTS = 0x0B, 0x4C, 0x5F7
_EQ, _OPEN, _CLOSE, _U32, _F32, _U64 = 0x01, 0x03, 0x04, 0x14, 0x0D, 0x29C
_POINT_SIZE = 34
_COUNTS_OFFSET = 18  # header: version = 4, counts = { i32 i32 i32 }


def location_order(definitions: Path) -> list[str]:
    """Location tags in the engine's index order (the leaves of ``definitions.txt``).

    Scalar settings inside a block (EU5 1.4: ``not_eligible_for_dynamic_country_name = yes`` on 551
    areas and provinces) are skipped with their value; counting ``yes`` as a location shifted every
    later index and put every navigation strip on the wrong anchors.
    """
    text = re.sub(r"#[^\n]*", "", definitions.read_text(encoding="utf-8-sig"))
    tokens = re.findall(r"[A-Za-z0-9_\-.]+|=|\{|\}", text)
    order: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in "{}":
            i += 1
        elif i + 1 < len(tokens) and tokens[i + 1] == "=":
            i += 2 if i + 2 < len(tokens) and tokens[i + 2] == "{" else 3
        else:
            order.append(token)
            i += 1
    return order


def template_locations(templates: Path) -> set[str]:
    """Every location that has an entry in ``location_templates.txt``."""
    return set(re.findall(r"^\s*([A-Za-z0-9_\-]+)\s*=", templates.read_text(encoding="utf-8-sig"), re.M))


def check_order(order: list[str], locations: set[str]) -> None:
    """The index order must hold each location once and nothing else, or every anchor id is off."""
    unknown = sorted({t for t in order if t not in locations})
    if unknown:
        raise ValueError("definitions.txt leaves that are no location: " + ", ".join(unknown[:10]))
    if len(set(order)) != len(order):
        raise ValueError("definitions.txt lists a location twice")
    missing = sorted(locations - set(order))
    if missing:
        raise ValueError("locations missing from definitions.txt: " + ", ".join(missing[:10]))


def locator_positions(locators: Path) -> dict[str, tuple[float, float]]:
    """Map position (x, z) of each location's unit stack locator, the frame the strips use."""
    pattern = re.compile(r"id=([A-Za-z0-9_\-]+)\s*position=\{\s*([-\d.]+)\s+[-\d.]+\s+([-\d.]+)")
    return {m.group(1): (float(m.group(2)), float(m.group(3))) for m in pattern.finditer(locators.read_text(encoding="utf-8-sig"))}


def _point(point_id: int, x: float, y: float) -> bytes:
    return struct.pack("<HHHHIHHHHfHfHH", _OPEN, _KEY_ID, _EQ, _U32, point_id, _KEY_POS, _EQ, _OPEN, _F32, x, _F32, y, _CLOSE, _CLOSE)


def _strip(strip_id: int, points: list[int]) -> bytes:
    body = b"".join(struct.pack("<HI", _U32, p) for p in points)
    return struct.pack("<HHHHQHHH", _OPEN, _KEY_ID, _EQ, _U64, strip_id, _KEY_STRIP_POINTS, _EQ, _OPEN) + body + struct.pack("<HH", _CLOSE, _CLOSE)


def _connection(key: int, strips: list[int]) -> bytes:
    body = b"".join(struct.pack("<HQ", _U64, s) for s in strips)
    return struct.pack("<HHHHQHHH", _OPEN, _KEY_ID, _EQ, _U64, key, _KEY_STRIPS, _EQ, _OPEN) + body + struct.pack("<HH", _CLOSE, _CLOSE)


def connection_key(a: int, b: int) -> int:
    a, b = max(a, b), min(a, b)
    return (a << 35) | (b << 6) | ROAD_TYPE


def extend(vanilla: bytes, order: list[str], positions: dict[str, tuple[float, float]], pairs: list[tuple[str, str]],
           added: list[tuple[str, str]] | None = None) -> tuple[bytes, dict[str, int]]:
    """Return the vanilla network plus one straight strip for every pair it does not already connect.

    New connections are merged into the sorted connection list; ``added`` (if given) collects the pairs that got one.
    """
    n_points, n_strips, n_connections = struct.unpack_from("<xxixxixxi", vanilla, _COUNTS_OFFSET - 2)
    points_start = _COUNTS_OFFSET + 18 + 6
    if vanilla[points_start - 6 : points_start] != struct.pack("<HHH", _KEY_POINTS, _EQ, _OPEN):
        raise ValueError("unexpected spline network header")
    points_end = points_start + n_points * _POINT_SIZE
    strips_start = points_end + 2 + 6
    if vanilla[points_end : strips_start] != struct.pack("<HHHH", _CLOSE, _KEY_STRIPS, _EQ, _OPEN):
        raise ValueError("unexpected spline network point section")
    connections_head = struct.pack("<HHHH", _CLOSE, _KEY_CONNECTIONS, _EQ, _OPEN)
    strips_end = vanilla.index(connections_head, strips_start)
    connections_start = strips_end + len(connections_head)
    connections_end = len(vanilla) - 2
    if vanilla[connections_end:] != struct.pack("<H", _CLOSE):
        raise ValueError("unexpected spline network end")

    point_ids = [struct.unpack_from("<I", vanilla, points_start + i * _POINT_SIZE + 8)[0] for i in range(n_points)]
    existing_points = set(point_ids)
    next_control = max(p & ~CONTROL for p in point_ids if p & CONTROL) + 1
    entries: list[tuple[int, int]] = []  # (key, start offset) of every vanilla connection, in file order
    offset = connections_start
    key_head = struct.pack("<HHHH", _OPEN, _KEY_ID, _EQ, _U64)
    while True:
        offset = vanilla.find(key_head, offset, connections_end)
        if offset < 0:
            break
        entries.append((struct.unpack_from("<Q", vanilla, offset + 8)[0], offset))
        offset += 16
    existing_keys = {key for key, _ in entries}
    if len(existing_keys) != n_connections or len(entries) != n_connections:
        raise ValueError("could not read every spline network connection")
    if any(entries[i][0] >= entries[i + 1][0] for i in range(len(entries) - 1)):
        raise ValueError("vanilla spline network connections are not sorted by id")

    index = {tag: i for i, tag in enumerate(order, 1)}
    new_anchors: dict[int, bytes] = {}
    new_controls: list[bytes] = []
    strips: list[bytes] = []
    connections: dict[int, bytes] = {}
    missing: set[str] = set()
    for a_tag, b_tag in pairs:
        if a_tag not in index or b_tag not in index:
            missing.update(t for t in (a_tag, b_tag) if t not in index)
            continue
        a, b = index[a_tag], index[b_tag]
        key = connection_key(a, b)
        if a == b or key in existing_keys or key in connections:
            continue
        if a_tag not in positions or b_tag not in positions:
            missing.update(t for t in (a_tag, b_tag) if t not in positions)
            continue
        if added is not None:
            added.append((a_tag, b_tag))
        for anchor, tag in ((a, a_tag), (b, b_tag)):
            if anchor not in existing_points and anchor not in new_anchors:
                new_anchors[anchor] = _point(anchor, *positions[tag])
        (ax, ay), (bx, by) = positions[a_tag], positions[b_tag]
        steps = max(1, math.ceil(math.dist((ax, ay), (bx, by)) / STEP))
        chain = [a]
        for s in range(1, steps):
            t = s / steps
            new_controls.append(_point(CONTROL | next_control, ax + (bx - ax) * t, ay + (by - ay) * t))
            chain.append(CONTROL | next_control)
            next_control += 1
        chain.append(b)
        strip_id = ((n_strips + len(strips)) << 8) | ROAD_TYPE
        strips.append(_strip(strip_id, chain))
        connections[key] = _connection(key, [strip_id])
    if missing:
        raise ValueError("navigation locations without index or locator: " + ", ".join(sorted(missing)[:10]))

    # anchors go before the control points in id order; control ids continue past vanilla's
    first_control = next((i for i, p in enumerate(point_ids) if p & CONTROL), n_points)
    anchor_block = bytearray()
    merged = sorted(new_anchors.items())
    for i in range(first_control):
        while merged and merged[0][0] < point_ids[i]:
            anchor_block += merged.pop(0)[1]
        anchor_block += vanilla[points_start + i * _POINT_SIZE : points_start + (i + 1) * _POINT_SIZE]
    cursor = points_start + first_control * _POINT_SIZE
    anchor_block += b"".join(p for _, p in merged)

    # connections stay sorted by id: each new one goes before the first vanilla connection with a larger id
    connection_parts: list[bytes] = [vanilla[strips_end:connections_start]]
    spans = [(key, start, entries[i + 1][1] if i + 1 < len(entries) else connections_end) for i, (key, start) in enumerate(entries)]
    pending = sorted(connections)
    for key, start, end in spans:
        while pending and pending[0] < key:
            connection_parts.append(connections[pending.pop(0)])
        connection_parts.append(vanilla[start:end])
    connection_parts += [connections[k] for k in pending]

    counts = struct.pack("<HiHiHi", 0x0C, n_points + len(new_anchors) + len(new_controls), 0x0C, n_strips + len(strips), 0x0C, n_connections + len(connections))
    out = b"".join([
        vanilla[: _COUNTS_OFFSET - 2], counts, vanilla[_COUNTS_OFFSET + 16 : points_start],
        bytes(anchor_block), vanilla[cursor:points_end], *new_controls,
        vanilla[points_end:strips_end], *strips,
        *connection_parts,
        vanilla[connections_end:],
    ])
    return out, {"anchors_added": len(new_anchors), "control_points_added": len(new_controls), "strips_added": len(strips), "connections_added": len(connections)}


def read_connections(data: bytes) -> dict[int, set[int]]:
    """Connection key -> the anchors its strips end on (to check a network the way the engine looks it up)."""
    head = struct.pack("<HHHH", _OPEN, _KEY_ID, _EQ, _U64)
    connections_head = struct.pack("<HHHH", _CLOSE, _KEY_CONNECTIONS, _EQ, _OPEN)
    connections_start = data.index(connections_head)
    ends: dict[int, tuple[int, int]] = {}
    offset = 0
    while (offset := data.find(head, offset, connections_start)) >= 0:
        strip_id = struct.unpack_from("<Q", data, offset + 8)[0]
        cursor = offset + 22
        first = struct.unpack_from("<I", data, cursor + 2)[0]
        while struct.unpack_from("<H", data, cursor)[0] == _U32:
            last = struct.unpack_from("<I", data, cursor + 2)[0]
            cursor += 6
        ends[strip_id] = (first, last)
        offset = cursor
    result: dict[int, set[int]] = {}
    offset = connections_start
    while (offset := data.find(head, offset)) >= 0:
        key = struct.unpack_from("<Q", data, offset + 8)[0]
        cursor = offset + 22
        anchors: set[int] = set()
        while struct.unpack_from("<H", data, cursor)[0] == _U64:
            anchors.update(ends[struct.unpack_from("<Q", data, cursor + 2)[0]])
            cursor += 10
        result[key] = anchors
        offset = cursor
    return result


def land_pairs(mod_root: Path, vanilla_root: Path, cache: Path | None = None) -> list[tuple[str, str]]:
    """Adjacent location pairs of the mod's map that a road can join: neither side is a sea zone, lake or impassable
    mountain. Vanilla has a strip for every such pair of its own map (50,754 in EU5 1.4); where the World Builder map
    makes two land locations touch that did not before, a road built there later would find none."""
    from . import coast

    paths = coast._inputs(Path(mod_root), Path(vanilla_root))
    key = coast._fingerprint(paths)
    if cache is not None and cache.is_file():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("fingerprint") == key:
            return [tuple(p) for p in data["pairs"]]
    default_map = paths["default_map"].read_text(encoding="utf-8-sig", errors="replace")
    blocked = {t for name in ("sea_zones", "lakes", "impassable_mountains") for t in coast._block_tokens(default_map, name)}
    colors = coast._named_colors([paths["vanilla_names"], paths["mod_names"]])
    result = set()
    for a, b in coast._adjacent_pairs(paths["png"]):
        ta, tb = colors.get(a), colors.get(b)
        if ta and tb and ta not in blocked and tb not in blocked:
            result.add((min(ta, tb), max(ta, tb)))
    pairs = sorted(result)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"fingerprint": key, "pairs": pairs}) + "\n", encoding="utf-8")
    return pairs


def write(mod_root: Path, vanilla_root: Path, pairs: list[tuple[str, str]], land_cache: Path | None = None) -> dict:
    """The vanilla network plus a strip for every navigation connection (``pairs``) and every land adjacency of the
    mod's map that vanilla has none for."""
    game = vanilla_root / "game" if (vanilla_root / "game" / "in_game").is_dir() else vanilla_root
    order = location_order(mod_root / "in_game/map_data/definitions.txt")
    check_order(order, template_locations(mod_root / "in_game/map_data/location_templates.txt"))
    positions = locator_positions(mod_root / "in_game/gfx/map/map_objects/generated_map_object_locators_unit_stack.txt")
    land = land_pairs(mod_root, vanilla_root, land_cache)
    added: list[tuple[str, str]] = []
    data, report = extend((game / RELATIVE_PATH).read_bytes(), order, positions, list(pairs) + land, added)
    navigation = {tuple(sorted(p)) for p in pairs}
    report["land_pairs"] = len(land)
    report["land_strips_added"] = sorted(f"{a}-{b}" for a, b in added if tuple(sorted((a, b))) not in navigation)
    target = mod_root / RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return report
