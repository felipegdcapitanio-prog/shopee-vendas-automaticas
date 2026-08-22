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
from sales_data import load_sales_map, effective_cooldown_days

ROOT = os.path.join(os.path.dirname(__file__), "..")
CATALOG_PATH = os.path.join(ROOT, "data", "catalogo_produtos.json")
WHATSAPP_POSTED_PATH = os.path.join(ROOT, "data", "whatsapp_posted_ids.json")
OUT_DIR = os.path.join(ROOT, "data", "whatsapp_digests")

DEFAULT_COUNT = 20
DEFAULT_COOLDOWN_DAYS = 3  # menos se o produto estiver vendendo bem, ver sales_data.py

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
    sales_map = load_sales_map()

    def sort_key(p):
        return (posted_map.get(p["itemId"], 0), -p["discountRate"])

    eligible = [
        p for p in catalog
        if (now - posted_map.get(p["itemId"], 0)) >= effective_cooldown_days(p["itemId"], args.cooldown_days, sales_map) * 86400
    ]
    eligible.sort(key=sort_key)
    selected = eligible[: args.count]

    if len(selected) < args.count:
        chosen_ids = {p["itemId"] for p in selected}
        rest = sorted((p for p in catalog if p["itemId"] not in chosen_ids), key=sort_key)
        selected.extend(rest[: args.count - len(selected)])

    if not selected:
        print("Catálogo vazio -- rode find_products.py pra popular data/catalogo_produtos.json.")
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
        offer_link_escaped = html.escape(p["offerLink"])
        cards.append(f"""
    <article class="card" data-index="{i}" data-item-id="{p['itemId']}" data-image-url="{html.escape(p['imageUrl'])}">
      <a class="media" href="{offer_link_escaped}" target="_blank" rel="noopener" title="Abrir o produto na Shopee"><img src="{p['imageUrl']}" alt="" loading="lazy"><span class="posted-badge">✓ Postado</span></a>
      <div class="body">
        <span class="tag">{niche_escaped} &middot; {i}/{len(products)}</span>
        <pre class="caption">{caption_escaped}</pre>
        <div class="actions">
          <button class="copy-img-btn">🖼️ Copiar imagem</button>
          <button class="copy-btn">Copiar legenda</button>
          <a class="img-link" href="{p['imageUrl']}" target="_blank" rel="noopener">Baixar imagem</a>
          <button class="undo-btn" title="Marcar como não postado de novo">desfazer</button>
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
  p.sub{{ color:var(--ink-soft); font-size:13.5px; margin:0 0 16px; }}
  .progress{{ display:flex; align-items:center; gap:12px; margin:0 0 24px; max-width:1100px; }}
  .progress-bar{{ flex:1; height:8px; background:var(--line); border-radius:99px; overflow:hidden; }}
  .progress-fill{{ height:100%; width:0%; background:var(--ok); border-radius:99px; transition:width .3s ease; }}
  .progress-label{{ font-size:13px; font-weight:700; color:var(--ink-soft); white-space:nowrap; font-variant-numeric:tabular-nums; }}
  .grid{{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:18px; max-width:1100px; }}
  .card{{ background:#fff; border:1px solid var(--line); border-radius:14px; overflow:hidden; display:flex; flex-direction:column; }}
  .card.done{{ opacity:.5; }}
  .media{{ display:block; position:relative; aspect-ratio:1/1; background:#f2eae8; cursor:pointer; }}
  .media img{{ width:100%; height:100%; object-fit:cover; display:block; }}
  .posted-badge{{ display:none; position:absolute; top:10px; left:10px; background:var(--ok); color:#fff; font-size:11.5px; font-weight:700; padding:4px 10px; border-radius:99px; }}
  .card.done .posted-badge{{ display:inline-block; }}
  .body{{ padding:14px 16px 16px; display:flex; flex-direction:column; gap:10px; }}
  .tag{{ font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; color:var(--accent-strong); }}
  .caption{{ font-family:inherit; font-size:12.5px; white-space:pre-wrap; background:var(--paper); border:1px solid var(--line); border-radius:8px; padding:10px; margin:0; max-height:220px; overflow-y:auto; }}
  .actions{{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
  .copy-btn, .copy-img-btn{{ font-family:inherit; font-size:13px; font-weight:700; padding:9px 14px; border-radius:8px; border:none; cursor:pointer; }}
  .copy-btn{{ background:var(--accent); color:#fff; }}
  .copy-img-btn{{ background:var(--accent-soft); color:var(--accent-strong); }}
  .copy-btn.copied, .copy-img-btn.copied{{ background:var(--ok); color:#fff; }}
  .img-link{{ font-size:12.5px; color:var(--accent-strong); }}
  .undo-btn{{ display:none; font-family:inherit; font-size:12px; padding:6px 10px; border-radius:8px; border:1px solid var(--line); background:none; color:var(--ink-soft); cursor:pointer; }}
  .card.done .undo-btn{{ display:inline-block; }}
</style></head>
<body>
  <h1>Fila de postagem — WhatsApp</h1>
  <p class="sub">{len(products)} produtos. 1) Clica em "🖼️ Copiar imagem" — 2) cola direto no WhatsApp (Ctrl+V) — 3) clica em "Copiar legenda" e cola embaixo. Sem precisar baixar nem salvar nada na mão. A foto de cada card também é clicável e abre o produto na Shopee, pra conferir antes de postar. O card marca "✓ Postado" sozinho depois que você copiar — e continua marcado mesmo se a fila for atualizada de novo amanhã, então nunca fica em dúvida do que já foi postado.</p>
  <div class="progress">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <span class="progress-label" id="progressLabel">0 de {len(products)} já postados</span>
  </div>
  <div class="grid">{"".join(cards)}</div>
<script>
var STORAGE_KEY = 'achadinhos_wpp_postados';

function loadPosted(){{
  try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {{}}; }}
  catch(e) {{ return {{}}; }}
}}
function savePosted(map){{
  try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(map)); }} catch(e) {{}}
}}
function updateProgress(){{
  var total = document.querySelectorAll('.card').length;
  var done = document.querySelectorAll('.card.done').length;
  document.getElementById('progressLabel').textContent = done + ' de ' + total + ' já postados';
  document.getElementById('progressFill').style.width = (total ? (done/total*100) : 0) + '%';
}}

var posted = loadPosted();
document.querySelectorAll('.card').forEach(function(card){{
  var id = card.getAttribute('data-item-id');
  if (posted[id]) {{
    card.classList.add('done');
    card.querySelector('.copy-btn').textContent = 'Copiar de novo';
  }}
}});
updateProgress();

async function fetchAsPngBlob(url){{
  var resp = await fetch(url, {{ mode: 'cors' }});
  var blob = await resp.blob();
  var bitmap = await createImageBitmap(blob);
  var canvas = document.createElement('canvas');
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  canvas.getContext('2d').drawImage(bitmap, 0, 0);
  return new Promise(function(resolve){{ canvas.toBlob(resolve, 'image/png'); }});
}}

document.querySelectorAll('.copy-img-btn').forEach(function(btn){{
  btn.addEventListener('click', async function(){{
    var card = btn.closest('.card');
    var url = card.getAttribute('data-image-url');
    var original = btn.textContent;
    try{{
      var pngBlob = await fetchAsPngBlob(url);
      await navigator.clipboard.write([new ClipboardItem({{ 'image/png': pngBlob }})]);
      btn.textContent = 'Imagem copiada!';
      btn.classList.add('copied');
      setTimeout(function(){{ btn.textContent = original; btn.classList.remove('copied'); }}, 2000);
    }} catch(e){{
      btn.textContent = 'Não deu, abrindo...';
      window.open(url, '_blank');
      setTimeout(function(){{ btn.textContent = original; }}, 2500);
    }}
  }});
}});

document.querySelectorAll('.copy-btn').forEach(function(btn){{
  btn.addEventListener('click', function(){{
    var card = btn.closest('.card');
    var id = card.getAttribute('data-item-id');
    var text = card.querySelector('.caption').textContent;
    navigator.clipboard.writeText(text).then(function(){{
      var original = card.classList.contains('done') ? 'Copiar de novo' : 'Copiar legenda';
      btn.textContent = 'Copiado!';
      btn.classList.add('copied');
      card.classList.add('done');
      posted[id] = Date.now();
      savePosted(posted);
      updateProgress();
      setTimeout(function(){{ btn.textContent = 'Copiar de novo'; btn.classList.remove('copied'); }}, 2000);
    }});
  }});
}});

document.querySelectorAll('.undo-btn').forEach(function(btn){{
  btn.addEventListener('click', function(){{
    var card = btn.closest('.card');
    var id = card.getAttribute('data-item-id');
    delete posted[id];
    savePosted(posted);
    card.classList.remove('done');
    card.querySelector('.copy-btn').textContent = 'Copiar legenda';
    updateProgress();
  }});
}});
</script>
</body></html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page_html)


if __name__ == "__main__":
    main()
