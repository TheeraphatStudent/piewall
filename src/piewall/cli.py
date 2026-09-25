"""piewall command line."""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import tempfile
from pathlib import Path
from typing import Callable

from .backend import Backend, FirewallError
from .conflicts import find_conflicts
from .elevate import ElevationCancelled, is_admin, run_elevated
from .listeners import current_listeners
from .model import PIEWALL_GROUP, Rule, filter_rules, is_any, parse_profiles, port_in
from .transfer import export_rules, import_rules

MUTATING = {"open", "close", "enable", "disable", "delete", "allow", "block", "import"}
EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_CANCELLED = 0, 1, 2, 3


def _port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port must be 1-65535, got {port}")
    return port


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="piewall", description="Manage Windows Firewall rules.")
    p.add_argument("--elevated-output", help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    ls = sub.add_parser("list", help="list rules (filters combine)")
    ls.add_argument("--search", "-s", default="", help="text in name, program or group")
    ls.add_argument("--port", "-p", type=_port, help="rules that name this local port")
    ls.add_argument("--any-port", action="store_true",
                    help="with --port: also rules open to every port (e.g. per-program rules)")
    ls.add_argument("--action", choices=["allow", "block"])
    ls.add_argument("--dir", choices=["in", "out"], dest="direction")
    state = ls.add_mutually_exclusive_group()
    state.add_argument("--enabled", action="store_const", const=True, dest="enabled")
    state.add_argument("--disabled", action="store_const", const=False, dest="enabled")

    op = sub.add_parser("open", help="allow a port (creates a rule in the 'piewall' group)")
    op.add_argument("port", type=_port)
    proto = op.add_mutually_exclusive_group()
    proto.add_argument("--udp", action="store_const", const="udp", dest="protocol")
    proto.add_argument("--any-protocol", action="store_const", const="any", dest="protocol")
    op.add_argument("--dir", choices=["in", "out"], default="in", dest="direction")
    op.add_argument("--profile", nargs="+", default=["any"],
                    choices=["any", "domain", "private", "public"])
    op.add_argument("--name", help="rule name (default: 'piewall TCP <port> in')")

    cl = sub.add_parser("close", help="delete the piewall rules that opened a port")
    cl.add_argument("port", type=_port)

    for name, text in [("enable", "enable rules by name"), ("disable", "disable rules by name"),
                       ("delete", "delete rules by name"), ("allow", "make rules allow"),
                       ("block", "make rules block")]:
        sub.add_parser(name, help=text).add_argument("name", help="exact rule name")

    sub.add_parser("conflicts", help="show Block rules overriding Allow rules")

    ex = sub.add_parser("export", help="save rules to a JSON file")
    ex.add_argument("file", type=Path)
    ex.add_argument("--piewall-only", action="store_true", help="only rules piewall created")

    im = sub.add_parser("import", help="add rules from a JSON file (skips identical ones)")
    im.add_argument("file", type=Path)

    sub.add_parser("gui", help="open the window")
    return p


def _short_program(program: str | None) -> str:
    return Path(program).name if program else ""


def print_table(rules: list[Rule], total: int) -> None:
    headers = ["On", "Action", "Dir", "Proto", "Ports", "Profiles", "Name", "Program"]
    rows = [["yes" if r.enabled else "no", r.action.upper(), r.direction, r.protocol,
             r.ports_label, r.profiles_label, r.title, _short_program(r.program)] for r in rules]
    caps = [3, 6, 3, 6, 18, 22, 48, 30]
    rows = [[c if len(c) <= cap else c[: cap - 3] + "..." for c, cap in zip(row, caps)] for row in rows]
    widths = [max([len(h)] + [len(row[i]) for row in rows]) for i, h in enumerate(headers)]
    for row in [headers, *rows]:
        print("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip())
    print(f"\n{len(rules)} of {total} rules")


def _by_name(backend: Backend, name: str, op: Callable[[], int], done: str) -> int:
    count = op()
    if count == 0:
        print(f"No rule named '{name}'. Try: piewall list --search \"{name}\"", file=sys.stderr)
        return EXIT_FAIL
    print(f"{done} {count} rule(s) named '{name}'.")
    return EXIT_OK


def run_command(args: argparse.Namespace, backend: Backend) -> int:
    cmd = args.command
    if cmd == "list":
        rules = backend.list_rules()
        shown = filter_rules(rules, search=args.search, port=args.port, action=args.action,
                             direction=args.direction, enabled=args.enabled,
                             any_port=args.any_port)
        print_table(sorted(shown, key=lambda r: r.title.casefold()), len(rules))
        return EXIT_OK

    if cmd == "open":
        protocol = args.protocol or "tcp"
        rule = Rule(
            name=args.name or f"piewall {protocol.upper()} {args.port} {args.direction}",
            enabled=True, direction=args.direction, action="allow", protocol=protocol,
            local_ports=str(args.port), profiles=parse_profiles(args.profile),
            group=PIEWALL_GROUP, description="Created by piewall",
        )
        backend.add_rule(rule)
        print(f"Opened port {args.port} ({protocol}, {args.direction}, {rule.profiles_label}) "
              f"as rule '{rule.name}'.")
        return EXIT_OK

    if cmd == "close":
        names = sorted({r.name for r in backend.list_rules()
                        if r.group == PIEWALL_GROUP and not is_any(r.local_ports)
                        and port_in(args.port, r.local_ports)})
        if not names:
            print(f"No piewall rules open port {args.port}. (Rules made elsewhere are never "
                  f"touched by close; use 'piewall list --port {args.port}'.)", file=sys.stderr)
            return EXIT_FAIL
        for name in names:
            backend.delete_rules(name)
            print(f"Deleted '{name}'.")
        return EXIT_OK

    if cmd in ("enable", "disable"):
        on = cmd == "enable"
        return _by_name(backend, args.name, lambda: backend.set_enabled(args.name, on),
                        "Enabled" if on else "Disabled")
    if cmd in ("allow", "block"):
        return _by_name(backend, args.name, lambda: backend.set_action(args.name, cmd),
                        f"Set to {cmd.upper()}:")
    if cmd == "delete":
        return _by_name(backend, args.name, lambda: backend.delete_rules(args.name), "Deleted")

    if cmd == "conflicts":
        conflicts = find_conflicts(backend.list_rules(), current_listeners())
        if not conflicts:
            print("No conflicts: no Block rule is overriding an Allow rule.")
            return EXIT_OK
        for c in conflicts:
            print(c.describe())
        blockers = sorted({c.blocker.name for c in conflicts})
        print(f"\n{len(conflicts)} conflict(s). To fix, flip or remove the blocking rule:")
        for name in blockers:
            print(f'  piewall allow "{name}"    or    piewall delete "{name}"')
        return EXIT_FAIL

    if cmd == "export":
        n = export_rules(backend.list_rules(), args.file, piewall_only=args.piewall_only)
        print(f"Exported {n} rule(s) to {args.file}.")
        return EXIT_OK
    if cmd == "import":
        added, skipped = import_rules(backend, args.file)
        print(f"Imported {added} rule(s), skipped {skipped} already present.")
        return EXIT_OK

    raise AssertionError(f"unhandled command {cmd}")


def _relaunch_elevated(argv: list[str], elevator) -> int:
    fd, out_file = tempfile.mkstemp(prefix="piewall-", suffix=".txt")
    os.close(fd)
    try:
        try:
            code = elevator(["piewall", "--elevated-output", out_file, *argv], wait=True)
        except ElevationCancelled:
            print("UAC prompt cancelled; nothing changed.", file=sys.stderr)
            return EXIT_CANCELLED
        print(Path(out_file).read_text(encoding="utf-8"), end="")
        return code
    finally:
        Path(out_file).unlink(missing_ok=True)


def main(argv: list[str] | None = None, *, backend_factory=None, admin_check=is_admin,
         elevator=run_elevated) -> int:
    argv = sys.argv[1:] if argv is None else argv
    for stream in (sys.stdout, sys.stderr):
        # Rule names can hold characters the console codepage can't show.
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE

    if args.command == "gui":
        from .gui import main as gui_main

        gui_main()
        return EXIT_OK

    if args.command in MUTATING and not admin_check():
        if args.elevated_output:  # already relaunched once; don't loop
            print("Still not elevated after UAC relaunch.", file=sys.stderr)
            return EXIT_FAIL
        return _relaunch_elevated(argv, elevator)

    if backend_factory is None:
        from .backend import ComBackend as backend_factory

    with contextlib.ExitStack() as stack:
        if args.elevated_output:
            f = stack.enter_context(open(args.elevated_output, "w", encoding="utf-8"))
            stack.enter_context(contextlib.redirect_stdout(f))
            stack.enter_context(contextlib.redirect_stderr(f))
        try:
            return run_command(args, backend_factory())
        except (FirewallError, OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
