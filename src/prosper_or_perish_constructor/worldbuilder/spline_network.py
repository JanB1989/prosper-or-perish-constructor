"""Extend the vanilla road spline network with strips for the navigation roads.

The engine draws every road from pre-baked strips in ``spline_network.splnet`` (binary Clausewitz).
A road between two anchors without a strip logs ``Could not find spline network strip`` on every
road redraw, which for the ~8,000 navigation connections floods ``error.log`` in bursts. This module
copies the vanilla file and appends one straight strip per navigation connection.

Layout (reverse-engineered from EU5 1.3): a header with the three section counts, then

* points ``{ id = u32  pos = { f32 f32 } }`` sorted by id: anchors use the 1-based location index in
  ``definitions.txt`` order, control points carry ``CONTROL`` in the id; fixed 34-byte entries;
* strips ``{ id = u64 (index << 8 | spline type)  points = { u32 ... } }`` with contiguous indices;
* connections ``{ id = u64 (a << 35 | b << 6 | spline type), a > b  strips = { u64 ... } }`` sorted by id.
"""

from __future__ import annotations

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
    """Location tags in the engine's index order (the leaves of ``definitions.txt``)."""
    text = re.sub(r"#[^\n]*", "", definitions.read_text(encoding="utf-8-sig"))
    tokens = re.findall(r"[A-Za-z0-9_\-]+|=|\{|\}", text)
    return [t for i, t in enumerate(tokens) if t not in "={}" and not (i + 1 < len(tokens) and tokens[i + 1] == "=")]


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


def extend(vanilla: bytes, order: list[str], positions: dict[str, tuple[float, float]], pairs: list[tuple[str, str]]) -> tuple[bytes, dict[str, int]]:
    """Return the vanilla network plus one straight strip for every pair it does not already connect."""
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
    existing_keys = set()
    offset = connections_start
    key_head = struct.pack("<HHHH", _OPEN, _KEY_ID, _EQ, _U64)
    while True:
        offset = vanilla.find(key_head, offset, connections_end)
        if offset < 0:
            break
        existing_keys.add(struct.unpack_from("<Q", vanilla, offset + 8)[0])
        offset += 16
    if len(existing_keys) != n_connections:
        raise ValueError("could not read every spline network connection")
    last_key = max(existing_keys)

    index = {tag: i for i, tag in enumerate(order, 1)}
    new_anchors: dict[int, bytes] = {}
    new_controls: list[bytes] = []
    strips: list[bytes] = []
    connections: dict[int, bytes] = {}
    missing: set[str] = set()
    for a_tag, b_tag in pairs:
        if a_tag not in index or b_tag not in index or a_tag not in positions or b_tag not in positions:
            missing.update(t for t in (a_tag, b_tag) if t not in index or t not in positions)
            continue
        a, b = index[a_tag], index[b_tag]
        key = connection_key(a, b)
        if a == b or key in existing_keys or key in connections:
            continue
        if key < last_key:
            raise ValueError(f"navigation connection {a_tag}-{b_tag} would sort inside the vanilla network")
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

    counts = struct.pack("<HiHiHi", 0x0C, n_points + len(new_anchors) + len(new_controls), 0x0C, n_strips + len(strips), 0x0C, n_connections + len(connections))
    out = b"".join([
        vanilla[: _COUNTS_OFFSET - 2], counts, vanilla[_COUNTS_OFFSET + 16 : points_start],
        bytes(anchor_block), vanilla[cursor:points_end], *new_controls,
        vanilla[points_end:strips_end], *strips,
        vanilla[strips_end:connections_end], *(connections[k] for k in sorted(connections)),
        vanilla[connections_end:],
    ])
    return out, {"anchors_added": len(new_anchors), "control_points_added": len(new_controls), "strips_added": len(strips), "connections_added": len(connections)}


def write(mod_root: Path, vanilla_root: Path, pairs: list[tuple[str, str]]) -> dict[str, int]:
    game = vanilla_root / "game" if (vanilla_root / "game" / "in_game").is_dir() else vanilla_root
    order = location_order(mod_root / "in_game/map_data/definitions.txt")
    positions = locator_positions(mod_root / "in_game/gfx/map/map_objects/generated_map_object_locators_unit_stack.txt")
    data, report = extend((game / RELATIVE_PATH).read_bytes(), order, positions, pairs)
    target = mod_root / RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return report
