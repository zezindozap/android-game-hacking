# Runbooks

Ordem típica: `recon → backup → técnica → evidence → cleanup`.

| runbook | quando |
|---|---|
| `recon.md` | antes de qualquer coisa; engine, storage, superfície |
| `save.md` | estado local (moedas, flags); sniff e edição |
| `memory.md` | valor vivo (contador/cache) que não está em arquivo |
| `iap-fkiab.md` | billing fake (FakeBinder) e recibos do FKIAB |
| `server-validated-iap.md` | grant vindo do servidor: forjar resposta no cliente, abort=exceção, campos obrigatórios |
| `iap-mitm.md` | forjar a validação server-side de compras |
| `rollback.md` | desmontar tudo e voltar ao estado inicial |

Regras gerais:

- Sempre `dops backup` antes de escrever; sempre `dops evidence` no resultado.
- Jogo parado durante edição de arquivo; escrita in-place (preserva dono/SELinux).
- Frida só durante a sessão; `dops cleanup` ao final.
- MITM: uma sessão por host; iptables transitório; reboot = rollback garantido.
