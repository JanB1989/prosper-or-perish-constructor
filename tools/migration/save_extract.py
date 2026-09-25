"""Extract migration-relevant data from an EU5 text save into a pickle (docs/migration_rulebook.md).

usage: python3 tools/migration/save_extract.py SAVE OUT.pkl
Keeps: date; markets (center, population, average_migration_attraction, migration list, members);
locations (owner, market, province, rank, development, prosperity, control, market_access, pops list,
per pop type: population_ratio, unemployed, changes, and MigrationIn/Out by owner); pops (type, size, culture,
religion, satisfaction, estate); migration_manager entries; country tags.
"""
import pickle
import re
import sys

re_sec = re.compile(r"^([a-z_]+)=\{")
re_top = re.compile(r"^(\d+)=\{$")


def _dec(s):
    v = int(s)
    if v >= 1 << 63:
        v -= 1 << 64
    return v / 100000


def num(s):
    try:
        return float(s)
    except ValueError:
        return s


def ids(v):
    return [int(x) for x in v.replace("{", " ").replace("}", " ").split() if x.lstrip("-").isdigit()]


def parse(path):
    out = dict(date=None, tags=[], ctags={}, markets={}, locations={}, pops={}, migrations=[])
    sec = None
    cur = None
    in_locs = False
    in_db = False
    ptype = None
    in_popstats = False
    in_changes = False
    chg_key = None       # location-level changes={ MigrationIn={ data={ {owner=.. change=..} } } }
    loc_depth_block = None
    pend_owner = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            c0 = line[0]
            if c0 != "\t" and c0 != "}":
                m = re_sec.match(line)
                if m:
                    name = m.group(1)
                    sec, cur, in_locs, in_db = name, None, False, False
                    continue
            if sec == "metadata":
                if line.startswith("\tdate="):
                    out["date"] = line.split("=", 1)[1].strip()
                elif line.startswith("\t\tlocations={"):
                    out["tags"] = line.split("{", 1)[1].replace("}", " ").split()
            elif sec == "countries":
                m = re.match(r"^\t\t(\d+)=(\S+)$", line)
                if m and not in_db:
                    out["ctags"][int(m.group(1))] = m.group(2)
                if line.startswith("\tdatabase={"):
                    in_db = True
                    continue
                if in_db:
                    m = re_top.match(line)
                    if m:
                        cur = {"id": int(m.group(1)), "var": {}}
                        out.setdefault("countries", {})[cur["id"]] = cur
                        continue
                    if cur is not None:
                        st = line.strip()
                        if line.startswith("\t") and not line.startswith("\t\t"):
                            k1, _, v1 = st.partition("=")
                            if k1 in ("primary_culture", "primary_religion", "capital"):
                                cur[k1] = int(v1)
                            elif k1 in ("accepted_cultures", "tolerated_cultures"):
                                cur[k1] = ids(v1)
                        if st.startswith("flag=pp_"):
                            cur["var"][st[5:]] = 0.0
                            cur["_lv"] = st[5:]
                        elif st.startswith("identity=") and cur.get("_lv"):
                            cur["var"][cur["_lv"]] = _dec(st[9:])
                            cur["_lv"] = None
            elif sec == "market_manager":
                m = re_top.match(line)
                if m:
                    cur = {"id": int(m.group(1))}
                    out["markets"][cur["id"]] = cur
                    continue
                if cur is None or not line.startswith("\t") or line.startswith("\t\t"):
                    continue
                k, _, v = line.strip().partition("=")
                if k in ("center", "population", "average_migration_attraction", "capacity", "price"):
                    cur[k] = num(v)
                elif k in ("migration", "members"):
                    cur[k] = ids(v)
            elif sec == "provinces":
                m = re_top.match(line)
                if m:
                    cur = {"id": int(m.group(1))}
                    out.setdefault("provinces", {})[cur["id"]] = cur
                    continue
                if cur is None or not line.startswith("\t") or line.startswith("\t\t"):
                    continue
                k, _, v = line.strip().partition("=")
                if k in ("capital", "owner"):
                    cur[k] = num(v)
            elif sec in ("building_manager", "townrights_manager"):
                m = re_top.match(line)
                if m:
                    cur = {"id": int(m.group(1))}
                    out.setdefault(sec, []).append(cur)
                    continue
                if cur is None or not line.startswith("\t") or line.startswith("\t\t"):
                    continue
                k, _, v = line.strip().partition("=")
                if k in ("type", "level", "employed", "location", "owner"):
                    cur[k] = num(v)
            elif sec == "migration_manager":
                m = re_top.match(line)
                if m:
                    cur = {"id": int(m.group(1)), "moves": []}
                    out["migrations"].append(cur)
                    continue
                if cur is None:
                    continue
                s = line.strip()
                k, _, v = s.partition("=")
                if line.startswith("\t") and not line.startswith("\t\t"):
                    if k in ("owner", "to_owner", "to", "from", "culture", "religion", "months", "amount", "type", "pop_type"):
                        cur[k] = num(v.strip('"'))
                elif k in ("from_pop", "to_pop", "amount"):
                    if k == "from_pop":
                        cur["moves"].append({})
                    if cur["moves"]:
                        cur["moves"][-1][k] = num(v)
            elif sec == "population":
                m = re_top.match(line)
                if m:
                    cur = {}
                    out["pops"][int(m.group(1))] = cur
                    continue
                if cur is None or not line.startswith("\t") or line.startswith("\t\t"):
                    continue
                k, _, v = line.strip().partition("=")
                if k in ("type", "size", "culture", "religion", "satisfaction", "estate", "status", "literacy"):
                    cur[k] = num(v)
            elif sec == "locations":
                if not in_locs:
                    if line.startswith("\tlocations={"):
                        in_locs = True
                    continue
                if line.startswith("\t\t") and not line.startswith("\t\t\t"):
                    m = re.match(r"^\t\t(\d+)=\{$", line)
                    if m:
                        cur = {"id": int(m.group(1)), "pt": {}, "mods": [], "own_chg": {}}
                        out["locations"][cur["id"]] = cur
                        in_popstats = False
                        chg_key = None
                        ptype = None
                    continue
                if cur is None:
                    continue
                if line.startswith("\t\t\t") and not line.startswith("\t\t\t\t"):
                    k, _, v = line.strip().partition("=")
                    if k in ("owner", "controller", "market", "province", "market_access", "development", "prosperity",
                             "control", "max_raw_material_workers", "market_attraction", "proximity", "local_proximity_propagation", "market_parent", "second_best_market"):
                        cur[k] = num(v)
                    elif k in ("rank", "raw_material", "culture", "religion"):
                        cur[k] = v
                    continue
                if line.startswith("\t\t\t\tpop_stats={"):
                    in_popstats = True
                    continue
                if line.startswith("\t\t\t\tpops={"):
                    cur["pops"] = ids(line.split("=", 1)[1])
                    in_popstats = False
                    continue
                if line.startswith("\t\t\t\tchanges={"):
                    in_popstats = False
                    loc_depth_block = "changes"
                    continue
                if line.startswith("\t\t\t\tlast_months_migrations={"):
                    in_popstats = False
                    loc_depth_block = "lmm"
                    cur["lmm"] = []
                    continue
                if line.startswith("\t\t\t\t") and not line.startswith("\t\t\t\t\t"):
                    in_popstats = False
                    loc_depth_block = None
                    continue
                if loc_depth_block == "lmm":
                    s = line.strip()
                    k, _, v = s.partition("=")
                    if k == "from_pop":
                        cur["lmm"].append({})
                    if k in ("from_pop", "destination", "pop_type", "pop_culture", "pop_religion", "amount", "allow") and cur["lmm"]:
                        cur["lmm"][-1][k] = num(v)
                    continue
                if loc_depth_block == "changes":
                    s = line.strip()
                    if line.startswith("\t\t\t\t\t") and not line.startswith("\t\t\t\t\t\t") and s.endswith("={"):
                        chg_key = s[:-2]
                    elif s.startswith("owner="):
                        pend_owner = int(s[6:])
                    elif s.startswith("change=") and chg_key in ("MigrationIn", "MigrationOut"):
                        cur["own_chg"].setdefault(chg_key, {})[pend_owner] = float(s[7:])
                    continue
                if in_popstats:
                    if line.startswith("\t\t\t\t\t") and not line.startswith("\t\t\t\t\t\t"):
                        m = re.match(r"^\t\t\t\t\t(\w+)=\{", line)
                        if m:
                            ptype = m.group(1)
                            cur["pt"][ptype] = {}
                        continue
                    if line.startswith("\t\t\t\t\t\t") and not line.startswith("\t\t\t\t\t\t\t"):
                        k, _, v = line.strip().partition("=")
                        if not v.startswith("{"):
                            cur["pt"][ptype][k] = num(v)
                        continue
                    if line.startswith("\t\t\t\t\t\t\t") and not line.startswith("\t\t\t\t\t\t\t\t"):
                        k, _, v = line.strip().partition("=")
                        cur["pt"][ptype]["c." + k] = num(v)
                    continue
                st = line.strip()
                if st.startswith("flag=pp_"):
                    cur.setdefault("var", {})[st[5:]] = 0.0
                    cur["_lv"] = st[5:]
                    continue
                if st.startswith("identity=") and cur.get("_lv"):
                    cur["var"][cur["_lv"]] = _dec(st[9:])
                    cur["_lv"] = None
                    continue
                if line.startswith("\t\t\t\t\t\tmodifier="):
                    cur["mods"].append(line.split("=", 1)[1].strip())
                    cur.setdefault("modsize", []).append(1.0)
                elif line.startswith("\t\t\t\t\t\tsize=") and cur.get("modsize"):
                    cur["modsize"][-1] = float(line.split("=", 1)[1])
    return out


if __name__ == "__main__":
    d = parse(sys.argv[1])
    with open(sys.argv[2], "wb") as f:
        pickle.dump(d, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(sys.argv[1], d["date"], "markets", len(d["markets"]), "locations", len(d["locations"]), "pops", len(d["pops"]),
          "migrations", len(d["migrations"]))
