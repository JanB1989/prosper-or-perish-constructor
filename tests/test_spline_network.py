import struct

import pytest

from prosper_or_perish_constructor.worldbuilder import spline_network as sn


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


def test_unknown_location_is_an_error():
    with pytest.raises(ValueError, match="without index or locator"):
        sn.extend(VANILLA, ["a", "b"], {"a": (0.0, 0.0), "b": (1.0, 0.0)}, [("a", "ghost")])


def test_location_order_follows_definitions_leaves():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "definitions.txt"
        path.write_text("europe = { north = { sweden = { stockholm norrtalje } # x\n lake_area = { malaren } } }\n")
        assert sn.location_order(path) == ["stockholm", "norrtalje", "malaren"]
