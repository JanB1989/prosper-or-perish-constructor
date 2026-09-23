"""YAML loading through libyaml when it is installed.

The pure-Python loader dominated blueprint-heavy runs (thousands of blueprint loads per build and test
session); the C loader returns the same data about nine times faster.
"""

from __future__ import annotations

import yaml

SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def safe_load(stream):
    return yaml.load(stream, Loader=SafeLoader)
