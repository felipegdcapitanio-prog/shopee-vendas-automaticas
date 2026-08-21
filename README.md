# Shopee Vendas Automáticas

Pipeline de afiliados Shopee (nicho beleza, moda e casa): garimpa produtos com bom desconto e comissão, e posta automaticamente num grupo/canal do Telegram todo dia.

## Scripts

- `scripts/test_shopee_api.py` — testa a conexão com a Shopee Affiliate API
- `scripts/find_products.py` — garimpa produtos por nicho, filtra e salva em `data/catalogo_produtos.json`
- `scripts/post_to_telegram.py` — posta produtos novos (ainda não postados) no Telegram, priorizando desconto

## Automação (GitHub Actions)

- `.github/workflows/daily-post.yml` — posta produtos novos todo dia
- `.github/workflows/refresh-catalog.yml` — renova o catálogo toda semana

Secrets necessários no repositório: `SHOPEE_AFFILIATE_APP_ID`, `SHOPEE_AFFILIATE_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Local

Copie `.env.example` para `.env` e preencha com suas credenciais (o `.env` nunca é commitado).
