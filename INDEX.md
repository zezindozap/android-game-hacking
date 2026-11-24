# droid-arsenal — índice

Entrada única do toolkit: `bin/dops`. Comece por `dops doctor`; por app, só `targets/<nome>.toml`.

## Mapa

| Caminho | O que é |
|---|---|
| `README.md` | visão, instalação, comandos, configuração de alvo e limites |
| `bin/dops` | CLI (recon, backup/restore, mem, save, iap, lsposed, mitm, evidence, hook, recipe, cleanup) |
| `lib/` | módulos (transporte, doctor, recon, backup, mem, iap, lsposed, mitm, save, evidence, hook, recipe) |
| `mitm/addon.py` | addon mitmproxy: log + patch JSON por host/path |
| `mitm/dispatch.py` | dispatcher por SNI: só o host alvo vai ao proxy; resto passa direto |
| `targets/` | **única parte por app** (package/uid, hosts, match/patch, save paths) |
| `recipes/` | sequências declarativas (`recon-save`, `iap-fkiab`, `iap-mitm`) |
| `runbooks/` | procedimentos por técnica (ver abaixo) |
| `tests/` | unit tests (`python3 -m unittest discover -s tests`) + fixture de ClientHello |
| `bootstrap/install.sh` | venv com frida + mitmproxy, checagens |
| `deps.lock` | versões validadas (host e device) |
| `Makefile` | `make test`, `make doctor`, `make dry` |

## Runbooks

| Runbook | Quando |
|---|---|
| `runbooks/recon.md` | antes de tocar: engine, storage, proteções, billing |
| `runbooks/save.md` | estado local (sniff, codec, edição, verificação) |
| `runbooks/memory.md` | valor vivo/não persistido (scan, refine, obscured) |
| `runbooks/iap-fkiab.md` | billing fake (FakeBinder), recibos, ownership |
| `runbooks/server-validated-iap.md` | grant no backend: hook da validação, resposta fabricada, `abort`=exceção, campos obrigatórios |
| `runbooks/iap-mitm.md` | forjar validação server-side (CA, dispatcher, gates) |
| `runbooks/rollback.md` | desmontar e voltar ao estado inicial |

## Recipes

| Recipe | Passos |
|---|---|
| `recipes/recon-save.toml` | recon → backup → evidence |
| `recipes/iap-fkiab.toml` | doctor → iap status → escopo → evidence |
| `recipes/iap-mitm.toml` | doctor → iap status → mitm enable → evidence |

## Alvos de referência

`cat-gunner` (IAP type=1 local, MITM bloqueado por CA própria/pinning), `bloons-blitz` (forge de
endpoint LiNK), `mob-control` (Voodoo/Nakama). Servem de template; remova IDs/segredos ao publicar.

## Validação e limites

Matriz em `README.md` (seção Validação). Resumo: CLI, recon/backup/restore, save sniff, iap,
mem, mitm enable/disable+dispatcher, evidence, hook, scope-db e recipe validados ao vivo;
`lspctl` developer-mode é impossível em build user (use `scope-db` + reboot); sucesso do MITM
depende de o app confiar na CA (ver `runbooks/iap-mitm.md`).

## Metodologia

Os runbooks acima são a referência; `android-game-hacking` (metodologia ampla) e os casos
`cat-gunner-ops`/`bloons-blitz-ops` vivem no acervo privado do operador, não neste repo.
