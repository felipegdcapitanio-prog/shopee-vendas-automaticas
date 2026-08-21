"""Publicador: posta os produtos do catálogo no grupo/canal do Telegram,
um por vez, com imagem + legenda + link de afiliado.

Prioriza sempre produto nunca postado; quando esses acabam, passa a
reciclar os já postados há mais tempo (respeitando um cooldown mínimo em
dias), sempre desempatando por maior desconto. Isso permite rodar isto
com alta frequência (ex: a cada 30 min, 48x/dia) sem esgotar o catálogo.

Uso:
    python scripts/post_to_telegram.py                  # posta 1 produto (padrão, pensado pra rodar de 30 em 30 min)
    python scripts/post_to_telegram.py --dry-run         # só mostra o que seria postado
    python scripts/post_to_telegram.py --niche "Maquiagem"
    python scripts/post_to_telegram.py --limit 10
    python scripts/post_to_telegram.py --cooldown-days 3 # muda o mínimo de dias antes de repetir um produto
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
DEFAULT_LIMIT = 1  # 1 por execução, pensado pra rodar a cada 30 min (48/dia)
DEFAULT_COOLDOWN_DAYS = 5  # dias mínimos antes de repetir um produto


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


def load_posted_map():
    """itemId -> timestamp da última vez que foi postado (0 = nunca)."""
    if not os.path.exists(POSTED_PATH):
        return {}
    with open(POSTED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):  # formato antigo (lista simples): migra tratando como "postado agora"
        now = int(time.time())
        return {item_id: now for item_id in data}
    return {int(k): v for k, v in data.items()}


def save_posted_map(posted_map):
    os.makedirs(os.path.dirname(POSTED_PATH), exist_ok=True)
    with open(POSTED_PATH, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in posted_map.items()}, f, ensure_ascii=False, indent=2)


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
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"quantidade máxima de posts (padrão {DEFAULT_LIMIT})")
    parser.add_argument("--cooldown-days", type=float, default=DEFAULT_COOLDOWN_DAYS, help=f"dias mínimos antes de repetir um produto (padrão {DEFAULT_COOLDOWN_DAYS})")
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

    posted_map = load_posted_map()
    cooldown_seconds = args.cooldown_days * 86400
    now = time.time()

    eligible = [
        p for p in catalog
        if (now - posted_map.get(p["itemId"], 0)) >= cooldown_seconds
    ]

    # nunca-postado primeiro (last_posted=0), depois o postado há mais tempo;
    # desempate por maior desconto (gatilho de atração de lead)
    eligible.sort(key=lambda p: (posted_map.get(p["itemId"], 0), -p["discountRate"]))

    if args.limit:
        eligible = eligible[: args.limit]

    if not eligible:
        print(f"Nada elegível pra postar agora (tudo em cooldown de {args.cooldown_days} dias). Rode find_products.py pra renovar o catálogo.")
        return

    catalog = eligible
    log = []
    newly_posted = {}
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
                newly_posted[p["itemId"]] = int(time.time())
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
        posted_map.update(newly_posted)
        save_posted_map(posted_map)
        print(f"{len(newly_posted)} produto(s) marcado(s) como postado(s) em {POSTED_PATH}")


if __name__ == "__main__":
    main()
