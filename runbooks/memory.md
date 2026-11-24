# Memória

```bash
# frida-server + forward (uma vez por sessão)
ponte root -- 'cd /data/local/tmp && setsid nohup ./.fs -l 0.0.0.0:27042 >.fs.log 2>&1 &'
ponte forward --listen 127.0.0.1:27042 127.0.0.1:27042

dops mem scan <valor> --type int64 --package <pkg>
dops mem next <novo> --mode eq|changed|gt|lt
dops mem list --read
dops mem write <addr> <valor>
```

Regras:

- Contadores que mudam (idle/moeda) só são confiáveis com **variação controlada** + `next`.
- Se o valor for `Obscured*` (ACTK), o scan acha só cópias; escrita não pega — pare e vá para
  save/MITM.
- Escreva no máximo em candidatos confirmados; o autosave do jogo consolida.
- Uma sessão, um alvo; `dops cleanup` ao final (SELinux volta a Enforcing).
