# Painel de status (grátis)

`status.html` é um painel estático que lê os arquivos de `data/*.json` e
mostra saúde do robô, tamanho do catálogo e vendas — sem precisar abrir
o GitHub.

## Pra ativar (GitHub Pages, grátis)

1. Settings → Pages → Source: "Deploy from a branch" → branch `master`,
   pasta `/ (root)`.
2. A página fica em `https://SEU-USUARIO.github.io/shopee-vendas-automaticas/docs/status.html`.

**Atenção:** este repositório está **privado**. GitHub Pages em
repositório privado só funciona em conta paga (Pro/Team). Duas opções:

- Deixar o repositório público (o código não tem segredo nenhum — as
  credenciais ficam nos *Secrets* do GitHub, nunca no código; mas vale
  vocês decidirem juntos se tudo bem deixar público);
- Ou manter privado e só abrir `docs/status.html` localmente / hospedar
  em outro lugar grátis (ex: Cloudflare Pages também tem plano grátis
  pra repositório privado).

Nenhuma dessas duas coisas foi feita — fica pra vocês escolherem.
