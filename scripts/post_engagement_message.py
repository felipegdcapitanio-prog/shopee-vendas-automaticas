"""Interação: manda uma mensagem de texto (sem produto) no grupo do
Telegram, com um tom diferente pra cada dia da semana -- pra o grupo não
parecer só um robô cuspindo produto atrás de produto. Roda uma vez por
dia (pensado pra rodar de manhã, horário de Brasília).

Aos sábados, além da saudação, também posta um mini-lote com os produtos
de MAIOR desconto do catálogo agora, com uma legenda especial de sábado
("SABADÃO") -- puxa os melhores achados do dia, fora do rodízio normal.

Uso:
    python scripts/post_engagement_message.py
    python scripts/post_engagement_message.py --dry-run
"""

import argparse
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, __import__("os").path.dirname(__file__))
from post_to_telegram import (  # noqa: E402
    load_env, load_posted_map, save_posted_map, send_photo,
    ENV_PATH, CATALOG_PATH, LOG_PATH, POSTED_PATH, DELAY_BETWEEN_POSTS, br_now,
)
from caption_builder import build_caption  # noqa: E402
import json
import os

SABADAO_TOP_N = 5

# índice = weekday() do Python: 0 segunda ... 6 domingo
WEEKDAY_GREETINGS = {
    0: [
        "🌅 Bom dia! Semana nova começando e o catálogo tá cheio de achadinho novo pra garimpar por aqui 💕",
        "Segundou! Bora começar a semana economizando? Fica de olho nos próximos posts 👀",
    ],
    1: [
        "Terça é dia de continuar de olho nas ofertas 👗 Não esquece de dar uma olhada nos últimos posts do grupo!",
    ],
    2: [
        "Já é metade da semana! 🙌 Um bom achadinho no meio da semana sempre anima, olha os posts de hoje.",
    ],
    3: [
        "Quinta chegando perto do fim de semana... aproveita pra já garantir aquele produto que você tá de olho 😉",
    ],
    4: [
        "SEXTOUUU! 🎉 Fim de semana chegando, e com ele, ofertas boas pra aproveitar com calma. Bora?",
    ],
    5: [
        "SABADÃOOOU! 🎉🔥 Hoje é dia das melhores ofertas — separei um combo especial só de hoje, olha só 👇",
        "Bom dia, sabadão chegou! ☀️ Hoje o grupo vem com uma leva de ofertas boas demais, fica ligada nos próximos posts 💕",
    ],
    6: [
        "Domingo é dia de descanso... mas as ofertas não descansam 😅 Dá uma olhadinha no que separei hoje.",
    ],
}


def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not args.dry_run and (not token or not chat_id):
        print("ERRO: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não encontrados")
        return

    weekday = br_now().weekday()
    greeting = random.choice(WEEKDAY_GREETINGS[weekday])
    print(f"[dia {weekday}] {greeting}")

    if args.dry_run:
        print("(dry-run, não enviado)")
    else:
        result = send_message(token, chat_id, greeting)
        print("  -> enviado" if result.get("ok") else f"  -> falhou: {result}")

    if weekday != 5:
        return  # só sábado tem o mini-lote especial

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)["products"]

    top = sorted(catalog, key=lambda p: -p["discountRate"])[:SABADAO_TOP_N]
    posted_map = load_posted_map()
    now = time.time()
    newly_posted = {}
    log_entries = []

    for i, p in enumerate(top, 1):
        caption = build_caption(p, style="telegram", theme="sabadao")
        print(f"\n[sabadão {i}/{len(top)}] {p['productName'][:60]}")
        if args.dry_run:
            continue
        try:
            result = send_photo(token, chat_id, p["imageUrl"], caption)
            ok = result.get("ok", False)
            print(f"  -> {'enviado' if ok else 'falhou: ' + str(result)}")
            log_entries.append({"itemId": p["itemId"], "ok": ok, "ts": int(time.time()), "special": "sabadao"})
            if ok:
                newly_posted[p["itemId"]] = int(time.time())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"  -> erro HTTP {e.code}: {body}")
            log_entries.append({"itemId": p["itemId"], "ok": False, "error": body, "ts": int(time.time())})
        except urllib.error.URLError as e:
            print(f"  -> erro: {e}")
            log_entries.append({"itemId": p["itemId"], "ok": False, "error": str(e), "ts": int(time.time())})
        time.sleep(DELAY_BETWEEN_POSTS)

    if log_entries and not args.dry_run:
        existing = []
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.extend(log_entries)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    if newly_posted and not args.dry_run:
        posted_map.update(newly_posted)
        save_posted_map(posted_map)
        print(f"\n{len(newly_posted)} produto(s) do especial de sábado marcado(s) como postado(s)")


if __name__ == "__main__":
    main()
