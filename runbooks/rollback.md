# Rollback

```bash
dops mitm disable        # iptables + adb reverse + mitmdump
dops cleanup             # + frida-server off + SELinux Enforcing
dops restore <pkg> <backup.tar.gz>
```

Estado que permanece (remover manualmente se necessário):

- CA de usuário em `/data/misc/user/0/cacerts-added/<hash>.0`.
- Módulo LSPosed de trust instalado; escopo do FKIAB no alvo.
- `state/` local (backups/evidências) — fora do git.

Rollback garantido: `reboot` limpa iptables/redsocks e qualquer estado transitório de rede.
Sempre confira `dops doctor` depois e guarde `dops evidence` do estado restaurado.
