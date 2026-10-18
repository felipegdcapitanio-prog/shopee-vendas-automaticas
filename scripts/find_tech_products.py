"""Garimpeiro de tecnologia pra vitrine "Achados Shopee" da loja PULSO.

Busca celulares, fones e carregadores na Shopee Affiliate API, filtra por
nota + vendas, e salva em data/catalogo_pulso_tech.json (arquivo separado:
não mexe no catálogo do robô do Telegram). A loja lê esse arquivo direto
do GitHub, então renovar aqui já atualiza a vitrine.

Uso:
    python scripts/find_tech_products.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from find_products import ENV_PATH, ROOT, build_signature, load_env, query_products  # noqa: E402

import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"
OUT_PATH = os.path.join(ROOT, "data", "catalogo_pulso_tech.json")

# preco_min evita capinha/película aparecendo na busca de celular
CATEGORIES = {
    "celulares": {
        "nome": "Celulares",
        "keywords": ["smartphone samsung galaxy", "celular xiaomi redmi", "celular motorola moto g", "smartphone poco", "iphone"],
        "preco_min": 400,
    },
    "fones": {
        "nome": "Fones",
        "keywords": ["fone bluetooth tws", "fone de ouvido sem fio", "headphone bluetooth", "headset gamer", "fone com cancelamento de ruído"],
        "preco_min": 15,
    },
    "carregadores": {
        "nome": "Carregadores",
        "keywords": ["carregador turbo usb c", "carregador iphone 20w", "power bank", "carregador sem fio magnético", "cabo usb c turbo"],
        "preco_min": 10,
    },
}

MIN_RATING = 4.5
MIN_SALES = 20
PER_KEYWORD_LIMIT = 30
MAX_PER_CATEGORY = 24
EXCLUDE = ["capa", "capinha", "película", "pelicula", "suporte", "case "]


def query_with_shop(app_id, secret, keyword):
    """Igual ao query_products, pedindo também o nome da loja. Se a API
    recusar o campo extra, cai pra consulta padrão."""
    gql = (
        "query{productOfferV2(keyword:\"%s\",sortType:2,limit:%d){nodes{"
        "itemId productName priceMin priceMax priceDiscountRate "
        "sales ratingStar commissionRate imageUrl offerLink shopName}}}"
        % (keyword, PER_KEYWORD_LIMIT)
    )
    payload = json.dumps({"query": gql}, separators=(",", ":"))
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={build_signature(app_id, secret, timestamp, payload)}",
    }
    req = urllib.request.Request(ENDPOINT, data=payload.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError):
        body = {"errors": True}
    if "errors" in body:
        return query_products(app_id, secret, keyword)
    return body.get("data", {}).get("productOfferV2", {}).get("nodes", []) or []


def qualifies(node, cat):
    name = (node.get("productName") or "").lower()
    if cat != "celulares" and any(w in name for w in EXCLUDE[:2]):
        return False
    if cat == "celulares" and any(w in name for w in EXCLUDE):
        return False
    try:
        rating = float(node.get("ratingStar") or 0)
        sales = int(node.get("sales") or 0)
        price = float(node.get("priceMin") or 0)
    except (TypeError, ValueError):
        return False
    return rating >= MIN_RATING and sales >= MIN_SALES and price >= CATEGORIES[cat]["preco_min"] and node.get("imageUrl") and node.get("offerLink")


def score(p):
    # aqui pesa mais a venda (prova social) do que o desconto
    return min(p["sales"], 5000) / 50 + p["discountRate"] + float(p["ratingStar"] or 0) * 10


def main():
    env = load_env(ENV_PATH)
    app_id = env.get("SHOPEE_AFFILIATE_APP_ID")
    secret = env.get("SHOPEE_AFFILIATE_SECRET")
    if not app_id or not secret:
        print("ERRO: credenciais não encontradas")
        return

    produtos = []
    for cat, info in CATEGORIES.items():
        print(f"\n== {info['nome']} ==")
        pool = {}
        for kw in info["keywords"]:
            nodes = query_with_shop(app_id, secret, kw)
            print(f"  {kw}: {len(nodes)} retornados")
            for n in nodes:
                if not qualifies(n, cat):
                    continue
                pool[n["itemId"]] = {
                    "categoria": cat,
                    "itemId": n["itemId"],
                    "nome": (n.get("productName") or "").strip(),
                    "precoMin": float(n.get("priceMin") or 0),
                    "precoMax": float(n.get("priceMax") or 0),
                    "discountRate": int(n.get("priceDiscountRate") or 0),
                    "sales": int(n.get("sales") or 0),
                    "ratingStar": n.get("ratingStar"),
                    "loja": n.get("shopName") or "",
                    "imagem": n["imageUrl"],
                    "link": n["offerLink"],
                }
            time.sleep(0.4)
        ranked = sorted(pool.values(), key=score, reverse=True)[:MAX_PER_CATEGORY]
        print(f"  -> {len(ranked)} na vitrine")
        produtos.extend(ranked)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": int(time.time()),
            "categorias": {k: v["nome"] for k, v in CATEGORIES.items()},
            "produtos": produtos,
        }, f, ensure_ascii=False, indent=1)
    print(f"\nTotal: {len(produtos)} produtos -> {OUT_PATH}")


if __name__ == "__main__":
    main()
