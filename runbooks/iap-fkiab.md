# IAP — FKIAB (FakeBinder)

Pré: FKIAB 1.8.1 (`com.fuck.iab`) instalado, LSPosed 2.x com escopo só no alvo.

```bash
dops iap status <pkg>          # instalado, injetado, escopo, scripts, recibos
dops iap scope  <pkg>          # adiciona escopo via lspctl
dops iap receipts <pkg>        # lista productId/orderId do store fake
dops iap receipts <pkg> --clean
dops iap script <pkg> --loader loader.js --payload b.js
```

Fluxo:

1. Loja do app deve mostrar preço falso (`$0.00`) → FakeBinder ativo.
2. `NonConsumable` (type=1) costuma conceder local mesmo com validação server-side falhando;
   o app pode ANR no tap → `force-stop` + reabrir consolida o grant.
3. Consumível (type=0) exige validação (MITM/patch).
4. Ownership/entitlement fica no save do app: recibo fake novo não re-concede produto já owned.
5. Não edite `fuck.iab.xml` à mão em produção; use `--clean` para parar replay no boot.
6. GumJS do FKIAB só executa o texto salvo no editor; o arquivo em
   `/data/data/com.fuck.iab/files/scripts/<pkg>.js` é cache. Use um loader que lê `b.js` do app.
