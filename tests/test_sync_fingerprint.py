"""The sync's World Builder fingerprint ignores what the stage never reads (2026-10-04, Jan: a Tavern weight edit
reran the whole start setup, about two minutes, before the sync could deploy)."""

from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor.cli import _worldbuilder_view

BLUEPRINT = b"""version: 2
tag: tavern
building:
  body: |2-
    max_levels = tavern_max_level   # cap
    ai_construct_weight = {
      value = -60
      add = { value = 6 subtract = pp_location_stored_months divide = 6 min = 0 max = 1 multiply = 120 }
    }
    unique_production_methods = {
      pp_tavern_serve_victuals = {
        victuals = 0.8
        output = 25.5
      }
    }
localization:
  entries:
    tavern: Tavern
icon:
  size: 512
evaluation:
  allow_rules:
    profit_percent: why
"""


def view(text: bytes, name: str = "tavern.yml") -> bytes:
    return _worldbuilder_view(Path(name), text)


def test_weights_comments_and_texts_are_ignored() -> None:
    base = view(BLUEPRINT)
    assert view(BLUEPRINT.replace(b"value = -60", b"value = -61")) == base
    assert view(BLUEPRINT.replace(b"# cap", b"# the cap, edited")) == base
    assert view(BLUEPRINT.replace(b"tavern: Tavern", b"tavern: Inn")) == base
    assert view(BLUEPRINT.replace(b"size: 512", b"size: 256")) == base
    assert view(BLUEPRINT.replace(b"profit_percent: why", b"profit_percent: because")) == base


def test_what_the_stage_reads_still_counts() -> None:
    base = view(BLUEPRINT)
    assert view(BLUEPRINT.replace(b"output = 25.5", b"output = 25.6")) != base
    assert view(BLUEPRINT.replace(b"tavern_max_level", b"other_max_level")) != base


def test_script_files_drop_comments_and_weights_only() -> None:
    script = b'building = {\n\tmax_levels = 3 # three\n\tai_construct_weight = { value = 5 }\n\tname = "a # b"\n}\n'
    out = view(script, "zz_pp_x.txt")
    assert b"three" not in out and b"ai_construct_weight" not in out
    assert b'"a # b"' in out and b"max_levels = 3" in out
    assert view(script.replace(b"value = 5", b"value = 9"), "zz_pp_x.txt") == out
    assert view(b"\x89PNG binary # data", "map.png") == b"\x89PNG binary # data"
