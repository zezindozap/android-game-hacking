"""Save-file sniffing: identify common Unity/Android save containers without game-specific code."""
from __future__ import annotations

import base64
import binascii
import math
from pathlib import Path


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in freq if c)


def sniff(path: Path) -> dict:
    data = path.read_bytes()
    info: dict = {"path": str(path), "size": len(data), "head": data[:16].hex(), "entropy": round(entropy(data[:4096]), 2)}
    if data.lstrip().startswith((b"{", b"[")):
        info.update(format="json", editable=True)
        return info
    if data.startswith(b"ENC1"):
        body = data[5:]
        info.update(format="actk-obscuredfile", editable=False)
        try:
            raw = base64.b64decode(body, validate=False)
            info.update(cipher_len=len(raw), block_aligned=(len(raw) % 16 == 0), cipher_entropy=round(entropy(raw[:4096]), 2))
        except binascii.Error:
            info["note"] = "payload not base64"
        info["hint"] = "ACTK ObscuredFile (AES); capture key/IV via runtime hook antes de editar"
        return info
    if data[:4] in (b"\x1f\x8b\x08\x00",) or data[:2] == b"\x1f\x8b":
        info.update(format="gzip", editable=True)
        return info
    try:
        raw = base64.b64decode(b"".join(data.split()), validate=True)
        info.update(format="base64", decoded_len=len(raw), decoded_entropy=round(entropy(raw[:4096]), 2))
        return info
    except binascii.Error:
        pass
    if info["entropy"] < 6.5:
        info.update(format="binary-low-entropy", hint="testar XOR de 1 byte / header fixo")
    else:
        info.update(format="binary-encrypted", hint="AES/DES provável; hook no primitivo de crypto")
    return info


def render(info: dict) -> str:
    lines = [f"file    : {info['path']} ({info['size']} B, entropy {info['entropy']})",
             f"format  : {info['format']}"]
    for k in ("cipher_len", "block_aligned", "decoded_len", "decoded_entropy", "cipher_entropy"):
        if k in info:
            lines.append(f"{k:8}: {info[k]}")
    if info.get("hint"):
        lines.append("hint    : " + info["hint"])
    return "\n".join(lines)
