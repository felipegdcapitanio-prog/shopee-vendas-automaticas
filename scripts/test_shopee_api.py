"""Teste rápido de conexão com a Shopee Affiliate Open API (GraphQL).

Lê as credenciais do .env na raiz do projeto e faz uma busca simples
de produtos, só para confirmar que App ID + Secret estão válidos.

Uso:
    python scripts/test_shopee_api.py
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def load_env(path):
    values = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def build_signature(app_id, secret, timestamp, payload):
    raw = f"{app_id}{timestamp}{payload}{secret}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main():
    env = load_env(ENV_PATH)
    app_id = env.get("SHOPEE_AFFILIATE_APP_ID")
    secret = env.get("SHOPEE_AFFILIATE_SECRET")

    if not app_id or not secret:
        print("ERRO: SHOPEE_AFFILIATE_APP_ID ou SHOPEE_AFFILIATE_SECRET não encontrados no .env")
        return

    query = {
        "query": (
            "query{productOfferV2(keyword:\"batom\",limit:3){nodes{"
            "itemId productName priceMin priceMax commissionRate "
            "sales ratingStar imageUrl offerLink}}}"
        )
    }
    payload = json.dumps(query, separators=(",", ":"))
    timestamp = str(int(time.time()))
    signature = build_signature(app_id, secret, timestamp, payload)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={signature}",
    }

    req = urllib.request.Request(ENDPOINT, data=payload.encode("utf-8"), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            print(f"HTTP {resp.status}")
            print(json.dumps(json.loads(body), indent=2, ensure_ascii=False))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}")
        print(e.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"Falha de conexão: {e.reason}")


if __name__ == "__main__":
    main()
