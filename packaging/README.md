# Packaging piewall for Windows

| File | What it is |
|---|---|
| `piewall.spec` | PyInstaller spec: builds `piewall.exe` (GUI, windowed), `piewall-cli.exe` and `piewall-mcp.exe` (console) |
| `piewall_gui.py`, `piewall_cli.py`, `piewall_mcp.py` | tiny entry scripts (`piewall.gui:main`, `piewall.cli:main`, `piewall.mcp_server:main`) |
| `piewall.manifest` | app manifest: `asInvoker`, PerMonitorV2 DPI, Windows 10/11, long paths |
| `piewall.iss` | Inno Setup 6 installer script |
| `build.ps1` | builds everything into `dist\release\` |

## Build locally

Needs [uv](https://docs.astral.sh/uv/) and Inno Setup 6:

```powershell
winget install --id JRSoftware.InnoSetup -e --scope user
.\packaging\build.ps1            # add -SkipTests to skip pytest
```

Output in `dist\release\`:

| Asset | Build |
|---|---|
| `piewall.exe` | portable GUI, one file |
| `piewall-cli.exe` | portable command line, one file |
| `piewall-mcp.exe` | portable MCP server, one file (what the `piewall-mcp` npm package downloads) |
| `piewall-setup.exe` | installer (per-user by default, no admin needed) |
| `SHA256SUMS.txt` | `sha256sum -c` compatible checksums |

The version in every file comes from `version` in `pyproject.toml`.

### Why two layouts

- The **installer** ships a *onedir* build: `piewall.exe`, `piewall-cli.exe` and `piewall-mcp.exe` share one
  `_internal\` folder. Nothing is unpacked at start-up, so it starts fast (~0.1 s for
  `piewall-cli --help`), and antivirus tools are much less suspicious of it than of
  self-extracting exes.
- The **portable** assets are *onefile*: one exe each, easy to download and run. They unpack to
  `%TEMP%` on every start (~0.9 s for `--help`), which is the usual trade-off.
- UPX is off on purpose: UPX-packed exes are a common cause of false positives.
- `piewall-mcp.exe` has its own analysis in the spec: it keeps `ssl`/`_hashlib` (uvicorn and
  httpx2 import them), collects the `mcp` SDK's lazily imported modules and dist metadata, and
  leaves out Tk. That is why it is ~21 MB against ~9.5 MB for the CLI.

### Admin rights

Both exes run as the current user (`asInvoker`). Reading rules needs no admin. When a change
needs admin, piewall relaunches itself through UAC: the frozen build maps `piewall` to
`piewall-cli.exe` and `piewall.gui` to `piewall.exe` next to the running exe
(see `src/piewall/elevate.py`). A lone `piewall-mcp.exe` (the npm download) has no
`piewall-cli.exe` beside it, so it relaunches itself: `piewall-mcp.exe <cli subcommand>` runs the CLI.

### Installer options

Silent install for the current user, adding `piewall-cli` and `piewall-mcp` to the user PATH:

```powershell
piewall-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /TASKS=addtopath
```

Tasks: `desktopicon`, `addtopath` (both off by default). `/ALLUSERS` installs to
`C:\Program Files\piewall` (needs admin; PATH then goes into the system PATH).
Uninstall: *Settings > Apps*, or `unins000.exe /VERYSILENT` in the install folder.
Keep the `AppId` in `piewall.iss` unchanged forever: upgrades rely on it.

## Release

1. Bump `version` in `pyproject.toml`, run `uv lock`, then sync the npm launcher's version
   (it downloads `piewall-mcp.exe` from release `v<its version>`; `release.yml` fails on a mismatch):

   ```powershell
   node npm/piewall-mcp/scripts/sync-version.mjs     # add --check to only compare
   ```

   Commit.
2. Tag and push:

   ```powershell
   git tag v0.2.0
   git push origin main v0.2.0
   ```

3. `.github/workflows/release.yml` runs on the tag: tests (pytest and the npm launcher's
   `node --test`), checks the tag equals `v` + the pyproject version and the npm version, runs
   `packaging\build.ps1`, then creates the GitHub Release with the four exes, `SHA256SUMS.txt`
   and auto-generated notes. Versions with letters (`0.2.0rc1`) are marked pre-release.
   Its `npm` job then publishes `npm/piewall-mcp` with provenance (dist-tag `next` for
   pre-releases), after checking that the release lists `piewall-mcp.exe`.
4. `.github/workflows/container.yml` builds `Containerfile` for linux/amd64 + arm64, smoke-tests
   it over MCP stdio and pushes `docker.io/th33raphat/piewall:<version>`, `:<major>.<minor>`
   and `:latest` (pre-releases: `:<version>` only), then updates the Docker Hub page from
   `docker/README.md`. Pushes to `main` and pull requests only build and test.

Repository secrets: `NPM_TOKEN` (npm token that can publish `piewall-mcp`),
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (Docker Hub personal access token with
Read, Write, Delete scope; updating the repository description needs it).

## MCP server distribution

| Channel | Source | What |
|---|---|---|
| npm `piewall-mcp` | `npm/piewall-mcp/` | zero-dependency launcher: downloads `piewall-mcp.exe` of its own version from the GitHub release, checks it against `SHA256SUMS.txt`, caches it in `%LOCALAPPDATA%\piewall\mcp\<version>\` and runs it (`npx -y piewall-mcp`) |
| container `th33raphat/piewall` | `Containerfile`, `docker/README.md` | Linux image, read-only file mode over an exported rules JSON |
| installer / portable | `dist\release\piewall-mcp.exe` | the same exe; on PATH with the installer's `addtopath` task |

Local checks:

```powershell
cd npm\piewall-mcp; npm test; npm pack --dry-run
podman build -t piewall-mcp:test -f Containerfile .     # or: docker build -f Containerfile .
```

Launcher test hooks: `PIEWALL_MCP_EXE` (run a local exe, no download), `PIEWALL_VERSION`,
`PIEWALL_MCP_DOWNLOAD_BASE` (a mirror with `v<version>/` folders), `PIEWALL_MCP_CACHE_DIR`.

`ci.yml` runs the tests on every push and pull request.

## Code signing

The builds are **unsigned**, so Windows SmartScreen shows "Windows protected your PC" on first
run until the file builds reputation, and some antivirus tools are stricter with unsigned exes.
Options:

- **Azure Trusted Signing** (about US$10/month): Microsoft-managed certificate, works from
  GitHub Actions with `azure/trusted-signing-action`. Needs an identity check of the publisher.
- **OV code-signing certificate** from a CA (DigiCert, Sectigo, ...): since 2023 the private key
  must live on a hardware token or cloud HSM, which makes CI signing harder.

Where signing slots in (all present but commented out):

1. `build.ps1`, after the PyInstaller builds: sign the six exes in `dist\onedir\piewall\`
   and `dist\onefile\` before Inno Setup packs them.
2. `build.ps1`, after Inno Setup: sign `piewall-setup.exe`. Alternatively enable
   `SignTool=` and `SignedUninstaller=yes` in `piewall.iss` so Inno signs the setup and
   uninstaller itself.
3. `release.yml`, "Signing would go here": set up credentials (e.g. Trusted Signing) before
   the build step, as repository secrets.

Always timestamp signatures (`/tr ... /td SHA256`) so they stay valid after the certificate
expires.

## macOS

`packaging/build-macos.sh` builds `dist/release/piewall-macos-<arch>.dmg` (piewall.app with the
GUI and `Contents/MacOS/piewall-cli`), using `packaging/piewall-macos.spec`, `iconutil` and
`hdiutil`. CI: `.github/workflows/macos.yml` builds arm64 (`macos-15`) and x86_64
(`macos-15-intel`); on tags `release.yml` calls it and uploads the DMGs to the release.

The app is signed ad hoc only, so Gatekeeper blocks the first launch until the user picks
**Open Anyway** in System Settings › Privacy & Security. To ship it cleanly: an Apple Developer
ID (US$99/year), `codesign --options runtime --sign "Developer ID Application: …"` in place of
the ad hoc signature, then `xcrun notarytool submit --wait` and `xcrun stapler staple` on the DMG.
