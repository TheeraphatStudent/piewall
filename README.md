# pywall

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
cd C:\Users\th33r\Desktop\Project\pywall
uv sync
```

## Window

```powershell
uv run pywall-gui          # or: uv run pywall gui
```

Search, filter by port / action / direction / state, click a column to sort.
Right-click rules to enable, disable, flip Allow/Block or delete; double-click
for details. A yellow banner appears when a Block rule overrides an Allow rule;
click it to review and fix. File menu: export / import.

## Command line

```powershell
uv run pywall list --search mp4                 # find rules
uv run pywall list --port 8080                  # rules that name port 8080
uv run pywall list --port 8080 --any-port       # ...plus rules open to every port
uv run pywall open 8080 --profile public        # allow inbound TCP 8080 on public networks
uv run pywall open 5353 --udp
uv run pywall close 8080                        # remove the rules pywall opened for 8080
uv run pywall conflicts                         # Block rules overriding Allow rules
uv run pywall allow "mp4toinc-ui"               # flip a rule (all rules with that name)
uv run pywall disable|enable|delete "<name>"
uv run pywall export rules.json [--pywall-only]
uv run pywall import rules.json                 # skips rules that already exist
```

Exit codes: `0` ok, `1` error / nothing matched / conflicts found, `2` usage,
`3` UAC prompt cancelled.

Rules created by pywall are in the group `pywall`; `close` only removes those,
never rules made by Windows or other apps.

## Tests

```powershell
uv run pytest
```

Design notes: `docs/superpowers/specs/2026-09-25-pywall-design.md`.
