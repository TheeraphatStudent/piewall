---
name: piewall
description: >
  Diagnose and fix Windows Defender Firewall problems with piewall (MCP tools or the piewall-cli).
  Use when a port or local server "refuses to connect" from another device (phone, LAN, VM,
  container), when asked to open, close, allow, block, enable, disable or delete a Windows
  firewall rule, to check why an Allow rule has no effect (Block always wins), to audit or
  export firewall rules, or when a Windows "allow access" firewall popup was dismissed. Works
  with Claude Code, Codex, Cursor and any agent that can run shell commands or MCP tools.
---

# piewall: Windows firewall, simple as pie

piewall reads and changes Windows Defender Firewall rules. Reads are instant and need no
rights. **Every change shows a UAC prompt on the user's desktop**: say so before you make one,
and wait for the user to click it.

## Pick the interface

1. **MCP tools** if a `piewall` MCP server is connected (tools `status`, `list_rules`,
   `find_conflicts`, `rule_details`, `open_port`, `close_port`, `set_rule_enabled`,
   `set_rule_action`, `delete_rule`, `export_rules`). Call `status` first: `mode: "file"` means
   a read-only export (e.g. in a container). Changes are impossible there, so give the user the
   CLI command to run on Windows instead.
2. **CLI** otherwise: `piewall-cli` (installer/portable) or `uv run piewall` (from source).
   Full reference: `references/cli.md`. If neither exists, point the user to
   https://github.com/TheeraphatStudent/piewall/releases/latest (`piewall-setup.exe`).

piewall only runs on Windows 10/11. On other OSes it can only analyse an export.

## "It refuses to connect from my phone / another machine"

Work through these in order and stop at the first cause you find:

1. **Is anything listening beyond loopback?** `netstat -ano | findstr :<port>`: a server bound
   to `127.0.0.1` is unreachable from other devices no matter what the firewall says. Fix the
   server's bind address (`0.0.0.0`) first. That's not a firewall problem.
2. **Which network profile is active?** `Get-NetConnectionProfile`: phone hotspots and café
   Wi-Fi are usually **Public**. A rule for the Private profile does nothing there.
3. **Conflicts.** `find_conflicts` / `piewall-cli conflicts`. Windows gives Block precedence over
   Allow. The classic cause is a per-program Block rule that Windows created when someone
   dismissed the "allow access" popup for that app (same name as the exe). Fix with
   `set_rule_action(name, "allow")` or disable it. Confirm with the user before changing a
   rule piewall didn't create.
4. **No Allow rule for the port?** `list_rules(port=N, any_port=true)`. If none covers it on
   the active profile: `open_port(port=N, profiles=["public"])` (or the active profile).
5. Re-test from the other device. Remember the laptop's IP may change on reconnect.

## Safety rules

- Read before you write: `list_rules` / `rule_details` before any change, and show the user
  what you're about to change.
- Prefer `open_port` / `close_port`. They only touch rules in the `piewall` group, and
  `close_port` can never remove Windows' own rules.
- Rule names are not unique: one name can cover several rules (TCP+UDP, in+out). Name-based
  changes apply to all of them; say so.
- Never delete or block rules from Windows or other apps (group set, names like
  "Core Networking…") without explicit user consent. Disabling is reversible; deleting isn't.
- Opening a port on a **Public** profile exposes it to everyone on that network. Mention it,
  suggest the narrowest profile, and suggest `close_port` when the user is done.
- If the UAC prompt is cancelled (CLI exit code 3), nothing changed. Don't retry in a loop.

## Reading results

- `ports: "Any"` + a `program` means a per-program rule (applies to every port that program uses).
- `find_conflicts` kinds: `full` means the Block rule covers everything the Allow rule allows.
  `live` means a per-program Block hits a program that is listening on the allowed port right
  now (in file mode, from the export's snapshot).
- Store-app rules show a friendly `title`; always pass the exact `name` to change tools.
