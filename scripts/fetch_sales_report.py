"""Analista: consulta o conversionReport da Shopee Affiliate API pra saber
quais produtos tiveram clique que virou venda, e quanto de comissão cada
um gerou. Junta esse resultado com o catálogo (nome, nicho, imagem) e
salva um snapshot em data/relatorio_vendas.json pro painel usar.

A Shopee só retorna dados de clique quando o clique VIROU pedido (não dá
pra saber cliques que não converteram por essa API), então este relatório
é exatamente "produtos que receberam clique e geraram venda", como pedido.

Uso:
    python scripts/fetch_sales_report.py                # últimos 90 dias
    python scripts/fetch_sales_report.py --days 30
"""

import argparse
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
CATALOG_PATH = os.path.join(ROOT, "data", "catalogo_produtos.json")
OUT_PATH = os.path.join(ROOT, "data", "relatorio_vendas.json")

DEFAULT_DAYS = 90  # limite da API é ~90 dias entre start e end
PAGE_LIMIT = 50

# pedidos cancelados não contam como venda real
COUNTS_AS_SALE = {"PENDING", "COMPLETED"}


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


def query_page(app_id, secret, start, end, scroll_id=None):
    scroll_part = f',scrollId:"{scroll_id}"' if scroll_id else ""
    gql = (
        "query{conversionReport(purchaseTimeStart:%d,purchaseTimeEnd:%d,limit:%d%s){"
        "pageInfo{limit hasNextPage scrollId}"
        "nodes{purchaseTime clickTime conversionId totalCommission "
        "orders{orderId orderStatus items{itemId itemName itemPrice qty itemTotalCommission}}}"
        "}}" % (start, end, PAGE_LIMIT, scroll_part)
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
        print(f"[erro HTTP {e.code}] {e.read().decode('utf-8')[:300]}")
        return None
    except urllib.error.URLError as e:
        print(f"[erro de conexão] {e.reason}")
        return None

    if "errors" in body:
        print(f"[erro GraphQL] {body['errors']}")
        return None
    return body.get("data", {}).get("conversionReport")


def load_catalog_index():
    if not os.path.exists(CATALOG_PATH):
        return {}
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(p["itemId"]): p for p in data.get("products", [])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    app_id = env.get("SHOPEE_AFFILIATE_APP_ID")
    secret = env.get("SHOPEE_AFFILIATE_SECRET")
    if not app_id or not secret:
        print("ERRO: credenciais não encontradas no .env")
        return

    now = int(time.time())
    start = now - args.days * 86400

    catalog_idx = load_catalog_index()
    per_product = {}
    totals = {"conversions": 0, "orders": 0, "qty": 0, "commission": 0.0}

    scroll_id = None
    page = 1
    while True:
        report = query_page(app_id, secret, start, now, scroll_id)
        if report is None:
            print("Falha ao consultar a API, abortando.")
            return
        nodes = report.get("nodes") or []
        print(f"  página {page}: {len(nodes)} conversões")
        for node in nodes:
            totals["conversions"] += 1
            commission = float(node.get("totalCommission") or 0)
            totals["commission"] += commission
            for order in node.get("orders") or []:
                status = order.get("orderStatus")
                if status not in COUNTS_AS_SALE:
                    continue
                totals["orders"] += 1
                for item in order.get("items") or []:
                    item_id = str(item.get("itemId"))
                    qty = int(item.get("qty") or 0)
                    item_commission = float(item.get("itemTotalCommission") or 0)
                    totals["qty"] += qty
                    entry = per_product.setdefault(item_id, {
                        "itemId": item_id,
                        "itemName": item.get("itemName"),
                        "orders": 0,
                        "qty": 0,
                        "commission": 0.0,
                        "lastPurchaseTime": 0,
                    })
                    entry["orders"] += 1
                    entry["qty"] += qty
                    entry["commission"] += item_commission
                    entry["lastPurchaseTime"] = max(entry["lastPurchaseTime"], int(node.get("purchaseTime") or 0))

        page_info = report.get("pageInfo") or {}
        if not page_info.get("hasNextPage") or not page_info.get("scrollId"):
            break
        scroll_id = page_info["scrollId"]
        page += 1
        time.sleep(0.4)

    # junta com o catálogo pra ter nicho/imagem/nome atualizado
    products = []
    for item_id, entry in per_product.items():
        cat = catalog_idx.get(item_id, {})
        products.append({
            **entry,
            "niche": cat.get("niche"),
            "imageUrl": cat.get("imageUrl"),
            "productName": cat.get("productName") or entry["itemName"],
        })
    products.sort(key=lambda p: p["commission"], reverse=True)

    out = {
        "generated_at": now,
        "period_days": args.days,
        "totals": totals,
        "products": products,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n{totals['conversions']} conversões, {totals['orders']} pedidos, "
          f"{len(products)} produtos distintos, R$ {totals['commission']:.2f} de comissão total")
    print(f"Salvo em: {OUT_PATH}")


if __name__ == "__main__":
    main()
