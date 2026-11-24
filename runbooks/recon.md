# Recon

```bash
dops recon <pkg>          # versão, engine, libs, data/prefs/external
dops --json recon <pkg> > state/recon-<pkg>.json
```

Checklist:

1. Engine (unity-il2cpp/mono, flutter, react-native, cocos, unreal).
2. Onde o estado mora: `shared_prefs`, `files/`, `databases/`, `Android/data/<pkg>/files`.
3. Proteções: libs do tipo `libpglarmor`, ACTK (metadata), Play Integrity/Firebase.
4. Billing: `billingclient` no dex, Unity IAP no metadata, URLs de validação.
5. Transporte de rede: hostnames no metadata/metadata strings (use APK + UnityPy).

Artefatos: APK pull, `python -c 'import UnityPy'` para TextAssets (catálogos/configs),
`strings` no metadata para literais (URLs, chaves, prefixos de save).
