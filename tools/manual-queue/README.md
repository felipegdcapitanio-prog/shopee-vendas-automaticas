# Fila manual (grátis)

Deixa o formulário "Adicionar produto" do painel (`docs/status.html`)
gravar direto em `data/manual_products.json` no GitHub. Dali,
`scripts/post_to_telegram.py` já pega e posta sozinho na próxima
execução (a cada ~8 min) -- sem entrar na conta da meta diária
automática, é sempre um extra.

## Deploy (~5 minutos, sem custo)

```bash
npm install -g wrangler
wrangler login
```

1. Criar um **GitHub Fine-grained Personal Access Token**:
   [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta)
   - Repository access: **só** `shopee-vendas-automaticas`
   - Permissions: **Contents → Read and write**

2. Configurar os segredos do worker:

```bash
wrangler secret put GITHUB_TOKEN
# cola o token criado acima

wrangler secret put ADMIN_TOKEN
# escolhe uma senha só sua -- é o que vai digitar no painel pra liberar o formulário
```

3. Deploy:

```bash
wrangler deploy
```

Isso devolve uma URL tipo
`https://achadinhos-manual-queue.SEU-USUARIO.workers.dev`.

4. No painel (`docs/status.html`), na seção "Adicionar produto", cola
   essa URL no campo **Endpoint** e a senha do `ADMIN_TOKEN` no campo
   **Senha** -- ele guarda os dois só no seu navegador (localStorage),
   nunca no código.

## Por que não é mais simples que isso

O painel é uma página estática (GitHub Pages) e não tem servidor
próprio, então não tem como escrever no repositório sozinha. Colocar a
chave de escrita do GitHub direto na página seria inseguro (o
repositório é público -- qualquer pessoa que abrisse a página
conseguiria roubar a chave e mexer no código). O Worker existe
exatamente pra guardar essa chave em segredo, do lado de fora do
navegador.
