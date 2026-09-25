"""Render real piewall CLI output (demo rules) as a terminal-style SVG.

    uv run python scripts/cli_screenshot.py > cli.svg
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from fakes import FakeBackend  # noqa: E402
from screenshot import DEMO, LISTENERS  # noqa: E402

from piewall import cli  # noqa: E402

cli.current_listeners = lambda: LISTENERS
backend = FakeBackend(DEMO)
session = []
for argv in (["list", "--port", "8080", "--any-port"], ["conflicts"]):
    _, out = cli.execute(argv, backend_factory=lambda: backend, admin_check=lambda: True)
    session.append((argv, out.rstrip("\n").splitlines()))

W, LH, PAD, TOP, WRAP = 1180, 22, 28, 56, 124
lines: list[tuple[str, str]] = []  # ("cmd" or color, text)
for argv, out in session:
    lines.append(("cmd", "piewall-cli " + " ".join(f'"{a}"' if " " in a else a for a in argv)))
    for line in out:  # soft-wrap like a terminal would; pieces keep the line's color
        color = "#FF6961" if " overrides " in line else (
            "#A1A1A6" if line.startswith("  piewall") or line.endswith("rules") else "#E5E5EA")
        while len(line) > WRAP:
            cut = line.rfind(" ", 0, WRAP)
            cut = cut if cut > 40 else WRAP
            lines.append((color, line[:cut]))
            line = "    " + line[cut:].lstrip()
        lines.append((color, line))
    lines.append(("#E5E5EA", ""))
H = TOP + LH * len(lines) + PAD

svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       f'<rect width="{W}" height="{H}" rx="14" fill="#1C1C1E"/>',
       '<circle cx="28" cy="26" r="7" fill="#FF5F57"/><circle cx="52" cy="26" r="7" fill="#FEBC2E"/>'
       '<circle cx="76" cy="26" r="7" fill="#28C840"/>',
       f'<text x="{W / 2}" y="31" fill="#8E8E93" font-family="Segoe UI, sans-serif" font-size="14" '
       'text-anchor="middle">Terminal</text>',
       '<g font-family="Cascadia Mono, Consolas, monospace" font-size="15" xml:space="preserve">']
y = TOP + 14
for kind, text in lines:
    if kind == "cmd":
        svg.append(f'<text x="{PAD}" y="{y}"><tspan fill="#FF9F52">PS&gt; </tspan>'
                   f'<tspan fill="#F5F5F7">{escape(text)}</tspan></text>')
    else:
        svg.append(f'<text x="{PAD}" y="{y}" fill="{kind}">{escape(text)}</text>')
    y += LH
svg.append("</g></svg>")
print("\n".join(svg))
