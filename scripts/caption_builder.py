"""Monta legendas variadas e mais humanas para os posts de produto.

Em vez de um template fixo repetido em todo post, sorteia entre várias
aberturas (por nicho, falando direto com a leitora), formas de mostrar
o preço e frases de fechamento — pra dois posts seguidos não parecerem
copiados um do outro. Funciona sem chamada de IA (roda sozinho, de
graça, dentro do agendador).

style="telegram" usa HTML (<b>, <s>, <i>); style="whatsapp" usa o
markdown do WhatsApp (*bold*, ~riscado~, _itálico_).
"""

import random

NICHE_EMOJI = {
    "Beleza & Skincare": "🧴",
    "Maquiagem": "💄",
    "Moda Feminina": "👗",
    "Calçados": "👟",
    "Decoração de Casa": "🏠",
    "Ferramentas": "🛠️",
    "Iluminação": "💡",
}

NICHE_OPENERS = {
    "Beleza & Skincare": [
        "Sua pele merece esse tipo de carinho 💕",
        "Rotina de skincare boa não precisa custar caro, olha só:",
        "Se cuidar também é sobre economizar sem abrir mão de qualidade.",
        "Um mimo pra pele que cabe no bolso:",
        "Separei esse aqui pensando em quem ama uma pele bem cuidada:",
        "Não custa nada testar, o preço tá um convite:",
    ],
    "Maquiagem": [
        "Pra arrasar no make sem gastar uma fortuna:",
        "Aquele produtinho que não pode faltar na nécessaire:",
        "Bora dar um upgrade na make de hoje?",
        "Se você é apaixonada por make, guarda esse:",
        "Achado certeiro pra quem ama testar coisa nova:",
        "Combina com qualquer produção, e o preço ajuda:",
    ],
    "Moda Feminina": [
        "Pra renovar o guarda-roupa sem culpa no cartão:",
        "Aquela peça que combina com tudo:",
        "Look novo com preço de amiga:",
        "Se você ama uma peça coringa, olha essa:",
        "Trocar de visual não precisa pesar no bolso:",
        "Separei essa pensando em quem gosta de estar sempre na moda:",
    ],
    "Calçados": [
        "Conforto e estilo juntos, sem pesar no bolso:",
        "Pra quem vive em pé o dia todo, esse aqui ajuda:",
        "Sapato bom é sinônimo de dia mais leve:",
        "Achado pra completar o look com conforto:",
        "Aquele calçado que dá pra usar com tudo:",
    ],
    "Decoração de Casa": [
        "Pra deixar sua casa com a sua cara:",
        "Detalhezinho que muda o clima do ambiente:",
        "Casa arrumada, mente mais leve — começa por aqui:",
        "Se você ama enfeitar os cantinhos de casa, olha isso:",
        "Um toque a mais no cantinho que você mais gosta:",
    ],
    "Ferramentas": [
        "Praticidade pra resolver aquele probleminha em casa:",
        "Ferramenta boa facilita muito o dia a dia:",
        "Pra deixar tudo mais fácil aí na sua casa:",
        "Aquele item que você vai usar toda semana:",
    ],
    "Iluminação": [
        "Uma luz certa muda todo o clima do ambiente:",
        "Pra deixar seu cantinho mais aconchegante:",
        "Detalhe pequeno, diferença grande no ambiente:",
        "Ilumina o cantinho e ainda cabe no bolso:",
    ],
}

DEFAULT_OPENERS = [
    "Separei esse achadinho pensando em você:",
    "Olha que preço bom pra esse aqui:",
    "Vale a pena dar uma olhada nesse:",
]

HIGH_DISCOUNT_HEADERS = [
    "🔥 OFERTA RELÂMPAGO 🔥",
    "🚨 DESCONTÃO DO DIA 🚨",
    "💥 PREÇO IMPERDÍVEL 💥",
]

SABADAO_HEADERS = [
    "🎉 SABADÃO DE OFERTA 🎉",
    "🔥 ESPECIAL DE SÁBADO 🔥",
    "🛍️ TOP DO SABADÃO 🛍️",
]

NORMAL_HEADER_TEMPLATES = [
    "{e} ACHADINHO DO DIA {e}",
    "{e} VALE A PENA CONFERIR {e}",
    "{e} SEPARADINHO PRA VOCÊ {e}",
]

CLOSING_LINES = [
    "Corre que costuma esgotar rápido!",
    "Esse tipo de oferta não dura muito, viu?",
    "Depois não diz que não avisei 👀",
    "Enquanto durar o estoque, vale a pena garantir.",
    "Se ficar na dúvida, o preço pode voltar ao normal amanhã.",
]


def _fmt_price(v):
    try:
        return f"{float(v):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(v)


def build_caption(p, style="telegram", theme=None):
    b, i, s = ("<b>", "<i>", "<s>") if style == "telegram" else ("*", "_", "~")
    b_, i_, s_ = ("</b>", "</i>", "</s>") if style == "telegram" else ("*", "_", "~")

    niche = p["niche"]
    emoji = NICHE_EMOJI.get(niche, "🛍️")
    price_min = float(p["priceMin"])
    discount = p["discountRate"]
    original = price_min / (1 - discount / 100) if discount > 0 else None

    opener = random.choice(NICHE_OPENERS.get(niche, DEFAULT_OPENERS))

    if theme == "sabadao":
        header = random.choice(SABADAO_HEADERS)
    elif discount >= 50:
        header = random.choice(HIGH_DISCOUNT_HEADERS)
    else:
        header = random.choice(NORMAL_HEADER_TEMPLATES).format(e=emoji)

    price_phrasings = []
    if original:
        price_phrasings = [
            f"De {s}R$ {_fmt_price(original)}{s_} por {b}R$ {_fmt_price(price_min)}{b_}",
            f"Tava R$ {_fmt_price(original)}, agora só {b}R$ {_fmt_price(price_min)}{b_}",
            f"{b}R$ {_fmt_price(price_min)}{b_} {i}(de R$ {_fmt_price(original)}){i_}",
        ]
    else:
        price_phrasings = [f"{b}R$ {_fmt_price(price_min)}{b_}"]
    price_line = random.choice(price_phrasings)

    closing = random.choice(CLOSING_LINES)

    lines = [
        opener,
        "",
        header,
    ]
    if discount > 0:
        lines.append(f"📉 {b}-{discount}% OFF{b_}")
    lines.append("")
    lines.append(f"{b}{p['productName'].strip()}{b_}")
    lines.append("")
    lines.append(price_line)
    lines.append("")
    lines.append(f"⭐ {p['ratingStar']}  ·  🛍️ {p['sales']} vendidos  ·  {emoji} {niche}")
    lines.append("")
    lines.append(f"👉 {b}Garanta o seu aqui:{b_}\n{p['offerLink']}")
    lines.append("")
    lines.append(f"{i}{closing}{i_}")
    return "\n".join(lines)
