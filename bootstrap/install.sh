#!/usr/bin/env bash
# Idempotent host bootstrap: venv com frida + mitmproxy, sanity checks.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
./.venv/bin/python -m pip -q install --upgrade pip
./.venv/bin/python -m pip -q install 'frida==17.27.4' 'mitmproxy>=10'

echo "host deps ok"
command -v ponte >/dev/null && echo "ponte: $(ponte status 2>/dev/null | head -1)" || echo "ponte: ausente"
command -v adb   >/dev/null && echo "adb: ok" || echo "adb: ausente"
echo "python: $(./.venv/bin/python -V)"
echo "próximo: export DOPS_PY=$PWD/.venv/bin/python; bin/dops doctor"
