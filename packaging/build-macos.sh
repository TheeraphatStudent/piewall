#!/bin/sh
# Build dist/release/piewall-macos-<arch>.dmg (piewall.app inside). Run from anywhere on macOS.
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

dmg="dist/release/piewall-macos-$arch.dmg"
rm -f "$dmg"
stage="$work/dmg"
mkdir -p "$stage"
cp -R dist/piewall.app "$stage/"
ln -s /Applications "$stage/Applications"
hdiutil create -volname piewall -srcfolder "$stage" -format UDZO -fs HFS+ "$dmg" >/dev/null
(cd dist/release && shasum -a 256 "$(basename "$dmg")" > "$(basename "$dmg").sha256")
echo "Built $dmg"
