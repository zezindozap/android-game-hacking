# Save files

```bash
dops save sniff <arquivo>            # JSON, ENC1/ACTK, gzip, base64, binário
dops restore ...                     # rollback
```

Fluxo:

1. Localize o save (`dops recon`, `save_paths` do target).
2. `sniff`: JSON → edição direta; `ENC1` → precisa de hook de crypto; gzip/base64 → decodificar.
3. Para cifrado: rode um hook que logue chave/IV (`Chave/EIV` no primitivo), ou capture o
   plaintext no load e reescreva pelo próprio app (memória) — nunca brute force.
4. Jogo parado; escrita in-place; verifique em 3 níveis (decode → UI → restart e reabrir).
5. `dops backup` antes; `dops evidence` depois.

Notas:

- Preserve prefixo/header/versão e padding; re-serialize igual ao original.
- Valores absurdos (2^31-1) são flag; use o maior plausível.
- Ownership/entitlements costumam ficar no mesmo blob do save (não em prefs).
