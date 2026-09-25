<#
.SYNOPSIS
  Build piewall release artifacts into dist\release.

.DESCRIPTION
  1. uv sync (locked)            4. Inno Setup -> piewall-setup.exe (from the onedir build)
  2. PyInstaller onedir build    5. copy piewall.exe, piewall-cli.exe, piewall-mcp.exe (onefile) and
  3. PyInstaller onefile build      piewall-setup.exe to dist\release, write SHA256SUMS.txt

  Safe to re-run: every output folder is wiped first. Any failing step stops the script.
  Works on Windows PowerShell 5.1 and PowerShell 7.

.PARAMETER SkipTests
  Do not run pytest before building.

.PARAMETER Iscc
  Path to ISCC.exe. Default: ISCC on PATH, then the usual per-user and machine install folders.
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [string]$Iscc
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root 'dist'
$Build = Join-Path $Root 'build'
$Release = Join-Path $Dist 'release'

function Invoke-Step {
    param([string]$Name, [scriptblock]$Command)
    Write-Host "==> $Name" -ForegroundColor Cyan
    # Native tools write progress to stderr; on PowerShell 5.1 that must not count as failure.
    # Success is judged by the exit code alone.
    $global:LASTEXITCODE = 0
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Command } finally { $ErrorActionPreference = $saved }
    if ($LASTEXITCODE -ne 0) { throw "$Name failed (exit code $LASTEXITCODE)" }
}

function Find-Iscc {
    if ($Iscc) {
        if (-not (Test-Path $Iscc)) { throw "ISCC not found at $Iscc" }
        return $Iscc
    }
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    )
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    throw 'Inno Setup 6 (ISCC.exe) not found. Install: winget install --id JRSoftware.InnoSetup -e --scope user'
}

Push-Location $Root
try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv not found on PATH' }
    $IsccExe = Find-Iscc

    Invoke-Step 'uv sync' { uv sync --locked }
    $Version = ([regex]::Match((Get-Content -Raw pyproject.toml), '(?m)^version\s*=\s*"([^"]+)"')).Groups[1].Value
    if (-not $Version) { throw 'Could not read version from pyproject.toml' }
    Write-Host "piewall $Version" -ForegroundColor Green

    if (-not $SkipTests) {
        Invoke-Step 'pytest' { uv run --no-sync pytest -q -p no:cacheprovider }
    }

    foreach ($dir in @($Release, (Join-Path $Dist 'onedir'), (Join-Path $Dist 'onefile'), (Join-Path $Dist 'installer'), $Build)) {
        if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
    }

    foreach ($mode in @('onedir', 'onefile')) {
        $env:PIEWALL_MODE = $mode
        try {
            Invoke-Step "PyInstaller ($mode)" {
                uv run --no-sync pyinstaller packaging\piewall.spec --noconfirm --clean --log-level WARN `
                    --distpath (Join-Path $Dist $mode) --workpath (Join-Path $Build $mode)
            }
        } finally {
            Remove-Item Env:\PIEWALL_MODE -ErrorAction SilentlyContinue
        }
    }

    $OneDir = Join-Path $Dist 'onedir\piewall'
    $OneFile = Join-Path $Dist 'onefile'

    # --- Code signing (disabled; see packaging/README.md) ------------------------------------
    # Sign the exes BEFORE Inno Setup packs them, then sign the installer after it is built.
    # $toSign = @("$OneDir\piewall.exe", "$OneDir\piewall-cli.exe", "$OneDir\piewall-mcp.exe",
    #             "$OneFile\piewall.exe", "$OneFile\piewall-cli.exe", "$OneFile\piewall-mcp.exe")
    # Azure Trusted Signing:
    #   signtool sign /v /fd SHA256 /tr http://timestamp.acs.microsoft.com /td SHA256 `
    #     /dlib "$env:TRUSTED_SIGNING_DLIB" /dmdf packaging\signing-metadata.json $toSign
    # OV certificate in the cert store:
    #   signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /n "Theeraphat" $toSign
    # ------------------------------------------------------------------------------------------

    $InstallerOut = Join-Path $Dist 'installer'
    Invoke-Step 'Inno Setup' {
        & $IsccExe /Q "/DAppVersion=$Version" "/DSourceDir=$OneDir" "/O$InstallerOut" packaging\piewall.iss
    }
    # (signing) signtool sign ... "$InstallerOut\piewall-setup.exe"

    New-Item -ItemType Directory -Force $Release | Out-Null
    $assets = @(
        (Join-Path $OneFile 'piewall.exe'),
        (Join-Path $OneFile 'piewall-cli.exe'),
        (Join-Path $OneFile 'piewall-mcp.exe'),
        (Join-Path $InstallerOut 'piewall-setup.exe')
    )
    foreach ($a in $assets) {
        if (-not (Test-Path $a)) { throw "Missing build output: $a" }
        Copy-Item $a $Release
    }

    # sha256sum-compatible: "<hash>  <file>", LF line endings, no BOM.
    $lines = Get-ChildItem $Release -File | Where-Object Name -ne 'SHA256SUMS.txt' | Sort-Object Name | ForEach-Object {
        '{0}  {1}' -f (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLowerInvariant(), $_.Name
    }
    [IO.File]::WriteAllText((Join-Path $Release 'SHA256SUMS.txt'), (($lines -join "`n") + "`n"))

    Write-Host "==> Done: $Release" -ForegroundColor Green
    Get-ChildItem $Release | Format-Table Name, @{ n = 'MB'; e = { [math]::Round($_.Length / 1MB, 1) } } -AutoSize
}
finally {
    Pop-Location
}
