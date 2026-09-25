"""PyInstaller entry point for piewall-cli.exe (console)."""

import sys

from piewall.cli import main

sys.exit(main())
