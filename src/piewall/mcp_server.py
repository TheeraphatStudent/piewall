"""piewall MCP server: firewall tools for AI agents.

Live mode (Windows): the real Windows Defender Firewall. Reads are direct;
changes run the piewall CLI, which relaunches through UAC when not elevated,
so a human approves every change on the desktop.

File mode (any OS, e.g. a container): read-only tools over a rules JSON made
by `piewall export`, including its snapshot of listening programs.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Annotated, Any, Callable, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from pydantic import Field

from . import cli
from .backend import Backend
from .conflicts import Listener, find_conflicts
from .elevate import is_admin, run_elevated
from .model import Rule, filter_rules
from .update import current_version

CLI_COMMANDS = {"list", "open", "close", "enable", "disable", "delete", "allow", "block",
                "conflicts", "export", "import"}

INSTRUCTIONS = """\
Tools for Windows Defender Firewall rules (piewall).
- Start with `status`, then read with `list_rules` / `find_conflicts` before changing anything.
- Windows always lets Block win: when a port "refuses to connect" although an Allow rule
  exists, run `find_conflicts`.
- Prefer the smallest change: `open_port` / `close_port` only touch rules in the 'piewall'
  group. Ask the user before deleting or blocking rules piewall did not create.
- Every change shows a UAC prompt (Windows) or an administrator password prompt (macOS) on
  the user's desktop; tell the user to expect it.
"""

READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
ADD = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                      open_world_hint=False)
CHANGE = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True,
                         open_world_hint=False)
DESTROY = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False,
                          open_world_hint=False)

Port = Annotated[int, Field(ge=1, le=65535, description="Local port, 1-65535")]
RuleName = Annotated[str, Field(min_length=1, description="Exact rule name (all rules with "
                                                          "this name are affected)")]


version = current_version


def rule_json(r: Rule, *, full: bool = False) -> dict[str, Any]:
    d = {"name": r.name, "title": r.title, "enabled": r.enabled, "action": r.action,
         "direction": r.direction, "protocol": r.protocol, "ports": r.ports_label,
         "profiles": sorted(r.profiles), "program": r.program, "group": r.group}
    if full:
        d.update(service=r.service, remote_addresses=r.remote_addresses,
                 description=r.description)
    return d


def build_server(backend: Backend, *, live: bool, listeners: Callable[[], list[Listener]],
                 admin_check: Callable[[], bool] = is_admin, elevator=None,
                 source: str = "Windows Defender Firewall") -> MCPServer:
    elevator = elevator or run_elevated
    server = MCPServer(
        name="piewall", title="piewall firewall", version=version(),
        instructions=INSTRUCTIONS, website_url="https://piewall.th33raphat.dev")

    def run_cli(*argv: str) -> dict[str, Any]:
        code, output = cli.execute(list(argv), backend_factory=lambda: backend,
                                   admin_check=admin_check, elevator=elevator)
        if code != 0:
            raise ToolError(output.strip() or f"piewall exited with code {code}")
        return {"ok": True, "output": output.strip()}

    @server.tool(annotations=READ)
    def status() -> dict[str, Any]:
        """Where rules come from, how many there are, and whether changes are possible."""
        return {"mode": "live" if live else "file", "source": source,
                "rules": len(backend.list_rules()), "can_change": live,
                "admin": bool(admin_check()) if live else False, "version": version()}

    @server.tool(annotations=READ)
    def list_rules(
        search: Annotated[str, Field(description="Text in name, program or group")] = "",
        port: Annotated[int | None, Field(ge=1, le=65535,
                                          description="Rules that name this local port")] = None,
        any_port: Annotated[bool, Field(description="With port: also rules open to every "
                                                    "port, e.g. per-program rules")] = False,
        action: Literal["allow", "block"] | None = None,
        direction: Literal["in", "out"] | None = None,
        enabled: bool | None = None,
        limit: Annotated[int, Field(ge=1, le=500)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict[str, Any]:
        """List firewall rules matching all given filters, sorted by name."""
        rules = backend.list_rules()
        matched = filter_rules(rules, search=search, port=port, any_port=any_port,
                               action=action, direction=direction, enabled=enabled)
        matched.sort(key=lambda r: r.title.casefold())
        page = matched[offset:offset + limit]
        nxt = offset + limit if offset + limit < len(matched) else None
        return {"total": len(rules), "matched": len(matched),
                "rules": [rule_json(r) for r in page], "next_offset": nxt}

    @server.tool(annotations=READ)
    def rule_details(name: RuleName) -> dict[str, Any]:
        """Every field of the rule(s) with this exact name."""
        found = [rule_json(r, full=True) for r in backend.list_rules() if r.name == name]
        if not found:
            raise ToolError(f"No rule named {name!r}. Use list_rules(search=...) to find it.")
        return {"rules": found}

    @server.tool(name="find_conflicts", annotations=READ)
    def conflicts_tool() -> dict[str, Any]:
        """Block rules that override Allow rules (Windows always lets Block win)."""
        found = find_conflicts(backend.list_rules(), listeners())
        blockers = sorted({c.blocker.name for c in found})
        return {
            "conflicts": [{"blocker": rule_json(c.blocker), "allowed": rule_json(c.allowed),
                           "kind": c.kind, "port": c.port, "description": c.describe()}
                          for c in found],
            "fix_suggestions": [f"set_rule_action(name={n!r}, action='allow') or "
                                f"set_rule_enabled(name={n!r}, enabled=False)" for n in blockers],
            "listener_data": "live" if live else ("snapshot" if listeners() else "none"),
        }

    if not live:
        return server

    @server.tool(annotations=ADD)
    def open_port(
        port: Port,
        protocol: Literal["tcp", "udp", "any"] = "tcp",
        direction: Literal["in", "out"] = "in",
        profiles: Annotated[list[Literal["any", "domain", "private", "public"]],
                            Field(min_length=1)] = ["any"],  # noqa: B006
        name: Annotated[str | None, Field(description="Default: 'piewall TCP <port> in'")] = None,
    ) -> dict[str, Any]:
        """Allow a port by adding a rule in the 'piewall' group. Shows a UAC prompt."""
        argv = ["open", str(port), "--dir", direction, "--profile", *profiles]
        if protocol == "udp":
            argv.append("--udp")
        elif protocol == "any":
            argv.append("--any-protocol")
        if name:
            argv += ["--name", name]
        return run_cli(*argv)

    @server.tool(annotations=DESTROY)
    def close_port(port: Port) -> dict[str, Any]:
        """Delete the rules piewall created for this port (never other rules). UAC prompt."""
        return run_cli("close", str(port))

    @server.tool(annotations=CHANGE)
    def set_rule_enabled(name: RuleName, enabled: bool) -> dict[str, Any]:
        """Enable or disable rules by exact name. Shows a UAC prompt."""
        return run_cli("enable" if enabled else "disable", name)

    @server.tool(annotations=CHANGE)
    def set_rule_action(name: RuleName, action: Literal["allow", "block"]) -> dict[str, Any]:
        """Make rules with this exact name Allow or Block. Shows a UAC prompt."""
        return run_cli(action, name)

    @server.tool(annotations=DESTROY)
    def delete_rule(name: RuleName) -> dict[str, Any]:
        """Permanently delete every rule with this exact name. Ask the user first. UAC prompt."""
        return run_cli("delete", name)

    @server.tool(annotations=ADD)
    def export_rules(
        path: Annotated[str, Field(description="JSON file path on this machine")],
        piewall_only: bool = False,
    ) -> dict[str, Any]:
        """Save rules and a listening-ports snapshot to JSON (for backup or the container)."""
        argv = ["export", str(Path(path).expanduser().resolve())]
        if piewall_only:
            argv.append("--piewall-only")
        return run_cli(*argv)

    return server


def allowed_hosts(extra: list[str]) -> list[str]:
    return ["localhost:*", "127.0.0.1:*", "[::1]:*", *extra]


def _parser() -> argparse.ArgumentParser:
    env = os.environ.get
    p = argparse.ArgumentParser(prog="piewall-mcp", description="piewall MCP server.")
    p.add_argument("--rules-file", default=env("PIEWALL_RULES_FILE"),
                   help="read-only mode over a `piewall export` JSON (env PIEWALL_RULES_FILE)")
    p.add_argument("--transport", choices=["stdio", "streamable-http"],
                   default=env("PIEWALL_TRANSPORT", "stdio"))
    p.add_argument("--host", default=env("PIEWALL_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(env("PIEWALL_PORT", "8000")))
    p.add_argument("--allowed-host", action="append",
                   default=[h for h in env("PIEWALL_ALLOWED_HOSTS", "").split(",") if h],
                   help="extra Host header allowed over HTTP (repeatable)")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # The frozen piewall-mcp.exe doubles as the CLI for UAC relaunches.
    if argv and (argv[0] in CLI_COMMANDS or argv[0] == "--elevated-output"):
        return cli.main(argv)

    args = _parser().parse_args(argv)
    if args.rules_file:
        from .transfer import FileBackend

        backend = FileBackend(Path(args.rules_file))
        server = build_server(backend, live=False, listeners=backend.listeners,
                              source=str(args.rules_file))
    elif sys.platform in ("win32", "darwin"):
        from .backend import default_backend
        from .listeners import current_listeners

        source = "Windows Defender Firewall" if sys.platform == "win32" else "macOS pf"
        server = build_server(default_backend(), live=True, listeners=current_listeners,
                              source=source)
    else:
        print("piewall-mcp: the live firewall needs Windows or macOS. Pass "
              "--rules-file (or PIEWALL_RULES_FILE) with a JSON made by `piewall export`.",
              file=sys.stderr)
        return 2

    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port,
                   transport_security=TransportSecuritySettings(
                       allowed_hosts=allowed_hosts(args.allowed_host)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
