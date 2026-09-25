import tkinter as tk

import pytest

from pywall import gui
from pywall.model import Rule

from fakes import FakeBackend


@pytest.fixture(scope="module")
def root():
    # One Tk interpreter per module: creating/destroying several in one process
    # intermittently fails with "Can't find a usable init.tcl" (the app makes one).
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def app(root, monkeypatch):
    monkeypatch.setattr(gui, "current_listeners",
                        lambda: [(r"d:\x\app.exe", "tcp", 8080)])
    backend = FakeBackend([
        Rule(name="web", enabled=True, direction="in", action="allow", protocol="tcp",
             local_ports="8080"),
        Rule(name="app-block", enabled=True, direction="in", action="block", protocol="tcp",
             local_ports="*", program=r"D:\x\app.exe"),
        Rule(name="old", enabled=False, direction="out", action="allow"),
    ])
    yield gui.App(root, backend, admin=True)
    for child in root.winfo_children():
        child.destroy()


def test_rows_tags_and_banner(app):
    rows = {app.tree.item(i, "values")[6]: app.tree.item(i, "tags") for i in app.tree.get_children()}
    assert set(rows) == {"web", "app-block", "old"}
    assert "block" in rows["app-block"]
    assert "disabled" in rows["old"]
    assert app.banner.winfo_manager() == "pack"
    assert "1 Block rule" in app.banner.cget("text")


def test_filters(app):
    app.action.set("Block")
    assert [app.tree.item(i, "values")[6] for i in app.tree.get_children()] == ["app-block"]
    app.action.set("All")
    app.state.set("Disabled")
    assert [app.tree.item(i, "values")[6] for i in app.tree.get_children()] == ["old"]


def test_hint_text_is_not_a_search(app):
    assert len(app.tree.get_children()) == 3


def test_make_allow_clears_conflict(app):
    iid = next(i for i in app.tree.get_children() if app.tree.item(i, "values")[6] == "app-block")
    app.tree.selection_set(iid)
    app.set_action("allow")
    assert app.conflicts == []
    assert app.banner.winfo_manager() == ""
