"""Admin detection and UAC relaunch."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path


class ElevationCancelled(Exception):
    pass


def is_admin() -> bool:
    if sys.platform == "darwin":
        return True  # pf.PfBackend asks for the admin password itself, once per change
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _python(windowed: bool) -> str:
    exe = Path(sys.executable)
    if windowed:
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(exe)


# Frozen (PyInstaller) builds ship one exe per entry point instead of `python -m`.
FROZEN_EXES = {"piewall": "piewall-cli.exe", "piewall.gui": "piewall.exe"}


def _command(module_args: list[str], windowed: bool) -> tuple[str, str]:
    """Return (file, parameters) that re-run `module_args` in a new process."""
    if getattr(sys, "frozen", False):
        module, *rest = module_args
        try:
            name = FROZEN_EXES[module]
        except KeyError:
            raise ValueError(f"no frozen executable for module {module!r}") from None
        exe = Path(sys.executable)
        target = exe.with_name(name)
        # A renamed portable exe still relaunches itself (callers relaunch their own kind).
        return str(target if target.exists() else exe), subprocess.list2cmdline(rest)
    return _python(windowed), subprocess.list2cmdline(["-m", *module_args])


def run_elevated(module_args: list[str], *, wait: bool, windowed: bool = False) -> int:
    """Run `python -m <module_args>` elevated via UAC. Returns the exit code when waiting.

    In a frozen build the module is mapped to its exe next to sys.executable.
    """
    import pywintypes
    import win32con
    import win32event
    import win32process
    from win32com.shell import shell, shellcon

    file, parameters = _command(module_args, windowed)
    try:
        info = shell.ShellExecuteEx(
            fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
            lpVerb="runas",
            lpFile=file,
            lpParameters=parameters,
            lpDirectory=os.getcwd(),
            nShow=win32con.SW_HIDE if not windowed else win32con.SW_SHOWNORMAL,
        )
    except pywintypes.error as exc:
        if exc.winerror == 1223:  # ERROR_CANCELLED: user said no to UAC
            raise ElevationCancelled from exc
        raise
    if not wait:
        return 0
    handle = info["hProcess"]
    win32event.WaitForSingleObject(handle, win32event.INFINITE)
    return win32process.GetExitCodeProcess(handle)
