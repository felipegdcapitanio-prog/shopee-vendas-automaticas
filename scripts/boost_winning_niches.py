"""Olha o relatório de vendas (data/relatorio_vendas.json) e, pros nichos
que já têm produto com pedido confirmado, busca mais produtos parecidos
na Shopee pra reforçar o catálogo onde já provou que vende de verdade.

Roda depois do fetch_sales_report.py no fluxo diário. Se ainda não tem
nenhuma venda registrada, não faz nada (fica pronto pra quando tiver).

Uso:
    python scripts/boost_winning_niches.py
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

sys.path.insert(0, os.path.dirname(__file__))
from find_products import NICHES, MIN_RATING, MIN_SALES, MIN_COMMISSION, MAX_PER_NICHE  # noqa: E402

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"
ROOT = os.path.join(os.path.dirname(__file__), "..")
ENV_PATH = os.path.join(ROOT, ".env")
CATALOG_PATH = os.path.join(ROOT, "data", "catalogo_produtos.json")
REPORT_PATH = os.path.join(ROOT, "data", "relatorio_vendas.json")

MIN_ORDERS_TO_BOOST = 2  # a partir de quantos pedidos um nicho é considerado "provado"
EXTRA_LIMIT_PER_KEYWORD = 20


def load_env(path):
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


def query_products(app_id, secret, keyword, limit):
    gql = (
        "query{productOfferV2(keyword:\"%s\",sortType:2,limit:%d){nodes{"
        "itemId productName priceMin priceMax priceDiscountRate "
        "sales ratingStar commissionRate imageUrl offerLink}}}"
        % (keyword, limit)
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
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"  [erro] {keyword}: {e}")
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


def main():
    if not os.path.exists(REPORT_PATH):
        print("Ainda não existe relatório de vendas. Nada a reforçar por enquanto.")
        return

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    winning_niches = {
        p["niche"] for p in report.get("products", [])
        if p.get("niche") and int(p.get("orders", 0)) >= MIN_ORDERS_TO_BOOST
    }

    if not winning_niches:
        print("Nenhum nicho com vendas suficientes pra reforçar ainda (normal no início).")
        return

    print(f"Nichos provados: {sorted(winning_niches)}")

    env = load_env(ENV_PATH)
    app_id = env.get("SHOPEE_AFFILIATE_APP_ID")
    secret = env.get("SHOPEE_AFFILIATE_SECRET")
    if not app_id or not secret:
        print("ERRO: credenciais não encontradas")
        return

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    catalog = data["products"]
    by_niche = {}
    for p in catalog:
        by_niche.setdefault(p["niche"], {})[p["itemId"]] = p

    total_new = 0
    for niche in winning_niches:
        keywords = NICHES.get(niche, [])
        if not keywords:
            continue
        pool = by_niche.get(niche, {})
        before = len(pool)
        for kw in keywords:
            nodes = query_products(app_id, secret, kw, EXTRA_LIMIT_PER_KEYWORD)
            for n in nodes:
                if not qualifies(n):
                    continue
                pool[n.get("itemId")] = to_entry(niche, n)
            time.sleep(0.4)
        added = len(pool) - before
        total_new += max(0, added)
        by_niche[niche] = pool
        print(f"  {niche}: +{added} produtos (agora {len(pool)})")

    # remonta o catálogo aplicando o teto por nicho, priorizando desconto/comissão/vendas
    def score(p):
        return p["discountRate"] * 3 + p["commissionRate"] * 100 + min(p["sales"], 500) / 10

    new_catalog = []
    for niche, pool in by_niche.items():
        ranked = sorted(pool.values(), key=score, reverse=True)[:MAX_PER_NICHE]
        new_catalog.extend(ranked)

    data["products"] = new_catalog
    data["generated_at"] = int(time.time())
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{total_new} produto(s) novo(s) adicionado(s) reforçando nicho(s) vencedor(es).")


if __name__ == "__main__":
    main()
