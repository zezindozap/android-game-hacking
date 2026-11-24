"""Frida hook runner (attach/spawn) using the configured python interpreter."""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import util

RUNNER = util.HOME / "lib" / "hookrun.py"


def run(script: Path, pkg: str, spawn: bool = False, seconds: int = 0, host: str | None = None) -> int:
    if not script.exists():
        raise util.DopsError(f"script not found: {script}")
    argv = [util.PY, str(RUNNER), str(script), pkg]
    if spawn:
        argv.append("--spawn")
    if seconds:
        argv += ["--seconds", str(seconds)]
    import os

    env = dict(os.environ)
    if host:
        env["FRIDA_HOST"] = host
    if os.environ.get("DOPS_DRY_RUN"):
        print("dry-run:", " ".join(argv))
        return 0
    return subprocess.call(argv, env=env)
