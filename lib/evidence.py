"""Evidence capture: logcat, screenshot, and selected app files into a timestamped bundle."""
from __future__ import annotations

import time
from pathlib import Path

from . import util


def capture(pkg: str, cfg: dict | None = None, seconds: int = 0, tag: str = "") -> Path:
    cfg = cfg or {}
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = util.STATE / "evidence" / f"{pkg}-{stamp}{('-' + tag) if tag else ''}"
    dest.mkdir(parents=True, exist_ok=True)

    if seconds:
        util.dev(f"logcat -c", timeout=30)
        time.sleep(seconds)
    log = util.dev("logcat -d -v threadtime", timeout=180)
    (dest / "logcat.txt").write_text(log, errors="replace")

    shot = f"/sdcard/Download/.dops-shot-{pkg}.png"
    util.dev(f"screencap -p {shot}", timeout=60)
    try:
        util.dev_pull(shot, dest / "screen.png")
    finally:
        util.dev(f"rm -f {shot}")

    paths = [f"/data/data/{pkg}/shared_prefs", f"/sdcard/Android/data/{pkg}/files"]
    paths += [util.expand(p, {"package": pkg}) for p in cfg.get("save_paths", [])]
    manifest = []
    for i, p in enumerate(paths):
        tmp = f"/sdcard/Download/.dops-ev-{pkg}-{i}.tar"
        try:
            util.dev(f"tar -cf {tmp} {p} 2>/dev/null || true", timeout=120)
            util.dev_pull(tmp, dest / f"files-{i}.tar")
            util.dev(f"rm -f {tmp}")
            manifest.append(f"files-{i}.tar <- {p}")
        except util.DopsError:
            continue
    (dest / "MANIFEST").write_text("\n".join(manifest) + f"\npackage={pkg}\n", errors="replace")
    return dest
