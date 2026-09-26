"""Ask GitHub whether a newer piewall release is out."""

from __future__ import annotations

import json
import platform
import sys
import urllib.request
from importlib import metadata

LATEST_URL = "https://api.github.com/repos/TheeraphatStudent/piewall/releases/latest"


def current_version() -> str:
    try:
        return metadata.version("piewall")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def _parse(version: str) -> tuple[int, ...] | None:
    """'v0.2.1' -> (0, 2, 1); None for anything else (pre-releases, dev builds)."""
    try:
        return tuple(int(part) for part in version.removeprefix("v").split("."))
    except ValueError:
        return None


def asset_name() -> str:
    """The release file this machine should download."""
    if sys.platform == "darwin":
        return f"piewall-macos-{'arm64' if platform.machine() == 'arm64' else 'x86_64'}.pkg"
    return "piewall-setup.exe"


def newer_release(release: dict, current: str) -> tuple[str, str] | None:
    """(version, download URL) when `release` (GitHub API JSON) is newer than `current`."""
    latest, mine = _parse(release.get("tag_name", "")), _parse(current)
    if latest is None or mine is None or latest <= mine:
        return None
    urls = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    return release["tag_name"].removeprefix("v"), urls.get(asset_name(), release["html_url"])


def check(timeout: float = 5) -> tuple[str, str] | None:
    """Network call. Raises OSError (offline, HTTP error) or ValueError (bad JSON)."""
    current = current_version()
    request = urllib.request.Request(LATEST_URL, headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"piewall/{current}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return newer_release(json.load(response), current)
