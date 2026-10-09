"""Generate a static web export of the Prosper or Perish Europedia."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eu5gameparser.clausewitz.parser import ParserError, parse_file
from eu5gameparser.clausewitz.syntax import CList, Value


EUROPEDIA_GUI = Path("in_game/gui/encyclopedia_lateralview.gui")
EUROPEDIA_LOCALIZATION = Path("main_menu/localization/english/pp_europedia_l_english.yml")
EUROPEDIA_CONCEPTS = Path("main_menu/common/game_concepts")


class EuropediaExportError(ValueError):
    """Raised when Europedia source files cannot be exported cleanly."""


@dataclass(frozen=True)
class GuiCard:
    order: int
    filter_id: str
    title_key: str
    body_key: str
    icon_texture: str | None
    # further texts of a styled card (pp_europedia_style.gui), in card order: (role, key); role is the
    # blockoverride name ("section_title", "step_text", ...) or "text"
    parts: tuple[tuple[str, str], ...] = ()


# texts of a card in reading order: plain text_multi bodies, the style's lead/text types and its blockoverrides
_CARD_TEXT = re.compile(
    r"pp_eu_(?:lead|text)\s*=\s*\{\s*text\s*=\s*\"(?P<styled>[^\"]+)\""
    r"|text_multi\s*=\s*\{[^{}]*?text\s*=\s*\"(?P<plain>[^\"]+)\""
    r"|blockoverride\s+\"(?P<role>section_title|step_title|step_text|scale_label|row_label)\"\s*\{\s*text\s*=\s*\"(?P<part>[^\"]+)\""
)
_TITLE_ROLES = ("section_title", "step_title")


@dataclass(frozen=True)
class ConceptDefinition:
    key: str
    file: str
    line: int
    family: str | None
    texture: str | None
    aliases: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "file": self.file,
            "line": self.line,
            "family": self.family,
            "texture": self.texture,
            "aliases": list(self.aliases),
        }


def write_europedia_export(
    mod_root: Path,
    html_path: Path,
    json_path: Path,
) -> tuple[Path, Path]:
    payload = build_europedia_payload(mod_root)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    html_path.write_text(_standalone_html(payload), encoding="utf-8")
    return html_path, json_path


def build_europedia_payload(mod_root: Path) -> dict[str, Any]:
    gui_path = mod_root / EUROPEDIA_GUI
    localization_path = mod_root / EUROPEDIA_LOCALIZATION
    concepts_root = mod_root / EUROPEDIA_CONCEPTS
    for path in (gui_path, localization_path, concepts_root):
        if not path.exists():
            raise EuropediaExportError(f"Missing Europedia source: {path}")

    cards = _extract_gui_cards(gui_path.read_text(encoding="utf-8-sig"))
    if not cards:
        raise EuropediaExportError(f"No custom Europedia cards found in {gui_path}")

    localization = _read_localization(localization_path)
    concepts = _read_concepts(concepts_root, mod_root)
    filter_labels = _extract_filter_labels(gui_path.read_text(encoding="utf-8-sig"))

    entries: list[dict[str, Any]] = []
    missing_keys: list[str] = []
    for card in cards:
        title = localization.get(card.title_key)
        body = localization.get(card.body_key)
        if title is None:
            missing_keys.append(card.title_key)
        if body is None:
            missing_keys.append(card.body_key)
        missing_keys += [key for _, key in card.parts if key not in localization]
        if title is None or body is None:
            continue
        # live lines (the player's own game) have nothing to show outside it
        body = _join_parts(body, [(role, localization[key]) for role, key in card.parts
                                  if key in localization and "GetPlayer" not in localization[key]])

        concept_key = _concept_key_from_title_key(card.title_key)
        definition = concepts.get(concept_key)
        source = {
            "gui": str(EUROPEDIA_GUI),
            "localization": str(EUROPEDIA_LOCALIZATION),
            "concept": definition.file if definition else None,
        }
        entries.append(
            {
                "id": _slug(concept_key),
                "order": card.order,
                "filter": card.filter_id,
                "filter_label": filter_labels.get(card.filter_id, _display_key(card.filter_id)),
                "concept_key": concept_key,
                "title_key": card.title_key,
                "body_key": card.body_key,
                "title": title,
                "body_raw": body,
                "body_plain": _plain_text(body),
                "icon_texture": card.icon_texture or (definition.texture if definition else None),
                "definition": definition.to_dict() if definition else None,
                "source": source,
                "links": sorted(set(_concept_refs(body))),
            }
        )

    if missing_keys:
        unique = ", ".join(sorted(set(missing_keys)))
        raise EuropediaExportError(f"Missing Europedia localization keys: {unique}")

    anchors = _entry_anchors(entries, concepts)
    for entry in entries:
        entry["body_html"] = _render_eu5_body(entry["body_raw"], anchors)

    filters = [
        {
            "id": filter_id,
            "label": label,
            "count": (
                len(entries)
                if filter_id == "all"
                else sum(1 for entry in entries if entry["filter"] == filter_id)
            ),
        }
        for filter_id, label in filter_labels.items()
        if filter_id == "all" or any(entry["filter"] == filter_id for entry in entries)
    ]
    if not any(filter_item["id"] == "all" for filter_item in filters):
        filters.insert(0, {"id": "all", "label": "All", "count": len(entries)})

    return {
        "metadata": {
            "title": "Prosper or Perish Europedia",
            "entry_count": len(entries),
            "sources": {
                "gui": str(EUROPEDIA_GUI),
                "localization": str(EUROPEDIA_LOCALIZATION),
                "concepts": str(EUROPEDIA_CONCEPTS),
            },
        },
        "filters": filters,
        "entries": entries,
    }


def _extract_gui_cards(text: str) -> list[GuiCard]:
    starts = re.compile(r"visible\s*=\s*\"\[Or\(GetVariableSystem\.HasValue\('pp_filter', 'all'\)")
    cards: list[GuiCard] = []
    for start in starts.finditer(text):
        following = starts.search(text, start.end())
        span = text[start.start():following.start() if following else len(text)]
        match = re.match(
            r"visible\s*=\s*\"\[Or\(GetVariableSystem\.HasValue\('pp_filter', 'all'\),\s*"
            r"GetVariableSystem\.HasValue\('pp_filter', '(?P<filter>[^']+)'\)\)\]\"",
            span,
        )
        title_match = re.search(r"text_single\s*=\s*\{[^{}]*?text\s*=\s*\"(?P<title_key>[^\"]+)\"", span, flags=re.DOTALL)
        texts = [(m.group("role") or "text", m.group("styled") or m.group("plain") or m.group("part"))
                 for m in _CARD_TEXT.finditer(span)]
        if match is None or title_match is None or not texts:
            continue
        icon_match = re.search(r"icon\s*=\s*\{[^{}]*?texture\s*=\s*\"(?P<texture>[^\"]+)\"", span, flags=re.DOTALL)
        cards.append(
            GuiCard(
                order=len(cards) + 1,
                filter_id=match.group("filter"),
                title_key=title_match.group("title_key"),
                body_key=texts[0][1],
                icon_texture=icon_match.group("texture") if icon_match else None,
                parts=tuple(texts[1:]),
            )
        )
    return cards


def _join_parts(body: str, parts: list[tuple[str, str]]) -> str:
    """A styled card's texts as one Europedia body: headings as titles, a scale's labels on one line."""
    out = [body]
    scale = False
    for role, text in parts:
        if role == "scale_label" and scale:
            out[-1] += f" · {text}"
        elif role in _TITLE_ROLES:
            out.append(f"#T {text}#!")
        else:
            out.append(text)
        scale = role == "scale_label"
    return "\n\n".join(out)


def _extract_filter_labels(text: str) -> dict[str, str]:
    labels: dict[str, str] = {"all": "All"}
    pattern = re.compile(
        r"raw_text\s*=\s*\"(?P<label>[^\"]+)\""
        r"(?:(?!button_regular\s*=\s*\{).)*?"
        r"onclick\s*=\s*\"\[GetVariableSystem\.Set\('pp_filter', '(?P<filter>[^']+)'\)\]\"",
        flags=re.DOTALL,
    )
    for match in pattern.finditer(text):
        labels.setdefault(match.group("filter"), match.group("label"))
    return labels


def _read_localization(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    entries: dict[str, str] = {}
    pattern = re.compile(
        r"^\s*(?P<key>[A-Za-z0-9_]+):(?:\d+)?\s*\"(?P<value>(?:\\.|[^\"\\])*)\"\s*$",
        flags=re.MULTILINE,
    )
    for match in pattern.finditer(text):
        try:
            entries[match.group("key")] = json.loads(f'"{match.group("value")}"')
        except json.JSONDecodeError as error:
            raise EuropediaExportError(
                f"Cannot decode localization value {match.group('key')!r} in {path}: {error}"
            ) from error
    return entries


def _read_concepts(root: Path, mod_root: Path) -> dict[str, ConceptDefinition]:
    concepts: dict[str, ConceptDefinition] = {}
    for path in sorted(root.glob("*.txt")):
        try:
            document = parse_file(path)
        except ParserError as error:
            raise EuropediaExportError(f"Cannot parse game concept file {path}: {error}") from error
        for entry in document.entries:
            if not isinstance(entry.value, CList):
                continue
            family = _scalar_string(entry.value.first("family"))
            texture = _scalar_string(entry.value.first("texture"))
            aliases = _string_items(entry.value.first("alias"))
            concepts[entry.key] = ConceptDefinition(
                key=entry.key,
                file=str(path.relative_to(mod_root)),
                line=entry.location.line,
                family=family,
                texture=texture,
                aliases=tuple(aliases),
            )
    return concepts


def _scalar_string(value: Value | None) -> str | None:
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, CList):
        return None
    return str(value)


def _string_items(value: Value | None) -> list[str]:
    if isinstance(value, CList):
        return [item for item in value.items if isinstance(item, str)]
    if isinstance(value, str):
        return [value]
    return []


def _concept_key_from_title_key(title_key: str) -> str:
    return title_key.removeprefix("game_concept_")


def _entry_anchors(
    entries: list[dict[str, Any]],
    concepts: dict[str, ConceptDefinition],
) -> dict[str, dict[str, str]]:
    anchors: dict[str, dict[str, str]] = {}
    for entry in entries:
        concept_key = entry["concept_key"]
        anchor = {"id": entry["id"], "title": entry["title"]}
        anchors[concept_key] = anchor
        definition = concepts.get(concept_key)
        if definition is not None:
            for alias in definition.aliases:
                anchors.setdefault(alias, anchor)
    return anchors


def _render_eu5_body(text: str, anchors: dict[str, dict[str, str]]) -> str:
    blocks: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(list_items) + "</ul>")
            list_items = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            continue
        heading = re.match(r"^#T\s*(.*?)#!\s*(.*)$", line)
        if heading:
            flush_list()
            blocks.append(f"<h3>{_format_inline(heading.group(1).strip(), anchors)}</h3>")
            if heading.group(2).strip():
                blocks.append(f"<p>{_format_inline(heading.group(2).strip(), anchors)}</p>")
            continue
        if line.startswith("$BULLET$"):
            list_items.append(f"<li>{_format_inline(line.removeprefix('$BULLET$').strip(), anchors)}</li>")
            continue
        flush_list()
        blocks.append(f"<p>{_format_inline(line, anchors)}</p>")

    flush_list()
    return "\n".join(blocks)


_INLINE_FUNCTIONS = (
    "ShowGoodsName",
    "ShowBuildingTypeName",
    "ShowModifier",
    "ShowModifierEffect",
    "ShowPopTypeName",
    "ScriptValue",
    "GetVariable",
)
_INLINE_FUNCTION_PATTERN = "|".join(_INLINE_FUNCTIONS)
_INLINE_TOKEN = re.compile(
    rf"(?P<bracket_func>\[(?P<bracket_func_name>{_INLINE_FUNCTION_PATTERN})"
    r"\('(?P<bracket_func_arg>[^']+)'\)(?:\|e)?\])"
    rf"|(?P<func>(?P<func_name>{_INLINE_FUNCTION_PATTERN})"
    r"\('(?P<func_arg>[^']+)'\))"
    r"|(?P<link>\[(?P<concept>[A-Za-z0-9_]+)\|e\])"
)


def _format_inline(text: str, anchors: dict[str, dict[str, str]]) -> str:
    out: list[str] = []
    position = 0
    style_pattern = re.compile(r"#(?:[A-Za-z_]+)\s*(.*?)#!")
    for match in style_pattern.finditer(text):
        out.append(_format_inline_plain(text[position : match.start()], anchors))
        out.append(f"<strong>{_format_inline_plain(match.group(1).strip(), anchors)}</strong>")
        position = match.end()
    out.append(_format_inline_plain(text[position:], anchors))
    return "".join(out)


def _format_inline_plain(text: str, anchors: dict[str, dict[str, str]]) -> str:
    out: list[str] = []
    position = 0
    for match in _INLINE_TOKEN.finditer(text):
        out.append(html.escape(text[position : match.start()]))
        if match.group("concept"):
            out.append(_format_concept_link(match.group("concept"), anchors))
        else:
            name = match.group("bracket_func_name") or match.group("func_name")
            arg = match.group("bracket_func_arg") or match.group("func_arg")
            out.append(_format_function_token(name, arg))
        position = match.end()
    out.append(html.escape(text[position:]))
    return "".join(out)


def _format_concept_link(concept: str, anchors: dict[str, dict[str, str]]) -> str:
    target = anchors.get(concept)
    if target is None:
        return f'<span class="concept-ref">{html.escape(_display_key(concept))}</span>'
    return (
        f'<a class="concept-link" href="#{html.escape(target["id"])}">'
        f'{html.escape(target["title"])}</a>'
    )


def _format_function_token(name: str, arg: str) -> str:
    label = _display_key(arg)
    if name == "ShowGoodsName":
        css_class = "token-good"
    elif name == "ShowBuildingTypeName":
        css_class = "token-building"
    elif name == "ShowModifierEffect":
        css_class = "token-effect"
        label = f"modifier effects: {label}"
    elif name == "ShowModifier":
        css_class = "token-modifier"
    elif name == "ShowPopTypeName":
        css_class = "token-pop"
    else:
        css_class = "token-value"
    return f'<span class="token {css_class}">{html.escape(label)}</span>'


def _plain_text(text: str) -> str:
    text = re.sub(r"#T\s*(.*?)#!", r"\1", text)
    text = re.sub(r"#[A-Za-z_]+\s*(.*?)#!", r"\1", text)
    text = text.replace("$BULLET$", "- ")
    text = re.sub(
        rf"\[(?:{_INLINE_FUNCTION_PATTERN})\('([^']+)'\)(?:\|e)?\]",
        lambda m: _display_key(m.group(1)),
        text,
    )
    text = re.sub(
        rf"(?:{_INLINE_FUNCTION_PATTERN})\('([^']+)'\)",
        lambda m: _display_key(m.group(1)),
        text,
    )
    text = re.sub(r"\[([A-Za-z0-9_]+)\|e\]", lambda m: _display_key(m.group(1)), text)
    return text


def _concept_refs(text: str) -> list[str]:
    return re.findall(r"\[([A-Za-z0-9_]+)\|e\]", text)


def _display_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "entry"


def _standalone_html(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = html.escape(str(payload["metadata"]["title"]))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      background: #f6f7f4;
      color: #1f2933;
      font-family: Inter, Segoe UI, system-ui, sans-serif;
      line-height: 1.5;
      margin: 0;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid #d7ddd2;
      position: sticky;
      top: 0;
      z-index: 4;
    }}
    .wrap {{
      margin: 0 auto;
      max-width: 1180px;
      padding: 0 20px;
    }}
    .topbar {{
      align-items: center;
      display: grid;
      gap: 14px;
      grid-template-columns: minmax(220px, 1fr) auto;
      min-height: 70px;
      padding: 12px 0;
    }}
    h1 {{
      font-size: 18px;
      line-height: 1.2;
      margin: 0;
    }}
    .meta {{
      color: #667085;
      font-size: 12px;
      margin-top: 3px;
    }}
    .controls {{
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }}
    button, input {{
      background: #ffffff;
      border: 1px solid #c8d0c2;
      border-radius: 6px;
      color: #1f2933;
      font: inherit;
      font-size: 13px;
      min-height: 34px;
      padding: 7px 10px;
    }}
    button {{ cursor: pointer; font-weight: 650; }}
    button:hover {{ background: #eef2ea; }}
    button.active {{
      background: #1f2933;
      border-color: #1f2933;
      color: #ffffff;
    }}
    input {{ min-width: 260px; }}
    .filters {{
      border-top: 1px solid #e5e9e1;
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      padding: 10px 0 12px;
    }}
    main {{
      display: grid;
      gap: 16px;
      padding-bottom: 48px;
      padding-top: 18px;
    }}
    .entry {{
      background: #ffffff;
      border: 1px solid #d7ddd2;
      border-radius: 8px;
      display: grid;
      gap: 0;
      overflow: hidden;
    }}
    .entry-head {{
      align-items: center;
      background: #f9faf7;
      border-bottom: 1px solid #e5e9e1;
      display: grid;
      gap: 12px;
      grid-template-columns: 46px minmax(0, 1fr);
      padding: 12px 14px;
    }}
    .icon {{
      align-items: center;
      background: #e9eee4;
      border: 1px solid #d7ddd2;
      border-radius: 6px;
      color: #566151;
      display: flex;
      font-size: 11px;
      font-weight: 800;
      height: 46px;
      justify-content: center;
      width: 46px;
    }}
    .entry h2 {{
      font-size: 18px;
      line-height: 1.25;
      margin: 0;
    }}
    .entry-body {{ padding: 6px 18px 18px; }}
    .entry-body h3 {{
      border-top: 1px solid #edf0ea;
      font-size: 15px;
      margin: 18px 0 8px;
      padding-top: 14px;
    }}
    .entry-body h3:first-child {{ border-top: 0; margin-top: 8px; padding-top: 0; }}
    .entry-body p {{ margin: 10px 0; }}
    .entry-body ul {{ margin: 8px 0 12px; padding-left: 22px; }}
    .source-row {{
      color: #667085;
      font-size: 11px;
      margin-top: 14px;
    }}
    .concept-link {{
      color: #1d5f8c;
      font-weight: 650;
      text-decoration: none;
    }}
    .concept-link:hover {{ text-decoration: underline; }}
    .concept-ref, .token {{
      background: #eef2ea;
      border: 1px solid #d9e2d1;
      border-radius: 5px;
      color: #2f3a2b;
      display: inline-block;
      font-size: 0.93em;
      padding: 0 5px;
    }}
    .token-building {{ background: #edf5ff; border-color: #cfe2ff; }}
    .token-good {{ background: #fff4df; border-color: #f0d69d; }}
    .token-effect {{ background: #f9eeee; border-color: #e7c8c8; }}
    .token-pop {{ background: #f3efff; border-color: #d9d0f6; }}
    .empty {{
      background: #ffffff;
      border: 1px solid #d7ddd2;
      border-radius: 8px;
      color: #667085;
      padding: 24px;
    }}
    @media (max-width: 760px) {{
      .topbar {{ grid-template-columns: 1fr; }}
      .controls {{ justify-content: stretch; }}
      input, button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <div class="topbar">
        <div>
          <h1>{title}</h1>
          <div class="meta" id="summaryMeta"></div>
        </div>
        <div class="controls">
          <input id="searchInput" type="search" placeholder="Search Europedia entries" aria-label="Search Europedia entries">
          <button id="exportJsonButton" type="button">Export JSON</button>
        </div>
      </div>
      <div class="filters" id="filterButtons" aria-label="Europedia filters"></div>
    </div>
  </header>
  <main class="wrap" id="entries"></main>
  <script>
    const europediaPayload = {payload_json};
    const entriesEl = document.getElementById("entries");
    const filterButtonsEl = document.getElementById("filterButtons");
    const searchInput = document.getElementById("searchInput");
    const summaryMeta = document.getElementById("summaryMeta");
    let activeFilter = "all";

    function renderFilters() {{
      filterButtonsEl.innerHTML = "";
      for (const filter of europediaPayload.filters) {{
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.filter = filter.id;
        button.className = filter.id === activeFilter ? "active" : "";
        button.textContent = `${{filter.label}} (${{filter.id === "all" ? europediaPayload.entries.length : filter.count}})`;
        button.addEventListener("click", () => {{
          activeFilter = filter.id;
          render();
        }});
        filterButtonsEl.appendChild(button);
      }}
    }}

    function render() {{
      renderFilters();
      const query = searchInput.value.trim().toLowerCase();
      const visibleEntries = europediaPayload.entries.filter(entry => {{
        const matchesFilter = activeFilter === "all" || entry.filter === activeFilter;
        const haystack = `${{entry.title}} ${{entry.body_plain}} ${{entry.title_key}} ${{entry.body_key}}`.toLowerCase();
        return matchesFilter && (!query || haystack.includes(query));
      }});
      summaryMeta.textContent = `${{visibleEntries.length}} of ${{europediaPayload.entries.length}} entries`;
      entriesEl.innerHTML = visibleEntries.length
        ? visibleEntries.map(entryHtml).join("")
        : '<div class="empty">No Europedia entries match the current filter.</div>';
    }}

    function entryHtml(entry) {{
      const iconLabel = entry.icon_texture ? entry.icon_texture.split("/").pop().replace(".dds", "") : "PP";
      const source = entry.definition?.file || entry.source.localization;
      return `
        <article class="entry" id="${{escapeHtml(entry.id)}}">
          <div class="entry-head">
            <div class="icon" title="${{escapeHtml(entry.icon_texture || "")}}">${{escapeHtml(iconLabel.slice(0, 3).toUpperCase())}}</div>
            <div>
              <h2>${{escapeHtml(entry.title)}}</h2>
              <div class="meta">${{escapeHtml(entry.filter_label)}} · ${{escapeHtml(entry.concept_key)}}</div>
            </div>
          </div>
          <div class="entry-body">
            ${{entry.body_html}}
            <div class="source-row">Source: ${{escapeHtml(source)}} · ${{escapeHtml(entry.title_key)}} / ${{escapeHtml(entry.body_key)}}</div>
          </div>
        </article>
      `;
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }}

    function exportJson() {{
      const blob = new Blob([JSON.stringify(europediaPayload, null, 2)], {{ type: "application/json" }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "europedia_entries.json";
      link.click();
      URL.revokeObjectURL(url);
    }}

    searchInput.addEventListener("input", render);
    document.getElementById("exportJsonButton").addEventListener("click", exportJson);
    render();
  </script>
</body>
</html>
"""
