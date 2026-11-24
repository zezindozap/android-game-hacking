"""Declarative recipe runner: TOML steps -> dops subcommands."""
from __future__ import annotations

import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

from . import util

RECIPES = util.HOME / "recipes"


def load(name: str) -> dict:
    path = RECIPES / f"{name}.toml"
    if not path.exists():
        raise util.DopsError(f"recipe not found: {path}")
    with open(path, "rb") as f:
        return tomllib.load(f)


def run(name: str, target: str | None = None, dry_run: bool = False) -> int:
    rec = load(name)
    rc = 0
    for step in rec.get("steps", []):
        argv = [str(x).format(target=target or "", package=target or "") for x in step]
        argv = [a for a in argv if a != ""]
        print("+ dops " + " ".join(shlex.quote(a) for a in argv))
        if dry_run:
            continue
        p = subprocess.run([sys.executable, str(util.HOME / "bin" / "dops"), *argv])
        if p.returncode != 0:
            rc = p.returncode
            print(f"! step failed: {argv}")
            if rec.get("stop_on_error", True):
                break
    return rc


def listing() -> list[str]:
    if not RECIPES.exists():
        return []
    return sorted(p.stem for p in RECIPES.glob("*.toml"))
