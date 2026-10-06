"""Branch edit (one-off, per blueprint): craft line outputs x(0.8/0.9) and the mastery ai_construct_weight.
python3 apply_branch_v2.py   (in the establishment worktree)"""
import re
import tomllib
from pathlib import Path

W = Path("/home/jan/development/ProsperOrPerishConstructor-establishment")
FACTOR = 0.8 / 0.9
K = 0.2845
lines = tomllib.loads((W / "constructor.toml").read_text())["legacy_methods"]["lines"]
lines["jewelry"] = ["jewelry_guild"]
for g in ("dyes", "paper", "saltpeter"):
    lines.pop(g)
TG = {t: ("weaponry" if g == "weapons" else g) for g, ts in lines.items() for t in ts}

for t, good in TG.items():
    p = W / f"blueprints/accepted/buildings/{t}.yml"
    s = p.read_text()
    outs = []

    def scale(mm):
        name, inner = mm.group(1), mm.group(2)
        if "_market_sales" in name or "_legacy_" in name or "produced =" not in inner:
            return mm.group(0)
        def rep(x):
            v = round(float(x.group(2)) * FACTOR, 5)
            outs.append(v)
            return f"{x.group(1)}{v:g}"
        return mm.group(0).replace(inner, re.sub(r"(\boutput = )([0-9.]+)", rep, inner, count=1))

    s = re.sub(r"\n\s+(pp_[a-z0-9_]+) = \{((?:[^{}]|\{[^{}]*\})*)\}", scale, s)
    assert outs, t
    block = (
        "    # mastery (establishment branch, 2026-10-06): the AI scores a workshop at its recipe output and never sees\n"
        "    # the +20 % a mastered workshop makes, so expanding one gets that extra profit as weight: 0.2 x best output x\n"
        "    # price x market access x sqrt(owner gold + 100) x K (K fitted in game on twin buildings; matches the median).\n"
        "    ai_construct_weight = {\n"
        "        value = 0\n"
        "        if = {\n"
        f"            limit = {{ exists = market has_building = building_type:{t} }}\n"
        "            add = {\n"
        f"                value = \"market.market_price(goods:{good})\"\n"
        f"                multiply = {0.2 * max(outs):.5f}\n"
        "                multiply = { value = market_access max = 1 min = 0 }\n"
        "                multiply = { value = scope:owner.gold min = 0 add = 100 pow = 0.5 }\n"
        f"                multiply = {K}\n"
        "            }\n"
        "        }\n"
        "    }\n")
    s = s.replace("    unique_production_methods = {", block + "    unique_production_methods = {", 1)
    p.write_text(s)
print("edited", len(TG))
