"""Write calibration twin building types into the LIVE mod (EU5 closed). Twins copy a live craft building with
renamed methods; outputs scaled by a factor; optional weight (constant or the mastery formula F). --remove deletes.
CAL_SET=x12wf (default) | old ; CAL_K = formula constant"""
import os
import re
import sys
from pathlib import Path

L = Path("/mnt/c/Users/Anwender/Documents/Paradox Interactive/Europa Universalis V/mod/"
         "Prosper or Perish (Population Growth & Food Rework)")
OUT = L / "in_game/common/building_types/zzz_pp_cal_twins.txt"
OUT_ADV = L / "in_game/common/advances/zzz_pp_cal_twins.txt"
if "--remove" in sys.argv:
    for p in (OUT, OUT_ADV):
        p.unlink(missing_ok=True)
    print("twins removed")
    sys.exit()

GOOD = {"tools_guild": "tools", "cloth_guild": "cloth", "weapon_guild": "weaponry", "pottery_guild": "pottery",
        "tannery": "leather", "brewery": "beer"}
K = float(os.environ.get("CAL_K", "0.2845"))
FORM = os.environ.get("CAL_FORM", "sqrtgold")


def weight_formula(src, out):
    g = GOOD[src]
    owner = {"sqrtgold": "multiply = { value = scope:owner.gold min = 0 add = 100 pow = 0.5 }",
             "flat": ""}[FORM]
    return ("{ value = 0 if = { limit = { exists = market } add = { value = \"market.market_price(goods:%s)\" "
            "multiply = %.5f multiply = { value = market_access max = 1 min = 0 } %s multiply = %.4f } } }"
            % (g, 0.2 * out, owner, K))


if os.environ.get("CAL_SET", "x12wf") == "old":
    TWINS = [("cal_tools_guild_x12", "tools_guild", 1.2, None), ("cal_cloth_guild_x12", "cloth_guild", 1.2, None),
             ("cal_weapon_guild_x12", "weapon_guild", 1.2, None), ("cal_pottery_guild_x12", "pottery_guild", 1.2, None),
             ("cal_tannery_x12", "tannery", 1.2, None), ("cal_brewery_x12", "brewery", 1.2, None),
             ("cal_tools_guild_x10", "tools_guild", 1.0, None), ("cal_tools_guild_w10", "tools_guild", 1.0, 10),
             ("cal_cloth_guild_x14", "cloth_guild", 1.4, None), ("cal_weapon_guild_x14", "weapon_guild", 1.4, None)]
else:
    TWINS = ([(f"cal_{b}_x12", b, 1.2, None) for b in GOOD] + [(f"cal_{b}_wf", b, 1.0, "F") for b in GOOD]
             + [("cal_tools_guild_x10", "tools_guild", 1.0, None)])
UNLOCK = {"tools_guild": "metallurgy", "weapon_guild": "weapon_guild_advance"}
METHOD_UNLOCK = {}
for f in (L / "in_game/common/advances").glob("pp_*.txt"):
    s = f.read_text(encoding="utf-8-sig")
    for adv, body in re.findall(r"TRY_INJECT:(\w+) = \{(.*?)\}", s, re.S):
        for m in re.findall(r"unlock_production_method = (\w+)", body):
            METHOD_UNLOCK[m] = adv

blocks, adv_inj = [], {}
for key, src, factor, weight in TWINS:
    s = (L / f"in_game/common/building_types/zz_pp_{src}.txt").read_text(encoding="utf-8-sig")
    m = re.search(rf"REPLACE:{src} = \{{(.*)\n\}}", s, re.S)
    body = m.group(1)
    outs = [float(x) for n, x in re.findall(r"(pp_[a-z0-9_]+) = \{(?:[^{}]|\{[^{}]*\})*?\boutput = ([0-9.]+)", body)
            if "_market_sales" not in n and "_legacy_" not in n]
    tag = key.split("_")[-1]
    for meth in re.findall(r"\b(pp_[a-z0-9_]+) = \{", body):
        new = f"cal{tag}_{meth}"[:90]
        if meth in METHOD_UNLOCK:
            adv_inj.setdefault(METHOD_UNLOCK[meth], []).append(f"unlock_production_method = {new}")
        body = re.sub(rf"\b{meth}\b", new, body)
    if factor != 1.0:
        def scale(mm):
            name, inner = mm.group(1), mm.group(2)
            if "_market_sales" in name or "produced =" not in inner:
                return mm.group(0)
            inner2 = re.sub(r"(\boutput = )([0-9.]+)", lambda x: f"{x.group(1)}{round(float(x.group(2)) * factor, 5):g}",
                            inner, count=1)
            return mm.group(0).replace(inner, inner2)
        body = re.sub(r"(cal\w+) = \{((?:[^{}]|\{[^{}]*\})*)\}", scale, body)
    if weight == "F":
        body += "\nai_construct_weight = " + weight_formula(src, max(outs))
    elif weight is not None:
        body += f"\nai_construct_weight = {{ value = {weight} }}"
    blocks.append(f"{key} = {{{body}\n}}\n")
    if src in UNLOCK:
        adv_inj.setdefault(UNLOCK[src], []).append(f"unlock_building = {key}")
OUT.write_text("﻿" + "\n".join(blocks), encoding="utf-8")
OUT_ADV.write_text("﻿" + "\n".join(f"TRY_INJECT:{a} = {{\n\t" + "\n\t".join(v) + "\n}\n" for a, v in adv_inj.items()),
                   encoding="utf-8")
print("twins", len(TWINS), "advance injects", {a: len(v) for a, v in adv_inj.items()})
