from __future__ import annotations

import re
from pathlib import Path

import yaml
from eu5gameparser.domain.eu5 import load_eu5_data


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"
BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted"
LOAD_ORDER_PATH = ROOT / "constructor.load_order.toml"

METHOD_RE = re.compile(r"^\s*(?P<method>pp_[A-Za-z0-9_]*_base_[A-Za-z0-9_]+)\s*=\s*\{", re.M)
PRODUCED_RE = re.compile(r"^\s*produced\s*=\s*(?P<good>[A-Za-z0-9_]+)\s*$", re.M)


def main() -> None:
    raw_materials = _raw_material_goods()
    base_methods = _base_production_methods()
    covered_goods = set(base_methods)
    missing = [good for good in raw_materials if good not in covered_goods]

    print(f"raw_material goods: {len(raw_materials)}")
    print(f"raw_material goods with base production methods: {len(raw_materials) - len(missing)}")
    print(f"raw_material goods missing base production methods: {len(missing)}")
    print()
    for good in missing:
        print(good)

    print()
    print("covered raw_material goods:")
    for good in raw_materials:
        methods = base_methods.get(good, [])
        if methods:
            method_list = ", ".join(f"{method} ({path})" for method, path in methods)
            print(f"{good}: {method_list}")


def _raw_material_goods() -> list[str]:
    data = load_eu5_data(profile="constructor", load_order_path=LOAD_ORDER_PATH)
    return (
        data.goods.filter(data.goods["category"] == "raw_material")
        .select("name")
        .to_series()
        .to_list()
    )


def _base_production_methods() -> dict[str, list[tuple[str, str]]]:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    methods_by_good: dict[str, list[tuple[str, str]]] = {}
    for entry in manifest["enabled"]:
        blueprint_path = BLUEPRINT_ROOT / entry
        raw = yaml.safe_load(blueprint_path.read_text(encoding="utf-8-sig"))
        body = raw.get("building", {}).get("body", "")
        if not isinstance(body, str):
            continue
        for method, block in _method_blocks(body):
            produced_match = PRODUCED_RE.search(block)
            if produced_match is None:
                continue
            good = produced_match.group("good")
            methods_by_good.setdefault(good, []).append((method, str(blueprint_path.relative_to(ROOT))))
    return methods_by_good


def _method_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for match in METHOD_RE.finditer(text):
        start = match.end()
        depth = 1
        index = start
        while index < len(text) and depth:
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            index += 1
        blocks.append((match.group("method"), text[start : index - 1]))
    return blocks


if __name__ == "__main__":
    main()
