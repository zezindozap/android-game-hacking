"""FKIAB (LSPosed FakeBinder) operations: scope, injected status, GumJS scripts, fake receipts."""
from __future__ import annotations

import html
import json
import random
import re
import string
import time
from pathlib import Path

from . import lsposed, util

FKIAB = "com.fuck.iab"
SCRIPTS = f"/data/data/{FKIAB}/files/scripts"


def _fk_uid() -> int | None:
    try:
        out = util.dev(f"dumpsys package {FKIAB} | grep -oE '(appId|userId)=[0-9]+' | head -1", timeout=60)
        return int(out.strip().split("=")[-1])
    except Exception:  # noqa: BLE001
        return None


def status(pkg: str) -> dict:
    cmd = "; ".join([
        "echo '@@VER'; dumpsys package com.fuck.iab | grep -m1 versionName",
        "echo '@@UID'; dumpsys package com.fuck.iab | grep -oE '(appId|userId)=[0-9]+' | head -1",
        f"echo '@@SCRIPTS'; ls {SCRIPTS} 2>/dev/null",
        f"echo '@@PID'; pidof {pkg}",
        f"echo '@@MAPS'; p=$(pidof {pkg}); [ -n \"$p\" ] && grep -c 'com.fuck.iab' /proc/$p/maps 2>/dev/null || echo 0",
        "echo '@@RECEIPTS'; cat " + _prefs_path(pkg, {}) + " 2>/dev/null",
    ])
    raw = util.dev(cmd, timeout=120)
    sec: dict[str, list[str]] = {}
    cur = None
    for line in raw.splitlines():
        if line.startswith("@@"):
            cur = line[2:].strip()
            sec[cur] = []
        elif cur:
            sec[cur].append(line)
    ver = "".join(sec.get("VER", [])).strip().split("=")[-1]
    uid_txt = "".join(sec.get("UID", []))
    uid = int(uid_txt.split("=")[-1]) if "=" in uid_txt else None
    res = {"installed": uid is not None, "uid": uid, "version": ver or None,
           "injected": "".join(sec.get("MAPS", [])).strip() not in ("", "0"),
           "scripts": [l.split("/")[-1] for l in sec.get("SCRIPTS", []) if l.strip()],
           "receipts": _parse_receipts("\n".join(sec.get("RECEIPTS", []))), "scope": []}
    try:
        res["scope"] = lsposed.scope_list(FKIAB)
    except Exception as e:  # noqa: BLE001
        res["scope_error"] = str(e)
    return res


def _parse_receipts(text: str) -> list[dict]:
    out = []
    for _key, val in re.findall(r'<string name="([^"]+)">(.*?)</string>', text, re.S):
        try:
            j = json.loads(html.unescape(val))
            out.append({"productId": j.get("productId"), "orderId": j.get("orderId"),
                        "purchaseTime": j.get("purchaseTime")})
        except Exception:  # noqa: BLE001
            continue
    return out


def _pid(pkg: str) -> str | None:
    try:
        return util.dev(f"pidof {pkg}", timeout=30).strip().splitlines()[0].strip()
    except Exception:  # noqa: BLE001
        return None


def scope_add(pkg: str) -> str:
    return lsposed.scope_add(FKIAB, pkg)


def scope_remove(pkg: str) -> str:
    return lsposed.scope_remove(FKIAB, pkg)


def install_script(pkg: str, loader: Path, payload: Path | None = None) -> dict:
    """Install loader as <pkg>.js (FKIAB editor-equivalent) and payload under the app's external files."""
    uid = _fk_uid()
    if uid is None:
        raise util.DopsError("FKIAB not installed")
    dst = f"{SCRIPTS}/{pkg}.js"
    util.dev_push(loader, dst)
    util.dev(f"chown {uid}:{uid} {dst}; chmod 660 {dst}")
    try:
        ctx = util.dev(f"ls -Z {SCRIPTS} | head -1", timeout=30)
        if "u:object_r" in ctx:
            util.dev(f"chcon '{ctx.split()[0]}' {dst} 2>/dev/null || true")
    except Exception:  # noqa: BLE001
        pass
    out = {"script": dst}
    if payload:
        ext = f"/sdcard/Android/data/{pkg}/files/b.js"
        util.dev_push(payload, ext)
        app_uid = util.dev(f"stat -c %U /sdcard/Android/data/{pkg}/files", timeout=30).strip()
        grp = util.dev(f"stat -c %G /sdcard/Android/data/{pkg}/files", timeout=30).strip()
        util.dev(f"chown {app_uid}:{grp} {ext}; chmod 660 {ext}")
        out["payload"] = ext
    return out


def remove_script(pkg: str) -> str:
    dst = f"{SCRIPTS}/{pkg}.js"
    util.dev(f"rm -f {dst}")
    return dst


def _prefs_path(pkg: str, cfg: dict) -> str:
    return util.expand(cfg.get("receipt_prefs", f"/data/data/{pkg}/shared_prefs/fuck.iab.xml"), {"package": pkg})


def receipts(pkg: str, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or {}
    try:
        text = util.dev(f"cat {_prefs_path(pkg, cfg)} 2>/dev/null", timeout=60)
    except util.DopsError:
        return []
    return _parse_receipts(text)


def clean_receipts(pkg: str, cfg: dict | None = None) -> None:
    cfg = cfg or {}
    util.dev(f"rm -f {_prefs_path(pkg, cfg)}")


def clone_receipts(pkg: str, cfg: dict, product: str, count: int) -> Path:
    """Duplicate an existing receipt for `product` with fresh orderIds (device write-back)."""
    path = _prefs_path(pkg, cfg)
    uid = util.dev(f"stat -c %u {path}", timeout=30).strip()
    gid = util.dev(f"stat -c %g {path}", timeout=30).strip()
    ctx = util.dev(f"ls -Z {path} | awk '{{print $1}}'", timeout=30).strip()
    text = util.dev(f"cat {path}", timeout=60)
    entries = re.findall(r'<string name="([^"]+)">(.*?)</string>', text, re.S)
    tpl = None
    for _k, v in entries:
        j = json.loads(html.unescape(v))
        if j.get("productId") == product:
            tpl = j
            break
    if tpl is None:
        raise util.DopsError(f"no template receipt for {product}")
    rows = []
    now = int(time.time() * 1000)
    for i in range(count):
        j = dict(tpl)
        j["orderId"] = "GPA.%04d-%04d-%04d-%04d-%05d" % tuple(
            random.randint(0, 9999) for _ in range(4)
        ) + str(random.randint(0, 99999))
        j["purchaseTime"] = now + i
        key = "".join(random.choice(string.ascii_lowercase) for _ in range(500))
        rows.append(f'<string name="{key}">{html.escape(json.dumps(j, separators=(",", ":")), quote=True)}</string>')
    xml = "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n<map>\n" + "\n".join(rows) + "\n</map>\n"
    local = util.STATE / f"receipts-{pkg}.xml"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(xml)
    util.dev_push(local, path)
    util.dev(f"chown {uid}:{gid} {path}; chmod 660 {path}")
    if ctx:
        util.dev(f"chcon '{ctx}' {path} 2>/dev/null || true")
    return local
