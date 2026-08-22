"""Verifica se o robô do Telegram está postando no ritmo esperado. Roda a
cada 2h. Se a última postagem for antiga demais, marca "alerta" no status
(pro painel mostrar) e manda uma mensagem direto pro admin no Telegram
(se TELEGRAM_ADMIN_CHAT_ID estiver configurado).

Uso:
    python scripts/check_telegram_health.py
"""

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
LOG_PATH = os.path.join(ROOT, "data", "log_postagens.json")
STATUS_PATH = os.path.join(ROOT, "data", "telegram_status.json")

# o disparo externo (cron-job.org) roda a cada 10 min -- se passar bem mais
# que isso sem post nenhum, algo travou
ALERT_THRESHOLD_MINUTES = 45


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


def send_alert(token, admin_chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": admin_chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    env = load_env(ENV_PATH)
    token = env.get("TELEGRAM_BOT_TOKEN")
    admin_chat_id = env.get("TELEGRAM_ADMIN_CHAT_ID")

    now = time.time()

    if not os.path.exists(LOG_PATH):
        last_ok_ts = 0
    else:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            log = json.load(f)
        ok_entries = [e for e in log if e.get("ok")]
        last_ok_ts = max((e.get("ts", 0) for e in ok_entries), default=0)

    minutes_since = (now - last_ok_ts) / 60 if last_ok_ts else None
    healthy = minutes_since is not None and minutes_since <= ALERT_THRESHOLD_MINUTES

    status = {
        "checked_at": int(now),
        "last_post_ts": int(last_ok_ts),
        "minutes_since_last_post": round(minutes_since, 1) if minutes_since is not None else None,
        "status": "ok" if healthy else "alerta",
        "threshold_minutes": ALERT_THRESHOLD_MINUTES,
    }

    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(json.dumps(status, ensure_ascii=False, indent=2))

    if not healthy and token and admin_chat_id:
        if last_ok_ts:
            msg = (
                f"⚠️ Robô do Telegram parado há {minutes_since:.0f} min "
                f"(última postagem confirmada). Verificar o GitHub Actions "
                f"e o cron-job.org."
            )
        else:
            msg = "⚠️ Robô do Telegram nunca postou nada ainda (ou log não encontrado). Verificar configuração."
        try:
            send_alert(token, admin_chat_id, msg)
            print("Alerta enviado pro admin.")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            print(f"Falha ao enviar alerta: {e}")
    elif not healthy:
        print("Status de alerta, mas TELEGRAM_ADMIN_CHAT_ID não configurado -- sem envio de mensagem.")


if __name__ == "__main__":
    main()
