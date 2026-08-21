"""Publicador: posta os produtos do catálogo no grupo/canal do Telegram,
um por vez, com imagem + legenda + link de afiliado.

Por padrão só posta produtos que ainda não foram postados (controle em
data/posted_ids.json), priorizando maior desconto, até --limit por execução.
Isso é o que permite rodar isto todo dia (local ou via GitHub Actions) sem
repetir produto.

Uso:
    python scripts/post_to_telegram.py                 # posta até 5 produtos novos (padrão)
    python scripts/post_to_telegram.py --dry-run        # só mostra o que seria postado
    python scripts/post_to_telegram.py --niche "Maquiagem"
    python scripts/post_to_telegram.py --limit 10
    python scripts/post_to_telegram.py --ignore-posted  # ignora o controle e considera o catálogo todo
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.join(os.path.dirname(__file__), "..")
ENV_PATH = os.path.join(ROOT, ".env")
CATALOG_PATH = os.path.join(ROOT, "data", "catalogo_produtos.json")
LOG_PATH = os.path.join(ROOT, "data", "log_postagens.json")
POSTED_PATH = os.path.join(ROOT, "data", "posted_ids.json")

DELAY_BETWEEN_POSTS = 3  # segundos, evita rate limit do Telegram
DEFAULT_DAILY_LIMIT = 5


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


def load_posted_ids():
    if not os.path.exists(POSTED_PATH):
        return set()
    with open(POSTED_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_posted_ids(ids):
    os.makedirs(os.path.dirname(POSTED_PATH), exist_ok=True)
    with open(POSTED_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=2)


def fmt_price(v):
    try:
        return f"{float(v):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(v)


NICHE_EMOJI = {
    "Beleza & Skincare": "🧴",
    "Maquiagem": "💄",
    "Moda Feminina": "👗",
    "Calçados": "👟",
    "Decoração de Casa": "🏠",
    "Ferramentas": "🛠️",
    "Iluminação": "💡",
}


def build_caption(p):
    price_min = float(p["priceMin"])
    discount = p["discountRate"]
    original = price_min / (1 - discount / 100) if discount > 0 else None
    niche_emoji = NICHE_EMOJI.get(p["niche"], "🛍️")

    lines = []
    if discount >= 50:
        lines.append("🔥 <b>OFERTA RELÂMPAGO</b> 🔥")
    else:
        lines.append(f"{niche_emoji} <b>ACHADINHO DO DIA</b> {niche_emoji}")
    if discount > 0:
        lines.append(f"📉 <b>-{discount}% OFF</b>")
    lines.append("")
    lines.append(f"<b>{p['productName'].strip()}</b>")
    lines.append("")
    if original:
        lines.append(f"💸 De: <s>R$ {fmt_price(original)}</s>")
        lines.append(f"✅ Por: <b>R$ {fmt_price(price_min)}</b>")
    else:
        lines.append(f"✅ <b>R$ {fmt_price(price_min)}</b>")
    lines.append("")
    lines.append(f"⭐ {p['ratingStar']}  ·  🛍️ {p['sales']} vendidos  ·  {niche_emoji} {p['niche']}")
    lines.append("")
    lines.append(f"👉 <b>Garanta o seu aqui:</b>\n{p['offerLink']}")
    lines.append("")
    lines.append("⏳ <i>Oferta por tempo limitado, pode acabar a qualquer momento.</i>")
    return "\n".join(lines)


def send_photo(token, chat_id, photo_url, caption):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="não posta, só mostra o que seria enviado")
    parser.add_argument("--niche", default=None, help="filtra por nicho exato")
    parser.add_argument("--limit", type=int, default=DEFAULT_DAILY_LIMIT, help=f"quantidade máxima de posts (padrão {DEFAULT_DAILY_LIMIT})")
    parser.add_argument("--ignore-posted", action="store_true", help="ignora o controle de já-postados")
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")

    if not args.dry_run and (not token or not chat_id):
        print("ERRO: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não encontrados (.env local ou variável de ambiente)")
        print("Rode com --dry-run pra testar sem precisar do bot configurado.")
        return

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)["products"]

    if args.niche:
        catalog = [p for p in catalog if p["niche"] == args.niche]

    posted_ids = load_posted_ids()
    if not args.ignore_posted:
        catalog = [p for p in catalog if p["itemId"] not in posted_ids]

    # prioriza maior desconto primeiro (gatilho de atração de lead)
    catalog = sorted(catalog, key=lambda p: p["discountRate"], reverse=True)

    if args.limit:
        catalog = catalog[: args.limit]

    if not catalog:
        print("Nada novo para postar (catálogo esgotado ou já todo postado). Rode find_products.py para renovar.")
        return

    log = []
    newly_posted = set()
    for i, p in enumerate(catalog, 1):
        caption = build_caption(p)
        print(f"\n[{i}/{len(catalog)}] {p['productName'][:60]}")
        print(caption)

        if args.dry_run:
            continue

        try:
            result = send_photo(token, chat_id, p["imageUrl"], caption)
            ok = result.get("ok", False)
            print(f"  -> {'enviado' if ok else 'falhou: ' + str(result)}")
            log.append({"itemId": p["itemId"], "ok": ok, "ts": int(time.time())})
            if ok:
                newly_posted.add(p["itemId"])
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"  -> erro HTTP {e.code}: {body}")
            log.append({"itemId": p["itemId"], "ok": False, "error": body, "ts": int(time.time())})
        except urllib.error.URLError as e:
            print(f"  -> erro: {e}")
            log.append({"itemId": p["itemId"], "ok": False, "error": str(e), "ts": int(time.time())})

        time.sleep(DELAY_BETWEEN_POSTS)

    if log:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        existing = []
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.extend(log)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"\nLog salvo em: {LOG_PATH}")

    if newly_posted and not args.dry_run:
        save_posted_ids(posted_ids | newly_posted)
        print(f"{len(newly_posted)} produto(s) marcado(s) como postado(s) em {POSTED_PATH}")


if __name__ == "__main__":
    main()
