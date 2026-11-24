"""Small shared helpers: device access, paths, target configs."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("DOPS_STATE", HOME / "state"))
TOOLS = Path(os.environ.get("DOPS_TOOLS", HOME / "tools"))
PY = os.environ.get("DOPS_PY") or (
    str(HOME / ".venv" / "bin" / "python")
    if (HOME / ".venv" / "bin" / "python").exists()
    else sys.executable
)
TARGETS = HOME / "targets"


class DopsError(RuntimeError):
    pass


def which(name: str) -> str | None:
    return shutil.which(name)


def run(argv: list[str], timeout: int = 120, input: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, timeout=timeout, input=input)


def out(argv: list[str], timeout: int = 120) -> str:
    p = run(argv, timeout)
    if p.returncode != 0:
        raise DopsError(f"{argv[0]} rc={p.returncode}: {p.stderr.decode(errors='replace')[:400]}")
    return p.stdout.decode(errors="replace")


def ponte_ok() -> bool:
    return which("ponte") is not None and run(["ponte", "status"], timeout=25).returncode == 0


def adb_ok() -> bool:
    return which("adb") is not None and run(["adb", "shell", "true"], timeout=15).returncode == 0


def dev(cmd: str, timeout: int = 120, root: bool = True) -> str:
    """Run a shell command on the device. Root shell when possible."""
    if ponte_ok():
        argv = ["ponte", "root", "--", cmd]
    elif which("adb"):
        argv = ["adb", "shell", ("su -c " + cmd) if root else cmd]
    else:
        raise DopsError("no device transport (ponte/adb)")
    p = run(argv, timeout)
    if p.returncode != 0:
        detail = (p.stdout + p.stderr).decode(errors="replace").strip()
        raise DopsError(f"device cmd failed rc={p.returncode}: {detail[:400]}")
    return p.stdout.decode(errors="replace")


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def adb_device() -> bool:
    if not which("adb"):
        return False
    p = run(["adb", "devices"], timeout=15)
    return b"\tdevice" in p.stdout


def dev_pull(remote: str, local: Path) -> None:
    """Copy a device file to host (adb pull when available, else root-safe temp path)."""
    local.parent.mkdir(parents=True, exist_ok=True)
    if adb_device():
        p = run(["adb", "pull", remote, str(local)], timeout=300)
        if p.returncode == 0 and local.exists() and local.stat().st_size > 0:
            return
    tmp = f"/sdcard/Download/.dops-{os.getpid()}-{local.name}"
    dev(f"cat {shell_quote(remote)} > {shell_quote(tmp)}")
    if which("ponte"):
        run(["ponte", "pull", tmp, str(local)])
    else:
        run(["adb", "pull", tmp, str(local)])
    dev(f"rm -f {shell_quote(tmp)}")
    if not local.exists() or local.stat().st_size == 0:
        raise DopsError(f"pull failed: {remote}")


def dev_push(local: Path, remote: str) -> None:
    if adb_device():
        p = run(["adb", "push", str(local), remote], timeout=300)
        if p.returncode == 0:
            return
    tmp = f"/sdcard/Download/.dops-{os.getpid()}-{local.name}"
    if which("ponte"):
        run(["ponte", "push", str(local), tmp])
    else:
        run(["adb", "push", str(local), tmp])
    dev(f"cat {shell_quote(tmp)} > {shell_quote(remote)}")
    dev(f"rm -f {shell_quote(tmp)}")


def host_adb(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return run(["adb", *args], timeout)


def target(name: str):
    import tomllib

    path = TARGETS / f"{name}.toml"
    if not path.exists():
        raise DopsError(f"target not found: {path}")
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    cfg.setdefault("package", name)
    return cfg


def expand(value: str, cfg: dict) -> str:
    return value.format(**{k: v for k, v in cfg.items() if isinstance(v, (str, int))})


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1))
