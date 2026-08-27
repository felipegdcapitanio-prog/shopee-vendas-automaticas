# Encurtador de link (grátis)

Roda no Cloudflare Workers (camada gratuita). Mostra quantas pessoas
clicaram num link, não só quantas compraram — o `relatorio_vendas.json`
já mostra venda, isso aqui mostra clique.

## Deploy (~5 minutos, sem custo)

```bash
npm install -g wrangler
wrangler login
wrangler kv namespace create LINKS
# copia o "id" que aparecer e cola em wrangler.toml
wrangler secret put ADMIN_TOKEN
# escolhe uma senha só sua -- é o que protege a criação de link e as estatísticas
wrangler deploy
```

Isso devolve uma URL tipo `https://achadinhos-links.SEU-USUARIO.workers.dev`.

## Criar um link curto

```bash
curl -X POST https://achadinhos-links.SEU-USUARIO.workers.dev/admin/link \
  -H "Authorization: Bearer SEU_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"slug": "creme123", "url": "https://s.shopee.com.br/xxxxxxx"}'
```

Isso deixa `https://achadinhos-links.SEU-USUARIO.workers.dev/creme123`
pronto pra usar no lugar do link direto da Shopee em qualquer post.

## Ver quantos cliques um link teve

```
GET https://achadinhos-links.SEU-USUARIO.workers.dev/creme123/stats?token=SEU_ADMIN_TOKEN
```

## Integrar no robô (próximo passo, opcional)

Hoje `post_to_telegram.py` e `post_engagement_message.py` usam o
`offerLink` direto do catálogo. Pra usar o encurtador automaticamente
seria preciso: 1) chamar a rota `/admin/link` ao gerar cada post pra
criar o slug, 2) trocar o link na legenda pelo link curto. Não fiz essa
parte ainda porque mexe no fluxo que já está rodando ao vivo a cada 8
minutos -- melhor testar o encurtador sozinho primeiro e só depois
plugar nos scripts, com calma.
