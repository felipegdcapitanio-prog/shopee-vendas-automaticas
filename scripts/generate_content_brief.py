"""Separa os 4 produtos do dia pra virar carrossel com a Sophia (2 peças de
roupa + 2 outros itens: maquiagem, ferramenta ou decoração) e já deixa
pronto o prompt de cada um pra colar no Gemini/Google Flow (Nano Banana
Pro) junto com a foto da Sophia + a foto do produto.

O carrossel final tem 6 imagens: 1) capa padrão, 2-5) os 4 produtos daqui,
6) CTA padrão. Este script só cuida das peças 2-5.

Evita repetir produto usado num carrossel nos últimos 14 dias.

Uso:
    python scripts/generate_content_brief.py
"""

import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.join(os.path.dirname(__file__), "..")
CATALOG_PATH = os.path.join(ROOT, "data", "catalogo_produtos.json")
USED_PATH = os.path.join(ROOT, "data", "content_brief_used.json")
OUT_PATH = os.path.join(ROOT, "data", "content_brief_hoje.json")

COOLDOWN_DAYS = 14
CLOTHING_NICHES = {"Moda Feminina"}
OTHER_NICHES = {"Maquiagem", "Ferramentas", "Decoração de Casa", "Iluminação"}
BEAUTY_NICHES = {"Maquiagem", "Beleza & Skincare"}

CLOTHING_TEMPLATE = """Use a primeira imagem como referência exata do rosto, cabelo, tom de pele e identidade da mulher — mantenha essas características idênticas, sem alterar as feições. Use a segunda imagem como referência exata da peça de roupa "{nome}" (cor, textura, estampa e corte devem ser reproduzidos fielmente).

Gere uma foto de CORPO INTEIRO, DE CORPO INTEIRO, da cabeça até os pés (ambos os pés visíveis dentro do enquadramento, nada cortado), dessa mesma mulher vestindo a roupa da segunda imagem, em uma pose natural e espontânea, sorrindo de forma genuína.

Apenas ela na imagem, nenhuma outra pessoa. Fundo neutro e clean (estúdio ou parede lisa, levemente desfocado), boa iluminação natural ou de estúdio suave. Foto em alta qualidade, fotorrealista, nível editorial de moda, corpo inteiro sem cortar pés ou cabeça, sem erros de anatomia, sem mãos deformadas, sem distorções na roupa, sem texto, sem marca d'água, sem logotipos."""

BEAUTY_TEMPLATE = """Use a primeira imagem como referência exata do rosto, cabelo, tom de pele e identidade da mulher — mantenha essas características idênticas, sem alterar as feições. Use a segunda imagem como referência exata do produto "{nome}" (cor, embalagem e acabamento devem ser reproduzidos fielmente).

Gere uma foto DA CINTURA PRA CIMA (busto, ombros, braços e mãos visíveis por completo, sem cortar o corpo antes da cintura), no gesto de aplicar o produto da segunda imagem — segurando-o com uma mão próximo ao rosto, com o resultado do produto já visível nela. Ela sorrindo de forma natural e genuína, pose espontânea.

Apenas ela na imagem, nenhuma outra pessoa. Fundo neutro e clean, boa iluminação suave que valorize a pele. Foto em alta qualidade, fotorrealista, nível editorial de beleza, enquadramento da cintura para cima sem cortar braços ou mãos, mão e dedos anatomicamente corretos, sem erros de anatomia, sem texto, sem marca d'água, sem logotipos."""

LIFESTYLE_TEMPLATE = """Use a primeira imagem como referência exata do rosto, cabelo, tom de pele e identidade da mulher — mantenha essas características idênticas, sem alterar as feições. Use a segunda imagem como referência exata do produto "{nome}" (cor, formato e acabamento devem ser reproduzidos fielmente).

Gere uma foto de CORPO INTEIRO, da cabeça até os pés (nada cortado), dessa mesma mulher interagindo naturalmente com o produto da segunda imagem — segurando, usando ou exibindo o produto de forma condizente com o que ele é, num ambiente estilizado (casa, estúdio ou cenário combinando com o produto). Ela sorrindo de forma genuína, pose espontânea.

Apenas ela na imagem, nenhuma outra pessoa. Boa iluminação natural ou de estúdio suave. Foto em alta qualidade, fotorrealista, nível editorial de lifestyle, corpo inteiro sem cortar nenhuma parte, mão e dedos anatomicamente corretos segurando o produto, sem erros de anatomia, sem texto, sem marca d'água, sem logotipos."""


def load_used():
    if not os.path.exists(USED_PATH):
        return {}
    with open(USED_PATH, "r", encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}


def save_used(m):
    with open(USED_PATH, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in m.items()}, f, ensure_ascii=False, indent=2)


def score(p):
    return p["discountRate"] * 3 + p["commissionRate"] * 100 + min(p["sales"], 500) / 10


def pick(pool, used, now, n):
    cooldown = COOLDOWN_DAYS * 86400
    eligible = [p for p in pool if (now - used.get(p["itemId"], 0)) >= cooldown]
    eligible.sort(key=lambda p: -score(p))
    if len(eligible) < n:
        chosen_ids = {p["itemId"] for p in eligible}
        rest = sorted((p for p in pool if p["itemId"] not in chosen_ids), key=lambda p: used.get(p["itemId"], 0))
        eligible.extend(rest[: n - len(eligible)])
    return eligible[:n]


def template_for(niche):
    if niche in CLOTHING_NICHES:
        return CLOTHING_TEMPLATE, "roupa"
    if niche in BEAUTY_NICHES:
        return BEAUTY_TEMPLATE, "beleza"
    return LIFESTYLE_TEMPLATE, "lifestyle"


def main():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)["products"]

    clothing_pool = [p for p in catalog if p["niche"] in CLOTHING_NICHES]
    other_pool = [p for p in catalog if p["niche"] in OTHER_NICHES]

    if len(clothing_pool) < 2 or len(other_pool) < 2:
        print("Catálogo não tem produto suficiente nas categorias necessárias ainda.")
        return

    used = load_used()
    now = time.time()

    clothing_pick = pick(clothing_pool, used, now, 2)
    other_pick = pick(other_pool, used, now, 2)
    selected = clothing_pick + other_pick

    briefs = []
    for p in selected:
        template, kind = template_for(p["niche"])
        prompt = template.format(nome=p["productName"].strip())
        briefs.append({
            "itemId": p["itemId"],
            "niche": p["niche"],
            "kind": kind,
            "productName": p["productName"],
            "imageUrl": p["imageUrl"],
            "offerLink": p["offerLink"],
            "priceMin": p["priceMin"],
            "discountRate": p["discountRate"],
            "prompt": prompt,
        })
        used[p["itemId"]] = now
    save_used(used)

    out = {"generated_at": int(now), "products": briefs}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Briefing de hoje ({len(briefs)} produtos) salvo em {OUT_PATH}")
    for b in briefs:
        print(f"  [{b['kind']}] {b['productName'][:60]}")
        print(f"    imagem: {b['imageUrl']}")


if __name__ == "__main__":
    main()
