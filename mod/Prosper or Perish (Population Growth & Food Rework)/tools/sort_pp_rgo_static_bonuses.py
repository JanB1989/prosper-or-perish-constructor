"""
Sort in_game/common/static_modifiers/pp_rgo_static_bonuses.txt by the # category line
(method: Mining, Farming, Gathering, Hunting, Forestry), then by modifier name.

Run from repo/mod root: python tools/sort_pp_rgo_static_bonuses.py
"""
from __future__ import annotations

import re
from pathlib import Path

MOD_ROOT = Path(__file__).resolve().parent.parent
TARGET = MOD_ROOT / "in_game/common/static_modifiers/pp_rgo_static_bonuses.txt"


def parse_blocks(lines: list[str]) -> tuple[str, list[tuple[str, str, str]]]:
    """
    Returns (header, [(category, sort_key, block_text), ...]).
    """
    i = 0
    while i < len(lines):
        if (
            lines[i].startswith("# ")
            and i + 1 < len(lines)
            and lines[i + 1].startswith("pp_rgo_bonus_")
        ):
            break
        i += 1
    header = "\n".join(lines[:i]).rstrip()
    blocks: list[tuple[str, str, str]] = []
    while i < len(lines):
        if not lines[i].startswith("# "):
            raise ValueError(f"expected # category at line {i + 1}: {lines[i]!r}")
        category = lines[i][2:].strip()
        if i + 1 >= len(lines) or not lines[i + 1].startswith("pp_rgo_bonus_"):
            raise ValueError(f"expected pp_rgo_bonus after category at line {i + 1}")
        m = re.match(r"^(pp_rgo_bonus_\w+)\s*=", lines[i + 1])
        if not m:
            raise ValueError(f"bad modifier line: {lines[i + 1]!r}")
        sort_key = m.group(1)
        depth = 0
        end = i + 1
        for k in range(i + 1, len(lines)):
            depth += lines[k].count("{") - lines[k].count("}")
            if depth == 0:
                end = k + 1
                break
        else:
            raise ValueError(f"unclosed block starting at line {i + 1}")
        block_text = "\n".join(lines[i:end])
        blocks.append((category, sort_key, block_text))
        i = end
        while i < len(lines) and lines[i].strip() == "":
            i += 1
    return header, blocks


def main() -> None:
    text = TARGET.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    header, blocks = parse_blocks(lines)
    blocks.sort(key=lambda t: (t[0].lower(), t[1].lower()))
    body = "\n\n".join(t[2] for t in blocks)
    out = header + "\n\n" + body + "\n"
    TARGET.write_text(out, encoding="utf-8", newline="\n")
    print(f"Sorted {len(blocks)} blocks in {TARGET}")


if __name__ == "__main__":
    main()
