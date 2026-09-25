"""Windows look & feel: Sun Valley (Windows 11) ttk theme, system light/dark,
brand colors, app icon, taskbar identity and a matching title bar."""

from __future__ import annotations

import ctypes
import threading
import tkinter as tk
from dataclasses import dataclass
from importlib import resources
from typing import Callable

APP_ID = "Theeraphat.piewall"


@dataclass(frozen=True)
class Palette:
    mode: str  # "light" | "dark"
    accent: str  # brand orange for small accents (wordmark, focus bits)
    text: str
    muted: str
    block_row: str
    disabled_fg: str
    banner_bg: str
    banner_fg: str
    list_bg: str
    list_fg: str
    list_select: str


LIGHT = Palette("light", accent="#C2410C", text="#1D1D1F", muted="#6E6E73",
                block_row="#FDECEC", disabled_fg="#8A8F98",
                banner_bg="#FFF4CE", banner_fg="#5C4400",
                list_bg="#FFFFFF", list_fg="#1D1D1F", list_select="#FFD9B8")
DARK = Palette("dark", accent="#FF9F52", text="#F5F5F7", muted="#A1A1A6",
               block_row="#3D2124", disabled_fg="#7C7C82",
               banner_bg="#3A3000", banner_fg="#FFE58F",
               list_bg="#1C1C1C", list_fg="#F5F5F7", list_select="#5A3418")


def system_mode() -> str:
    try:
        import darkdetect

        return "dark" if darkdetect.isDark() else "light"
    except Exception:
        return "light"


def palette_for(mode: str) -> Palette:
    return DARK if mode == "dark" else LIGHT


def set_app_id() -> None:
    """Own taskbar group + icon instead of python/pythonw's. Call before Tk()."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError):
        pass


def set_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _asset(name: str):
    return resources.files("piewall") / "assets" / name


def set_icon(root: tk.Tk) -> None:
    try:
        with resources.as_file(_asset("piewall.ico")) as ico:
            root.iconbitmap(default=str(ico))  # crisp small title-bar icon
        big = tk.PhotoImage(master=root, file=str(_asset("icon-256.png")))
        small = tk.PhotoImage(master=root, file=str(_asset("icon-32.png")))
        root.iconphoto(True, big, small)
        root._piewall_icons = (big, small)  # keep references alive
    except (tk.TclError, OSError, FileNotFoundError):
        pass


def wordmark_image(root: tk.Misc, size: int = 22) -> tk.PhotoImage | None:
    try:
        img = tk.PhotoImage(master=root, file=str(_asset("icon-32.png")))
        if size < 32:
            img = img.subsample(max(1, round(32 / size)))
        return img
    except (tk.TclError, OSError, FileNotFoundError):
        return None


def set_title_bar(root: tk.Tk, dark: bool) -> None:
    """Dark/light title bar on Windows 10 20H1+ / 11 (DWMWA_USE_IMMERSIVE_DARK_MODE)."""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # 19 on pre-20H1 builds
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except (AttributeError, OSError):
        pass


def set_menu_mode(dark: bool) -> None:
    """Dark native popup menus. uxtheme ordinals 135 (SetPreferredAppMode) and
    136 (FlushMenuThemes) are undocumented but stable since Windows 10 1903."""
    try:
        uxtheme = ctypes.WinDLL("uxtheme")
        set_mode = uxtheme[135]
        set_mode.argtypes = [ctypes.c_int]
        set_mode(2 if dark else 3)  # ForceDark / ForceLight
        uxtheme[136]()
    except (AttributeError, OSError):
        pass


def apply_theme(root: tk.Tk, mode: str) -> Palette:
    try:
        import sv_ttk

        sv_ttk.set_theme(mode, root)
    except Exception:
        pass
    set_menu_mode(mode == "dark")
    set_title_bar(root, mode == "dark")
    return palette_for(mode)


def watch_system_theme(root: tk.Tk, on_change: Callable[[str], None]) -> None:
    """Follow Windows light/dark switches while the app runs."""
    try:
        import darkdetect
    except ImportError:
        return

    def listen() -> None:
        try:
            darkdetect.listener(
                lambda value: root.after(0, on_change, "dark" if value == "Dark" else "light"))
        except Exception:
            pass

    threading.Thread(target=listen, daemon=True, name="piewall-theme").start()
