"""Export River Exporter v2 variables using the existing EU5 save parser.

Run with the constructor's uv environment. This is acquisition only; the
agriculture model consumes the resulting JSON without a constructor dependency.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from eu5gameparser.savegame.exporter import (
    _document_value, _extract_top_level_sections, _location_slugs, is_text_save,
)
from eu5gameparser.savegame.references import _first_block, _iter_id_blocks


def export(save: Path, output: Path):
    if not is_text_save(save):
        raise ValueError("Load the diagnostic save with -debug_mode and save it as text first.")
    text = save.read_text(encoding="utf-8-sig")
    sections = _extract_top_level_sections(text.split("\n", 1)[1], frozenset({"metadata", "locations"}))
    names = _location_slugs(_document_value("metadata", sections["metadata"], save))
    body = _first_block(sections["locations"][1:-1], "locations")
    if body is None:
        raise ValueError("Missing location database")
    rows = []
    pattern = re.compile(r'flag=(river_exporter_\w+)\s+data=\{\s+type=value\s+(?:identity=(-?\d+)\s+)?\}')
    for location_id, block in _iter_id_blocks(body):
        values = {m[1]: int(m[2] or 0) / 100000 for m in pattern.finditer(block)}
        rows.append({"location_tag": names[location_id], "save_location_id": location_id, **values})
    if len(rows) != len(names):
        raise ValueError("Save metadata and location database coverage differ")
    payload = {
        "source": {"save_name": save.name, "save_sha256": hashlib.sha256(save.read_bytes()).hexdigest(),
                   "game_version": re.search(r'\bversion="([^"]+)"', sections["metadata"])[1],
                   "date": re.search(r'\bdate=([^\s]+)', sections["metadata"])[1],
                   "parser": "eu5gameparser.savegame", "exporter_schema": 2,
                   "license": "Derived local EU5 game data; do not redistribute the source save."},
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Exported {len(rows)} location records to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    export(args.save, args.output)
