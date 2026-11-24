"""IL2CPP dump orchestration: pull APK(s), extract metadata/libil2cpp, run Il2CppDumper."""
from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

from . import util

DUMPER = Path(os.environ.get(
    "DOPS_IL2CPP_DUMPER",
    str(Path.home() / ".local" / "share" / "droid-arsenal" / "Il2CppDumper" / "Il2CppDumper.dll"),
))


def _device_apks(pkg: str) -> list[str]:
    out = util.dev(f"pm path {pkg}", timeout=60)
    return [l.split(":", 1)[1].strip() for l in out.splitlines() if l.startswith("package:")]


def _extract(apk: Path, dest: Path) -> tuple[Path | None, Path | None]:
    meta = lib = None
    with zipfile.ZipFile(apk) as z:
        for name in z.namelist():
            if name.endswith("assets/bin/Data/Managed/Metadata/global-metadata.dat"):
                meta = dest / "global-metadata.dat"
                meta.write_bytes(z.read(name))
            elif name.endswith("lib/arm64-v8a/libil2cpp.so"):
                lib = dest / "libil2cpp.so"
                lib.write_bytes(z.read(name))
    return meta, lib


def dump(pkg: str, cfg: dict | None = None, apks: list[Path] | None = None, force_pull: bool = False) -> dict:
    cfg = cfg or {}
    work = util.STATE / "il2cpp" / pkg
    work.mkdir(parents=True, exist_ok=True)
    local_apks: list[Path] = []
    if apks:
        local_apks = apks
    elif force_pull or not any(work.glob("*.apk")):
        for i, remote in enumerate(_device_apks(pkg)):
            dest = work / f"apk{i}-{remote.split('/')[-1]}"
            util.dev_pull(remote, dest)
            local_apks.append(dest)
    else:
        local_apks = sorted(work.glob("*.apk"))
    meta = lib = None
    for apk in local_apks:
        m, l = _extract(apk, work)
        meta = meta or m
        lib = lib or l
    if cfg.get("dump_meta") and not meta:
        meta = Path(cfg["dump_meta"])
    if cfg.get("dump_lib") and not lib:
        lib = Path(cfg["dump_lib"])
    if not meta or not lib:
        raise util.DopsError("global-metadata.dat ou libil2cpp.so não encontrados nos APKs")
    if not DUMPER.exists():
        raise util.DopsError(f"Il2CppDumper não encontrado em {DUMPER} (defina DOPS_IL2CPP_DUMPER)")
    outdir = work / "dump"
    env = dict(os.environ, DOTNET_ROLL_FORWARD="LatestMajor")
    proc = subprocess.run(
        ["dotnet", str(DUMPER), str(lib), str(meta), str(outdir)],
        env=env, capture_output=True, text=True, timeout=900,
    )
    found = list(outdir.glob("dump.cs")) or list(work.glob("dump.cs"))
    # dumper antigo ignora o diretório e escreve no cwd; normaliza
    if not found:
        for cand in (Path.cwd() / "dump.cs", DUMPER.parent / "dump.cs"):
            if cand.exists():
                outdir.mkdir(parents=True, exist_ok=True)
                cand.replace(outdir / "dump.cs")
                found = [outdir / "dump.cs"]
                break
    if not found:
        raise util.DopsError(
            "dump falhou (metadata cifrada/protegida?).\n"
            + (proc.stdout or "")[-500:] + (proc.stderr or "")[-500:]
        )
    return {"dump": str(found[0]), "metadata": str(meta), "libil2cpp": str(lib),
            "outdir": str(outdir), "apks": [str(p) for p in local_apks]}
