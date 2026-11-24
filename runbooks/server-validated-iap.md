# IAP validado no servidor (cliente burlável por hook)

Para jogos em que o grant **não** vem do Google Play, mas de um hit do backend do jogo
(ex.: `CServerHits.ValidateShopPurchaseHit` / `EHit.ValidatePurchaseRequest`). FakeBinder sozinho
só faz o preço virar `$0.00`; o servidor recusa o token fake e o cliente reverte (aqui:
`EErrorState 15 = InvalidPurchaseValidation`, popup “Erro de conexão (ID:15)”, rollback no restart).

## Classificar antes

1. `dops il2cpp dump <pkg>` → `dump.cs`; procure `ValidateShopPurchase`, `PurchaseResponse`,
   `CShop`, `CPurchasing`.
2. Fluxo típico: `CPurchasing.BuyProductId` → billing → `CServerHits.ValidateXHit(EProductId,
   token, onSuccess, onError)` → backend responde `CValidateXResponse { rewards, error, ... }`
   → `CShop.ValidatePurchaseServer(response, ...)` aplica os rewards.
3. Se o reward está na resposta do servidor, não existe “recibo válido local”: a rota é
   **forjar a resposta no cliente** (hook) ou patch de código.

## Rota: hook da validação (frida-il2cpp-bridge)

```ts
Il2Cpp.perform(() => {
  Il2Cpp.installExceptionListener("all");      // abort vira stack de C# útil
  const hits = findClass("Zombero.CServerHits");
  const m = hits.method("ValidateShopPurchaseHit");
  m.implementation = function (...args) {
    const pid = args[0], cb = args[2] as Il2Cpp.Object;
    const resp = buildValidateResponse(pid);   // preencher TODOS os campos aninhados
    cb.method("Invoke").invoke(resp);          // executar na thread do hit
  };
});
```

Construção da resposta (lições):

- `Cls.alloc()` + `field("...").value = ...`; **enums** via `obj.handle.add(0x11).writeU8(valor)`
  (setter de enum lança “expected a pointer”).
- Preencher **arrays vazios e objetos aninhados** que o cliente percorre:
  `remainingAds` (`CTransportRemainingAd[]`), `modificatedQuests`, `nextQueuedRewards`,
  `champions`/`boosters`/`rewards` (`CTransportRewardData`). Campo nulo = `NullReferenceException`
  em `CLocalInfoRemainingAds.Replace` / `CShop.ValidatePurchaseServer`.
- `error = EErrorState.Ok (1)` (raw write, 0x11 no `CHitResponseBase`).
- Rewards: `CValidatePurchaseResponse.rewards` (`CTransportReward`) → `.reward`
  (`CTransportRewardData`: softCurrency/hardCurrency/energy/holyWater/luckyWheelSpins/...).

## “abort was called” não é ABI

`abort was called` do bridge = **exceção C#** na chamada. Use
`Il2Cpp.installExceptionListener("all")` e leia o stack; itere preenchendo campos até o callback
completar. Só depois disso investigue thread (`csproto` de delegate: `method_ptr@0x10`,
`invoke_impl@0x18`, `m_target@0x20`, `method_code@0x40`).

Se invocar o delegate continuar inviável, hooke o **dispatch interno**
(`CIncomingDataPreparer.DecodeIncomingHit` / lambda de `CServerClient.AddHit`) e substitua o
`SHitWrapper` antes de o jogo chamar `onSuccess` sozinho.

## Pegadinhas do alvo

- Transação pendente no servidor: todo boot revalida e mostra ID15; limpar prefs do app não
  resolve se o servidor guarda o estado. Conta nova (dados limpos) evita o pendente.
- Moeda é espelhada no servidor; `GameGuardian`/scan de memória falha com valores obscured.
- Protocolo binário próprio (`CClientSocket`/`CInPacket`, `ICrypt`): MITM HTTPS não se aplica.
- ACTK: Frida só na sessão; prefira o hook mínimo e não deixe scripts residentes.
- `Task.FromResult`/delegates: não fabricar Task; chame o callback com objeto completo.

## Alternativas (ordem)

1. Hook da validação com resposta fabricada (acima) — menor diff.
2. Hook do dispatch interno (`DecodeIncomingHit`) — evita delegate externo.
3. Patch inline do call-site de sucesso (maior risco de integridade).
4. MITM **só** se a validação for HTTP(S) JSON (não é o caso de socket binário).
