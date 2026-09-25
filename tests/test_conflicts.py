from piewall.conflicts import find_conflicts, ports_overlap
from piewall.model import Rule

ALL = frozenset({"domain", "private", "public"})


def rule(**kw) -> Rule:
    base = dict(name="r", enabled=True, direction="in", action="allow",
                protocol="tcp", local_ports="8080", profiles=ALL)
    base.update(kw)
    return Rule(**base)


def test_ports_overlap():
    assert ports_overlap("*", "80")
    assert ports_overlap("", "80")
    assert ports_overlap("80,443", "443")
    assert ports_overlap("8000-8100", "8080")
    assert ports_overlap("8000-8100", "8100-9000")
    assert not ports_overlap("80", "443")
    assert not ports_overlap("8000-8079", "8080")
    assert ports_overlap("RPC", "rpc")
    assert not ports_overlap("RPC", "135")


def test_mp4toinc_case_is_detected():
    # Program-scoped Block rule from a dismissed popup vs a port Allow rule.
    allow = rule(name="mp4toinc UI 8080", profiles=frozenset({"public"}))
    block = rule(name="mp4toinc-ui", action="block", local_ports="*",
                 program=r"D:\users\desktop\work\mp4toinc\mp4toinc-ui.exe",
                 profiles=frozenset({"public"}))
    listening = [(r"d:\users\desktop\work\mp4toinc\mp4toinc-ui.exe", "tcp", 8080)]
    found = find_conflicts([allow, block], listening)
    assert [(c.blocker.name, c.allowed.name, c.kind, c.port) for c in found] == [
        ("mp4toinc-ui", "mp4toinc UI 8080", "live", 8080)]


def test_program_block_ignored_when_program_not_listening_on_allowed_port():
    # e.g. a game's Block rule vs an unrelated DNS Allow rule: noise, not a conflict.
    allow = rule(name="dns", protocol="udp", local_ports="53")
    block = rule(action="block", protocol="any", local_ports="", program=r"C:\game.exe")
    assert find_conflicts([allow, block]) == []
    assert find_conflicts([allow, block], [(r"c:\game.exe", "tcp", 7777)]) == []
    assert len(find_conflicts([allow, block], [(r"c:\game.exe", "udp", 53)])) == 1


def test_no_conflict_when_any_dimension_is_disjoint():
    allow = rule(name="allow", remote_addresses="192.168.1.1")
    blocks = [
        rule(action="block", direction="out"),
        rule(action="block", local_ports="443"),
        rule(action="block", protocol="udp"),
        rule(action="block", enabled=False),
        rule(action="block", remote_addresses="10.0.0.1"),
    ]
    for block in blocks:
        assert find_conflicts([allow, block]) == [], block


def test_different_services_do_not_conflict():
    allow = rule(service="Dnscache")
    assert find_conflicts([allow, rule(action="block", service="W32Time")]) == []
    assert len(find_conflicts([allow, rule(action="block")])) == 1


def test_matching_block_conflicts():
    assert len(find_conflicts([rule(name="allow"), rule(action="block")])) == 1


def test_profiles_must_intersect():
    allow = rule(profiles=frozenset({"private"}))
    block = rule(action="block", profiles=frozenset({"public"}))
    assert find_conflicts([allow, block]) == []


def test_different_programs_do_not_conflict():
    allow = rule(program=r"C:\a.exe")
    block = rule(action="block", program=r"C:\B.exe")
    assert find_conflicts([allow, block]) == []
    assert len(find_conflicts([allow, rule(action="block", program=r"c:\A.EXE")])) == 1


def test_any_protocol_block_covers_tcp():
    assert len(find_conflicts([rule(), rule(action="block", protocol="any", local_ports="")])) == 1


def test_disabled_allow_is_ignored():
    assert find_conflicts([rule(enabled=False), rule(action="block")]) == []
