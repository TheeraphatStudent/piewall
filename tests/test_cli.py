import json

import pytest

from piewall import cli
from piewall.elevate import ElevationCancelled
from piewall.model import ALL_PROFILES, PIEWALL_GROUP, Rule

from fakes import FakeBackend


def rule(**kw) -> Rule:
    base = dict(name="r", enabled=True, direction="in", action="allow",
                protocol="tcp", local_ports="8080")
    base.update(kw)
    return Rule(**base)


@pytest.fixture
def backend():
    return FakeBackend([
        rule(name="web", local_ports="8080"),
        rule(name="mp4toinc-ui", action="block", local_ports="*",
             program=r"D:\mp4toinc\mp4toinc-ui.exe", profiles=frozenset({"public"})),
        rule(name="ssh", local_ports="22", enabled=False),
    ])


def run(backend, *argv, admin=True, elevator=None):
    return cli.main(list(argv), backend_factory=lambda: backend,
                    admin_check=lambda: admin, elevator=elevator)


def test_list_filters(backend, capsys):
    assert run(backend, "list", "--port", "8080") == 0
    out = capsys.readouterr().out
    assert "web" in out and "mp4toinc-ui" not in out and "1 of 3 rules" in out
    assert run(backend, "list", "--port", "8080", "--any-port") == 0
    out = capsys.readouterr().out
    assert "web" in out and "mp4toinc-ui" in out and "ssh" not in out
    assert "2 of 3 rules" in out


def test_list_disabled_and_action(backend, capsys):
    run(backend, "list", "--disabled")
    assert "ssh" in capsys.readouterr().out
    run(backend, "list", "--action", "block")
    out = capsys.readouterr().out
    assert "mp4toinc-ui" in out and "web" not in out


def test_open_creates_piewall_rule(backend, capsys):
    assert run(backend, "open", "9000", "--profile", "public") == 0
    new = backend.rules[-1]
    assert new == Rule(name="piewall TCP 9000 in", enabled=True, direction="in", action="allow",
                       protocol="tcp", local_ports="9000", profiles=frozenset({"public"}),
                       group=PIEWALL_GROUP, description="Created by piewall")
    assert "Opened" in capsys.readouterr().out


def test_open_defaults_to_any_profile_and_accepts_udp_and_name(backend):
    run(backend, "open", "5353", "--udp", "--name", "mdns")
    new = backend.rules[-1]
    assert (new.name, new.protocol, new.profiles) == ("mdns", "udp", ALL_PROFILES)


def test_open_rejects_bad_port(backend, capsys):
    assert run(backend, "open", "70000") == 2


def test_close_removes_only_piewall_rules_for_port(backend, capsys):
    run(backend, "open", "8080")
    assert run(backend, "close", "8080") == 0
    names = [r.name for r in backend.rules]
    assert "piewall TCP 8080 in" not in names
    assert "web" in names  # not piewall-made: untouched


def test_close_nothing_to_close(backend, capsys):
    assert run(backend, "close", "1234") == 1
    assert "No piewall rules" in capsys.readouterr().err


def test_enable_disable_allow_block_delete(backend, capsys):
    assert run(backend, "enable", "ssh") == 0
    assert next(r for r in backend.rules if r.name == "ssh").enabled
    assert run(backend, "allow", "mp4toinc-ui") == 0
    assert next(r for r in backend.rules if r.name == "mp4toinc-ui").action == "allow"
    assert run(backend, "delete", "ssh") == 0
    assert "ssh" not in [r.name for r in backend.rules]


def test_unknown_rule_name(backend, capsys):
    assert run(backend, "disable", "nope") == 1
    assert "No rule named 'nope'" in capsys.readouterr().err


def test_conflicts_none(backend, capsys, monkeypatch):
    monkeypatch.setattr(cli, "current_listeners", lambda: [])
    assert run(backend, "conflicts") == 0
    assert "No conflicts" in capsys.readouterr().out


def test_conflicts_found(backend, capsys, monkeypatch):
    monkeypatch.setattr(cli, "current_listeners",
                        lambda: [(r"d:\mp4toinc\mp4toinc-ui.exe", "tcp", 8080)])
    backend.rules[1] = rule(name="mp4toinc-ui", action="block", local_ports="*",
                            program=r"D:\mp4toinc\mp4toinc-ui.exe")
    assert run(backend, "conflicts") == 1
    out = capsys.readouterr().out
    assert "BLOCK 'mp4toinc-ui' overrides ALLOW 'web'" in out
    assert "piewall allow" in out  # suggests the fix


def test_export_import(backend, tmp_path, capsys):
    path = tmp_path / "r.json"
    assert run(backend, "export", str(path)) == 0
    assert len(json.loads(path.read_text())["rules"]) == 3
    fresh = FakeBackend()
    assert run(fresh, "import", str(path)) == 0
    assert len(fresh.rules) == 3


def test_mutation_without_admin_elevates_and_relays_output(backend, capsys):
    calls = []

    def elevator(module_args, *, wait):
        calls.append(module_args)
        out_file = module_args[module_args.index("--elevated-output") + 1]
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("Opened port 9000\n")
        return 0

    assert run(backend, "open", "9000", admin=False, elevator=elevator) == 0
    assert calls[0][0] == "piewall" and calls[0][-2:] == ["open", "9000"]
    assert "Opened port 9000" in capsys.readouterr().out
    assert len(backend.rules) == 3  # nothing changed in the unelevated process


def test_uac_cancelled(backend, capsys):
    def elevator(module_args, *, wait):
        raise ElevationCancelled

    assert run(backend, "delete", "web", admin=False, elevator=elevator) == 3
    assert "cancelled" in capsys.readouterr().err


def test_reads_never_elevate(backend):
    def elevator(module_args, *, wait):
        raise AssertionError("should not elevate")

    assert run(backend, "list", admin=False, elevator=elevator) == 0


def test_execute_captures_output_instead_of_printing(backend, capsys):
    code, text = cli.execute(["disable", "web"], backend_factory=lambda: backend,
                             admin_check=lambda: True)
    assert code == 0 and "Disabled 1 rule(s) named 'web'" in text
    assert capsys.readouterr().out == ""


def test_execute_relays_elevated_output(backend, capsys):
    def elevator(module_args, *, wait):
        out_file = module_args[module_args.index("--elevated-output") + 1]
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("Deleted 1 rule(s) named 'web'.\n")
        return 0

    code, text = cli.execute(["delete", "web"], backend_factory=lambda: backend,
                             admin_check=lambda: False, elevator=elevator)
    assert (code, text) == (0, "Deleted 1 rule(s) named 'web'.\n")
    assert capsys.readouterr().out == ""


def test_export_includes_listeners(backend, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "current_listeners", lambda: [("x.exe", "tcp", 1)])
    path = tmp_path / "r.json"
    run(backend, "export", str(path))
    assert json.loads(path.read_text())["listeners"] == [["x.exe", "tcp", 1]]
