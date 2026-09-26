"""Which programs are listening on which local ports right now."""

from __future__ import annotations

import socket

import psutil

from .conflicts import Listener


def _connections() -> list[tuple[object, int | None]]:
    try:
        return [(c, c.pid) for c in psutil.net_connections(kind="inet")]
    except psutil.AccessDenied:  # macOS without root: only the processes we may inspect
        out = []
        for proc in psutil.process_iter():
            try:
                out += [(c, proc.pid) for c in proc.net_connections(kind="inet")]
            except psutil.Error:
                pass
        return out


def current_listeners() -> list[Listener]:
    out: set[Listener] = set()
    exe_cache: dict[int, str | None] = {}
    for conn, pid in _connections():
        if not conn.laddr or not pid:
            continue
        if conn.type == socket.SOCK_STREAM and conn.status != psutil.CONN_LISTEN:
            continue
        proto = "tcp" if conn.type == socket.SOCK_STREAM else "udp"
        if pid not in exe_cache:
            try:
                exe_cache[pid] = psutil.Process(pid).exe()
            except (psutil.Error, OSError):
                exe_cache[pid] = None
        exe = exe_cache[pid]
        if exe:
            out.add((exe.casefold(), proto, conn.laddr.port))
    return sorted(out)
