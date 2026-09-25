"""Render the piewall window with demo rules and save a screenshot.

    uv run --with pillow python scripts/screenshot.py docs/images/app-light.png --mode light

Demo data only, so screenshots never show the machine's real rules.
"""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))


from fakes import FakeBackend  # noqa: E402
from piewall import gui, theme  # noqa: E402
from piewall.model import ALL_PROFILES, PIEWALL_GROUP, Rule  # noqa: E402

PUB = frozenset({"public"})
PRIV = frozenset({"private"})
HOME = frozenset({"private", "public"})


def r(name, action="allow", direction="in", protocol="tcp", ports="", program=None,
      profiles=ALL_PROFILES, enabled=True, group=""):
    return Rule(name=name, enabled=enabled, direction=direction, action=action,
                protocol=protocol, local_ports=ports, program=program, profiles=profiles,
                group=group)


DEMO = [
    r("piewall TCP 8080 in", ports="8080", profiles=PUB, group=PIEWALL_GROUP),
    r("piewall TCP 5173 in", ports="5173", profiles=PRIV, group=PIEWALL_GROUP),
    r("devserver", action="block", ports="", program=r"C:\Tools\devserver\devserver.exe",
      profiles=PUB),
    r("devserver", action="block", protocol="udp", program=r"C:\Tools\devserver\devserver.exe",
      profiles=PUB),
    r("Core Networking - DNS (UDP-Out)", direction="out", protocol="udp", ports="53"),
    r("Core Networking - DHCP (DHCP-In)", protocol="udp", ports="68"),
    r("File and Printer Sharing (SMB-In)", ports="445", profiles=PRIV),
    r("File and Printer Sharing (Echo Request - ICMPv4-In)", protocol="icmpv4", profiles=PRIV,
      enabled=False),
    r("Remote Desktop - User Mode (TCP-In)", ports="3389", enabled=False),
    r("Microsoft Teams", protocol="any", program=r"C:\Program Files\Teams\ms-teams.exe",
      profiles=HOME),
    r("Spotify Music", ports="57621", program=r"C:\Users\me\AppData\Roaming\Spotify\Spotify.exe"),
    r("Steam", protocol="udp", ports="27000-27100", program=r"C:\Program Files\Steam\steam.exe"),
    r("Telemetry uploader", action="block", direction="out", protocol="any",
      program=r"C:\Program Files\Vendor\telemetry.exe"),
    r("Visual Studio Code", protocol="any", program=r"C:\Program Files\VS Code\Code.exe",
      profiles=PRIV),
    r("Windows Media Player Network Sharing (HTTP-Streaming-In)", ports="10243",
      profiles=PRIV, enabled=False),
    r("Zoom Video Meeting", protocol="udp", ports="8801-8810", program=r"C:\Zoom\Zoom.exe"),
    r("mDNS (UDP-In)", protocol="udp", ports="5353", profiles=PRIV),
    r("Node.js JavaScript Runtime", protocol="any", program=r"C:\Program Files\nodejs\node.exe",
      profiles=PRIV),
]
LISTENERS = [(r"c:\tools\devserver\devserver.exe", "tcp", 8080)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--mode", choices=["light", "dark"], default="light")
    ap.add_argument("--size", default="1180x720")
    args = ap.parse_args()

    theme.set_dpi_awareness()
    theme.set_app_id()
    gui.current_listeners = lambda: LISTENERS
    theme.system_mode = lambda: args.mode
    theme.watch_system_theme = lambda root, cb: None

    root = tk.Tk()
    theme.set_icon(root)
    root.geometry(args.size)
    app = gui.App(root, FakeBackend(DEMO), admin=False)
    root.geometry(args.size + "+80+60")
    app.tree.selection_set(app.tree.get_children()[3])

    def snap() -> None:
        from PIL import ImageGrab
        root.lift()
        root.attributes("-topmost", True)
        root.update()
        # Exact window frame incl. title bar, without the drop shadow.
        import ctypes
        from ctypes import wintypes

        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        rect = wintypes.RECT()
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))  # EXTENDED_FRAME_BOUNDS
        left, frame_top = rect.left, rect.top
        width, height = rect.right - rect.left, rect.bottom - rect.top
        args.out.parent.mkdir(parents=True, exist_ok=True)
        ImageGrab.grab((left, frame_top, left + width, frame_top + height),
                       all_screens=True).save(args.out)
        print(args.out, width, height)
        root.destroy()

    root.after(2000, snap)
    root.mainloop()


if __name__ == "__main__":
    main()
