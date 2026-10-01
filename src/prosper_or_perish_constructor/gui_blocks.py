"""Find `blockoverride`s that name a block their widget type does not have.

The game drops such an override without a word in any log: whatever it carried is simply not built. EU5 1.4 turned
`TooltipScrolledContentSection` from a scroll area with a `scrollarea_content` block into a scroll vbox with a
`section_content` block, so the tooltips that filled `scrollarea_content` (the land-pressure and harvest chips of the
location view) lost their effect rows and showed an empty frame.

`type_index` reads the widget types and templates of a GUI tree (vanilla, then the mod; a later definition wins).
`TypeIndex.blocks` gives a type the block names an instance can override: its own, its base type's, those of the
templates it uses and of the typed widgets inside it (an override reaches blocks anywhere in the type's expansion).
`dead_overrides` lists the overrides of each typed instance in a GUI text that match none of them.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|#[^\n]*|[{}=]|[^\s{}="#]+')
GUI_FOLDERS = ("loading_screen/gui", "main_menu/gui", "in_game/gui")


@dataclass
class Node:
    key: str
    label: str = ""                                       # block / blockoverride / type / template name
    base: str = ""                                        # a type's base type
    usings: list[str] = field(default_factory=list)       # `using = <template>` directly inside
    children: list["Node"] = field(default_factory=list)


def parse(text: str) -> Node:
    """GUI text -> the tree of its `{ }` blocks; scalars other than `using` are dropped."""
    tokens = [t for t in _TOKEN.findall(text.lstrip("﻿")) if not t.startswith("#")]
    root = Node("root")
    stack = [root]
    i, n = 0, len(tokens)

    def at(k: int) -> str:
        return tokens[k] if k < n else ""

    while i < n:
        tok, nxt = tokens[i], at(i + 1)
        if tok == "}":
            if len(stack) > 1:
                stack.pop()
            i += 1
            continue
        if tok == "{":                                    # anonymous block (a list value): keeps the nesting
            node, i = Node(""), i + 1
        elif tok in ("block", "blockoverride") and nxt.startswith('"') and at(i + 2) == "{":
            node, i = Node(tok, nxt.strip('"')), i + 3
        elif tok == "type" and at(i + 2) == "=" and at(i + 4) == "{":
            node, i = Node("type", nxt, at(i + 3)), i + 5
        elif tok in ("template", "local_template", "types") and at(i + 2) == "{":
            node, i = Node(tok, nxt), i + 3
        elif nxt == "=" and at(i + 2) == "{":
            node, i = Node(tok), i + 3
        elif nxt == "{":                                  # `key { ... }` without `=`
            node, i = Node(tok), i + 2
        else:
            if tok == "using" and nxt == "=" and at(i + 2) not in ("", "{", "}"):
                stack[-1].usings.append(at(i + 2))
                i += 3
            else:
                i += 1
            continue
        stack[-1].children.append(node)
        stack.append(node)
    return root


def walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children:
        yield from walk(child)


@dataclass
class TypeIndex:
    types: dict[str, Node] = field(default_factory=dict)
    templates: dict[str, Node] = field(default_factory=dict)
    _cache: dict[str, frozenset[str]] = field(default_factory=dict)

    def add(self, text: str) -> None:
        for node in walk(parse(text)):
            if node.key == "type":
                self.types[node.label] = node
            elif node.key in ("template", "local_template"):
                self.templates[node.label] = node
        self._cache.clear()

    def blocks(self, name: str) -> frozenset[str] | None:
        """Block names an instance of type ``name`` can override; None when ``name`` is no known type."""
        if name not in self.types:
            return None
        if name not in self._cache:
            self._cache[name] = frozenset()                 # cycle guard
            self._cache[name] = frozenset(self._collect(self.types[name], {name}))
        return self._cache[name]

    def _collect(self, node: Node, seen: set[str]) -> set[str]:
        names: set[str] = set()
        for sub in walk(node):
            if sub.key == "block":
                names.add(sub.label)
            for used in sub.usings:
                if used in self.templates and used not in seen:
                    names |= self._collect(self.templates[used], seen | {used})
            if sub is not node and sub.key in self.types and sub.key not in seen:
                names |= self.blocks(sub.key) or frozenset()
        if node.key == "type" and node.base in self.types and node.base not in seen:
            names |= self.blocks(node.base) or frozenset()
        return names


def type_index(roots: Iterable[Path]) -> TypeIndex:
    """Widget types and templates of every `*.gui` under ``roots``, in order (a later definition wins)."""
    index = TypeIndex()
    for root in roots:
        for path in sorted(Path(root).rglob("*.gui")):
            index.add(path.read_text(encoding="utf-8-sig", errors="replace"))
    return index


def game_gui_roots(vanilla_game: Path, mod_root: Path | None = None) -> list[Path]:
    """The GUI folders the game reads: vanilla's, then the mod's."""
    roots = [Path(vanilla_game) / p for p in GUI_FOLDERS]
    if mod_root is not None:
        roots += [Path(mod_root) / p for p in GUI_FOLDERS]
    return [r for r in roots if r.is_dir()]


_DEFINITIONS = ("type", "template", "local_template", "types")


def dead_overrides(text: str, index: TypeIndex) -> Counter[tuple[str, str]]:
    """(type, block) -> count of `blockoverride`s that no enclosing typed instance can take.

    An override may sit anywhere inside an instance (also in plain widgets nested in it); it counts as live when any
    typed instance around it, up to the enclosing type definition (whose base type's blocks count too), has the
    block. A dead one is reported against the nearest typed instance around it.
    """
    found: Counter[tuple[str, str]] = Counter()

    def visit(node: Node, typed: list[str]) -> None:
        for child in node.children:
            if child.key == "blockoverride":
                if typed and not any(child.label in (index.blocks(t) or ()) for t in typed):
                    found[(typed[-1], child.label)] += 1
                visit(child, typed)
            elif child.key in _DEFINITIONS:
                visit(child, [child.base] if child.key == "type" and child.base in index.types else [])
            elif child.key in index.types:
                visit(child, typed + [child.key])
            else:
                visit(child, typed)

    visit(parse(text), [])
    return found
