# pywall — design

Date: 2026-09-25

## Goal

Easy management of Windows Defender Firewall rules from a clean desktop window
and from a CLI. Motivating case: a dismissed firewall popup silently created
`mp4toinc-ui` **Block** rules that overrode a correct Allow rule for port 8080.

## Decisions

- **Backend:** Windows Firewall COM API (`HNetCfg.FwPolicy2`) via `pywin32`.
  Lists ~850 rules in ~0.5 s with ports/program included. PowerShell cmdlets
  were rejected (per-rule filter lookups take tens of seconds); `netsh` text
  parsing was rejected (fragile, localized).
- **UI:** Tkinter/ttk desktop window (stdlib, no server to secure).
- **Scope:** all rules on the machine, not only pywall-created ones. Rules that
  pywall creates get the group `pywall`; `close` only ever removes those.
- **Elevation:** reads work unelevated. Mutations relaunch through UAC
  (`ShellExecuteEx` verb `runas`). The CLI waits for the elevated child and
  prints its captured output; the GUI restarts itself as admin.

## Units

| Module | Purpose | Windows-only? |
|---|---|---|
| `model.py` | `Rule` dataclass, COM value mappings, `filter_rules` | no |
| `conflicts.py` | find enabled Block rules that shadow enabled Allow rules | no |
| `transfer.py` | export/import rules as JSON | no |
| `backend.py` | `FirewallBackend` (COM): list/add/delete/set_enabled/set_action | yes |
| `elevate.py` | `is_admin`, `run_elevated` | yes |
| `cli.py` | argparse subcommands | no (backend injected) |
| `gui.py` | Tkinter window | no (backend injected) |

## CLI

```
pywall list [--search S] [--port N] [--action allow|block] [--dir in|out] [--enabled|--disabled]
pywall open PORT [--udp|--any-protocol] [--dir in|out] [--profile any|domain|private|public ...] [--name N]
pywall close PORT
pywall enable|disable|delete NAME
pywall allow|block NAME
pywall conflicts
pywall export FILE [--pywall-only]
pywall import FILE
pywall gui
```

NAME matches every rule with that exact name (Windows allows duplicates, as
the two `mp4toinc-ui` rules show). Exit codes: 0 ok, 1 error / nothing matched,
2 usage, 3 UAC cancelled.

## Conflict heuristic

A Block rule shadows an Allow rule when both are enabled and: same direction,
profiles intersect, protocols compatible (equal or either is any), local ports
overlap (either any, ranges intersect, or same keyword such as `RPC`),
programs compatible (either unset or equal, case-insensitive), services
compatible, and remote addresses compatible (either `*` or equal). It is a
heuristic: it ignores remote address ranges and authenticated-bypass rules.

## Window

Toolbar: search, Action / Direction filters, "Open port…", "Run as admin"
(hidden when elevated). Sortable table (Name, Dir, Action, Protocol, Ports,
Program, Profiles, On); Block rows tinted red, disabled rows grey. Right-click:
Enable/Disable, Allow/Block, Delete (confirmed). Yellow banner when conflicts
exist; click to list them. Menu: Export…, Import…, Refresh. Status bar: counts
and admin state.

## Testing

pytest on model, conflicts, transfer and CLI (with a fake backend).
Real backend smoke-tested read-only (`list`, `conflicts`), plus one
open/close round trip on an unused port.
