"""Backup/restore app data (internal + external) with checksums."""
from __future__ import annotations

import hashlib
import tarfile
import time
from pathlib import Path

from . import util

BACKUPS = util.STATE / "backups"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup(pkg: str, cfg: dict | None = None, name: str | None = None) -> Path:
    cfg = cfg or {}
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = BACKUPS / (name or f"{pkg}-{stamp}.tar.gz")
    if dest.suffix != ".gz":
        dest = dest.with_name(dest.name + ".tar.gz")
    tmp = f"/sdcard/Download/.dops-backup-{pkg}.tar"
    paths = [f"/data/data/{pkg}", f"/sdcard/Android/data/{pkg}"]
    paths += [util.expand(p, {"package": pkg}) for p in cfg.get("save_paths", [])]
    existing = " ".join(p for p in paths if _exists(p))
    util.dev(f"tar -czf {util.shell_quote(tmp)} {existing} 2>/dev/null || true", timeout=180)
    util.dev_pull(tmp, dest)
    util.dev(f"rm -f {util.shell_quote(tmp)}")
    meta = dest.with_suffix(dest.suffix + ".sha256")
    meta.write_text(_sha256(dest) + "\n")
    return dest


def restore(pkg: str, archive: Path) -> None:
    if not archive.exists():
        raise util.DopsError(f"archive not found: {archive}")
    remote = f"/sdcard/Download/.dops-restore-{pkg}.tar.gz"
    util.dev_push(archive, remote)
    # tar rc=1 means warnings only (changed/vanished files); rc>=2 is an error
    util.dev(f"tar -xf {util.shell_quote(remote)} -C / 2>/dev/null; rc=$?; rm -f {util.shell_quote(remote)}; test $rc -le 1", timeout=180)
def list_backups(pkg: str | None = None) -> list[str]:
    if not BACKUPS.exists():
        return []
    out = []
    for p in sorted(BACKUPS.glob("*.tar.gz")):
        if pkg and not p.name.startswith(pkg):
            continue
        sha = p.with_suffix(p.suffix + ".sha256")
        out.append(f"{p.name}  {p.stat().st_size} B  {_sha256(p)[:12] if sha.exists() else ''}")
    return out


def _exists(path: str) -> bool:
    try:
        util.dev(f"test -e {util.shell_quote(path)}", timeout=30)
        return True
    except util.DopsError:
        return False
