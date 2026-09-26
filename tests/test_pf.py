"""pf rendering and commits. The fake runner stands in for the root shell; no firewall is touched."""

import json

import pytest

from piewall.backend import FirewallError, batch
from piewall.elevate import ElevationCancelled
from piewall.model import Rule
from piewall.pf import PfBackend, render, render_rule


def rule(name="r", **kw):
    base = dict(enabled=True, direction="in", action="allow", protocol="tcp", local_ports="22")
    return Rule(name=name, **{**base, **kw})


def test_render_rule():
    assert render_rule(rule()) == 'pass in proto tcp from any to any port 22 label "r"'
    assert render_rule(rule(action="block", direction="out", protocol="udp",
                            local_ports="53,8000-8010", remote_addresses="10.0.0.1")) == \
        'block out proto udp from any port { 53 8000:8010 } to 10.0.0.1 label "r"'
    assert render_rule(rule(protocol="any", local_ports="80")).startswith(
        "pass in proto { tcp udp } from any to any port 80")
    assert render_rule(rule(protocol="icmpv4", local_ports="")) == \
        'pass in inet proto icmp from any to any label "r"'


@pytest.mark.parametrize("bad", [rule(program="/bin/nc"), rule(local_ports="RPC"),
                                 rule(protocol="icmpv4", local_ports="1")])
def test_render_refuses(bad):
    with pytest.raises(FirewallError):
        render_rule(bad)


def test_block_last_and_disabled_skipped():
    text = render([rule("b", action="block"), rule("a"), rule("off", enabled=False)])
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    assert [line.split('"')[1] for line in lines] == ["a", "b"]


class Root:
    """Fake root shell: applies the install of rules.json so the backend re-reads it."""

    def __init__(self, state, cancel=False):
        self.state, self.cancel, self.scripts = state, cancel, []

    def __call__(self, script):
        if self.cancel:
            raise ElevationCancelled
        self.scripts.append(script)
        src = script.split("/usr/bin/install -m 644 ")[1].split(" ")[0]
        self.state.write_text(open(src).read())


def test_changes_commit_and_batch_prompts_once(tmp_path):
    state = tmp_path / "rules.json"
    root = Root(state)
    fw = PfBackend(state, run=root)
    fw.add_rule(rule("a"))
    assert len(root.scripts) == 1 and "pfctl -q -n -a" in root.scripts[0]
    with batch(fw):
        fw.add_rule(rule("b"))
        fw.set_action("a", "block")
        fw.set_enabled("b", False)
    assert len(root.scripts) == 2
    saved = {d["name"]: d for d in json.loads(state.read_text())["rules"]}
    assert saved["a"]["action"] == "block" and saved["b"]["enabled"] is False
    assert fw.delete_rules("a") == 1 and [r.name for r in fw.list_rules()] == ["b"]


def test_cancel_changes_nothing(tmp_path):
    state = tmp_path / "rules.json"
    fw = PfBackend(state, run=Root(state, cancel=True))
    with pytest.raises(ElevationCancelled):
        with batch(fw):
            fw.add_rule(rule())
    assert fw.list_rules() == [] and not state.exists()
