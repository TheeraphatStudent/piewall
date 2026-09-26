"""pf rendering and commits. The fake runner stands in for the root shell; no firewall is touched."""

import json
import shlex

import pytest

from piewall.backend import FirewallError, batch
from piewall.elevate import ElevationCancelled
from piewall.model import Rule
from piewall.pf import ALF_GROUP, PfBackend, parse_alf, render, render_rule


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
        src = shlex.split(script.split("/usr/bin/install -m 644 ")[1])[0]
        self.state.write_text(open(src).read())


def test_changes_commit_and_batch_prompts_once(tmp_path):
    state = tmp_path / "rules.json"
    root = Root(state)
    fw = PfBackend(state, run=root, read_alf=list)
    fw.add_rule(rule("a"))
    assert len(root.scripts) == 1
    assert "pfctl -q -n -a" in root.scripts[0]
    with batch(fw):
        fw.add_rule(rule("b"))
        fw.set_action("a", "block")
        fw.set_enabled("b", False)
    assert len(root.scripts) == 2
    saved = {d["name"]: d for d in json.loads(state.read_text())["rules"]}
    assert saved["a"]["action"] == "block"
    assert saved["b"]["enabled"] is False
    assert fw.delete_rules("a") == 1
    assert [r.name for r in fw.list_rules()] == ["b"]


def test_cancel_changes_nothing(tmp_path):
    state = tmp_path / "rules.json"
    fw = PfBackend(state, run=Root(state, cancel=True), read_alf=list)
    with pytest.raises(ElevationCancelled), batch(fw):
        fw.add_rule(rule())
    assert fw.list_rules() == []
    assert not state.exists()


LISTAPPS = """Total number of apps = 2 

1 : /usr/sbin/cupsd 
             (Allow incoming connections)
2 : /Applications/Some Game.app 
             (Block incoming connections)
"""


def test_parse_alf():
    cups, game = parse_alf(LISTAPPS, firewall_on=True)
    assert (cups.name, cups.action, cups.program, cups.enabled) == \
        ("/usr/sbin/cupsd", "allow", "/usr/sbin/cupsd", True)
    assert (game.action, game.title, game.group) == ("block", "Some Game", ALF_GROUP)
    assert not any(r.enabled for r in parse_alf(LISTAPPS, firewall_on=False))


class Recorder:
    def __init__(self):
        self.scripts = []

    def __call__(self, script):
        self.scripts.append(script)


def alf_backend(tmp_path):
    run = Recorder()
    fw = PfBackend(tmp_path / "rules.json", run=run,
                   read_alf=lambda: parse_alf(LISTAPPS, firewall_on=True))
    return fw, run


def test_app_rules_are_listed_and_changed_through_socketfilterfw(tmp_path):
    fw, run = alf_backend(tmp_path)
    assert [r.title for r in fw.list_rules()] == ["cupsd", "Some Game"]
    with batch(fw):  # one password prompt for both
        assert fw.set_action("/Applications/Some Game.app", "allow") == 1
        assert fw.delete_rules("/usr/sbin/cupsd") == 1
    assert len(run.scripts) == 1
    assert "--unblockapp '/Applications/Some Game.app'" in run.scripts[0]
    assert "--remove /usr/sbin/cupsd" in run.scripts[0]
    assert "pfctl" not in run.scripts[0]  # pf untouched


def test_program_rule_goes_to_the_application_firewall(tmp_path):
    fw, run = alf_backend(tmp_path)
    fw.add_rule(rule("nc", program="/usr/bin/nc", local_ports="", protocol="any",
                     action="block"))
    assert run.scripts == ["/usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/bin/nc && "
                           "/usr/libexec/ApplicationFirewall/socketfilterfw --blockapp /usr/bin/nc"]
    with pytest.raises(FirewallError):
        fw.add_rule(rule("out", program="/usr/bin/nc", direction="out"))


def test_app_rules_cannot_be_disabled_one_by_one(tmp_path):
    fw, run = alf_backend(tmp_path)
    with pytest.raises(FirewallError):
        fw.set_enabled("/usr/sbin/cupsd", False)
    assert run.scripts == []
