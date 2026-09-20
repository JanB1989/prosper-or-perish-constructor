"""Load and validate a World Builder handover directory (see EU5WorldBuilder handover.py).

All people values are physical people; 1 game capacity unit = 1,000 people.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

PEOPLE_PER_UNIT = 1000.0
REQUIRED_FILES = (
    "contract.json",
    "attribute_rows.csv",
    "building_types.csv",
    "location_buildings.csv",
    "location_targets.csv",
    "location_attributes.csv",
    "goods_floor.csv",
)


@dataclass(frozen=True)
class WorldBuilderConfig:
    """``[worldbuilder]`` section of constructor.toml."""

    handover: Path
    geography_export: Path
    building_map: dict[str, str]
    farm_land: dict[str, dict[str, float]]
    farm_classes: dict[str, list[str]]
    level_scale: dict[str, float]
    level_limit: int
    goods_floor: float
    overpopulation_peasant_unrest: float
    sync_geography: bool
    raw: dict[str, Any] = field(default_factory=dict)
    niche: dict[str, dict[str, Any]] = field(default_factory=dict)
    compat_files: list[str] = field(default_factory=list)


def load_config(repo: Path, project: Path) -> WorldBuilderConfig:
    raw = tomllib.loads(project.read_text(encoding="utf-8"))
    section = raw.get("worldbuilder")
    if not isinstance(section, dict):
        raise ValueError(f"{project}: missing [worldbuilder] section")

    def path_of(key: str) -> Path:
        value = section.get(key)
        if not value:
            raise ValueError(f"{project}: [worldbuilder].{key} is required")
        path = Path(str(value)).expanduser()
        return path if path.is_absolute() else (repo / path).resolve()

    buildings = section.get("buildings") if isinstance(section.get("buildings"), dict) else {}
    farm = section.get("farm_land") if isinstance(section.get("farm_land"), dict) else {}
    farm_land = {k: {"land": float(v["land"]), "reserve": float(v["reserve"])} for k, v in farm.items() if isinstance(v, dict) and "land" in v}
    farm_classes = {k: [str(x) for x in v] for k, v in (farm.get("classes") or {}).items()} if isinstance(farm.get("classes"), dict) else {}
    scale = section.get("level_scale") if isinstance(section.get("level_scale"), dict) else {}
    niche_raw = buildings.get("niche") if isinstance(buildings.get("niche"), dict) else {}
    niche = {
        str(k): {"family": str(v["family"]), "strength": float(v.get("strength", 1.5)), "lock": [str(x) for x in (v.get("lock") or [])]}
        for k, v in niche_raw.items() if isinstance(v, dict) and v.get("family")
    }
    return WorldBuilderConfig(
        handover=path_of("handover"),
        geography_export=path_of("geography_export"),
        building_map={str(k): str(v) for k, v in (buildings.get("map") or {}).items()},
        niche=niche,
        compat_files=[str(x) for x in ((section.get("compat") or {}).get("vanilla_files") or [])] if isinstance(section.get("compat"), dict) else [],
        farm_land=farm_land,
        farm_classes=farm_classes,
        level_scale={str(k): float(v) for k, v in scale.items()},
        level_limit=int(section.get("level_limit", 20)),
        goods_floor=float(section.get("goods_floor", -0.2)),
        overpopulation_peasant_unrest=float(section.get("overpopulation_peasant_unrest", 0.1)),
        sync_geography=bool(section.get("sync_geography", True)),
        raw=section,
    )


@dataclass(frozen=True)
class Contract:
    root: Path
    meta: dict[str, Any]
    attribute_rows: pl.DataFrame
    building_types: pl.DataFrame
    location_buildings: pl.DataFrame
    location_targets: pl.DataFrame
    location_attributes: pl.DataFrame
    goods_floor: pl.DataFrame

    @property
    def features(self) -> list[str]:
        return [str(f) for f in self.meta["attributes"]["features"]]

    @property
    def goods(self) -> list[str]:
        return sorted(c.removeprefix("output_") for c in self.attribute_rows.columns if c.startswith("output_"))

    @property
    def version(self) -> str:
        return str(self.meta.get("version", self.root.name))


def load_contract(root: Path) -> Contract:
    root = Path(root)
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"handover {root} is missing: {', '.join(missing)}")
    meta = json.loads((root / "contract.json").read_text(encoding="utf-8"))
    if str(meta.get("schema_version", "")).split(".")[0] != "1":
        raise ValueError(f"unsupported handover schema {meta.get('schema_version')!r}")
    read = lambda name, **kw: pl.read_csv(root / name, infer_schema_length=100000, **kw)  # noqa: E731
    rows = read("attribute_rows.csv").with_columns(pl.col("value").cast(pl.String))
    attrs = read("location_attributes.csv").with_columns([pl.col(c).cast(pl.String) for c in meta["attributes"]["features"]])
    return Contract(
        root=root,
        meta=meta,
        attribute_rows=rows,
        building_types=read("building_types.csv"),
        location_buildings=read("location_buildings.csv"),
        location_targets=read("location_targets.csv"),
        location_attributes=attrs,
        goods_floor=read("goods_floor.csv"),
    )


def units(people: float) -> float:
    """People to game capacity units, two decimals."""
    return round(float(people) / PEOPLE_PER_UNIT, 2)
