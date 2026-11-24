"""SNI dispatcher: TLS passthrough for everything except the configured host.

iptables redirects the app's 443 to this listener. We peek the ClientHello SNI:
- target host -> relay to mitmproxy reverse (which terminates TLS with our CA)
- anything else -> raw TCP passthrough to the real host (no interception, no breakage)

Env: DOPS_DISPATCH = {"listen": 0, "mitm": 8081, "targets": ["host", ...], "log": "path"}
"""
from __future__ import annotations

import asyncio
import json
import os
import ssl
import struct
import time

CFG = json.loads(os.environ.get("DOPS_DISPATCH", "{}"))
LOG = CFG.get("log")


def log(msg: str) -> None:
    line = f"{time.time():.3f} {msg}"
    print(line, flush=True)
    if LOG:
        with open(LOG, "a") as f:
            f.write(line + "\n")


def parse_sni(data: bytes) -> str | None:
    try:
        if len(data) < 5 or data[0] != 0x16:  # handshake record
            return None
        p = 5
        if data[p] != 1:  # ClientHello
            return None
        p += 4  # handshake header
        p += 2 + 32  # version + random
        sid = data[p]
        p += 1 + sid
        cs = struct.unpack("!H", data[p:p + 2])[0]
        p += 2 + cs
        comp = data[p]
        p += 1 + comp
        if p + 2 > len(data):
            return None
        ext_total = struct.unpack("!H", data[p:p + 2])[0]
        p += 2
        end = min(len(data), p + ext_total)
        while p + 4 <= end:
            et, el = struct.unpack("!HH", data[p:p + 4])
            p += 4
            if et == 0 and p + el <= end:
                # server_name list
                q = p + 2
                while q + 3 <= p + el:
                    nt = data[q]
                    nl = struct.unpack("!H", data[q + 1:q + 3])[0]
                    if nt == 0:
                        return data[q + 3:q + 3 + nl].decode("ascii", "ignore")
                    q += 3 + nl
            p += el
    except Exception:  # noqa: BLE001
        return None
    return None


async def relay(a: asyncio.StreamReader, b: asyncio.StreamWriter) -> None:
    try:
        while data := await a.read(65536):
            b.write(data)
            await b.drain()
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            b.close()
        except Exception:  # noqa: BLE001
            pass


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    targets = set(CFG.get("targets", []))
    try:
        head = await asyncio.wait_for(reader.read(8192), timeout=5)
    except Exception:  # noqa: BLE001
        writer.close()
        return
    if not head:
        writer.close()
        return
    sni = parse_sni(head)
    if sni is None:
        log("HEAD " + head[:24].hex())
    target = bool(sni and any(t == sni or sni.endswith("." + t) for t in targets))
    log(f"SNI={sni} target={target}")
    try:
        if target:
            up_r, up_w = await asyncio.open_connection("127.0.0.1", CFG["mitm"])
        else:
            if not sni:
                writer.close()
                return
            up_r, up_w = await asyncio.open_connection(sni, 443, ssl=None)
        up_w.write(head)
        await up_w.drain()
    except Exception as e:  # noqa: BLE001
        log(f"upstream ERR {e}")
        writer.close()
        return
    await asyncio.gather(relay(reader, up_w), relay(up_r, writer))


async def main() -> None:
    server = await asyncio.start_server(handle, "0.0.0.0", int(CFG["listen"]))
    log(f"dispatch listening {CFG['listen']} targets={CFG.get('targets')} mitm=127.0.0.1:{CFG['mitm']}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
