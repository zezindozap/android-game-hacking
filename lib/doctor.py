"""Environment/device readiness checks for the toolkit."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor

from . import util

LSPCTL = "/data/adb/modules/zygisk_lsposed/lspctl"
FKIAB = "com.fuck.iab"


def _dev_status() -> dict:
    info = {"transport": None, "model": None, "android": None, "root": None, "selinux": None}
    if util.ponte_ok():
        info["transport"] = "ponte"
    elif util.adb_ok():
        info["transport"] = "adb"
    if not info["transport"]:
        return info
    try:
        out = util.dev("getprop ro.product.model; getprop ro.build.version.release; id; getenforce")
        model, ver, uid, se = [x.strip() for x in out.strip().splitlines()[-4:]]
        info.update(model=model, android=ver, root=("uid=0" in uid), selinux=se)
    except Exception as e:  # noqa: BLE001
        info["error"] = str(e)
    return info


def _lsposed() -> dict:
    res = {"lspctl": None, "daemon": None, "developer": None, "modules": []}
    try:
        out = util.dev(f"{LSPCTL} status 2>&1")
        for line in out.splitlines():
            if line.startswith("LSPosed "):
                res["lspctl"] = line.strip()
            if "System server:" in line:
                res["daemon"] = line.split(":", 1)[1].strip()
            if "Developer mode:" in line:
                res["developer"] = line.split(":", 1)[1].strip()
        res["modules"] = [x for x in util.dev(f"{LSPCTL} module list 2>&1").splitlines() if x.strip()]
    except Exception as e:  # noqa: BLE001
        res["error"] = str(e)
    return res


def _fkiab() -> dict:
    res = {"installed": False, "version": None, "injected_into": []}
    try:
        out = util.dev("pm list packages com.fuck.iab")
        res["installed"] = FKIAB in out
        if res["installed"]:
            res["version"] = util.dev("dumpsys package com.fuck.iab | grep -m1 versionName").strip().split("=")[-1]
    except Exception as e:  # noqa: BLE001
        res["error"] = str(e)
    return res


def _mitm() -> dict:
    venv_bin = Path(util.PY).parent / "mitmdump"
    return {
        "mitmdump": shutil.which("mitmdump") or (str(venv_bin) if venv_bin.exists() else None),
        "ca": str(Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"),
    }


def collect() -> dict:
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_dev = ex.submit(_dev_status)
        f_ls = ex.submit(_lsposed)
        f_fk = ex.submit(_fkiab)
        mitm = _mitm()
        return {
            "tools": {
                "ponte": bool(shutil.which("ponte")),
                "adb": bool(shutil.which("adb")),
                "agm": (util.TOOLS / "agm").exists(),
                "frida_py": util.PY,
            },
            "device": f_dev.result(),
            "lsposed": f_ls.result(),
            "fkiab": f_fk.result(),
            "mitm": mitm,
        }


def render(info: dict) -> str:
    lines = []

    def g(*ks):
        cur = info
        for k in ks:
            cur = cur.get(k) if isinstance(cur, dict) else None
        return cur

    dev = info["device"]
    lines.append(f"transport : {dev.get('transport') or 'NENHUM (ponte/adb)'}")
    lines.append(f"device    : {dev.get('model')} Android {dev.get('android')} root={dev.get('root')} selinux={dev.get('selinux')}")
    ls = info["lsposed"]
    lines.append(f"lsposed   : {ls.get('lspctl') or 'ausente'} daemon={ls.get('daemon')} dev={ls.get('developer')}")
    fk = info["fkiab"]
    lines.append(f"fkiab     : installed={fk.get('installed')} version={fk.get('version')}")
    mitm = info["mitm"]
    lines.append(f"mitmproxy : {mitm.get('mitmdump') or 'ausente (pip install mitmproxy)'}")
    lines.append(f"tools     : agm={info['tools']['agm']} python={info['tools']['frida_py']}")
    ok = bool(dev.get("transport")) and bool(dev.get("root"))
    lines.append("STATUS    : " + ("OK" if ok else "INCOMPLETO"))
    return "\n".join(lines)
