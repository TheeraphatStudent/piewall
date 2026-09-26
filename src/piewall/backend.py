"""Windows Defender Firewall access through the HNetCfg.FwPolicy2 COM API."""

from __future__ import annotations

import contextlib
import ctypes
import sys
from ctypes import wintypes
from functools import lru_cache
from typing import Protocol

from .model import (
    ACTIONS,
    DIRECTIONS,
    Rule,
    is_any,
    package_label,
    profiles_from_mask,
    profiles_to_mask,
    protocol_from_num,
    protocol_to_num,
)

_DIRECTION_NAMES = {v: k for k, v in DIRECTIONS.items()}
_ACTION_NAMES = {v: k for k, v in ACTIONS.items()}
_PORTLESS = {"any", "icmpv4", "icmpv6"}


@lru_cache(maxsize=None)
def resolve_indirect(text: str) -> str:
    """'@{Pkg?ms-resource://...}' -> the app's display name ('' if unresolvable)."""
    if not text.startswith("@"):
        return ""
    fn = ctypes.windll.shlwapi.SHLoadIndirectString
    fn.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, ctypes.c_void_p]
    buf = ctypes.create_unicode_buffer(1024)
    return buf.value if fn(text, buf, len(buf), None) == 0 else ""


class Backend(Protocol):
    def list_rules(self) -> list[Rule]: ...
    def add_rule(self, rule: Rule) -> None: ...
    def delete_rules(self, name: str) -> int: ...
    def set_enabled(self, name: str, enabled: bool) -> int: ...
    def set_action(self, name: str, action: str) -> int: ...


class FirewallError(Exception):
    pass


def _com_error_message(exc: Exception) -> str:
    # pywintypes.com_error args: (hresult, text, excepinfo, argerror)
    hresult = getattr(exc, "hresult", None) or (exc.args[0] if exc.args else None)
    if hresult in (-2147024891, 0x80070005):
        return "Access denied: run as administrator."
    return str(exc)


class ComBackend:
    def __init__(self) -> None:
        import win32com.client.dynamic

        # Late binding on purpose: a gen_py cache (if one exists) renames
        # properties (ServiceName -> serviceName).
        self._client = win32com.client.dynamic
        self._policy = self._client.Dispatch("HNetCfg.FwPolicy2")

    def _com_rules(self):
        # Enumeration hands back gen_py-typed items when a cache exists; re-wrap.
        return [self._client.Dispatch(c._oleobj_) for c in self._policy.Rules]

    @staticmethod
    def _to_rule(c) -> Rule:
        return Rule(
            name=c.Name or "",
            enabled=bool(c.Enabled),
            direction=_DIRECTION_NAMES.get(c.Direction, str(c.Direction)),
            action=_ACTION_NAMES.get(c.Action, str(c.Action)),
            protocol=protocol_from_num(c.Protocol),
            local_ports=c.LocalPorts or "",
            program=c.ApplicationName or None,
            service=c.ServiceName or None,
            profiles=profiles_from_mask(c.Profiles),
            group=c.Grouping or "",
            remote_addresses=c.RemoteAddresses or "*",
            description=c.Description or "",
            display_name=resolve_indirect(c.Name or "") or package_label(c.Name or ""),
        )

    def list_rules(self) -> list[Rule]:
        return [self._to_rule(c) for c in self._com_rules()]

    def add_rule(self, rule: Rule) -> None:
        c = self._client.Dispatch("HNetCfg.FWRule")
        try:
            c.Name = rule.name
            c.Description = rule.description
            c.Grouping = rule.group
            c.Direction = DIRECTIONS[rule.direction]
            c.Action = ACTIONS[rule.action]
            c.Protocol = protocol_to_num(rule.protocol)  # must precede ports
            if rule.protocol not in _PORTLESS and not is_any(rule.local_ports):
                c.LocalPorts = rule.local_ports
            if rule.program:
                c.ApplicationName = rule.program
            if rule.service:
                c.ServiceName = rule.service
            if not is_any(rule.remote_addresses):
                c.RemoteAddresses = rule.remote_addresses
            c.Profiles = profiles_to_mask(rule.profiles)
            c.Enabled = rule.enabled
            self._policy.Rules.Add(c)
        except Exception as exc:  # pywintypes.com_error
            raise FirewallError(_com_error_message(exc)) from exc

    def _matching(self, name: str):
        return [c for c in self._com_rules() if c.Name == name]

    def delete_rules(self, name: str) -> int:
        count = len(self._matching(name))
        try:
            # Rules.Remove deletes one rule per call when names repeat.
            for _ in range(count):
                self._policy.Rules.Remove(name)
        except Exception as exc:
            raise FirewallError(_com_error_message(exc)) from exc
        return count

    def _set(self, name: str, attr: str, value) -> int:
        matches = self._matching(name)
        try:
            for c in matches:
                setattr(c, attr, value)
        except Exception as exc:
            raise FirewallError(_com_error_message(exc)) from exc
        return len(matches)

    def set_enabled(self, name: str, enabled: bool) -> int:
        return self._set(name, "Enabled", enabled)

    def set_action(self, name: str, action: str) -> int:
        return self._set(name, "Action", ACTIONS[action])


def default_backend() -> Backend:
    """The live firewall: Windows Defender Firewall, or pf on macOS."""
    if sys.platform == "darwin":
        from .pf import PfBackend

        return PfBackend()
    return ComBackend()


def batch(backend: Backend):
    """Group changes into one commit (on macOS: one password prompt instead of one per rule)."""
    return getattr(backend, "batch", contextlib.nullcontext)()
