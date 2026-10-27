from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
FILE = MOD_ROOT / "in_game/common/advances/pp_public_health_advances_adjustments.txt"
VANILLA_ADVANCES = Path.home() / ".cache/eu5-vanilla/game/in_game/common/advances"

# Public Health (2026-10-05, Jan): growth comes only from food and storage, so the 1.4 growth lines became disease
# resistance; their population capacity % became more resistance on 2026-10-27 (a third of it: +0.02 / +0.03).
EXPECTED = {
    "sanitation_advance": {"global_disease_resistance": 0.12},
    "vaccination_advance": {"global_disease_resistance": 0.15},
}


def _blocks(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r"(?ms)^TRY_REPLACE:(\w+) = \{\n(.*?)\n\}", text)}


def test_public_health_advances_trade_growth_and_capacity_for_resistance() -> None:
    raw = FILE.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    blocks = _blocks(raw.decode("utf-8-sig"))
    assert set(blocks) == set(EXPECTED)
    for name, values in EXPECTED.items():
        body = re.sub(r"#.*", "", blocks[name])
        assert "population_growth =" not in body, name
        assert "population_capacity" not in body, name
        for key, value in values.items():
            assert re.search(rf"(?m)^\s*{key} = {value:.2f}\b", body), (name, key)


def test_the_replaced_advances_still_exist_in_vanilla() -> None:
    if not VANILLA_ADVANCES.is_dir():
        return
    text = "\n".join(p.read_text(encoding="utf-8-sig", errors="replace") for p in VANILLA_ADVANCES.glob("*.txt"))
    for name in EXPECTED:
        assert re.search(rf"(?m)^{name} = \{{", text), name
