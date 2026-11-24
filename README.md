# droid-arsenal

Índice completo: `INDEX.md`.

Toolkit reprodutível para análise e modificação de apps Android no device próprio, com
**interferência mínima**: nada de patch de APK, nada em `/system`, Frida só quando necessário.
Entrada única: `bin/dops`. Por app, só um arquivo em `targets/`.

## Instalação

```bash
bootstrap/install.sh          # venv com frida + mitmproxy, checagens
export PATH="$PWD/bin:$PATH"
dops doctor
```

Requisitos: `ponte` (preferido) ou `adb` com root; device com KernelSU/Magisk; LSPosed 2.x e
FKIAB 1.8.1 para a parte de billing.

## Comandos

```bash
dops doctor                     # transporte, root, SELinux, LSPosed, FKIAB, mitmproxy
dops recon com.exemplo.app      # engine, APKs, libs, prefs, paths de save
dops backup com.exemplo.app     # tar internal+external + sha256 (state/backups)
dops restore com.exemplo.app state/backups/foo.tar.gz

dops mem scan 18000 --type int64 --package com.exemplo.app   # passthrough agm
dops save sniff caminho/save.bin
dops il2cpp dump com.exemplo.app   # pull APK(s) + Il2CppDumper; --apks a.apk,b.apk reusa locais
# Il2CppDumper: coloque em ~/.local/share/droid-arsenal/Il2CppDumper/ ou exporte DOPS_IL2CPP_DUMPER

dops iap status com.exemplo.app
dops iap scope  com.exemplo.app [--remove]
dops iap receipts com.exemplo.app [--clean | --clone <produto> --count N]
dops iap script com.exemplo.app --loader loader.js [--payload b.js]

dops lsposed status | modules
dops lsposed scope com.fuck.iab com.exemplo.app [--remove]
dops lsposed scope-db com.fuck.iab com.exemplo.app [--remove] [--reboot]

dops mitm enable com.exemplo.app [--host h] [--port 8080] [--dry-run]
dops mitm disable
dops mitm ca [--install]

dops evidence com.exemplo.app [--seconds N] [--tag label]
dops hook run script.js com.exemplo.app [--spawn] [--seconds N]

dops recipe list
dops recipe run iap-mitm --target com.exemplo.app [--dry-run]
dops cleanup                    # mitm off + frida off + SELinux enforcing
```

## Alvos (`targets/<nome>.toml`)

A única parte específica por app:

```toml
package = "com.exemplo.app"
uid = 10478                       # opcional
save_paths = ["/sdcard/Android/data/{package}/files"]
receipt_prefs = "/data/data/{package}/shared_prefs/fuck.iab.xml"

[mitm]
hosts = ["validador.exemplo.com"]
match_path = "/verify"
patch = { result = 1 }
```

`--target` aceita o nome do arquivo (ex.: `cat-gunner`) ou o próprio package (procura
`<pkg>.toml`, `<pkg-com-hifens>.toml`, `<último-segmento>.toml`).

## Receitas

`recipes/*.toml` encadeiam verbos com `{target}`. `--dry-run` mostra a sequência.

## Runbooks

`runbooks/` cobre recon, save, memória, FKIAB, MITM e rollback. Metodologia genérica:
veja `runbooks/recon.md` e `runbooks/save.md`; casos de referência em `targets/`.

## Segurança e rollback

- `cleanup` remove iptables do MITM, mata frida-server e volta SELinux para `Enforcing`.
- CA de usuário e módulo LSPosed ficam instalados (reutilizáveis); remova manualmente se quiser.
- Backups têm sha256; restaure com `dops restore`.
- `state/` e segredos ficam fora do git.

## Validação (2026-11-24)

Validado ao vivo (device Android 16, root via KernelSU): `doctor` (5 s), `recon` (6 s), `backup`, `restore` ponta a ponta
(sentinel restaurado), `save sniff`, `iap status` (5 s)/`scripts`, `mem` passthrough,
`mitm enable/disable` com dispatcher SNI, `evidence`, `cleanup`, recipe real (`recon-save`),
`hook run` (frida-server attach), `lsposed scope-db` (add/remove no `modules_config.db`),
10 testes unitários (inclui parser SNI). Forge do addon validado com mitmproxy reverse + curl
(`result:1` no corpo). `lsposed scope` via lspctl é **impossível em build user** (exige ADB root
real); use `scope-db` + reboot. MITM no alvo Cat Gunner: handshake recusado mesmo com CA no system
store (init+zygote) → gate por app registrado em `runbooks/iap-mitm.md`.

Não exercitado: aplicação do escopo LSPosed pós-reboot, sucesso do MITM em app que confie na CA.

## Limites conhecidos

- MITM depende de o app aceitar CA (usuário+módulo de trust ou sistema) e não ter pinning.
- Metadata IL2CPP cifrada (PGL Armor) impede dump estático; use recon por runtime/string-xref.
- Consumíveis com validação server-side só passam com MITM/patch; `NonConsumable` costuma
  conceder localmente (ver skill `cat-gunner-ops`).
