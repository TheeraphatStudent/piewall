from pywall.model import (
    package_label,
    PROFILE_ALL,
    Rule,
    filter_rules,
    parse_profiles,
    profiles_from_mask,
    profiles_to_mask,
    protocol_from_num,
    protocol_to_num,
)


def rule(**kw) -> Rule:
    base = dict(name="r", enabled=True, direction="in", action="allow",
                protocol="tcp", local_ports="8080")
    base.update(kw)
    return Rule(**base)


def test_protocol_roundtrip():
    assert protocol_from_num(6) == "tcp"
    assert protocol_from_num(17) == "udp"
    assert protocol_from_num(256) == "any"
    assert protocol_from_num(1) == "icmpv4"
    assert protocol_from_num(47) == "47"
    for name in ("tcp", "udp", "any", "icmpv4", "47"):
        assert protocol_from_num(protocol_to_num(name)) == name


def test_profile_mask():
    assert profiles_from_mask(4) == frozenset({"public"})
    assert profiles_from_mask(PROFILE_ALL) == frozenset({"domain", "private", "public"})
    assert profiles_to_mask(frozenset({"domain", "private", "public"})) == PROFILE_ALL
    assert profiles_to_mask(frozenset({"private", "public"})) == 6


def test_parse_profiles():
    assert parse_profiles(["any"]) == frozenset({"domain", "private", "public"})
    assert parse_profiles(["public", "private"]) == frozenset({"public", "private"})


def test_rule_dict_roundtrip():
    r = rule(program=r"C:\a.exe", profiles=frozenset({"public"}), group="pywall")
    assert Rule.from_dict(r.to_dict()) == r


def test_rule_display_helpers():
    assert rule(profiles=frozenset({"domain", "private", "public"})).profiles_label == "Any"
    assert rule(profiles=frozenset({"public", "private"})).profiles_label == "Private, Public"
    assert rule(local_ports="").ports_label == "Any"


def test_filter_search_matches_name_program_and_group():
    rules = [rule(name="mp4toinc-ui"), rule(name="x", program=r"D:\mp4toinc\ui.exe"),
             rule(name="y", group="MP4 stuff"), rule(name="other")]
    assert [r.name for r in filter_rules(rules, search="MP4")] == ["mp4toinc-ui", "x", "y"]


def test_filter_by_port_action_dir_enabled():
    rules = [
        rule(name="a", local_ports="8080"),
        rule(name="b", local_ports="8000-8100", action="block"),
        rule(name="c", local_ports="*", direction="out"),
        rule(name="d", local_ports="443", enabled=False),
    ]
    assert [r.name for r in filter_rules(rules, port=8080)] == ["a", "b"]
    assert [r.name for r in filter_rules(rules, port=8080, any_port=True)] == ["a", "b", "c"]
    assert [r.name for r in filter_rules(rules, action="block")] == ["b"]
    assert [r.name for r in filter_rules(rules, direction="out")] == ["c"]
    assert [r.name for r in filter_rules(rules, enabled=False)] == ["d"]


def test_display_name_is_cosmetic():
    raw = "@{Microsoft.Store?ms-resource://x}"
    a = rule(name=raw, display_name="Microsoft Store")
    assert a.title == "Microsoft Store"
    assert a == rule(name=raw)  # equality ignores it (import dedup, name-based ops)
    assert "display_name" not in a.to_dict()
    assert filter_rules([a], search="store") == [a]


def test_package_label():
    raw = "@{MicrosoftCorporationII.WindowsSubsystemForLinux_2.6.1.0_x64__8wekyb3d8bbwe?ms-resource://x}"
    assert package_label(raw) == "MicrosoftCorporationII.WindowsSubsystemForLinux"
    assert package_label("Zoom") == ""
