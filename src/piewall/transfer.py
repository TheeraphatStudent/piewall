"""Export / import rules as JSON, and a read-only backend over an export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .backend import Backend, FirewallError
from .conflicts import Listener
from .model import PIEWALL_GROUP, Rule

FORMAT_VERSION = 1


def export_rules(rules: Iterable[Rule], path: Path, *, piewall_only: bool = False,
                 listeners: Iterable[Listener] = ()) -> int:
    """Write rules (and a snapshot of listening programs, for offline conflict checks)."""
    rules = [r for r in rules if not piewall_only or r.group == PIEWALL_GROUP]
    payload = {"version": FORMAT_VERSION, "rules": [r.to_dict() for r in rules],
               "listeners": [list(item) for item in listeners]}
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(rules)


def load_export(path: Path) -> tuple[list[Rule], list[Listener]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != FORMAT_VERSION:
        raise ValueError(f"unsupported rules file version: {data.get('version')!r}")
    rules = [Rule.from_dict(d) for d in data["rules"]]
    listeners = [(str(prog), str(proto), int(port)) for prog, proto, port in data.get("listeners", [])]
    return rules, listeners


def load_rules(path: Path) -> list[Rule]:
    return load_export(path)[0]


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


class FileBackend:
    """Rules from an export file. Read-only: works on any OS (e.g. in a container)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._rules, self._listeners = load_export(self.path)

    def list_rules(self) -> list[Rule]:
        return list(self._rules)

    def listeners(self) -> list[Listener]:
        return list(self._listeners)

    def _read_only(self, *_args) -> int:
        raise FirewallError(f"{self.path.name} is a read-only export; changes need the live "
                            f"firewall on Windows or macOS.")

    add_rule = delete_rules = set_enabled = set_action = _read_only
