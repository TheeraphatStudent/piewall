# piewall CLI reference

`piewall-cli` (installed/portable) and `uv run piewall` (source) take the same arguments.
Commands that change rules relaunch through UAC and print the result in the same terminal.

| Command | Effect |
|---|---|
| `list [--search S] [--port N [--any-port]] [--action allow\|block] [--dir in\|out] [--enabled\|--disabled]` | table of matching rules |
| `open PORT [--udp\|--any-protocol] [--dir in\|out] [--profile any\|domain\|private\|public ...] [--name N]` | add an Allow rule in group `piewall` (default name `piewall TCP <port> in`) |
| `close PORT` | delete the `piewall`-group rules for that port only |
| `enable NAME` / `disable NAME` | toggle every rule with that exact name |
| `allow NAME` / `block NAME` | set the action of every rule with that exact name |
| `delete NAME` | permanently delete every rule with that exact name |
| `conflicts` | Block rules overriding Allow rules, with fix commands (exit 1 when any) |
| `export FILE [--piewall-only]` | JSON of rules + listening-program snapshot |
| `import FILE` | add rules from JSON, skipping identical ones |
| `gui` | open the window |

Exit codes: `0` ok · `1` error, nothing matched, or conflicts found · `2` usage · `3` UAC
cancelled (nothing changed).

## Examples

```powershell
piewall-cli list --port 8080 --any-port        # everything that could affect 8080
piewall-cli open 8080 --profile public         # allow inbound TCP 8080 on public networks
piewall-cli conflicts
piewall-cli allow "mp4toinc-ui"                # flip a popup-created Block rule
piewall-cli close 8080                         # undo the open
piewall-cli export rules.json                  # for backups or container analysis
```

## MCP server

- Live (Windows): `npx -y piewall-mcp` (or `piewall-mcp.exe`), stdio.
- Read-only anywhere: `podman run -i --rm -v ./rules.json:/data/rules.json:ro docker.io/th33raphat/piewall`
  (also works with `docker`).
