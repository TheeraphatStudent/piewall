# piewall

Manage Windows Defender Firewall rules from a simple window or the command line.

- Lists all rules fast (~0.5 s for ~850 rules) with friendly names for Store apps.
- One-command `open` / `close` for ports.
- Finds **Block rules that silently override Allow rules** (Windows always lets
  Block win), including per-program blocks created when a firewall popup was
  dismissed.
- Export / import rules as JSON.
- Reading needs no admin rights; changes trigger a UAC prompt automatically.

## Setup

```powershell
cd C:\Users\th33r\Desktop\Project\piewall
uv sync
```

## Window

```powershell
uv run piewall-gui          # or: uv run piewall gui
```

Search, filter by port / action / direction / state, click a column to sort.
Right-click rules to enable, disable, flip Allow/Block or delete; double-click
for details. A yellow banner appears when a Block rule overrides an Allow rule;
click it to review and fix. File menu: export / import.

## Command line

```powershell
uv run piewall list --search mp4                 # find rules
uv run piewall list --port 8080                  # rules that name port 8080
uv run piewall list --port 8080 --any-port       # ...plus rules open to every port
uv run piewall open 8080 --profile public        # allow inbound TCP 8080 on public networks
uv run piewall open 5353 --udp
uv run piewall close 8080                        # remove the rules piewall opened for 8080
uv run piewall conflicts                         # Block rules overriding Allow rules
uv run piewall allow "mp4toinc-ui"               # flip a rule (all rules with that name)
uv run piewall disable|enable|delete "<name>"
uv run piewall export rules.json [--piewall-only]
uv run piewall import rules.json                 # skips rules that already exist
```

Exit codes: `0` ok, `1` error / nothing matched / conflicts found, `2` usage,
`3` UAC prompt cancelled.

Rules created by piewall are in the group `piewall`; `close` only removes those,
never rules made by Windows or other apps.

## Tests

```powershell
uv run pytest
```

Design notes: `docs/superpowers/specs/2026-09-25-piewall-design.md`.
