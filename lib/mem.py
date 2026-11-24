"""Memory scan/edit passthrough to the existing `agm` tool."""
from __future__ import annotations

import os
import subprocess
import sys

from . import util


def agm(args: list[str], host: str | None = None) -> int:
    tool = util.TOOLS / "agm"
    if not tool.exists():
        raise util.DopsError(f"agm not found at {tool} (set DOPS_TOOLS)")
    env = dict(os.environ)
    env["AGM_HOST"] = host or env.get("AGM_HOST", "127.0.0.1:27042")
    argv = [util.PY, str(tool), *args]
    if os.environ.get("DOPS_DRY_RUN"):
        print("dry-run:", " ".join(argv))
        return 0
    return subprocess.call(argv, env=env)


def note() -> str:
    return (
        "agm requer frida-server no device e um forward local:\n"
        "  ponte root -- 'cd /data/local/tmp && setsid nohup ./.fs -l 0.0.0.0:27042 >.fs.log 2>&1 &'\n"
        "  ponte forward --listen 127.0.0.1:27042 127.0.0.1:27042\n"
        "  AGM_HOST=127.0.0.1:27042 dops mem scan <valor> --type int64 --package <pkg>"
    )
