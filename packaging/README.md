# Packaging piewall for Windows

| File | What it is |
|---|---|
| `piewall.spec` | PyInstaller spec: builds `piewall.exe` (GUI, windowed) and `piewall-cli.exe` (console) |
| `piewall_gui.py`, `piewall_cli.py` | tiny entry scripts (`piewall.gui:main`, `piewall.cli:main`) |
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
| `piewall-setup.exe` | installer (per-user by default, no admin needed) |
| `SHA256SUMS.txt` | `sha256sum -c` compatible checksums |

The version in every file comes from `version` in `pyproject.toml`.

### Why two layouts

- The **installer** ships a *onedir* build: `piewall.exe` and `piewall-cli.exe` share one
  `_internal\` folder. Nothing is unpacked at start-up, so it starts fast (~0.1 s for
  `piewall-cli --help`), and antivirus tools are much less suspicious of it than of
  self-extracting exes.
- The **portable** assets are *onefile*: one exe each, easy to download and run. They unpack to
  `%TEMP%` on every start (~0.9 s for `--help`), which is the usual trade-off.
- UPX is off on purpose: UPX-packed exes are a common cause of false positives.

### Admin rights

Both exes run as the current user (`asInvoker`). Reading rules needs no admin. When a change
needs admin, piewall relaunches itself through UAC: the frozen build maps `piewall` to
`piewall-cli.exe` and `piewall.gui` to `piewall.exe` next to the running exe
(see `src/piewall/elevate.py`).

### Installer options

Silent install for the current user, adding `piewall-cli` to the user PATH:

```powershell
piewall-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /TASKS=addtopath
```

Tasks: `desktopicon`, `addtopath` (both off by default). `/ALLUSERS` installs to
`C:\Program Files\piewall` (needs admin; PATH then goes into the system PATH).
Uninstall: *Settings > Apps*, or `unins000.exe /VERYSILENT` in the install folder.
Keep the `AppId` in `piewall.iss` unchanged forever: upgrades rely on it.

## Release

1. Bump `version` in `pyproject.toml`, run `uv lock`, commit.
2. Tag and push:

   ```powershell
   git tag v0.2.0
   git push origin main v0.2.0
   ```

3. `.github/workflows/release.yml` runs on the tag: tests, checks the tag equals
   `v` + the pyproject version, runs `packaging\build.ps1`, then creates the GitHub Release
   with the three exes and `SHA256SUMS.txt` and auto-generated notes. Versions with letters
   (`0.2.0rc1`) are marked pre-release.

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

1. `build.ps1`, after the PyInstaller builds: sign the four exes in `dist\onedir\piewall\`
   and `dist\onefile\` before Inno Setup packs them.
2. `build.ps1`, after Inno Setup: sign `piewall-setup.exe`. Alternatively enable
   `SignTool=` and `SignedUninstaller=yes` in `piewall.iss` so Inno signs the setup and
   uninstaller itself.
3. `release.yml`, "Signing would go here": set up credentials (e.g. Trusted Signing) before
   the build step, as repository secrets.

Always timestamp signatures (`/tr ... /td SHA256`) so they stay valid after the certificate
expires.
