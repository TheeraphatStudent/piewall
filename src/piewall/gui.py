"""piewall desktop window (Tkinter/ttk)."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from .backend import Backend, FirewallError, batch
from .conflicts import Conflict, find_conflicts
from .elevate import ElevationCancelled, is_admin, run_elevated
from .listeners import current_listeners
from .model import PIEWALL_GROUP, Rule, filter_rules, parse_profiles
from .transfer import export_rules, import_rules
from . import theme

COLUMNS = [  # (id, heading, width, stretch)
    ("enabled", "On", 44, False),
    ("action", "Action", 70, False),
    ("direction", "Dir", 44, False),
    ("protocol", "Protocol", 72, False),
    ("ports", "Ports", 120, False),
    ("profiles", "Profiles", 130, False),
    ("name", "Name", 380, True),
    ("program", "Program", 200, False),
]
FILTER_ALL = "All"


def _row_values(r: Rule) -> tuple:
    return ("●" if r.enabled else "○", r.action.capitalize(), r.direction, r.protocol.upper(),
            r.ports_label, r.profiles_label, r.title, Path(r.program).name if r.program else "")


def _sort_key(column: str):
    getters = {
        "enabled": lambda r: not r.enabled,
        "action": lambda r: r.action,
        "direction": lambda r: r.direction,
        "protocol": lambda r: r.protocol,
        "ports": lambda r: r.ports_label.casefold(),
        "profiles": lambda r: r.profiles_label,
        "name": lambda r: r.title.casefold(),
        "program": lambda r: (r.program or "").casefold(),
    }
    return getters[column]


class OpenPortDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, muted: str) -> None:
        super().__init__(master)
        self.title("Open port")
        self.resizable(False, False)
        self.transient(master)
        self.result: Rule | None = None

        body = ttk.Frame(self, padding=16)
        body.grid(sticky="nsew")
        self.port = tk.StringVar()
        self.protocol = tk.StringVar(value="TCP")
        self.direction = tk.StringVar(value="Inbound")
        self.name = tk.StringVar()
        self.profiles = {p: tk.BooleanVar(value=True) for p in ("domain", "private", "public")}

        ttk.Label(body, text="Port").grid(row=0, column=0, sticky="w", pady=4)
        port_entry = ttk.Entry(body, textvariable=self.port, width=12)
        port_entry.grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(body, text="Protocol").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(body, textvariable=self.protocol, values=["TCP", "UDP", "Any"],
                     state="readonly", width=10).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(body, text="Direction").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(body, textvariable=self.direction, values=["Inbound", "Outbound"],
                     state="readonly", width=10).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(body, text="Networks").grid(row=3, column=0, sticky="nw", pady=4)
        nets = ttk.Frame(body)
        nets.grid(row=3, column=1, sticky="w", pady=4)
        for p, var in self.profiles.items():
            ttk.Checkbutton(nets, text=p.capitalize(), variable=var).pack(side="left", padx=(0, 8))

        ttk.Label(body, text="Name").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=self.name, width=34).grid(row=4, column=1, sticky="we", pady=4)
        ttk.Label(body, text="Optional. Default: piewall TCP <port> in", foreground=muted
                  ).grid(row=5, column=1, sticky="w")

        buttons = ttk.Frame(body)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Open port", style="Accent.TButton",
                   command=self._submit).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self.destroy())
        port_entry.focus_set()
        self.grab_set()

    def _submit(self) -> None:
        text = self.port.get().strip()
        if not text.isdigit() or not 1 <= int(text) <= 65535:
            messagebox.showerror("Open port", "Port must be a number from 1 to 65535.", parent=self)
            return
        chosen = [p for p, v in self.profiles.items() if v.get()]
        if not chosen:
            messagebox.showerror("Open port", "Pick at least one network type.", parent=self)
            return
        protocol = self.protocol.get().lower()
        direction = "in" if self.direction.get() == "Inbound" else "out"
        self.result = Rule(
            name=self.name.get().strip() or f"piewall {protocol.upper()} {text} {direction}",
            enabled=True, direction=direction, action="allow", protocol=protocol,
            local_ports=text, profiles=parse_profiles(chosen), group=PIEWALL_GROUP,
            description="Created by piewall",
        )
        self.destroy()


class App:
    def __init__(self, root: tk.Tk, backend: Backend, admin: bool) -> None:
        self.root = root
        self.backend = backend
        self.admin = admin
        self.rules: list[Rule] = []
        self.conflicts: list[Conflict] = []
        self.by_iid: dict[str, Rule] = {}
        self.sort_column, self.sort_reverse = "name", False
        self.pal = theme.palette_for(theme.system_mode())

        root.title("piewall" + ("  (Administrator)" if admin and sys.platform == "win32" else ""))
        root.geometry("1180x680")
        root.minsize(760, 420)
        self._style()
        self._menu()
        self._toolbar()
        self._banner()
        self._table()
        self._statusbar()
        self._recolor()
        self.reload()
        theme.watch_system_theme(root, self.set_mode)

    def set_mode(self, mode: str) -> None:
        self.pal = theme.apply_theme(self.root, mode)
        self._style_fonts()
        self._recolor()

    def _recolor(self) -> None:
        pal = self.pal
        self.tree.tag_configure("block", background=pal.block_row)
        self.tree.tag_configure("disabled", foreground=pal.disabled_fg)
        self.banner.configure(bg=pal.banner_bg, fg=pal.banner_fg)
        self.wordmark.configure(foreground=pal.text)
        ttk.Style(self.root).configure("Status.TLabel", foreground=pal.muted)
        entry, _ = self._search_hint
        if getattr(entry, "_hint", False):
            entry.configure(foreground=pal.muted)

    # ---------- layout ----------
    def _style(self) -> None:
        self.pal = theme.apply_theme(self.root, self.pal.mode)
        self._style_fonts()

    def _style_fonts(self) -> None:
        # Sun Valley ships Segoe UI Variable fonts; keep rows roomy (Fluent spacing).
        style = ttk.Style(self.root)
        base = tkfont.nametofont("TkDefaultFont")
        style.configure("Treeview", rowheight=int(base.metrics("linespace") * 1.9))
        style.configure("Status.TLabel", padding=(14, 6))
        style.configure("Wordmark.TLabel", font=(base.actual("family"), 13, "bold"))

    def _menu(self) -> None:
        # Windows 11 style: no classic menu bar; secondary actions live under "⋯".
        more = tk.Menu(self.root, tearoff=False)
        more.add_command(label="Refresh", accelerator="F5", command=self.reload)
        more.add_separator()
        more.add_command(label="Export all rules…", command=lambda: self.export(False))
        more.add_command(label="Export piewall rules…", command=lambda: self.export(True))
        more.add_command(label="Import rules…", command=self.import_)
        more.add_separator()
        more.add_command(label="Exit", command=self.root.destroy)
        self.more_menu = more
        self.root.bind("<F5>", lambda e: self.reload())

    def _post_more(self, button: ttk.Button) -> None:
        self.more_menu.tk_popup(button.winfo_rootx(),
                                button.winfo_rooty() + button.winfo_height() + 2)

    def _toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(12, 10, 12, 6))
        bar.pack(fill="x")
        self.toolbar = bar
        top = ttk.Frame(bar)
        top.pack(fill="x")
        filters = ttk.Frame(bar)
        filters.pack(fill="x", pady=(8, 0))

        # Row 1: search on the left, actions on the right.
        more = ttk.Button(top, text="⋯", width=3)
        more.configure(command=lambda: self._post_more(more))
        more.pack(side="right")
        if not self.admin:
            ttk.Button(top, text="Run as admin", command=self.restart_as_admin
                       ).pack(side="right", padx=(0, 8))
        ttk.Button(top, text="Open port…", style="Accent.TButton", command=self.open_port).pack(side="right", padx=(0, 8))
        self._mark = theme.wordmark_image(self.root)
        self.wordmark = ttk.Label(top, text=" piewall", image=self._mark, compound="left",
                                  style="Wordmark.TLabel")
        self.wordmark.pack(side="left", padx=(0, 16))
        self.search = tk.StringVar()
        search = ttk.Entry(top, textvariable=self.search)
        search.pack(side="left", fill="x", expand=True, padx=(0, 16))
        self._placeholder(search, self.search, "Search name, program or group   (Ctrl+F)")
        self.root.bind("<Control-f>", lambda e: search.focus_set())

        # Row 2: filters.
        self.port = tk.StringVar()
        ttk.Label(filters, text="Port").pack(side="left", padx=(0, 4))
        ttk.Entry(filters, textvariable=self.port, width=7).pack(side="left")
        self.any_port = tk.BooleanVar(value=False)
        ttk.Checkbutton(filters, text="+ any-port rules", variable=self.any_port
                        ).pack(side="left", padx=(6, 0))

        self.action = tk.StringVar(value=FILTER_ALL)
        self.direction = tk.StringVar(value=FILTER_ALL)
        self.state = tk.StringVar(value=FILTER_ALL)
        for label, var, values in [("Action", self.action, [FILTER_ALL, "Allow", "Block"]),
                                   ("Direction", self.direction, [FILTER_ALL, "Inbound", "Outbound"]),
                                   ("State", self.state, [FILTER_ALL, "Enabled", "Disabled"])]:
            ttk.Label(filters, text=label).pack(side="left", padx=(18, 4))
            ttk.Combobox(filters, textvariable=var, values=values, state="readonly",
                         width=9).pack(side="left")
        ttk.Button(filters, text="Clear filters", command=self.clear_filters).pack(side="right")

        for var in (self.search, self.port, self.any_port, self.action, self.direction,
                    self.state):
            var.trace_add("write", lambda *_: self.refresh_view())

    def clear_filters(self) -> None:
        entry, _ = self._search_hint
        if not getattr(entry, "_hint", False):
            self.search.set("")
            entry.event_generate("<FocusOut>")
        self.port.set("")
        self.any_port.set(False)
        for var in (self.action, self.direction, self.state):
            var.set(FILTER_ALL)

    def _placeholder(self, entry: ttk.Entry, var: tk.StringVar, text: str) -> None:
        # ttk has no placeholder; show grey hint text while empty and unfocused.
        entry._hint = True  # type: ignore[attr-defined]

        def show(_=None):
            if not var.get():
                entry._hint = True
                entry.configure(foreground=self.pal.muted)
                entry.insert(0, text)

        def hide(_=None):
            if entry._hint:
                entry._hint = False
                entry.delete(0, "end")
                entry.configure(foreground="")

        entry.bind("<FocusIn>", hide)
        entry.bind("<FocusOut>", show)
        show()
        self._search_hint = (entry, text)

    def _banner(self) -> None:
        self.banner = tk.Label(self.root, anchor="w",
                               padx=14, pady=6, cursor="hand2")
        self.banner.bind("<Button-1>", lambda e: self.show_conflicts())

    def _table(self) -> None:
        frame = ttk.Frame(self.root, padding=(12, 0, 12, 0))
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=[c[0] for c in COLUMNS], show="headings",
                                 selectmode="extended")
        for cid, heading, width, stretch in COLUMNS:
            self.tree.heading(cid, text=heading, anchor="w",
                              command=lambda c=cid: self.sort_by(c))
            self.tree.column(cid, width=width, stretch=stretch, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Enable", command=lambda: self.set_enabled(True))
        self.menu.add_command(label="Disable", command=lambda: self.set_enabled(False))
        self.menu.add_separator()
        self.menu.add_command(label="Make Allow", command=lambda: self.set_action("allow"))
        self.menu.add_command(label="Make Block", command=lambda: self.set_action("block"))
        self.menu.add_separator()
        self.menu.add_command(label="Delete…", command=self.delete)
        self.tree.bind("<Button-3>", self._popup)
        self.tree.bind("<Delete>", lambda e: self.delete())
        self.tree.bind("<Double-1>", lambda e: self.show_details())

    def _statusbar(self) -> None:
        self.status = ttk.Label(self.root, style="Status.TLabel", anchor="w")
        self.status.pack(fill="x", side="bottom")

    # ---------- data ----------
    def reload(self) -> None:
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        try:
            self.rules = self.backend.list_rules()
            self.conflicts = find_conflicts(self.rules, current_listeners())
        except Exception as exc:
            messagebox.showerror("piewall", f"Could not read firewall rules:\n{exc}")
            self.rules, self.conflicts = [], []
        finally:
            self.root.configure(cursor="")
        self._update_banner()
        self.refresh_view()

    def _filters(self) -> dict:
        entry, hint = self._search_hint
        search = "" if getattr(entry, "_hint", False) else self.search.get().strip()
        port_text = self.port.get().strip()
        choice = {FILTER_ALL: None, "Allow": "allow", "Block": "block",
                  "Inbound": "in", "Outbound": "out", "Enabled": True, "Disabled": False}
        return dict(search=search,
                    port=int(port_text) if port_text.isdigit() else None,
                    action=choice[self.action.get()],
                    direction=choice[self.direction.get()],
                    enabled=choice[self.state.get()],
                    any_port=self.any_port.get())

    def refresh_view(self) -> None:
        shown = filter_rules(self.rules, **self._filters())
        shown.sort(key=_sort_key(self.sort_column), reverse=self.sort_reverse)
        self.tree.delete(*self.tree.get_children())
        self.by_iid.clear()
        for i, r in enumerate(shown):
            tags = []
            if r.action == "block":
                tags.append("block")
            if not r.enabled:
                tags.append("disabled")
            iid = str(i)
            self.by_iid[iid] = r
            self.tree.insert("", "end", iid=iid, values=_row_values(r), tags=tags)
        for cid, heading, *_ in COLUMNS:
            arrow = (" ▼" if self.sort_reverse else " ▲") if cid == self.sort_column else ""
            self.tree.heading(cid, text=heading + arrow)
        admin = "Administrator" if self.admin else "Read-only - changes will ask for admin rights"
        self.status.configure(text=f"{len(shown)} shown  ·  {len(self.rules)} rules  ·  {admin}")

    def _update_banner(self) -> None:
        if self.conflicts:
            n = len(self.conflicts)
            self.banner.configure(text=f"⚠  {n} Block rule{'s' if n > 1 else ''} "
                                       f"overriding Allow rules. Click to review.")
            self.banner.pack(fill="x", after=self.toolbar, padx=12, pady=(0, 6))
        else:
            self.banner.pack_forget()

    def sort_by(self, column: str) -> None:
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column, self.sort_reverse = column, False
        self.refresh_view()

    def selected(self) -> list[Rule]:
        return [self.by_iid[i] for i in self.tree.selection()]

    def selected_names(self) -> list[str]:
        return sorted({r.name for r in self.selected()})

    def _popup(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        if self.tree.selection():
            self.menu.tk_popup(event.x_root, event.y_root)

    # ---------- actions ----------
    def _can_change(self) -> bool:
        if self.admin:
            return True
        if messagebox.askyesno(
                "Administrator rights needed",
                "Changing firewall rules needs administrator rights.\n\n"
                "Restart piewall as administrator?", parent=self.root):
            self.restart_as_admin()
        return False

    def restart_as_admin(self) -> None:
        try:
            run_elevated(["piewall.gui"], wait=False, windowed=True)
        except ElevationCancelled:
            return
        self.root.destroy()

    def _apply(self, work) -> None:
        try:
            with batch(self.backend):
                work()
        except ElevationCancelled:
            pass
        except FirewallError as exc:
            messagebox.showerror("piewall", str(exc), parent=self.root)
        self.reload()

    def set_enabled(self, on: bool) -> None:
        names = self.selected_names()
        if names and self._can_change():
            self._apply(lambda: [self.backend.set_enabled(n, on) for n in names])

    def set_action(self, action: str) -> None:
        names = self.selected_names()
        if names and self._can_change():
            self._apply(lambda: [self.backend.set_action(n, action) for n in names])

    def delete(self) -> None:
        names = self.selected_names()
        if not names or not self._can_change():
            return
        count = sum(1 for r in self.rules if r.name in names)
        listing = "\n".join(f"  • {n}" for n in names[:10]) + ("\n  …" if len(names) > 10 else "")
        if messagebox.askyesno("Delete rules",
                               f"Delete {count} rule(s)? This cannot be undone.\n\n{listing}",
                               icon="warning", default="no", parent=self.root):
            self._apply(lambda: [self.backend.delete_rules(n) for n in names])

    def open_port(self) -> None:
        if not self._can_change():
            return
        dialog = OpenPortDialog(self.root, self.pal.muted)
        self.root.wait_window(dialog)
        if dialog.result:
            rule = dialog.result
            self._apply(lambda: self.backend.add_rule(rule))
            self.port.set(rule.local_ports)  # show the new rule

    def export(self, piewall_only: bool) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile="piewall-rules.json" if piewall_only else "firewall-rules.json")
        if path:
            n = export_rules(self.rules, Path(path), piewall_only=piewall_only,
                             listeners=current_listeners())
            messagebox.showinfo("Export", f"Exported {n} rule(s).", parent=self.root)

    def import_(self) -> None:
        if not self._can_change():
            return
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with batch(self.backend):
                added, skipped = import_rules(self.backend, Path(path))
        except ElevationCancelled:
            self.reload()
            return
        except (FirewallError, ValueError, KeyError, OSError) as exc:
            messagebox.showerror("Import", f"Import failed:\n{exc}", parent=self.root)
        else:
            messagebox.showinfo("Import", f"Added {added} rule(s), skipped {skipped} "
                                          f"already present.", parent=self.root)
        self.reload()

    def show_details(self) -> None:
        rules = self.selected()
        if not rules:
            return
        r = rules[0]
        lines = [("Name", r.title), *([("Internal name", r.name)] if r.display_name else []),
                 ("Enabled", "Yes" if r.enabled else "No"),
                 ("Action", r.action.capitalize()), ("Direction", r.direction),
                 ("Protocol", r.protocol.upper()), ("Local ports", r.ports_label),
                 ("Remote addresses", r.remote_addresses), ("Program", r.program or "Any"),
                 ("Service", r.service or "Any"), ("Networks", r.profiles_label),
                 ("Group", r.group or "-"), ("Description", r.description or "-")]
        messagebox.showinfo("Rule details", "\n".join(f"{k}:  {v}" for k, v in lines),
                            parent=self.root)

    def show_conflicts(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Conflicts")
        win.transient(self.root)
        win.geometry("820x360")
        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Windows always lets Block win. These Block rules stop traffic "
                             "that an Allow rule is meant to let through:",
                  wraplength=780).pack(anchor="w", pady=(0, 8))
        pal = self.pal
        box = tk.Listbox(body, activestyle="none", selectmode="extended", borderwidth=0,
                         highlightthickness=0, bg=pal.list_bg, fg=pal.list_fg,
                         selectbackground=pal.list_select, selectforeground=pal.list_fg,
                         font=tkfont.nametofont("TkDefaultFont"))
        for c in self.conflicts:
            box.insert("end", c.describe())
        box.pack(fill="both", expand=True)

        def blockers() -> list[str]:
            picked = box.curselection() or range(len(self.conflicts))
            return sorted({self.conflicts[i].blocker.name for i in picked})

        def fix(action: str) -> None:
            names = blockers()
            if not self._can_change():
                return
            win.destroy()
            if action == "allow":
                self._apply(lambda: [self.backend.set_action(n, "allow") for n in names])
            else:
                self._apply(lambda: [self.backend.set_enabled(n, False) for n in names])

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Close", command=win.destroy).pack(side="right")
        ttk.Button(buttons, text="Disable blocking rule",
                   command=lambda: fix("disable")).pack(side="right", padx=(0, 8))
        ttk.Button(buttons, text="Make blocking rule Allow", style="Accent.TButton",
                   command=lambda: fix("allow")).pack(side="right", padx=(0, 8))
        ttk.Label(buttons, text="Applies to selected lines, or all if none selected.",
                  foreground=pal.muted).pack(side="left")


def main(backend_factory=None) -> None:
    theme.set_dpi_awareness()
    theme.set_app_id()
    if backend_factory is None:
        from .backend import default_backend as backend_factory
    root = tk.Tk()
    theme.set_icon(root)
    App(root, backend_factory(), is_admin())
    root.mainloop()


if __name__ == "__main__":
    main()
