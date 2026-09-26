"""run_elevated builds the right command in source and frozen (PyInstaller) mode."""

import sys

import pytest

pywintypes = pytest.importorskip("pywintypes")  # Windows-only module
import win32con
import win32event
import win32process
from win32com.shell import shell

from piewall import elevate


@pytest.fixture
def shellexec(monkeypatch):
    """Capture ShellExecuteEx calls instead of showing a UAC prompt."""
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return {"hProcess": "HANDLE"}

    monkeypatch.setattr(shell, "ShellExecuteEx", fake)
    monkeypatch.setattr(win32event, "WaitForSingleObject", lambda handle, ms: 0)
    monkeypatch.setattr(win32process, "GetExitCodeProcess", lambda handle: 7)
    return calls


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    """Pretend we run from a PyInstaller build in tmp_path with both exes present."""
    for name in ("piewall.exe", "piewall-cli.exe"):
        (tmp_path / name).write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "piewall.exe"))
    return tmp_path


def test_source_mode_runs_python_dash_m(monkeypatch, tmp_path, shellexec):
    monkeypatch.delattr(sys, "frozen", raising=False)
    (tmp_path / "python.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    code = elevate.run_elevated(["piewall", "--elevated-output", r"C:\t\o u.txt", "open", "80"],
                                wait=True)
    assert code == 7
    (call,) = shellexec
    assert call["lpVerb"] == "runas"
    assert call["lpFile"] == str(tmp_path / "python.exe")
    assert call["lpParameters"] == '-m piewall --elevated-output "C:\\t\\o u.txt" open 80'
    assert call["nShow"] == win32con.SW_HIDE


def test_source_mode_windowed_prefers_pythonw(monkeypatch, tmp_path, shellexec):
    monkeypatch.delattr(sys, "frozen", raising=False)
    for name in ("python.exe", "pythonw.exe"):
        (tmp_path / name).write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    assert elevate.run_elevated(["piewall.gui"], wait=False, windowed=True) == 0
    (call,) = shellexec
    assert call["lpFile"] == str(tmp_path / "pythonw.exe")
    assert call["lpParameters"] == "-m piewall.gui"
    assert call["nShow"] == win32con.SW_SHOWNORMAL


def test_frozen_cli_maps_to_piewall_cli_exe(frozen, shellexec):
    code = elevate.run_elevated(["piewall", "--elevated-output", r"C:\t\o u.txt", "close", "8080"],
                                wait=True)
    assert code == 7
    (call,) = shellexec
    assert call["lpFile"] == str(frozen / "piewall-cli.exe")
    assert call["lpParameters"] == '--elevated-output "C:\\t\\o u.txt" close 8080'
    assert call["nShow"] == win32con.SW_HIDE


def test_frozen_gui_maps_to_piewall_exe(frozen, monkeypatch, shellexec):
    monkeypatch.setattr(sys, "executable", str(frozen / "piewall-cli.exe"))
    assert elevate.run_elevated(["piewall.gui"], wait=False, windowed=True) == 0
    (call,) = shellexec
    assert call["lpFile"] == str(frozen / "piewall.exe")
    assert call["lpParameters"] == ""
    assert call["nShow"] == win32con.SW_SHOWNORMAL


def test_frozen_renamed_portable_exe_relaunches_itself(monkeypatch, tmp_path, shellexec):
    (tmp_path / "piewall-0.1.0.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "piewall-0.1.0.exe"))
    elevate.run_elevated(["piewall.gui"], wait=False, windowed=True)
    assert shellexec[0]["lpFile"] == str(tmp_path / "piewall-0.1.0.exe")


def test_frozen_unknown_module_is_an_error(frozen, shellexec):
    with pytest.raises(ValueError):
        elevate.run_elevated(["something.else"], wait=False)
    assert shellexec == []


def test_uac_cancel_raises_elevation_cancelled(frozen, monkeypatch):
    def cancelled(**kwargs):
        raise pywintypes.error(1223, "ShellExecuteEx", "The operation was canceled by the user.")

    monkeypatch.setattr(shell, "ShellExecuteEx", cancelled)
    with pytest.raises(elevate.ElevationCancelled):
        elevate.run_elevated(["piewall", "open", "80"], wait=True)
