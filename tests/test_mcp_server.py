import anyio
from mcp import Client

from piewall import mcp_server
from piewall.model import ALL_PROFILES, PIEWALL_GROUP, Rule
from piewall.transfer import FileBackend, export_rules

from fakes import FakeBackend


def rule(**kw) -> Rule:
    base = dict(name="r", enabled=True, direction="in", action="allow",
                protocol="tcp", local_ports="8080")
    base.update(kw)
    return Rule(**base)


RULES = [
    rule(name="web"),
    rule(name="devserver", action="block", local_ports="*", program=r"C:\dev\devserver.exe"),
    rule(name="ssh", local_ports="22", enabled=False),
]
LISTENING = [(r"c:\dev\devserver.exe", "tcp", 8080)]

READ_TOOLS = {"status", "list_rules", "rule_details", "find_conflicts"}
WRITE_TOOLS = {"open_port", "close_port", "set_rule_enabled", "set_rule_action", "delete_rule",
               "export_rules"}


def live_server(backend=None, admin=True, elevator=None):
    backend = backend or FakeBackend(RULES)
    server = mcp_server.build_server(
        backend, live=True, listeners=lambda: LISTENING, admin_check=lambda: admin,
        elevator=elevator)
    return server, backend


def call(server, tool, args=None):
    async def go():
        async with Client(server) as client:
            return await client.call_tool(tool, args or {})
    return anyio.run(go)


def tool_names(server) -> dict:
    async def go():
        async with Client(server) as client:
            return {t.name: t for t in (await client.list_tools()).tools}
    return anyio.run(go)


def test_live_mode_exposes_all_tools_with_hints():
    tools = tool_names(live_server()[0])
    assert set(tools) == READ_TOOLS | WRITE_TOOLS
    assert tools["list_rules"].annotations.read_only_hint is True
    assert tools["delete_rule"].annotations.destructive_hint is True
    assert tools["open_port"].annotations.destructive_hint is False


def test_file_mode_is_read_only(tmp_path):
    path = tmp_path / "rules.json"
    export_rules(RULES, path, listeners=LISTENING)
    backend = FileBackend(path)
    server = mcp_server.build_server(backend, live=False, listeners=backend.listeners)
    assert set(tool_names(server)) == READ_TOOLS
    status = call(server, "status").structured_content
    assert status["mode"] == "file" and status["rules"] == 3 and status["can_change"] is False
    conflicts = call(server, "find_conflicts").structured_content
    assert conflicts["listener_data"] == "snapshot"
    assert [c["blocker"]["name"] for c in conflicts["conflicts"]] == ["devserver"]


def test_list_rules_filters_and_pages():
    server, _ = live_server()
    out = call(server, "list_rules", {"port": 8080}).structured_content
    assert (out["total"], out["matched"]) == (3, 1)
    assert [r["name"] for r in out["rules"]] == ["web"]
    out = call(server, "list_rules", {"port": 8080, "any_port": True, "limit": 1}).structured_content
    assert out["matched"] == 2 and len(out["rules"]) == 1 and out["next_offset"] == 1


def test_find_conflicts_live_suggests_fix():
    out = call(live_server()[0], "find_conflicts").structured_content
    assert out["listener_data"] == "live"
    c = out["conflicts"][0]
    assert (c["blocker"]["name"], c["allowed"]["name"], c["kind"], c["port"]) == (
        "devserver", "web", "live", 8080)
    assert any("set_rule_action" in s for s in out["fix_suggestions"])


def test_rule_details_unknown_name_is_an_error():
    result = call(live_server()[0], "rule_details", {"name": "nope"})
    assert result.is_error


def test_open_and_close_port_as_admin():
    server, backend = live_server()
    out = call(server, "open_port", {"port": 9000, "profiles": ["public"]}).structured_content
    assert out["ok"] and "Opened port 9000" in out["output"]
    assert backend.rules[-1] == Rule(
        name="piewall TCP 9000 in", enabled=True, direction="in", action="allow", protocol="tcp",
        local_ports="9000", profiles=frozenset({"public"}), group=PIEWALL_GROUP,
        description="Created by piewall")
    assert call(server, "close_port", {"port": 9000}).structured_content["ok"]
    assert "piewall TCP 9000 in" not in [r.name for r in backend.rules]


def test_open_port_validates_port():
    assert call(live_server()[0], "open_port", {"port": 70000}).is_error


def test_set_action_enabled_delete():
    server, backend = live_server()
    call(server, "set_rule_action", {"name": "devserver", "action": "allow"})
    call(server, "set_rule_enabled", {"name": "ssh", "enabled": True})
    call(server, "delete_rule", {"name": "web"})
    by_name = {r.name: r for r in backend.rules}
    assert by_name["devserver"].action == "allow"
    assert by_name["ssh"].enabled
    assert "web" not in by_name


def test_unknown_rule_change_is_an_error():
    assert call(live_server()[0], "delete_rule", {"name": "nope"}).is_error


def test_changes_elevate_when_not_admin():
    calls = []

    def elevator(module_args, *, wait):
        calls.append(module_args)
        out = module_args[module_args.index("--elevated-output") + 1]
        with open(out, "w", encoding="utf-8") as f:
            f.write("Set to ALLOW: 1 rule(s) named 'devserver'.\n")
        return 0

    server, backend = live_server(admin=False, elevator=elevator)
    out = call(server, "set_rule_action", {"name": "devserver", "action": "allow"}).structured_content
    assert out["ok"] and "Set to ALLOW" in out["output"]
    assert calls[0][-2:] == ["allow", "devserver"]


def test_uac_cancel_is_reported():
    def elevator(module_args, *, wait):
        from piewall.elevate import ElevationCancelled
        raise ElevationCancelled

    server, _ = live_server(admin=False, elevator=elevator)
    result = call(server, "delete_rule", {"name": "web"})
    assert result.is_error
    assert "cancelled" in result.content[0].text.lower()


def test_export_rules_tool(tmp_path):
    path = tmp_path / "out.json"
    out = call(live_server()[0], "export_rules", {"path": str(path)}).structured_content
    assert out["ok"] and path.exists()


def test_main_dispatches_cli_commands(monkeypatch):
    seen = []
    monkeypatch.setattr(mcp_server.cli, "main", lambda argv: seen.append(argv) or 0)
    assert mcp_server.main(["list", "--port", "80"]) == 0
    assert mcp_server.main(["--elevated-output", "f", "delete", "x"]) == 0
    assert seen == [["list", "--port", "80"], ["--elevated-output", "f", "delete", "x"]]


def test_main_requires_rules_file_off_windows(monkeypatch, capsys):
    monkeypatch.setattr(mcp_server.sys, "platform", "linux")
    monkeypatch.delenv("PIEWALL_RULES_FILE", raising=False)
    assert mcp_server.main([]) == 2
    assert "--rules-file" in capsys.readouterr().err


def test_allowed_hosts_defaults_and_extras():
    hosts = mcp_server.allowed_hosts(["piewall.local:8000"])
    assert "localhost:*" in hosts and "127.0.0.1:*" in hosts and "piewall.local:8000" in hosts


def test_open_port_defaults_to_all_profiles():
    server, backend = live_server()
    call(server, "open_port", {"port": 9100})
    assert backend.rules[-1].profiles == ALL_PROFILES
