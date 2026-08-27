# Painel (grátis)

`status.html` é o painel — lê os arquivos de `data/*.json` direto do
repositório, sem precisar abrir o GitHub:

- **Visão geral** — saúde do robô, tamanho do catálogo, posts enviados
- **Grupos** — link do Telegram e do WhatsApp com botão de copiar
- **Catálogo** — busca/filtro/ordenação nos produtos qualificados
- **Vendas** — conversões, pedidos e comissão dos últimos 90 dias
- **Cliques** — status honesto: ainda não é medido (falta plugar `tools/link-shortener/`)
- **Adicionar produto** — formulário que joga um produto na fila do robô
  (precisa do `tools/manual-queue/` publicado — ver README de lá)

Já está no ar em:
`https://felipegdcapitanio-prog.github.io/shopee-vendas-automaticas/docs/status.html`

Ativado via Settings → Pages → branch `master`, pasta `/ (root)`. O
repositório está público (sem segredo no código — as credenciais ficam
só nos *Secrets* do GitHub).
