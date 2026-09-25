"""Find Block rules that override Allow rules (Windows: block always wins).

Two kinds are reported:

- **full**: the Block rule's scope covers everything the Allow rule allows
  (same or broader program/service/remote scope). Always a real override.
- **live**: the Block rule is scoped to one program and the Allow rule to none,
  so the block only bites for that program. Reported only when that program is
  listening on a port the Allow rule opens right now — the mp4toinc case, where
  a dismissed popup blocked the exe that an 8080 Allow rule was meant for.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .model import Rule, is_any, port_in

# (program path casefolded, protocol, port)
Listener = tuple[str, str, int]


@dataclass(frozen=True)
class Conflict:
    blocker: Rule
    allowed: Rule
    kind: str = "full"  # "full" | "live"
    port: int | None = None  # the live port, for kind == "live"

    def describe(self) -> str:
        a, b = self.allowed, self.blocker
        text = (f"BLOCK '{b.name}' overrides ALLOW '{a.name}' "
                f"({a.direction}, {a.protocol} {a.ports_label}, {b.profiles_label})")
        if self.kind == "live":
            text += f" - {b.program} is listening on {self.port}"
        return text


def _parse_ports(ports: str) -> tuple[list[tuple[int, int]], set[str]]:
    ranges, keywords = [], set()
    for part in ports.split(","):
        part = part.strip()
        lo, _, hi = part.partition("-")
        if lo.isdigit() and (hi or lo).isdigit():
            ranges.append((int(lo), int(hi or lo)))
        elif part:
            keywords.add(part.casefold())
    return ranges, keywords


def ports_overlap(a: str, b: str) -> bool:
    if is_any(a) or is_any(b):
        return True
    ra, ka = _parse_ports(a)
    rb, kb = _parse_ports(b)
    if ka & kb:
        return True
    return any(lo1 <= hi2 and lo2 <= hi1 for lo1, hi1 in ra for lo2, hi2 in rb)


def _covers(block: str | None, allow: str | None) -> bool:
    """Block scope value includes everything the allow scope value includes."""
    return is_any(block) or (not is_any(allow) and block.casefold() == allow.casefold())


def _compatible(a: str | None, b: str | None) -> bool:
    return is_any(a) or is_any(b) or a.casefold() == b.casefold()


def _base_overlap(block: Rule, allow: Rule) -> bool:
    return (
        block.enabled and allow.enabled
        and block.action == "block" and allow.action == "allow"
        and block.direction == allow.direction
        and bool(block.profiles & allow.profiles)
        and (block.protocol == allow.protocol or "any" in (block.protocol, allow.protocol))
        and ports_overlap(block.local_ports, allow.local_ports)
        and _compatible(block.service, allow.service)
        and _covers(block.remote_addresses, allow.remote_addresses)
    )


def _live_port(block: Rule, allow: Rule, listeners: Iterable[Listener]) -> int | None:
    program = block.program.casefold()
    for prog, proto, port in listeners:
        if (prog == program
                and (allow.protocol in ("any", proto)) and (block.protocol in ("any", proto))
                and port_in(port, allow.local_ports) and port_in(port, block.local_ports)):
            return port
    return None


def find_conflicts(rules: Iterable[Rule], listeners: Iterable[Listener] = ()) -> list[Conflict]:
    rules = list(rules)
    listeners = list(listeners)
    blocks = [r for r in rules if r.enabled and r.action == "block"]
    allows = [r for r in rules if r.enabled and r.action == "allow"]
    found = []
    for b in blocks:
        for a in allows:
            if not _base_overlap(b, a):
                continue
            if _covers(b.program, a.program) and _covers(b.service, a.service):
                found.append(Conflict(b, a))
            elif not is_any(b.program) and is_any(a.program) and _covers(b.service, a.service):
                # inbound allow only: listeners are local ports
                if a.direction == "in" and not is_any(a.local_ports):
                    port = _live_port(b, a, listeners)
                    if port is not None:
                        found.append(Conflict(b, a, "live", port))
    return found
