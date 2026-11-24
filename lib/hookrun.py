#!/usr/bin/env python3
"""Attach or spawn the target and load a Frida script; prints messages."""
from __future__ import annotations

import argparse
import os
import sys
import time

try:
    import frida
except ImportError:
    sys.exit("frida python package missing (install in DOPS_PY venv)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("package")
    ap.add_argument("--spawn", action="store_true")
    ap.add_argument("--seconds", type=int, default=0)
    ap.add_argument("--host", default=os.environ.get("FRIDA_HOST", "127.0.0.1:27042"))
    a = ap.parse_args()

    dev = frida.get_device_manager().add_remote_device(a.host)
    if a.spawn:
        pid = dev.spawn([a.package])
        session = dev.attach(pid)
        dev.resume(pid)
    else:
        app = next((x for x in dev.enumerate_applications() if x.identifier == a.package), None)
        if app:
            pid = app.pid
        else:
            tail = a.package.split(".")[-1].lower()
            pid = next((p.pid for p in dev.enumerate_processes()
                        if p.name.lower() == tail or tail in p.name.lower()), None)
        if not pid:
            sys.exit(f"process not found for {a.package}")
        session = dev.attach(pid)
    src = open(a.script).read()
    script = session.create_script(src)
    script.on("message", lambda m, d: print(m.get("payload", m), flush=True))
    script.load()
    print(f"[hookrun] attached pid={pid}", flush=True)
    try:
        if a.seconds:
            time.sleep(a.seconds)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        session.detach()


if __name__ == "__main__":
    main()
