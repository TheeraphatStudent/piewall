# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for piewall.app (macOS). packaging/build-macos.sh runs it.

One bundle, two executables sharing Contents/Frameworks:
  Contents/MacOS/piewall      windowed GUI  (piewall.gui:main)
  Contents/MacOS/piewall-cli  console CLI   (piewall.cli:main)
"""

import os
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

HERE = Path(SPECPATH)  # noqa: F821 (injected by PyInstaller)
ROOT = HERE.parent
SRC = ROOT / "src"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
ICON = os.environ.get("PIEWALL_ICNS")  # made by build-macos.sh with iconutil

DATAS = [(str(SRC / "piewall" / "assets"), "piewall/assets"), *collect_data_files("sv_ttk")]
EXCLUDES = ["pytest", "_pytest", "pip", "setuptools", "pkg_resources", "lib2to3", "idlelib",
            "pydoc_data", "turtle", "turtledemo", "test", "tkinter.test", "numpy", "PIL",
            "mcp", "uvicorn", "starlette", "pydantic"]  # MCP server is not bundled on macOS


def analysis(script: str):
    return Analysis(  # noqa: F821
        [str(HERE / script)], pathex=[str(SRC)], datas=DATAS,
        hiddenimports=["sv_ttk", "darkdetect", "piewall.pf"], excludes=EXCLUDES, optimize=1)


def exe(a, name: str, console: bool):
    return EXE(  # noqa: F821
        PYZ(a.pure), a.scripts, [], exclude_binaries=True, name=name, console=console,  # noqa: F821
        strip=False, upx=False, target_arch=None, argv_emulation=False)


gui_a, cli_a = analysis("piewall_gui.py"), analysis("piewall_cli.py")
coll = COLLECT(  # noqa: F821
    exe(gui_a, "piewall", console=False), gui_a.binaries, gui_a.datas,
    exe(cli_a, "piewall-cli", console=True), cli_a.binaries, cli_a.datas,
    strip=False, upx=False, name="piewall")

BUNDLE(  # noqa: F821
    coll,
    name="piewall.app",
    icon=ICON,
    bundle_identifier="io.github.theeraphatstudent.piewall",
    version=VERSION,
    info_plist={
        "CFBundleExecutable": "piewall",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,  # follow light/dark
        "NSHumanReadableCopyright": "© 2026 Theeraphat. MIT License.",
    },
)
