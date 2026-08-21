"""Garimpeiro: busca produtos por nicho na Shopee Affiliate API,
filtra por venda + nota + comissão, prioriza desconto, e salva
um catálogo consolidado em data/catalogo_produtos.json.

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
    "Beleza & Skincare": ["skincare facial", "creme hidratante rosto"],
    "Maquiagem": ["batom", "paleta de sombra"],
    "Moda Feminina": ["vestido feminino", "blusa feminina"],
    "Calçados": ["tênis feminino", "sandália feminina"],
    "Decoração de Casa": ["decoração quarto", "enfeite sala de estar"],
    "Ferramentas": ["kit ferramentas", "furadeira parafusadeira"],
    "Iluminação": ["luminária led", "fita led"],
}

# critérios mínimos de qualidade
MIN_RATING = 4.0
MIN_SALES = 10
MIN_COMMISSION = 0.08  # 8%
PER_KEYWORD_LIMIT = 20
TOP_PER_NICHE = 5


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


def main():
    env = load_env(ENV_PATH)
    app_id = env.get("SHOPEE_AFFILIATE_APP_ID")
    secret = env.get("SHOPEE_AFFILIATE_SECRET")
    if not app_id or not secret:
        print("ERRO: credenciais não encontradas no .env")
        return

    catalog = []
    for niche, keywords in NICHES.items():
        print(f"\n== {niche} ==")
        seen_in_niche = {}
        for kw in keywords:
            print(f"  buscando: {kw}")
            nodes = query_products(app_id, secret, kw)
            print(f"    {len(nodes)} produtos retornados")
            for n in nodes:
                if not qualifies(n):
                    continue
                item_id = n.get("itemId")
                if item_id in seen_in_niche:
                    continue
                seen_in_niche[item_id] = n
            time.sleep(0.4)  # respeitar rate limit

        ranked = sorted(seen_in_niche.values(), key=score, reverse=True)[:TOP_PER_NICHE]
        print(f"  -> {len(ranked)} produtos selecionados após filtro (nota>={MIN_RATING}, vendas>={MIN_SALES}, comissão>={MIN_COMMISSION*100:.0f}%)")

        for n in ranked:
            catalog.append({
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
            })

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated_at": int(time.time()), "products": catalog}, f, ensure_ascii=False, indent=2)

    print(f"\nTotal no catálogo: {len(catalog)} produtos")
    print(f"Salvo em: {OUT_PATH}")


if __name__ == "__main__":
    main()
