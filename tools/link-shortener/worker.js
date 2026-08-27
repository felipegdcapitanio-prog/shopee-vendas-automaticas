/**
 * Encurtador de link com contagem de clique, rodando de graça no
 * Cloudflare Workers (camada gratuita: até 100.000 requisições/dia).
 *
 * Resolve a ideia #45 do kit de crescimento: hoje só se sabe quando um
 * clique VIRA venda (via relatorio_vendas.json); isso aqui mostra o
 * clique em si, mesmo quando não converte.
 *
 * Rotas:
 *   GET  /:slug                  -> redireciona pro link da Shopee e conta o clique
 *   GET  /:slug/stats            -> retorna o total de clique (precisa do ADMIN_TOKEN)
 *   POST /admin/link             -> cria/atualiza um link (precisa do ADMIN_TOKEN)
 *                                    body: {"slug": "abc123", "url": "https://s.shopee.com.br/..."}
 *
 * Deploy (grátis, ~5 min):
 *   1. npm install -g wrangler
 *   2. wrangler login
 *   3. wrangler kv namespace create LINKS   (copia o id gerado pro wrangler.toml)
 *   4. wrangler secret put ADMIN_TOKEN      (escolhe uma senha só sua)
 *   5. wrangler deploy
 */

function unauthorized() {
  return new Response("unauthorized", { status: 401 });
}

async function handleRedirect(env, slug) {
  const url = await env.LINKS.get(`url:${slug}`);
  if (!url) return new Response("link nao encontrado", { status: 404 });

  const clicksKey = `clicks:${slug}`;
  const current = parseInt((await env.LINKS.get(clicksKey)) || "0", 10);
  await env.LINKS.put(clicksKey, String(current + 1));

  return Response.redirect(url, 302);
}

async function handleStats(env, slug, token) {
  if (token !== env.ADMIN_TOKEN) return unauthorized();
  const clicks = parseInt((await env.LINKS.get(`clicks:${slug}`)) || "0", 10);
  const url = await env.LINKS.get(`url:${slug}`);
  return Response.json({ slug, url, clicks });
}

async function handleCreateLink(request, env) {
  const auth = request.headers.get("Authorization") || "";
  if (auth !== `Bearer ${env.ADMIN_TOKEN}`) return unauthorized();

  const { slug, url } = await request.json();
  if (!slug || !url) {
    return new Response("informe slug e url", { status: 400 });
  }
  await env.LINKS.put(`url:${slug}`, url);
  return Response.json({ ok: true, slug, url, shortlink: `/${slug}` });
}

export default {
  async fetch(request, env) {
    const { pathname, searchParams } = new URL(request.url);

    if (request.method === "POST" && pathname === "/admin/link") {
      return handleCreateLink(request, env);
    }

    const parts = pathname.split("/").filter(Boolean);
    if (parts.length === 1) {
      return handleRedirect(env, parts[0]);
    }
    if (parts.length === 2 && parts[1] === "stats") {
      return handleStats(env, parts[0], searchParams.get("token"));
    }

    return new Response("uso: /:slug para redirecionar, /:slug/stats?token=... pra ver clique", { status: 200 });
  },
};
