"""Firewall rule model and pure helpers. No Windows imports here."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

PYWALL_GROUP = "pywall"

# NET_FW_PROFILE2_* bit flags; "all" is the value Windows stores for "Any".
PROFILE_BITS = {"domain": 1, "private": 2, "public": 4}
PROFILE_ALL = 0x7FFFFFFF
ALL_PROFILES = frozenset(PROFILE_BITS)

PROTOCOLS = {"tcp": 6, "udp": 17, "any": 256, "icmpv4": 1, "icmpv6": 58}
_PROTOCOL_NAMES = {v: k for k, v in PROTOCOLS.items()}

DIRECTIONS = {"in": 1, "out": 2}
ACTIONS = {"block": 0, "allow": 1}


def protocol_from_num(num: int) -> str:
    return _PROTOCOL_NAMES.get(num, str(num))


def protocol_to_num(name: str) -> int:
    return PROTOCOLS[name] if name in PROTOCOLS else int(name)


def profiles_from_mask(mask: int) -> frozenset[str]:
    if mask == PROFILE_ALL:
        return ALL_PROFILES
    return frozenset(p for p, bit in PROFILE_BITS.items() if mask & bit)


def profiles_to_mask(profiles: Iterable[str]) -> int:
    profiles = frozenset(profiles)
    if profiles >= ALL_PROFILES:
        return PROFILE_ALL
    return sum(PROFILE_BITS[p] for p in profiles)


def parse_profiles(values: Iterable[str]) -> frozenset[str]:
    """CLI/GUI profile names -> profile set; 'any' means all three."""
    values = [v.lower() for v in values]
    if "any" in values:
        return ALL_PROFILES
    return frozenset(values)


def is_any(value: str | None) -> bool:
    return value in (None, "", "*")


@dataclass(frozen=True)
class Rule:
    name: str
    enabled: bool
    direction: str  # "in" | "out"
    action: str  # "allow" | "block"
    protocol: str = "any"  # "tcp" | "udp" | "any" | "icmpv4" | number
    local_ports: str = ""  # "" or "*" = any; "80,443,8000-8010"; keywords like "RPC"
    program: str | None = None
    service: str | None = None
    profiles: frozenset[str] = field(default=ALL_PROFILES)
    group: str = ""
    remote_addresses: str = "*"
    description: str = ""
    # Friendly name for "@{Package?ms-resource://...}" names; `name` stays the key.
    display_name: str = field(default="", compare=False)

    @property
    def title(self) -> str:
        return self.display_name or self.name

    @property
    def profiles_label(self) -> str:
        if self.profiles >= ALL_PROFILES:
            return "Any"
        order = ["domain", "private", "public"]
        return ", ".join(p.capitalize() for p in order if p in self.profiles)

    @property
    def ports_label(self) -> str:
        return "Any" if is_any(self.local_ports) else self.local_ports

    def to_dict(self) -> dict:
        d = asdict(self)
        d["profiles"] = sorted(self.profiles)
        del d["display_name"]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Rule:
        d = dict(d)
        d["profiles"] = frozenset(d.get("profiles", ALL_PROFILES))
        return cls(**d)


def package_label(name: str) -> str:
    """'@{Microsoft.Foo_1.0_x64__id?ms-resource://...}' -> 'Microsoft.Foo'."""
    if not name.startswith("@{"):
        return ""
    return name[2:].split("?")[0].split("_")[0]


def port_in(port: int, ports: str) -> bool:
    """True when `port` is covered by a LocalPorts string. Keywords never match a number."""
    if is_any(ports):
        return True
    for part in ports.split(","):
        part = part.strip()
        lo, _, hi = part.partition("-")
        if lo.isdigit() and (hi or lo).isdigit() and int(lo) <= port <= int(hi or lo):
            return True
    return False


def filter_rules(
    rules: Iterable[Rule],
    *,
    search: str = "",
    port: int | None = None,
    action: str | None = None,
    direction: str | None = None,
    enabled: bool | None = None,
    any_port: bool = False,
) -> list[Rule]:
    """`port` matches rules that name the port; `any_port` adds rules open to every port."""
    needle = search.casefold()
    out = []
    for r in rules:
        if needle and not any(needle in (s or "").casefold() for s in (r.name, r.display_name, r.program, r.group)):
            continue
        if port is not None:
            if is_any(r.local_ports) and not any_port:
                continue
            if not port_in(port, r.local_ports):
                continue
        if action and r.action != action:
            continue
        if direction and r.direction != direction:
            continue
        if enabled is not None and r.enabled != enabled:
            continue
        out.append(r)
    return out
