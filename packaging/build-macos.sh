#!/bin/sh
# Build dist/release/piewall-macos-<arch>.pkg (installs piewall.app + the piewall command). Run from anywhere on macOS.
#   packaging/build-macos.sh [--skip-tests]
set -eu
cd "$(dirname "$0")/.."

[ "${1:-}" = "--skip-tests" ] || uv run pytest -q

arch=$(uname -m)  # arm64 | x86_64
work=build/macos
rm -rf "$work" dist/piewall dist/piewall.app
mkdir -p "$work/piewall.iconset" dist/release

# .icns from the brand PNGs (iconutil wants icon_<n>x<n>[@2x].png).
for n in 16 32 128 256 512; do
  cp "brand/png/app-icon-$n.png" "$work/piewall.iconset/icon_${n}x${n}.png"
  cp "brand/png/app-icon-$((n * 2)).png" "$work/piewall.iconset/icon_${n}x${n}@2x.png"
done
iconutil -c icns "$work/piewall.iconset" -o "$work/piewall.icns"

PIEWALL_ICNS="$PWD/$work/piewall.icns" uv run pyinstaller packaging/piewall-macos.spec \
  --noconfirm --clean --workpath "$work/pyi" --distpath dist

# PyInstaller signs ad hoc; re-sign the whole bundle so it verifies as one (Apple Silicon needs it).
codesign --force --deep --sign - dist/piewall.app
codesign --verify --deep --strict dist/piewall.app

# Smoke test: the bundled CLI runs and reads without a password prompt.
dist/piewall.app/Contents/MacOS/piewall-cli list >/dev/null

# Installer package: macOS Installer asks for an admin password to install into /Applications,
# and apps it installs carry no quarantine flag, so piewall opens without Gatekeeper prompts.
version=$(sed -n 's/^version *= *"\([^"]*\)".*/\1/p' pyproject.toml | head -n1)
root="$work/pkgroot"
mkdir -p "$root/Applications"
ditto --noextattr --noqtn dist/piewall.app "$root/Applications/piewall.app"  # drop quarantine & co.
pkgbuild --analyze --root "$root" "$work/component.plist" >/dev/null
# Install exactly at /Applications/piewall.app, even if another copy exists elsewhere.
plutil -replace 0.BundleIsRelocatable -bool NO "$work/component.plist"
pkgbuild --root "$root" --component-plist "$work/component.plist" \
  --scripts packaging/macos-scripts --install-location / \
  --identifier io.github.theeraphatstudent.piewall --version "$version" "$work/component.pkg"

pkg="dist/release/piewall-macos-$arch.pkg"
rm -f "$pkg"
productbuild --package "$work/component.pkg" "$pkg"
(cd dist/release && shasum -a 256 "$(basename "$pkg")" > "$(basename "$pkg").sha256")
echo "Built $pkg"
