"""Gera um lote de conteúdo pronto pra postar manualmente no WhatsApp
(grupo ou canal). Como não existe automação oficial gratuita pro
WhatsApp, aqui a pessoa mesmo copia a legenda e salva/anexa a imagem
pelo link, no ritmo que der ao longo do dia.

Formatação usa o markdown do WhatsApp (*negrito*, _itálico_, ~riscado~),
diferente do HTML usado no Telegram.

Uso:
    python scripts/generate_whatsapp_digest.py                # top 20 por desconto, sem repetir do dia anterior
    python scripts/generate_whatsapp_digest.py --count 10
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.join(os.path.dirname(__file__), "..")
CATALOG_PATH = os.path.join(ROOT, "data", "catalogo_produtos.json")
WHATSAPP_POSTED_PATH = os.path.join(ROOT, "data", "whatsapp_posted_ids.json")
OUT_DIR = os.path.join(ROOT, "data", "whatsapp_digests")

DEFAULT_COUNT = 20
DEFAULT_COOLDOWN_DAYS = 5

NICHE_EMOJI = {
    "Beleza & Skincare": "🧴",
    "Maquiagem": "💄",
    "Moda Feminina": "👗",
    "Calçados": "👟",
    "Decoração de Casa": "🏠",
    "Ferramentas": "🛠️",
    "Iluminação": "💡",
}


def fmt_price(v):
    try:
        return f"{float(v):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(v)


def load_posted_map():
    if not os.path.exists(WHATSAPP_POSTED_PATH):
        return {}
    with open(WHATSAPP_POSTED_PATH, "r", encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}


def save_posted_map(m):
    os.makedirs(os.path.dirname(WHATSAPP_POSTED_PATH), exist_ok=True)
    with open(WHATSAPP_POSTED_PATH, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in m.items()}, f, ensure_ascii=False, indent=2)


def build_caption_whatsapp(p):
    price_min = float(p["priceMin"])
    discount = p["discountRate"]
    original = price_min / (1 - discount / 100) if discount > 0 else None
    niche_emoji = NICHE_EMOJI.get(p["niche"], "🛍️")

    lines = []
    if discount >= 50:
        lines.append("🔥 *OFERTA RELÂMPAGO* 🔥")
    else:
        lines.append(f"{niche_emoji} *ACHADINHO DO DIA* {niche_emoji}")
    if discount > 0:
        lines.append(f"📉 *-{discount}% OFF*")
    lines.append("")
    lines.append(f"*{p['productName'].strip()}*")
    lines.append("")
    if original:
        lines.append(f"💸 De: ~R$ {fmt_price(original)}~")
        lines.append(f"✅ Por: *R$ {fmt_price(price_min)}*")
    else:
        lines.append(f"✅ *R$ {fmt_price(price_min)}*")
    lines.append("")
    lines.append(f"⭐ {p['ratingStar']}  ·  🛍️ {p['sales']} vendidos  ·  {niche_emoji} {p['niche']}")
    lines.append("")
    lines.append(f"👉 *Garanta o seu aqui:*\n{p['offerLink']}")
    lines.append("")
    lines.append("⏳ _Oferta por tempo limitado, pode acabar a qualquer momento._")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--cooldown-days", type=float, default=DEFAULT_COOLDOWN_DAYS)
    args = parser.parse_args()

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)["products"]

    posted_map = load_posted_map()
    now = time.time()
    cooldown_seconds = args.cooldown_days * 86400

    eligible = [p for p in catalog if (now - posted_map.get(p["itemId"], 0)) >= cooldown_seconds]
    eligible.sort(key=lambda p: (posted_map.get(p["itemId"], 0), -p["discountRate"]))
    selected = eligible[: args.count]

    if not selected:
        print("Nada elegível (tudo em cooldown). Rode find_products.py pra renovar o catálogo.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(OUT_DIR, f"whatsapp_{today}.txt")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"LOTE DE POSTS PRO WHATSAPP — {today}\n")
        f.write(f"{len(selected)} produtos prontos. Copie a legenda de cada bloco, salve a imagem do link e poste.\n")
        f.write("=" * 60 + "\n\n")
        for i, p in enumerate(selected, 1):
            f.write(f"--- PRODUTO {i}/{len(selected)} ---\n")
            f.write(f"Imagem: {p['imageUrl']}\n\n")
            f.write(build_caption_whatsapp(p))
            f.write("\n\n")

    posted_map.update({p["itemId"]: int(now) for p in selected})
    save_posted_map(posted_map)

    print(f"{len(selected)} produtos gerados em: {out_path}")


if __name__ == "__main__":
    main()
