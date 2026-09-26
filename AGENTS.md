# Agent guide for piewall

piewall manages Windows Defender Firewall rules (and macOS pf rules): Python 3.12, uv, Tkinter GUI, argparse CLI,
MCP server.

## Using piewall as a tool
Follow `skills/piewall/SKILL.md` (install it for your agent with
`npx skills add TheeraphatStudent/piewall`). MCP: `npx -y piewall-mcp`.

## Working on this repo
- `uv sync`, then `uv run pytest -q`. Tests use `tests/fakes.py::FakeBackend`; never touch the
  real firewall in tests.
- Layout: `src/piewall/` (`model`, `conflicts`, `transfer` are pure and OS-independent;
  `backend`/`elevate` are Windows-specific, `pf` is the macOS backend; `cli`, `gui`, `theme`, `mcp_server`).
- Only read-only commands (`list`, `conflicts`, `export`) may run against the real firewall
  without asking the user. Changes pop a UAC prompt on the user's desktop.
- Packaging: `packaging/` (PyInstaller + Inno Setup; `build-macos.sh` for the .app/.pkg), site: `site/` (Astro → Cloudflare),
  brand: `brand/`.
- Commit messages: plain, no AI attribution trailers.
