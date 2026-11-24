"""LSPosed 2.x control via lspctl (developer mode), with explicit DB fallback."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from . import util

LSPCTL = "/data/adb/modules/zygisk_lsposed/lspctl"
DB = "/data/adb/lspd/config/modules_config.db"
DEV_ERR = "developer commands are only allowed from an ADB root shell"


def _call(cmd: str) -> str:
    try:
        out = util.dev(f"{LSPCTL} {cmd} 2>&1", timeout=60)
    except util.DopsError as e:
        if DEV_ERR in str(e):
            raise util.DopsError(
                "lspctl developer commands exigem ADB root shell.\n"
                "Opções: (a) adb TCP + 'adb shell su'; (b) UI do Manager; "
                "(c) 'dops lsposed scope-db ... --reboot'."
            ) from e
        raise
    if DEV_ERR in out:
        raise util.DopsError(
            "lspctl developer commands exigem ADB root shell.\n"
            "Opções: (a) habilitar adb TCP e usar 'adb shell su'; "
            "(b) usar a UI do Manager; (c) 'dops lsposed scope-db ... --reboot'."
        )
    return out.strip()


def status() -> str:
    return util.dev(f"{LSPCTL} status 2>&1", timeout=60).strip()


def modules() -> list[str]:
    return [l for l in _call("module list").splitlines() if l.strip()]


def scope_list(module: str) -> list[str]:
    out = _call(f"scope list {module} --user 0")
    return [l.strip() for l in out.splitlines() if l.strip() and not l.lower().startswith(("package", "scope"))]


def scope_add(module: str, pkg: str) -> str:
    return _call(f"scope add {module} {pkg} --user 0")


def scope_remove(module: str, pkg: str) -> str:
    return _call(f"scope remove {module} {pkg} --user 0")


def module_toggle(module: str, enable: bool, user: int = 0) -> str:
    return _call(f"module {'enable' if enable else 'disable'} {module} --user {user}")


def scope_db(module: str, pkg: str, add: bool = True, reboot: bool = False) -> str:
    """Edit modules_config.db directly; requires reboot for lspd to reload scopes."""
    local = Path(tempfile.mkdtemp()) / "modules_config.db"
    util.dev(f"cp {DB} /sdcard/Download/.dops-modules.db; chmod 644 /sdcard/Download/.dops-modules.db", timeout=60)
    if util.which("ponte"):
        util.run(["ponte", "pull", "/sdcard/Download/.dops-modules.db", str(local)])
    else:
        util.run(["adb", "pull", "/sdcard/Download/.dops-modules.db", str(local)])
    util.dev("rm -f /sdcard/Download/.dops-modules.db")
    con = sqlite3.connect(local)
    with con:
        if add:
            con.execute("insert or ignore into scope(module_pkg_name,app_pkg_name,user_id) values(?,?,0)", (module, pkg))
            con.execute(
                "insert or replace into modules_state(module_pkg_name,user_id,enabled,scope_request_blocked) values(?,0,1,0)",
                (module,),
            )
        else:
            con.execute("delete from scope where module_pkg_name=? and app_pkg_name=? and user_id=0", (module, pkg))
    con.commit()
    con.close()
    uid = util.dev(f"stat -c %u {DB}", timeout=30).strip()
    gid = util.dev(f"stat -c %g {DB}", timeout=30).strip()
    ctx = util.dev(f"ls -Z {DB} | awk '{{print $1}}'", timeout=30).strip()
    util.dev_push(local, DB)
    util.dev(f"rm -f {DB}-wal {DB}-shm; chown {uid}:{gid} {DB}; chmod 600 {DB}")
    if ctx:
        util.dev(f"chcon '{ctx}' {DB} 2>/dev/null || true")
    if reboot:
        util.dev("nohup sh -c 'sleep 2; reboot' >/dev/null 2>&1 &", timeout=30)
        return "db atualizado; device reiniciando"
    return "db atualizado; reinicie o device para lspd reler o escopo"
