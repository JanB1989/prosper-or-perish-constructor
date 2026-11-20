"""No scripted effect or trigger of the compiled mod is called with an argument its body never uses.

The engine refuses such a call when it compiles it ("Compiling source for <name> failed for unknown arguments: ...",
in debug.log and in the load part of error.log, which rotates into error.<n>.log) and the call then does nothing, with
no error at run time. In game 2026-11-20 every town-right plan target was a no-op that way: pp_lprof_expand, _start
and _upgrade shared one argument list and each used only a part of it. This scans every script file of the mod.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
COMMON = MOD / "in_game" / "common"


def _code(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _definitions() -> dict[str, set[str]]:
    """Each top-level scripted effect / trigger whose body uses $parameters$."""
    found: dict[str, set[str]] = {}
    for folder in ("scripted_effects", "scripted_triggers"):
        for path in sorted((COMMON / folder).glob("*.txt")):
            text = _code(path)
            for match in re.finditer(r"^([A-Za-z_][A-Za-z0-9_]*) = \{", text, re.MULTILINE):
                end = text.find("\n}", match.end())
                params = set(re.findall(r"\$([A-Za-z_0-9]+)\$", text[match.end():end]))
                if params:
                    found[match.group(1)] = params
    return found


def test_no_call_passes_an_argument_the_body_never_uses() -> None:
    definitions = _definitions()
    assert len(definitions) > 50
    files = sorted(COMMON.rglob("*.txt")) + sorted((MOD / "in_game" / "events").rglob("*.txt"))
    calls = 0
    unknown: dict[str, int] = {}
    for path in files:
        for name, args in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*) = \{ ((?:[A-Za-z_0-9]+ = [^\s{}]+ )+)\}", _code(path)):
            if name not in definitions:
                continue
            calls += 1
            extra = set(re.findall(r"([A-Za-z_0-9]+) = ", args)) - definitions[name]
            if extra:
                key = f"{path.name}: {name} gets {sorted(extra)}"
                unknown[key] = unknown.get(key, 0) + 1
    assert calls > 2000
    assert not unknown, "calls with arguments the body never uses (the game makes them no-ops): " + "; ".join(
        f"{key} x{count}" for key, count in sorted(unknown.items())[:10])
