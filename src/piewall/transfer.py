"""Export / import rules as JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .backend import Backend
from .model import PIEWALL_GROUP, Rule

FORMAT_VERSION = 1


def export_rules(rules: Iterable[Rule], path: Path, *, piewall_only: bool = False) -> int:
    rules = [r for r in rules if not piewall_only or r.group == PIEWALL_GROUP]
    payload = {"version": FORMAT_VERSION, "rules": [r.to_dict() for r in rules]}
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(rules)


def load_rules(path: Path) -> list[Rule]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != FORMAT_VERSION:
        raise ValueError(f"unsupported rules file version: {data.get('version')!r}")
    return [Rule.from_dict(d) for d in data["rules"]]


def import_rules(backend: Backend, path: Path) -> tuple[int, int]:
    """Add rules from `path` that don't already exist identically. Returns (added, skipped)."""
    existing = set(backend.list_rules())
    added = skipped = 0
    for rule in load_rules(path):
        if rule in existing:
            skipped += 1
            continue
        backend.add_rule(rule)
        existing.add(rule)
        added += 1
    return added, skipped
