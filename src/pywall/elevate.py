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


def run_elevated(module_args: list[str], *, wait: bool, windowed: bool = False) -> int:
    """Run `python -m <module_args>` elevated via UAC. Returns the exit code when waiting."""
    import pywintypes
    import win32con
    import win32event
    import win32process
    from win32com.shell import shell, shellcon

    try:
        info = shell.ShellExecuteEx(
            fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
            lpVerb="runas",
            lpFile=_python(windowed),
            lpParameters=subprocess.list2cmdline(["-m", *module_args]),
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
