from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted"
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"
MOD_ICON_ROOT = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "in_game"
    / "gfx"
    / "interface"
    / "icons"
    / "buildings"
)


def _enabled_blueprints() -> dict[str, dict[str, Any]]:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw_enabled = manifest["enabled"]
    assert isinstance(raw_enabled, list)

    blueprints: dict[str, dict[str, Any]] = {}
    for relative in raw_enabled:
        path = BLUEPRINT_ROOT / relative
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        raw["_path"] = path
        blueprints[raw["building"]["key"]] = raw
    return blueprints


def _icon_source(raw: dict[str, Any]) -> Path | None:
    icon = raw.get("icon")
    if not isinstance(icon, dict):
        return None
    source = icon.get("source_png") or icon.get("source_dds")
    if not isinstance(source, str):
        return None
    return (raw["_path"].parent / source).resolve()


def test_upgrade_buildings_use_unique_pipeline_icons() -> None:
    blueprints = _enabled_blueprints()
    outputs: dict[str, str] = {}

    for key, raw in blueprints.items():
        icon = raw.get("icon")
        if not isinstance(icon, dict):
            continue
        output = icon.get("output_dds")
        assert isinstance(output, str), f"{key} must declare icon.output_dds"
        assert output not in outputs, f"{key} and {outputs[output]} both output {output}"
        outputs[output] = key

    for key, raw in blueprints.items():
        chain = raw.get("upgrade_chain")
        if not isinstance(chain, dict) or chain.get("tier", 0) <= 0:
            continue

        previous_key = chain.get("previous")
        assert isinstance(previous_key, str), f"{key} upgrade_chain.previous must be set"
        assert previous_key in blueprints, f"{key} previous tier {previous_key} is not enabled"

        source = _icon_source(raw)
        previous_source = _icon_source(blueprints[previous_key])
        assert source is not None, f"{key} must declare its own icon source"
        if previous_source is not None:
            assert source != previous_source, f"{key} reuses previous-tier icon source {source}"

        output = raw["icon"]["output_dds"]
        previous_icon = blueprints[previous_key].get("icon")
        if isinstance(previous_icon, dict):
            previous_output = previous_icon["output_dds"]
            assert output != previous_output, f"{key} reuses previous-tier icon output {output}"


def test_enabled_building_icons_do_not_render_duplicate_hashes() -> None:
    by_hash: dict[str, list[str]] = defaultdict(list)

    for key, raw in _enabled_blueprints().items():
        icon = raw.get("icon")
        if not isinstance(icon, dict):
            continue
        output = icon.get("output_dds")
        if not isinstance(output, str):
            continue

        icon_path = MOD_ICON_ROOT / output
        assert icon_path.exists(), f"{key} generated icon is missing: {icon_path}"
        digest = hashlib.sha256(icon_path.read_bytes()).hexdigest()
        by_hash[digest].append(f"{key}:{output}")

    duplicates = {digest: names for digest, names in by_hash.items() if len(names) > 1}
    assert not duplicates, f"Duplicate rendered building icons: {duplicates}"
