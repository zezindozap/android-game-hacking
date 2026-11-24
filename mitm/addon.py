"""mitmproxy addon: log requests and rewrite a matched JSON response.

Env:
  DOPS_RULES   path to rules JSON: {"host": "...", "match_path": "...", "patch": {...}}
  DOPS_LOG     append request/response log
  DOPS_CAPTURE_ONLY=1  never rewrite, only log
"""
from __future__ import annotations

import json
import os
import time


def _load_rules() -> dict:
    path = os.environ.get("DOPS_RULES")
    if not path or not os.path.exists(path):
        return {"host": "", "match_path": "", "patch": {"result": 1}}
    with open(path) as f:
        return json.load(f)


def _log(line: str) -> None:
    path = os.environ.get("DOPS_LOG")
    if not path:
        return
    with open(path, "a") as f:
        f.write(f"{time.time():.3f} {line}\n")


def patched_body(rules: dict, original: bytes | None) -> bytes:
    """Build the forged body; keeps original JSON fields when parseable."""
    try:
        base = json.loads(original) if original else {}
        if not isinstance(base, dict):
            base = {}
    except Exception:  # noqa: BLE001
        base = {}
    base.update(rules.get("patch") or {"result": 1})
    return json.dumps(base, separators=(",", ":")).encode()


def matches(rules: dict, host: str, path: str) -> bool:
    want_host = rules.get("host") or ""
    want_path = rules.get("match_path") or ""
    return (not want_host or want_host in host) and (not want_path or want_path in path)


def response(flow) -> None:  # noqa: ANN001 - mitmproxy hook
    rules = _load_rules()
    host = flow.request.pretty_host
    _log(f"REQ {flow.request.method} https://{host}{flow.request.path}")
    if not matches(rules, host, flow.request.path):
        return
    original = getattr(flow.response, "content", None) if flow.response else None
    _log(f"RESP {getattr(flow.response, 'status_code', '?')} {original[:300]!r}" if original else "RESP empty")
    if os.environ.get("DOPS_CAPTURE_ONLY") == "1":
        return
    from mitmproxy import http  # imported lazily so the module is unit-testable

    flow.response = http.Response.make(
        200,
        patched_body(rules, original),
        {"Content-Type": "application/json; charset=utf-8"},
    )
    _log("PATCHED " + patched_body(rules, original).decode())
