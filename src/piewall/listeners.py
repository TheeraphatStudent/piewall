"""Which programs are listening on which local ports right now."""

from __future__ import annotations

import socket

import psutil

from .conflicts import Listener


def current_listeners() -> list[Listener]:
    out: set[Listener] = set()
    exe_cache: dict[int, str | None] = {}
    for conn in psutil.net_connections(kind="inet"):
        if not conn.laddr or not conn.pid:
            continue
        if conn.type == socket.SOCK_STREAM and conn.status != psutil.CONN_LISTEN:
            continue
        proto = "tcp" if conn.type == socket.SOCK_STREAM else "udp"
        if conn.pid not in exe_cache:
            try:
                exe_cache[conn.pid] = psutil.Process(conn.pid).exe()
            except (psutil.Error, OSError):
                exe_cache[conn.pid] = None
        exe = exe_cache[conn.pid]
        if exe:
            out.add((exe.casefold(), proto, conn.laddr.port))
    return sorted(out)
