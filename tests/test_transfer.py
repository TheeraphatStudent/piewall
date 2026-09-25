import json

from pywall.model import PYWALL_GROUP, Rule
from pywall.transfer import export_rules, import_rules

from fakes import FakeBackend

A = Rule(name="a", enabled=True, direction="in", action="allow", protocol="tcp",
         local_ports="8080", group=PYWALL_GROUP)
B = Rule(name="b", enabled=False, direction="out", action="block", program=r"C:\x.exe")


def test_export_writes_versioned_json(tmp_path):
    path = tmp_path / "rules.json"
    assert export_rules([A, B], path) == 2
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert [Rule.from_dict(d) for d in data["rules"]] == [A, B]


def test_export_pywall_only(tmp_path):
    path = tmp_path / "rules.json"
    assert export_rules([A, B], path, pywall_only=True) == 1


def test_import_adds_missing_and_skips_identical(tmp_path):
    path = tmp_path / "rules.json"
    export_rules([A, B], path)
    backend = FakeBackend([A])
    added, skipped = import_rules(backend, path)
    assert (added, skipped) == (1, 1)
    assert backend.rules == [A, B]
