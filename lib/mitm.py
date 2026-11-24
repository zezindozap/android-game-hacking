"""Transparent TLS interception with SNI dispatch: adb reverse + iptables + mitmproxy reverse."""
from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

from . import recon, util

STATE = util.STATE / "mitm.json"
TAG = "dops-mitm"
DEFAULT_PORT = 8080


def _uid(pkg: str, cfg: dict) -> int:
    if cfg.get("uid"):
        return int(cfg["uid"])
    uid = recon.uid(pkg)
    if uid is None:
        raise util.DopsError("cannot resolve uid; set uid in targets/<pkg>.toml")
    return uid


def _rules(cfg: dict, hosts: list[str]) -> Path:
    rules = {
        "host": "",
        "hosts": hosts,
        "match_path": cfg.get("mitm", {}).get("match_path", ""),
        "patch": cfg.get("mitm", {}).get("patch", {"result": 1}),
    }
    path = util.STATE / "mitm-rules.json"
    util.write_json(path, rules)
    return path


def _free_port(preferred: int = 0) -> int:
    for cand in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", cand))
                return s.getsockname()[1]
            except OSError:
                continue
    raise util.DopsError("no free local port")


def _mitmdump() -> str | None:
    return shutil.which("mitmdump") or (
        str(Path(util.PY).parent / "mitmdump") if (Path(util.PY).parent / "mitmdump").exists() else None
    )


def _ensure_adb() -> int | None:
    """Make an adb-over-TCP device available (authorize host key), via ponte forward when needed."""
    p = util.run(["adb", "devices"], timeout=20)
    if b"\tdevice" in p.stdout:
        return None
    pub = Path.home() / ".android" / "adbkey.pub"
    if pub.exists():
        key = pub.read_text().strip()
        util.dev("mkdir -p /data/misc/adb; touch /data/misc/adb/adb_keys")
        util.dev(f"grep -qF '{key}' /data/misc/adb/adb_keys || echo '{key}' >> /data/misc/adb/adb_keys; chmod 640 /data/misc/adb/adb_keys; chown system:shell /data/misc/adb/adb_keys")
    util.dev("setprop service.adb.tcp.port 5555; stop adbd; sleep 1; start adbd", timeout=40)
    fwd = subprocess.Popen(["ponte", "forward", "--listen", "127.0.0.1:5555", "127.0.0.1:5555"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(10):
        time.sleep(1)
        util.run(["adb", "connect", "127.0.0.1:5555"], timeout=15)
        if b"\tdevice" in util.run(["adb", "devices"], timeout=15).stdout:
            return fwd.pid
    fwd.terminate()
    raise util.DopsError("adb TCP indisponível (autorização/porta); use 'adb connect' manual")


def enable(pkg: str, cfg: dict, host: str | None = None, port: int = DEFAULT_PORT, dry_run: bool = False) -> dict:
    hosts = [host] if host else list(cfg.get("mitm", {}).get("hosts", []))
    if not hosts:
        raise util.DopsError("no host: pass --host or set [mitm].hosts in the target")
    mitmdump = _mitmdump()
    if not mitmdump and not dry_run:
        raise util.DopsError("mitmdump not found (run bootstrap/install.sh)")
    public = _free_port(port)
    internal = _free_port(0)
    uid = _uid(pkg, cfg)
    rules = _rules(cfg, hosts)
    addon = util.HOME / "mitm" / "addon.py"
    dispatcher = util.HOME / "mitm" / "dispatch.py"
    specs = [
        f"-p tcp --dport 443 -m owner --uid-owner {uid} -m comment --comment {TAG} -j REDIRECT --to-ports {public}",
    ]
    disp_cfg = {"listen": public, "mitm": internal, "targets": hosts, "log": str(util.STATE / "dispatch.log")}
    cmds = {
        "mitmdump": [mitmdump or "mitmdump", "--mode", f"reverse:https://{hosts[0]}",
                     "--listen-host", "127.0.0.1", "--listen-port", str(internal),
                     "--set", "keep_host_header=true", "--scripts", str(addon)],
        "dispatch": [util.PY, str(dispatcher)],
    }
    if dry_run:
        return {"dry_run": True, "uid": uid, "public_port": public, "internal_port": internal,
                "mitmdump": " ".join(cmds["mitmdump"]), "dispatch(env)": disp_cfg,
                "iptables": [f"iptables -t nat -A OUTPUT {s}" for s in specs], "rules": str(rules)}

    adb_proc = _ensure_adb()
    util.host_adb(["reverse", f"tcp:{public}", f"tcp:{public}"])
    for spec in specs:
        for ipt in ("iptables", "ip6tables"):
            try:
                util.dev(f"{ipt} -t nat -A OUTPUT {spec}")
            except util.DopsError:
                pass
    util.STATE.mkdir(parents=True, exist_ok=True)
    env1 = dict(os.environ, DOPS_RULES=str(rules), DOPS_LOG=str(util.STATE / "mitm-requests.log"))
    env2 = dict(os.environ, DOPS_DISPATCH=json.dumps(disp_cfg))
    fh = open(util.STATE / "mitm.log", "ab")
    p_mitm = subprocess.Popen(cmds["mitmdump"], env=env1, stdout=fh, stderr=fh, start_new_session=True)
    p_disp = subprocess.Popen(cmds["dispatch"], env=env2, stdout=fh, stderr=fh, start_new_session=True)
    util.write_json(STATE, {"pkg": pkg, "uid": uid, "hosts": hosts, "public": public, "internal": internal,
                            "pid_mitm": p_mitm.pid, "pid_dispatch": p_disp.pid,
                            "specs": specs, "rules": str(rules), "adb_forward": adb_proc})
    return {"public_port": public, "internal_port": internal, "logs": [str(util.STATE / "mitm.log"),
            str(util.STATE / "mitm-requests.log")], "rules": str(rules),
            "ca": str(Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem")}


def disable() -> dict:
    st = util.read_json(STATE, None)
    if not st:
        return {"status": "not-running"}
    for key in ("pid_mitm", "pid_dispatch", "adb_forward"):
        pid = st.get(key)
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    util.host_adb(["reverse", "--remove", f"tcp:{st['public']}"])
    for spec in st.get("specs", []):
        for ipt in ("iptables", "ip6tables"):
            while True:
                try:
                    util.dev(f"{ipt} -t nat -D OUTPUT {spec}")
                except util.DopsError:
                    break
    STATE.unlink(missing_ok=True)
    return {"status": "stopped", "port": st["public"]}


SYS_STORE = "/system/etc/security/cacerts"
SYS_TMP = "/data/local/tmp/dops-cacerts"


def install_ca_system() -> dict:
    """Bind-mount a copy of the system CA store + mitmproxy CA (session-wide, reversible)."""
    ca = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"
    if not ca.exists():
        raise util.DopsError(f"{ca} missing; run mitmdump once")
    if not shutil.which("openssl"):
        raise util.DopsError("openssl needed to compute cert hash")
    h = subprocess.run(["openssl", "x509", "-inform", "PEM", "-subject_hash_old", "-in", str(ca)],
                       capture_output=True, text=True, check=True).stdout.splitlines()[0].strip()
    util.dev(f"rm -rf {SYS_TMP}; cp -a {SYS_STORE} {SYS_TMP}", timeout=90)
    util.dev_push(ca, f"{SYS_TMP}/{h}.0")
    util.dev(f"chmod 644 {SYS_TMP}/{h}.0; chcon -R u:object_r:system_file:s0 {SYS_TMP}", timeout=60)
    util.dev(f"nsenter -t 1 -m -- mount --bind {SYS_TMP} {SYS_STORE}", timeout=30)
    # apps inherit the zygote mount namespace, not init's: mount there too
    for z in ("zygote64", "zygote"):
        try:
            util.dev(f"for p in $(pidof {z}); do nsenter -t $p -m -- mount --bind {SYS_TMP} {SYS_STORE} 2>/dev/null; done", timeout=40)
        except util.DopsError:
            pass
    if "ok" not in util.dev(f"test -f {SYS_STORE}/{h}.0 && echo ok", timeout=30):
        raise util.DopsError("system CA mount not visible")
    return {"system_ca": f"{SYS_STORE}/{h}.0", "note": "vale para processos novos; reinicie o app"}


def unmount_ca_system() -> dict:
    try:
        for z in ("zygote64", "zygote"):
            util.dev(f"for p in $(pidof {z}); do nsenter -t $p -m -- umount {SYS_STORE} 2>/dev/null; done", timeout=40)
        util.dev(f"nsenter -t 1 -m -- umount {SYS_STORE}", timeout=30)
        return {"status": "unmounted"}
    except util.DopsError as e:
        return {"status": "not-mounted-or-failed", "detail": str(e)}


def ca_info() -> dict:
    ca = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"
    return {"ca": str(ca), "exists": ca.exists(),
            "install": "dops mitm ca --install (user) | --system (bind mount, sessão) | --unmount"}


def install_ca() -> dict:
    ca = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"
    if not ca.exists():
        raise util.DopsError(f"{ca} missing; run mitmdump once")
    if not shutil.which("openssl"):
        raise util.DopsError("openssl needed to compute cert hash")
    h = subprocess.run(["openssl", "x509", "-inform", "PEM", "-subject_hash_old", "-in", str(ca)],
                       capture_output=True, text=True, check=True).stdout.splitlines()[0].strip()
    dst = f"/data/misc/user/0/cacerts-added/{h}.0"
    util.dev_push(ca, dst)
    util.dev(f"chown system:system {dst}; chmod 644 {dst}")
    return {"installed": dst, "note": "CA de usuário; apps target 34+ exigem trust module ou CA de sistema"}
