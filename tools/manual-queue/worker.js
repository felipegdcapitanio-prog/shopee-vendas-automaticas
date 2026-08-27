/**
 * Recebe produto adicionado no painel (docs/status.html) e grava direto
 * em data/manual_products.json no GitHub -- dali, scripts/post_to_telegram.py
 * pega e posta na próxima execução (a cada ~8 min).
 *
 * O painel é uma página estática (GitHub Pages) e não tem como escrever
 * no repositório sozinha -- por isso esse Worker existe: ele guarda a
 * chave de escrita do GitHub em segredo (nunca aparece no navegador) e
 * só aceita pedido de quem souber o ADMIN_TOKEN.
 *
 * Deploy (grátis, ~5 min):
 *   1. npm install -g wrangler
 *   2. wrangler login
 *   3. Criar um GitHub Fine-grained Personal Access Token em
 *      https://github.com/settings/tokens?type=beta
 *      - Repository access: só este repositório (shopee-vendas-automaticas)
 *      - Permissions: Contents -> Read and write
 *   4. wrangler secret put GITHUB_TOKEN         (cola o token do passo 3)
 *   5. wrangler secret put ADMIN_TOKEN          (senha só sua, usada no painel)
 *   6. wrangler deploy
 *   7. Cola a URL do worker no campo "Endpoint" do formulário em docs/status.html
 */

const OWNER = "felipegdcapitanio-prog";
const REPO = "shopee-vendas-automaticas";
const PATH = "data/manual_products.json";
const BRANCH = "master";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

function b64EncodeUtf8(str) {
  return btoa(unescape(encodeURIComponent(str)));
}

function b64DecodeUtf8(str) {
  return decodeURIComponent(escape(atob(str)));
}

async function githubRequest(env, path, options = {}) {
  const res = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "User-Agent": "achadinhos-manual-queue-worker",
      Accept: "application/vnd.github+json",
      ...(options.headers || {}),
    },
  });
  return res;
}

async function addProduct(env, product) {
  const getRes = await githubRequest(env, `contents/${PATH}?ref=${BRANCH}`);
  if (!getRes.ok) throw new Error(`falha ao ler arquivo atual (${getRes.status})`);
  const file = await getRes.json();
  const current = JSON.parse(b64DecodeUtf8(file.content));

  const entry = {
    itemId: `manual-${Date.now()}`,
    niche: product.niche,
    productName: product.productName,
    priceMin: Number(product.priceMin),
    priceMax: Number(product.priceMin),
    discountRate: Number(product.discountRate || 0),
    commissionRate: Number(product.commissionRate || 0),
    sales: Number(product.sales || 0),
    ratingStar: Number(product.ratingStar || 5),
    imageUrl: product.imageUrl,
    offerLink: product.offerLink,
    posted: false,
    added_at: new Date().toISOString(),
  };
  current.push(entry);

  const putRes = await githubRequest(env, `contents/${PATH}`, {
    method: "PUT",
    body: JSON.stringify({
      message: `chore: adiciona produto manual via painel (${entry.productName.slice(0, 60)})`,
      content: b64EncodeUtf8(JSON.stringify(current, null, 2)),
      sha: file.sha,
      branch: BRANCH,
    }),
  });
  if (!putRes.ok) {
    const body = await putRes.text();
    throw new Error(`falha ao salvar (${putRes.status}): ${body}`);
  }
  return entry;
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }
    if (request.method !== "POST") {
      return json({ error: "use POST" }, 405);
    }

    const auth = request.headers.get("Authorization") || "";
    if (auth !== `Bearer ${env.ADMIN_TOKEN}`) {
      return json({ error: "token inválido" }, 401);
    }

    let product;
    try {
      product = await request.json();
    } catch {
      return json({ error: "corpo inválido, esperado JSON" }, 400);
    }

    const required = ["niche", "productName", "priceMin", "imageUrl", "offerLink"];
    const missing = required.filter((k) => !product[k]);
    if (missing.length) {
      return json({ error: `faltando: ${missing.join(", ")}` }, 400);
    }

    try {
      const entry = await addProduct(env, product);
      return json({ ok: true, entry });
    } catch (e) {
      return json({ error: e.message }, 500);
    }
  },
};
