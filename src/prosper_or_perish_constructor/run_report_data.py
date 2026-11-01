"""The data files of the run report's goods and food pages, as scripts.

A browser refuses fetch() on a page opened from disk (file://), which is how the report is read before it is
published (Jan, 2026-10-28: the goods and food pages stayed empty locally, worked on the site). A script tag loads
from disk and from the site alike, so every data file is a script that hands its payload to the page's loadData().
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def data_script(name: str, payload: Any) -> str:
    """``payload`` as the data script ``name`` (a path relative to the report, e.g. ``goods/003.js``)."""
    body = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    return f"(window.PP_DATA=window.PP_DATA||{{}})[{json.dumps(name)}]={body};\n"


def write_data(out: Path, name: str, payload: Any) -> None:
    (out / name).write_text(data_script(name, payload), encoding="utf-8")


# loadData(name): the payload of a data script, loaded once per page; rejects when the file is missing
LOADER_JS = r"""
  window.PP_DATA = window.PP_DATA || {};
  const DATA_LOADS = new Map();
  function loadData(name) {
    if (!DATA_LOADS.has(name)) DATA_LOADS.set(name, new Promise((resolve, reject) => {
      const tag = document.createElement('script');
      tag.src = name;
      tag.onload = () => {
        const data = window.PP_DATA[name];
        delete window.PP_DATA[name];
        tag.remove();
        if (data === undefined) reject(new Error('no data in ' + name)); else resolve(data);
      };
      tag.onerror = () => { DATA_LOADS.delete(name); tag.remove(); reject(new Error('cannot load ' + name)); };
      document.head.appendChild(tag);
    }));
    return DATA_LOADS.get(name);
  }
"""
