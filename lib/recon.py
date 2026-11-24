"""Package recon: version, engine, native libs, storage layers."""
from __future__ import annotations

import re

from . import util


def uid(pkg: str) -> int | None:
    try:
        out = util.dev(f"dumpsys package {pkg} | grep -oE '(appId|userId)=[0-9]+' | head -1", timeout=60)
        m = re.search(r"=(\d+)", out)
        return int(m.group(1)) if m else None
    except Exception:  # noqa: BLE001
        return None


def apks(pkg: str) -> list[str]:
    out = util.dev(f"pm path {pkg}", timeout=60)
    return [l.split(":", 1)[1].strip() for l in out.splitlines() if l.startswith("package:")]


def recon(pkg: str, cfg: dict | None = None) -> dict:
    cfg = cfg or {}
    paths = [f"/data/data/{pkg}", f"/data/data/{pkg}/files", f"/data/data/{pkg}/shared_prefs",
             f"/sdcard/Android/data/{pkg}/files"]
    cmd = "; ".join([
        f"echo '@@META'; dumpsys package {pkg} | grep -E 'versionName|versionCode|firstInstallTime|lastUpdateTime'",
        f"echo '@@UID'; dumpsys package {pkg} | grep -oE '(appId|userId)=[0-9]+' | head -1",
        f"echo '@@APK'; pm path {pkg}",
        f"echo '@@LIBS'; ls /data/app/*/{pkg}-*/lib/*/*.so 2>/dev/null | xargs -n1 basename 2>/dev/null",
        "echo '@@LS0'; ls -la " + paths[0] + " 2>/dev/null",
        "echo '@@LS1'; ls -la " + paths[1] + " 2>/dev/null",
        "echo '@@LS2'; ls -la " + paths[2] + " 2>/dev/null",
        "echo '@@LS3'; ls -la " + paths[3] + " 2>/dev/null",
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
    info: dict = {"package": pkg, "meta": [l.strip() for l in sec.get("META", []) if l.strip()],
                  "apks": [l.split(":", 1)[1].strip() for l in sec.get("APK", []) if l.startswith("package:")],
                  "native_libs": sorted({l.strip() for l in sec.get("LIBS", []) if l.strip()})}
    m = re.search(r"=(\d+)", "\n".join(sec.get("UID", [])))
    info["uid"] = int(m.group(1)) if m else None
    info["engine"] = _engine(info["native_libs"])
    for i, key in enumerate(("data", "data_files", "prefs", "external")):
        info[key] = [l.strip() for l in sec.get(f"LS{i}", []) if l.strip()]
    info["save_paths"] = [util.expand(p, {"package": pkg}) for p in cfg.get("save_paths", [])]
    return info


def _engine(libs: list[str]) -> str:
    if any("libil2cpp" in x for x in libs):
        return "unity-il2cpp"
    if any("libmono" in x for x in libs):
        return "unity-mono"
    if any("libflutter" in x for x in libs):
        return "flutter"
    if any("libreactnative" in x for x in libs):
        return "react-native"
    if any("libcocos" in x for x in libs):
        return "cocos"
    if any("libUE4" in x or "libUnreal" in x for x in libs):
        return "unreal"
    return "unknown"


def _ls(path: str) -> list[str]:
    try:
        return [l.strip() for l in util.dev(f"ls -la {path} 2>/dev/null", timeout=60).splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        return []


def render(info: dict) -> str:
    lines = [f"package : {info['package']} (uid {info.get('uid')})", f"engine  : {info['engine']}"]
    for m in info.get("meta", []):
        lines.append("meta    : " + m)
    lines.append("apks    : " + ", ".join(a.split("/")[-1] for a in info["apks"]))
    if info.get("native_libs"):
        lines.append("libs    : " + ", ".join(info["native_libs"][:12]) + (" ..." if len(info["native_libs"]) > 12 else ""))
    for key in ("data", "data_files", "prefs", "external"):
        if info.get(key):
            lines.append(f"[{key}]")
            lines += ["  " + x for x in info[key][:20]]
    if info.get("save_paths"):
        lines.append("[save_paths] " + ", ".join(info["save_paths"]))
    return "\n".join(lines)
