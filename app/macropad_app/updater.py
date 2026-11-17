"""App updates from GitHub releases, and the file check for "Repair".

Each release carries:
    MacroPad-Setup-<version>.exe   the installer
    manifest.json                  {"version", "firmware", "setup": {"name", "sha256", "size"},
                                    "files": {"relative/path": "sha256", ...}}
The installer is only started after its SHA-256 matches the manifest.
"""

import hashlib
import json
import logging
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import VERSION, paths, protocol

log = logging.getLogger("macropad.update")

API = "https://api.github.com/repos/{repo}/releases/latest"
TAG_API = "https://api.github.com/repos/{repo}/releases/tags/v{version}"
USER_AGENT = f"MacroPadApp/{VERSION}"
CHUNK = 64 * 1024


class UpdateError(Exception):
    pass


class Cancelled(Exception):
    pass


@dataclass
class Release:
    version: str
    notes: str = ""
    notes_by_lang: dict = field(default_factory=dict)   # {"en": [...], "de": [...]} from the manifest
    setup_name: str = ""
    setup_url: str = ""
    setup_size: int = 0
    setup_sha256: str = ""
    firmware: str = ""
    files: dict = field(default_factory=dict)

    @property
    def newer(self) -> bool:
        return protocol.is_newer(self.version, VERSION)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    ctx = ssl.create_default_context()   # Windows' own certificate store
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def _get_json(url, timeout=15):
    try:
        with _get(url, timeout) as r:
            return json.loads(r.read(2_000_000).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("no release found") from e
        if e.code == 403:
            raise UpdateError("GitHub limit reached, try again in an hour") from e
        raise UpdateError(f"GitHub answered {e.code}") from e
    except urllib.error.URLError as e:
        raise UpdateError("no internet connection") from e
    except (TimeoutError, OSError) as e:
        raise UpdateError(f"network problem ({e})") from e
    except (ValueError, UnicodeDecodeError) as e:
        raise UpdateError("unexpected answer from GitHub") from e


def _release_from(data) -> Release:
    if not isinstance(data, dict):
        raise UpdateError("unexpected answer from GitHub")
    assets = {a.get("name"): a for a in data.get("assets", []) if isinstance(a, dict)}
    man_asset = assets.get("manifest.json")
    if not man_asset:
        raise UpdateError("the release has no manifest.json")
    manifest = _get_json(man_asset["browser_download_url"])
    if not isinstance(manifest, dict) or "version" not in manifest:
        raise UpdateError("broken manifest.json")
    setup = manifest.get("setup") or {}
    setup_asset = assets.get(setup.get("name", ""))
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    return Release(
        version=str(manifest["version"]),
        notes=str(data.get("body") or "")[:4000],
        notes_by_lang={k: [str(x)[:200] for x in v[:20]] for k, v in (manifest.get("notes") or {}).items()
                       if k in ("en", "de") and isinstance(v, list)} if isinstance(manifest.get("notes"), dict) else {},
        setup_name=str(setup.get("name", "")),
        setup_url=setup_asset["browser_download_url"] if setup_asset else "",
        setup_size=int(setup.get("size") or (setup_asset or {}).get("size") or 0),
        setup_sha256=str(setup.get("sha256", "")).lower(),
        firmware=str(manifest.get("firmware", "")),
        files=files,
    )


def latest_release(repo: str) -> Release:
    if not repo:
        raise UpdateError("updates are not set up")
    return _release_from(_get_json(API.format(repo=repo)))


def release_for(repo: str, version: str) -> Release:
    return _release_from(_get_json(TAG_API.format(repo=repo, version=version)))


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(release: Release, progress=None, cancel=None) -> Path:
    """Downloads the installer (resumes nothing, but never leaves a half file
    behind). progress(done_bytes, total_bytes); cancel: threading.Event."""
    if not release.setup_url or not release.setup_sha256:
        raise UpdateError("the release has no installer")
    target = paths.downloads_dir() / release.setup_name
    if target.exists() and sha256_of(target) == release.setup_sha256:
        if progress:
            progress(release.setup_size, release.setup_size)
        return target
    part = target.with_suffix(".part")
    try:
        with _get(release.setup_url, timeout=30) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or release.setup_size or 0)
            done = 0
            while True:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                block = r.read(CHUNK)
                if not block:
                    break
                f.write(block)
                done += len(block)
                if progress:
                    progress(done, total)
        if sha256_of(part) != release.setup_sha256:
            raise UpdateError("the download is damaged (checksum does not match)")
        os.replace(part, target)
        return target
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UpdateError(f"download failed ({e})") from e
    finally:
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass


def _writable(folder: Path) -> bool:
    try:
        probe = folder / f".write_test_{os.getpid()}"
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def start_installer(setup: Path) -> bool:
    """Runs the installer silently over the current installation; it closes this
    app, updates it and starts it again. Asks for admin rights (UAC) when the
    app sits in a protected folder such as Program Files."""
    install = paths.install_dir()
    admin = not _writable(install)
    args = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RELAUNCH=1",
            f'/DIR="{install}"', "/ALLUSERS" if admin else "/CURRENTUSER"]
    if sys.platform != "win32":
        log.info("Installer would run: %s %s", setup, " ".join(args))
        return False
    try:
        import ctypes
        params = " ".join(args)
        verb = "runas" if admin else "open"
        rc = ctypes.windll.shell32.ShellExecuteW(None, verb, str(setup), params, None, 1)
        if rc <= 32:
            raise UpdateError(f"Windows could not start the installer (code {rc})")
        return True
    except UpdateError:
        raise
    except Exception as e:
        raise UpdateError(f"could not start the installer ({e})") from e


def check_files(files: dict, base: Path | None = None):
    """Compares the installed files with the release list.
    Returns (ok_count, bad: list of relative paths)."""
    base = base or paths.install_dir()
    ok, bad = 0, []
    for rel, digest in sorted(files.items()):
        p = (base / rel).resolve()
        try:
            p.relative_to(base.resolve())        # never look outside the app folder
        except ValueError:
            continue
        try:
            if p.is_file() and sha256_of(p) == str(digest).lower():
                ok += 1
            else:
                bad.append(rel)
        except OSError:
            bad.append(rel)
    return ok, bad


def due_for_check(settings: dict, every_hours=12) -> bool:
    up = settings.get("updates", {})
    return bool(up.get("auto_check")) and time.time() - float(up.get("last_check") or 0) > every_hours * 3600
