"""Auto-update: checks GitHub Releases, downloads the .deb, installs it.

Design rules:
 - Never raises, never blocks the UI thread (callers use threads).
 - Result cached in ~/.cache/session-sync/update.json for UPDATE_CHECK_HOURS.
 - Install uses `pkexec apt-get install` for a GUI password prompt.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
from datetime import datetime

from config import APP_VERSION, GITHUB_REPO, UPDATE_CHECK_HOURS, CACHE_DIR

CACHE_PATH = os.path.join(CACHE_DIR, "update.json")
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
UA = f"session-sync/{APP_VERSION} (Linux Mint; +https://github.com/{GITHUB_REPO})"


def _version_tuple(tag: str) -> tuple:
    nums = re.findall(r"\d+", tag or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(latest_tag: str, current: str = APP_VERSION) -> bool:
    return _version_tuple(latest_tag) > _version_tuple(current)


def _http_json(url: str, timeout: int = 10):
    try:
        import requests
        r = requests.get(url, timeout=timeout,
                         headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
        r.raise_for_status()
        return r.json()
    except Exception:
        pass
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _read_cache():
    try:
        if not os.path.exists(CACHE_PATH):
            return None
        age_h = (datetime.now().timestamp() - os.path.getmtime(CACHE_PATH)) / 3600
        if age_h >= UPDATE_CHECK_HOURS:
            return None
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_cache(payload) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1)
    except Exception:
        pass


def check_for_update(force: bool = False):
    """Return dict or None.

    dict: {tag, version, deb_url, html_url, notes}
    None: up to date (or check failed). Never raises.
    """
    if not force:
        cached = _read_cache()
        if cached is not None:
            return cached.get("update") or None

    data = _http_json(API_URL)
    result = None
    if isinstance(data, dict):
        tag = str(data.get("tag_name") or "")
        if is_newer(tag):
            assets = data.get("assets") or []
            deb_url = ""
            for a in assets:
                name = str(a.get("name") or "")
                if name.endswith(".deb"):
                    deb_url = str(a.get("browser_download_url") or "")
                    break
            result = {
                "tag": tag,
                "version": tag.lstrip("vV"),
                "deb_url": deb_url,
                "html_url": str(data.get("html_url") or ""),
                "notes": (str(data.get("body") or ""))[:1500],
            }
    _write_cache({"checked": datetime.now().isoformat(timespec="seconds"),
                  "update": result})
    return result


def download_deb(url: str, dest_path: str) -> bool:
    """Download the release .deb. Returns True on success. Never raises."""
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        tmp = dest_path + ".part"
        ok = False
        try:
            import requests
            with requests.get(url, stream=True, timeout=60,
                              headers={"User-Agent": UA}) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            ok = True
        except Exception:
            ok = False
        if not ok:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
                f.write(resp.read())
            ok = True
        os.replace(tmp, dest_path)
        return True
    except Exception:
        try:
            if os.path.exists(dest_path + ".part"):
                os.remove(dest_path + ".part")
        except Exception:
            pass
        return False


def install_deb(deb_path: str) -> bool:
    """Install the .deb with a GUI password prompt (pkexec), sudo fallback."""
    if not os.path.exists(deb_path):
        return False
    for cmd in (["pkexec", "apt-get", "install", "-y", deb_path],
                ["sudo", "-n", "apt-get", "install", "-y", deb_path]):
        exe = cmd[0]
        if not _which(exe):
            continue
        try:
            code = subprocess.call(cmd)
            return code == 0
        except Exception:
            continue
    return False


def _which(name: str) -> bool:
    from shutil import which
    return which(name) is not None


def open_in_browser(url: str) -> None:
    try:
        if url:
            subprocess.Popen(["xdg-open", url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
