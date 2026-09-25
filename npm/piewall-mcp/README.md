# piewall-mcp

MCP server for [piewall](https://piewall.th33raphat.dev): lets AI assistants read, analyse and
(with your approval) change **Windows Defender Firewall** rules.

This package is a small launcher with no dependencies. On first run it downloads `piewall-mcp.exe`
of the same version from the [GitHub release](https://github.com/TheeraphatStudent/piewall/releases),
checks its SHA-256 against the release's `SHA256SUMS.txt`, caches it in
`%LOCALAPPDATA%\piewall\mcp\<version>\` and runs it. Later starts are offline.

Requires Windows 10/11 and Node.js 18 or newer.

## Add it to your MCP client

**Claude Code**

```sh
claude mcp add piewall -- npx -y piewall-mcp
```

**Claude Desktop, Cursor** and other clients with an `mcpServers` JSON file
(`claude_desktop_config.json`, `.cursor/mcp.json`, ...):

```json
{
  "mcpServers": {
    "piewall": {
      "command": "npx",
      "args": ["-y", "piewall-mcp"]
    }
  }
}
```

If the client cannot start `npx` directly, use `"command": "cmd"` and
`"args": ["/c", "npx", "-y", "piewall-mcp"]`.

**Codex** (`~/.codex/config.toml`)

```toml
[mcp_servers.piewall]
command = "npx"
args = ["-y", "piewall-mcp"]
```

Installed piewall with `piewall-setup.exe` and ticked *Add to PATH*? Then `piewall-mcp.exe` is
already on your PATH, and you can use `"command": "piewall-mcp"` without Node.js.

## Tools

| Tool | Mode | What it does |
|---|---|---|
| `status` | both | where the rules come from, how many, whether changes are possible |
| `list_rules` | both | search and filter rules (text, port, action, direction, enabled) |
| `rule_details` | both | every field of the rules with a given name |
| `find_conflicts` | both | Block rules that override Allow rules, with suggested fixes |
| `open_port`, `close_port` | live | add or remove piewall's own Allow rules for a port |
| `set_rule_enabled`, `set_rule_action` | live | enable/disable a rule, flip Allow/Block |
| `delete_rule` | live | delete rules by name |
| `export_rules` | live | save rules and a listening-ports snapshot to JSON (backup, or for the container) |

**Live mode** (the default) works on this PC's firewall. **File mode** is read-only and works on a
rules file made by `piewall-cli export rules.json`, for example one exported from another PC:

```sh
npx -y piewall-mcp --rules-file C:\path\to\rules.json
```

Other options: `--transport streamable-http` (serves `http://127.0.0.1:8000/mcp`), `--host`,
`--port`, `--allowed-host`. Each also has an environment variable: `PIEWALL_RULES_FILE`,
`PIEWALL_TRANSPORT`, `PIEWALL_HOST`, `PIEWALL_PORT`, `PIEWALL_ALLOWED_HOSTS`.

## Safety

- Reading rules needs no admin rights. **Every change shows a Windows UAC prompt on your
  desktop**, so nothing changes until you click *Yes*. Read the prompt; *No* cancels the change.
- Do not run your MCP client as administrator: an elevated process gets no UAC prompt, so
  changes would apply without that confirmation.
- `open_port` / `close_port` only touch rules in the `piewall` group, never Windows' own rules.
  The assistant is told to ask you before deleting or blocking other rules.
- The HTTP transport binds to `127.0.0.1` and checks the `Host` header against DNS rebinding.
  It has no authentication: do not expose live mode to a network.
- The downloaded exe is verified against the release's `SHA256SUMS.txt` before it is cached.
  Builds are not code-signed yet.

## Not on Windows?

The Windows Firewall only exists on Windows. For read-only analysis on macOS or Linux, export
the rules on Windows (`piewall-cli export rules.json`) and use the container image:

```sh
podman run -i --rm -v ./rules.json:/data/rules.json:ro docker.io/th33raphat/piewall
```

or let the launcher start it with docker or podman:
`npx -y piewall-mcp --docker --rules-file ./rules.json`.

## Environment variables for the launcher

| Variable | Effect |
|---|---|
| `PIEWALL_VERSION` | download this release instead of the package's own version |
| `PIEWALL_MCP_EXE` | run this local `piewall-mcp.exe`, no download (testing) |
| `PIEWALL_MCP_CACHE_DIR` | cache root instead of `%LOCALAPPDATA%\piewall\mcp` |
| `PIEWALL_MCP_DOWNLOAD_BASE` | mirror URL with `v<version>/` folders instead of GitHub releases |

The launcher writes only to stderr; stdout carries the MCP protocol.

## License

MIT, Theeraphat. Source: <https://github.com/TheeraphatStudent/piewall>.
