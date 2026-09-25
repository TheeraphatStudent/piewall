import json

from piewall.model import PIEWALL_GROUP, Rule
from piewall.transfer import export_rules, import_rules

from fakes import FakeBackend

A = Rule(name="a", enabled=True, direction="in", action="allow", protocol="tcp",
         local_ports="8080", group=PIEWALL_GROUP)
B = Rule(name="b", enabled=False, direction="out", action="block", program=r"C:\x.exe")


def test_export_writes_versioned_json(tmp_path):
    path = tmp_path / "rules.json"
    assert export_rules([A, B], path) == 2
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert [Rule.from_dict(d) for d in data["rules"]] == [A, B]


def test_export_piewall_only(tmp_path):
    path = tmp_path / "rules.json"
    assert export_rules([A, B], path, piewall_only=True) == 1


def test_import_adds_missing_and_skips_identical(tmp_path):
    path = tmp_path / "rules.json"
    export_rules([A, B], path)
    backend = FakeBackend([A])
    added, skipped = import_rules(backend, path)
    assert (added, skipped) == (1, 1)
    assert backend.rules == [A, B]


def test_export_includes_listener_snapshot_and_display_names(tmp_path):
    from piewall.transfer import load_export

    path = tmp_path / "rules.json"
    named = Rule(name="@{Pkg?ms-resource://x}", enabled=True, direction="in", action="allow",
                 display_name="Spotify")
    export_rules([named], path, listeners=[(r"c:\app.exe", "tcp", 8080)])
    rules, listeners = load_export(path)
    assert rules[0].title == "Spotify"
    assert listeners == [(r"c:\app.exe", "tcp", 8080)]


def test_old_exports_without_listeners_still_load(tmp_path):
    from piewall.transfer import load_export

    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"version": 1, "rules": [A.to_dict()]}), encoding="utf-8")
    assert load_export(path) == ([A], [])


def test_file_backend_is_read_only(tmp_path):
    import pytest

    from piewall.backend import FirewallError
    from piewall.transfer import FileBackend

    path = tmp_path / "rules.json"
    export_rules([A, B], path, listeners=[("x.exe", "udp", 53)])
    fb = FileBackend(path)
    assert fb.list_rules() == [A, B]
    assert fb.listeners() == [("x.exe", "udp", 53)]
    with pytest.raises(FirewallError, match="read-only"):
        fb.delete_rules("a")
