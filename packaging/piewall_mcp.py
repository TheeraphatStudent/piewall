"""PyInstaller entry point for piewall-mcp.exe (console MCP server; CLI subcommands pass through)."""

import sys

from piewall.mcp_server import main

sys.exit(main())
