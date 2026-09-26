<p align="center">
  <img src="brand/png/app-icon-128.png" width="96" height="96" alt="piewall logo">
</p>

<h1 align="center">piewall</h1>

<p align="center"><strong>Your firewall, simple as pie.</strong><br>
Manage Windows Defender Firewall (or macOS pf) rules from a clean window or the command line.</p>

<p align="center">
  <a href="https://piewall.th33raphat.dev">Website</a> ·
  <a href="https://github.com/TheeraphatStudent/piewall/releases/latest">Download</a> ·
  <a href="https://piewall.th33raphat.dev/#coffee">Buy me a coffee</a>
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/app-dark.png">
  <img src="docs/images/app-light.png" alt="piewall window listing firewall rules, with a yellow banner warning that a Block rule overrides an Allow rule">
</picture>

## Why

Windows silently creates **Block** rules when you dismiss a firewall popup, and
Block always beats Allow. Your "open port 8080" rule is correct, yet the port is
still closed. piewall shows every rule at a glance, points out the Block rule
that is overriding your Allow rule, and fixes it in one click.

- **Everything at once.** ~850 rules load in half a second, with real app names
  instead of `@{Package?ms-resource://…}` codes.
- **Open or close a port in one step.** Rules piewall creates are grouped, so
  `close` never touches Windows' own rules.
- **Conflict finder.** Flags Block rules that shadow Allow rules, including a
  per-program block for an app that is listening on the allowed port right now.
- **Safe by default.** Read-only until you change something; administrator
  rights are requested through UAC only then.
- **Export / import** rules as JSON, and a **CLI** for scripts.
- Windows 11 look that follows your light/dark setting.

## Install

Download from [Releases](https://github.com/TheeraphatStudent/piewall/releases/latest):

| File | What it is |
|---|---|
| `piewall-setup.exe` | Installer: Start-menu entry, optional `piewall-cli` on PATH, uninstaller. No admin needed. |
| `piewall.exe` | Portable window app, nothing to install. |
| `piewall-cli.exe` | Portable command line tool. |

Builds are not code-signed yet, so Windows SmartScreen may show
"Windows protected your PC" the first time: choose **More info → Run anyway**.
Checksums are in `SHA256SUMS.txt`.

**macOS 12+**: `piewall-macos-arm64.pkg` (Apple Silicon) or `piewall-macos-x86_64.pkg` (Intel).
Open it and follow the installer; it asks for your administrator password, installs
`/Applications/piewall.app` and adds the `piewall` command to `/usr/local/bin`. The package is
not notarized yet, so the first time macOS says it can't verify it: click **Done**, then
**Open Anyway** in System Settings › Privacy & Security. Uninstall:
`sudo rm -rf /Applications/piewall.app /usr/local/bin/piewall`.

On macOS piewall manages its own rules in the pf anchor `com.apple/piewall` (the stock
`/etc/pf.conf` already loads it) and keeps them across reboots with a LaunchDaemon. pf filters
ports and addresses, not programs, and piewall lists only the rules it manages. Every change
asks for your administrator password; Block rules are ordered last so Block wins, as on Windows.

**Updates**: when the window opens, piewall asks GitHub once for the latest release (nothing
else is sent). If a newer version is out, it offers to download the installer for your system.

## Use the window

Search, filter by port / action / direction / state, click a column to sort.
Right-click rules to enable, disable, flip Allow/Block or delete; double-click
for details. When a Block rule overrides an Allow rule, a yellow banner appears;
click it to review and fix. **⋯** holds refresh, export and import.

## Use the command line

```powershell
piewall-cli list --search mp4                 # find rules
piewall-cli list --port 8080                  # rules that name port 8080
piewall-cli list --port 8080 --any-port       # ...plus rules open to every port
piewall-cli open 8080 --profile public        # allow inbound TCP 8080 on public networks
piewall-cli open 5353 --udp
piewall-cli close 8080                        # remove the rules piewall opened for 8080
piewall-cli conflicts                         # Block rules overriding Allow rules
piewall-cli allow "mp4toinc-ui"               # flip a rule (all rules with that name)
piewall-cli disable|enable|delete "<name>"
piewall-cli export rules.json [--piewall-only]
piewall-cli import rules.json                 # skips rules that already exist
```

Commands that change rules ask for administrator rights through UAC and print
the result in the same terminal. Exit codes: `0` ok, `1` error / nothing matched
/ conflicts found, `2` usage, `3` UAC prompt cancelled.

## Use with AI agents

**Skill** (Claude Code, Codex, Cursor and other agents that support Agent Skills):

```bash
npx skills add TheeraphatStudent/piewall
```

It teaches the agent to diagnose "port refuses to connect", read before changing, and stay
inside safe defaults. See [`skills/piewall/SKILL.md`](skills/piewall/SKILL.md).

**MCP server** on Windows (live firewall; every change asks you through UAC):

```bash
claude mcp add piewall -- npx -y piewall-mcp        # Claude Code
```

```json
{ "mcpServers": { "piewall": { "command": "npx", "args": ["-y", "piewall-mcp"] } } }
```

Tools: `status`, `list_rules`, `rule_details`, `find_conflicts`, `open_port`, `close_port`,
`set_rule_enabled`, `set_rule_action`, `delete_rule`, `export_rules`.

**Container** ([`th33raphat/piewall`](https://hub.docker.com/r/th33raphat/piewall), any OS,
read-only): a container can't reach the Windows host firewall, so it analyses an export.

```bash
piewall-cli export rules.json                                   # on Windows
podman run -i --rm -v ./rules.json:/data/rules.json:ro docker.io/th33raphat/piewall
# HTTP instead of stdio:
podman run --rm -p 8000:8000 -e PIEWALL_TRANSPORT=streamable-http -e PIEWALL_HOST=0.0.0.0 \
  -v ./rules.json:/data/rules.json:ro docker.io/th33raphat/piewall   # http://localhost:8000/mcp
```

`docker` works the same way. More: [`npm/piewall-mcp/README.md`](npm/piewall-mcp/README.md),
[`docker/README.md`](docker/README.md).

## Develop

Needs [uv](https://docs.astral.sh/uv/) and Windows 10/11 or macOS 12+.

```powershell
uv sync
uv run piewall-gui               # window from source
uv run piewall list              # CLI from source
uv run pytest                    # tests
powershell -File packaging\build.ps1   # build exes + installer into dist\release
packaging/build-macos.sh               # macOS: build piewall.app + .pkg into dist/release
```

- Releases: bump `version` in `pyproject.toml`, tag `vX.Y.Z`, push the tag;
  GitHub Actions builds and publishes. See `packaging/README.md`.
- Screenshots: `uv run --with pillow python scripts/screenshot.py docs/images/app-light.png --mode light`
  (demo data, never your real rules).
- Brand kit: `brand/`. Design notes: `docs/superpowers/specs/`.
- Website: `site/` (Astro, deployed to Cloudflare).

macOS support is planned.

## License

MIT © 2026 Theeraphat
