"""Módulo compartilhado: sabe quais produtos estão vendendo bem, pra
permitir repetir um produto ANTES do cooldown normal quando ele tiver
histórico de venda real (dado que vem de data/relatorio_vendas.json,
gerado por fetch_sales_report.py).
"""

import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
SALES_REPORT_PATH = os.path.join(ROOT, "data", "relatorio_vendas.json")

# a partir de quantos pedidos um produto é considerado "vendendo bem"
HIGH_PERFORMER_MIN_ORDERS = 2
# cooldown reduzido pra esses produtos (dias)
HIGH_PERFORMER_COOLDOWN_DAYS = 1


def load_sales_map():
    """itemId (str) -> {orders, qty, commission, ...}"""
    if not os.path.exists(SALES_REPORT_PATH):
        return {}
    with open(SALES_REPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(p["itemId"]): p for p in data.get("products", [])}


def effective_cooldown_days(item_id, base_days, sales_map):
    """Se o produto tem venda boa registrada, encurta o cooldown -- ele
    pode voltar a ser postado mais cedo porque está convertendo de verdade."""
    entry = sales_map.get(str(item_id))
    if entry and int(entry.get("orders", 0)) >= HIGH_PERFORMER_MIN_ORDERS:
        return min(base_days, HIGH_PERFORMER_COOLDOWN_DAYS)
    return base_days
