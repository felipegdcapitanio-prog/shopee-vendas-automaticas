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
import html
import json
import os
import sys
import time
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(__file__))
from caption_builder import build_caption

ROOT = os.path.join(os.path.dirname(__file__), "..")
CATALOG_PATH = os.path.join(ROOT, "data", "catalogo_produtos.json")
WHATSAPP_POSTED_PATH = os.path.join(ROOT, "data", "whatsapp_posted_ids.json")
OUT_DIR = os.path.join(ROOT, "data", "whatsapp_digests")

DEFAULT_COUNT = 20
DEFAULT_COOLDOWN_DAYS = 5

def load_posted_map():
    if not os.path.exists(WHATSAPP_POSTED_PATH):
        return {}
    with open(WHATSAPP_POSTED_PATH, "r", encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}


def save_posted_map(m):
    os.makedirs(os.path.dirname(WHATSAPP_POSTED_PATH), exist_ok=True)
    with open(WHATSAPP_POSTED_PATH, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in m.items()}, f, ensure_ascii=False, indent=2)


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
            f.write(build_caption(p, style="whatsapp"))
            f.write("\n\n")

    posted_map.update({p["itemId"]: int(now) for p in selected})
    save_posted_map(posted_map)

    html_path = os.path.join(OUT_DIR, f"whatsapp_{today}.html")
    write_html_page(selected, html_path, today)

    # copia de nome fixo, sempre sobrescrita -- pra poder abrir com um atalho
    # fixo (area de trabalho) sem precisar achar o arquivo do dia
    stable_path = os.path.join(OUT_DIR, "fila_atual.html")
    write_html_page(selected, stable_path, today)

    print(f"{len(selected)} produtos gerados em: {out_path}")
    print(f"Pagina de postagem (abra no navegador): {html_path}")
    print(f"Atalho fixo (sempre a versao mais recente): {stable_path}")


def write_html_page(products, out_path, date_label):
    cards = []
    for i, p in enumerate(products, 1):
        caption = build_caption(p, style="whatsapp")
        caption_escaped = html.escape(caption)
        niche_escaped = html.escape(p["niche"])
        cards.append(f"""
    <article class="card" data-index="{i}">
      <div class="media"><img src="{p['imageUrl']}" alt="" loading="lazy"></div>
      <div class="body">
        <span class="tag">{niche_escaped} &middot; {i}/{len(products)}</span>
        <pre class="caption">{caption_escaped}</pre>
        <div class="actions">
          <button class="copy-btn">Copiar legenda</button>
          <a class="img-link" href="{p['imageUrl']}" target="_blank" rel="noopener">Abrir imagem</a>
        </div>
      </div>
    </article>""")

    page_html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Fila WhatsApp — {date_label}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root{{ --paper:#FBF6F4; --ink:#2B1E22; --ink-soft:#6B585D; --line:#E9DBDD; --accent:#B23A63; --accent-strong:#8C2A4C; --ok:#3F7D5C; --ok-soft:#DCEEE3; }}
  *{{box-sizing:border-box;}}
  body{{ margin:0; background:var(--paper); color:var(--ink); font-family:system-ui,sans-serif; padding:24px; }}
  h1{{ font-size:20px; margin:0 0 4px; }}
  p.sub{{ color:var(--ink-soft); font-size:13.5px; margin:0 0 24px; }}
  .grid{{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:18px; max-width:1100px; }}
  .card{{ background:#fff; border:1px solid var(--line); border-radius:14px; overflow:hidden; display:flex; flex-direction:column; }}
  .card.done{{ opacity:.45; }}
  .media{{ aspect-ratio:1/1; background:#f2eae8; }}
  .media img{{ width:100%; height:100%; object-fit:cover; display:block; }}
  .body{{ padding:14px 16px 16px; display:flex; flex-direction:column; gap:10px; }}
  .tag{{ font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; color:var(--accent-strong); }}
  .caption{{ font-family:inherit; font-size:12.5px; white-space:pre-wrap; background:var(--paper); border:1px solid var(--line); border-radius:8px; padding:10px; margin:0; max-height:220px; overflow-y:auto; }}
  .actions{{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
  .copy-btn{{ font-family:inherit; font-size:13px; font-weight:700; padding:9px 14px; border-radius:8px; border:none; background:var(--accent); color:#fff; cursor:pointer; }}
  .copy-btn.copied{{ background:var(--ok); }}
  .img-link{{ font-size:12.5px; color:var(--accent-strong); }}
</style></head>
<body>
  <h1>Fila de postagem — WhatsApp</h1>
  <p class="sub">{len(products)} produtos. Clica em "Copiar legenda", cola no WhatsApp junto com a imagem (abre em nova aba pra salvar), manda. O card fica esmaecido depois que você copiar, só de referência visual.</p>
  <div class="grid">{"".join(cards)}</div>
<script>
document.querySelectorAll('.copy-btn').forEach(function(btn){{
  btn.addEventListener('click', function(){{
    var text = btn.closest('.card').querySelector('.caption').textContent;
    navigator.clipboard.writeText(text).then(function(){{
      btn.textContent = 'Copiado!';
      btn.classList.add('copied');
      btn.closest('.card').classList.add('done');
      setTimeout(function(){{ btn.textContent = 'Copiar legenda'; }}, 2000);
    }});
  }});
}});
</script>
</body></html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page_html)


if __name__ == "__main__":
    main()
