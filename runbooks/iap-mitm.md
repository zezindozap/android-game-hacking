# IAP — MITM da validação

```bash
dops mitm ca --install        # CA de usuário (apps target 34+ exigem trust module)
dops mitm enable <pkg> --dry-run
dops mitm enable <pkg>        # adb reverse + iptables (uid) + mitmdump reverse
# comprar item barato e ver o request no log
dops mitm disable             # remove iptables/reverse e mata o mitmdump
```

Como funciona:

- `iptables -t nat OUTPUT --dport 443 -m owner --uid-owner <uid> -j REDIRECT --to-ports 8080`
  só para o app alvo.
- `adb reverse tcp:8080 tcp:8080` leva o tráfego ao mitmproxy no host.
- mitmproxy em `reverse:https://<host>` apresenta cert do host e encaminha para o real.
- `mitm/addon.py` casa host/path do `targets/<alvo>.toml` e aplica `patch` no JSON
  (ex.: `result=1`). `DOPS_CAPTURE_ONLY=1` só loga.

Resultado verificado (Cat Gunner, 2026-11-24): CA do mitmproxy no system store em **init e zygote**
(`${SYS_STORE}` bind mount), app reiniciado → `Client TLS handshake failed ... tlsv1 alert access denied`.
Conclusão: esse app **não usa a store do sistema** (CA embutida no Unity) ou faz pinning nativo.
Sem hook/patch nativo, MITM não passa; pare e vá para codec/patch do cliente.

Forge validado localmente: mitmproxy reverse + addon + `curl --cacert` → corpo reescrito com
`result:1` (log `PATCHED`). O que falta é o app confiar na CA.

Gates:

1. Handshake falhou → o app não confia na CA (módulo de trust só cobre Java?) ou há pinning.
2. Nada aparece no log → o app ignora proxy/redirect (lib própria); revise a regra/uid.
3. Sucesso não concede → schema diferente; itere `patch` (campos `items`, `expires`, etc.).
4. Anti-tamper: não use Frida/memory patch nessa sessão; `dops cleanup` ao final.
