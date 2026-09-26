"""Update check: version comparison and asset choice. No network."""

import pytest

from piewall import update


def release(tag, *names):
    return {"tag_name": tag, "html_url": f"https://example/{tag}",
            "assets": [{"name": n, "browser_download_url": f"https://dl/{n}"} for n in names]}


@pytest.mark.parametrize("platform, machine, asset", [
    ("win32", "AMD64", "piewall-setup.exe"),
    ("darwin", "arm64", "piewall-macos-arm64.pkg"),
    ("darwin", "x86_64", "piewall-macos-x86_64.pkg"),
])
def test_newer_release_offers_this_machines_download(monkeypatch, platform, machine, asset):
    monkeypatch.setattr(update.sys, "platform", platform)
    monkeypatch.setattr(update.platform, "machine", lambda: machine)
    names = ["piewall-setup.exe", "piewall-macos-arm64.pkg", "piewall-macos-x86_64.pkg"]
    assert update.newer_release(release("v0.10.0", *names), "0.9.3") == ("0.10.0", f"https://dl/{asset}")


@pytest.mark.parametrize("tag, current", [("v0.2.1", "0.2.1"), ("v0.2.0", "0.2.1"),
                                          ("v0.3.0rc1", "0.2.1"), ("v0.3.0", "0.3.0.dev1")])
def test_no_offer_when_not_newer_or_unparseable(tag, current):
    assert update.newer_release(release(tag), current) is None


def test_falls_back_to_release_page_without_matching_asset():
    assert update.newer_release(release("v9.0.0"), "0.2.1") == ("9.0.0", "https://example/v9.0.0")
