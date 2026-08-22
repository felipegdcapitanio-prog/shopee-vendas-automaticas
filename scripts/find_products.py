"""Garimpeiro: busca produtos por nicho na Shopee Affiliate API,
filtra por venda + nota + comissão, prioriza desconto, e MESCLA com o
catálogo existente em data/catalogo_produtos.json (não sobrescreve —
soma produto novo aos que já tem, até um teto por nicho). Pensado pra
rodar todo dia, alimentando um volume alto de postagem (ex: 48/dia).

Uso:
    python scripts/find_products.py
"""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"
ROOT = os.path.join(os.path.dirname(__file__), "..")
ENV_PATH = os.path.join(ROOT, ".env")
OUT_PATH = os.path.join(ROOT, "data", "catalogo_produtos.json")

# sortType: 2 = mais vendidos
SORT_BY_SALES = 2

NICHES = {
    "Beleza & Skincare": ["skincare facial", "creme hidratante rosto", "protetor solar facial", "sérum facial", "esfoliante facial", "hidratante corporal"],
    "Maquiagem": ["batom", "paleta de sombra", "base facial", "máscara de cílios", "pó compacto", "delineador"],
    "Moda Feminina": ["vestido feminino", "blusa feminina", "conjunto feminino", "short feminino", "saia feminina", "cropped feminino"],
    "Calçados": ["tênis feminino", "sandália feminina", "rasteirinha feminina", "bota feminina", "chinelo feminino", "sapatilha feminina"],
    "Decoração de Casa": ["decoração quarto", "enfeite sala de estar", "organizador cozinha", "cortina blackout", "quadro decorativo", "tapete sala"],
    "Ferramentas": ["kit ferramentas", "furadeira parafusadeira", "trena a laser", "parafuso caixa", "chave de fenda kit", "serra elétrica"],
    "Iluminação": ["luminária led", "fita led", "abajur quarto", "pisca pisca led", "spot led", "luminária pendente"],
}

# critérios mínimos de qualidade
MIN_RATING = 4.0
MIN_SALES = 10
MIN_COMMISSION = 0.08  # 8%
PER_KEYWORD_LIMIT = 30
MAX_PER_NICHE = 90  # teto do catálogo por nicho -- subiu pra sustentar 180 posts/dia com cooldown de 3 dias sem esgotar


def load_env(path):
    # Local: lê o .env (não versionado). Em CI (GitHub Actions), o .env não
    # existe e os valores já vêm como variável de ambiente via secrets.
    values = dict(os.environ)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if value.strip():
                    values[key.strip()] = value.strip()
    return values


def build_signature(app_id, secret, timestamp, payload):
    raw = f"{app_id}{timestamp}{payload}{secret}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def query_products(app_id, secret, keyword, limit=PER_KEYWORD_LIMIT, sort_type=SORT_BY_SALES):
    gql = (
        "query{productOfferV2(keyword:\"%s\",sortType:%d,limit:%d){nodes{"
        "itemId productName priceMin priceMax priceDiscountRate "
        "sales ratingStar commissionRate imageUrl offerLink}}}"
        % (keyword, sort_type, limit)
    )
    payload = json.dumps({"query": gql}, separators=(",", ":"))
    timestamp = str(int(time.time()))
    signature = build_signature(app_id, secret, timestamp, payload)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={signature}",
    }
    req = urllib.request.Request(ENDPOINT, data=payload.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  [erro HTTP {e.code}] {keyword}: {e.read().decode('utf-8')[:200]}")
        return []
    except urllib.error.URLError as e:
        print(f"  [erro de conexão] {keyword}: {e.reason}")
        return []

    if "errors" in body:
        print(f"  [erro GraphQL] {keyword}: {body['errors']}")
        return []
    return body.get("data", {}).get("productOfferV2", {}).get("nodes", []) or []


def qualifies(node):
    try:
        rating = float(node.get("ratingStar") or 0)
        sales = int(node.get("sales") or 0)
        commission = float(node.get("commissionRate") or 0)
    except (TypeError, ValueError):
        return False
    return rating >= MIN_RATING and sales >= MIN_SALES and commission >= MIN_COMMISSION


def score(node):
    discount = int(node.get("priceDiscountRate") or 0)
    sales = int(node.get("sales") or 0)
    commission = float(node.get("commissionRate") or 0)
    # desconto pesa mais forte (prioridade pedida: atrair lead via desconto)
    return (discount * 3) + (commission * 100) + min(sales, 500) / 10


def to_entry(niche, n):
    return {
        "niche": niche,
        "itemId": n.get("itemId"),
        "productName": n.get("productName"),
        "priceMin": n.get("priceMin"),
        "priceMax": n.get("priceMax"),
        "discountRate": int(n.get("priceDiscountRate") or 0),
        "commissionRate": float(n.get("commissionRate") or 0),
        "sales": int(n.get("sales") or 0),
        "ratingStar": n.get("ratingStar"),
        "imageUrl": n.get("imageUrl"),
        "offerLink": n.get("offerLink"),
    }


def load_existing_catalog():
    if not os.path.exists(OUT_PATH):
        return {}
    with open(OUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    by_niche = {}
    for p in data.get("products", []):
        by_niche.setdefault(p["niche"], {})[p["itemId"]] = p
    return by_niche


def main():
    env = load_env(ENV_PATH)
    app_id = env.get("SHOPEE_AFFILIATE_APP_ID")
    secret = env.get("SHOPEE_AFFILIATE_SECRET")
    if not app_id or not secret:
        print("ERRO: credenciais não encontradas no .env")
        return

    existing_by_niche = load_existing_catalog()
    catalog = []
    total_new = 0

    for niche, keywords in NICHES.items():
        print(f"\n== {niche} ==")
        pool = dict(existing_by_niche.get(niche, {}))  # itemId -> entry, começa com o que já tinha
        before = len(pool)

        for kw in keywords:
            print(f"  buscando: {kw}")
            nodes = query_products(app_id, secret, kw)
            print(f"    {len(nodes)} produtos retornados")
            for n in nodes:
                if not qualifies(n):
                    continue
                item_id = n.get("itemId")
                pool[item_id] = to_entry(niche, n)  # atualiza dados (preço/desconto podem mudar)
            time.sleep(0.4)  # respeitar rate limit

        total_new += max(0, len(pool) - before)

        ranked = sorted(pool.values(), key=lambda p: score({
            "priceDiscountRate": p["discountRate"],
            "sales": p["sales"],
            "commissionRate": p["commissionRate"],
        }), reverse=True)[:MAX_PER_NICHE]

        print(f"  -> catálogo do nicho: {len(ranked)} produtos (era {before}, {len(pool) - before} novos/atualizados nesta rodada)")
        catalog.extend(ranked)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated_at": int(time.time()), "products": catalog}, f, ensure_ascii=False, indent=2)

    print(f"\nTotal no catálogo: {len(catalog)} produtos ({total_new} novos/atualizados nesta rodada)")
    print(f"Salvo em: {OUT_PATH}")


if __name__ == "__main__":
    main()
