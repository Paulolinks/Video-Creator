"""Build the script-framework PDFs (one per approved template) plus JSON models for the downloads folder.

Each PDF is meant to be attached to ChatGPT so new scripts always come back in the same format.
Run with the lab venv (reportlab). Usage: make_framework_pdfs.py
"""
import json
import re
import shutil
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

LAB = Path(__file__).resolve().parent.parent
DL = LAB / "downloads"
ASSETS = DL / "_assets"
FONTS = LAB / "inputs" / "fonts"

pdfmetrics.registerFont(TTFont("Body", "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("BodyBold", "C:/Windows/Fonts/arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Mono", "C:/Windows/Fonts/consola.ttf"))
pdfmetrics.registerFont(TTFont("Head", str(FONTS / "Poppins-ExtraBold.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyBold", italic="Body", boldItalic="BodyBold")

NAVY, GOLD, INK, MUTED, CODEBG, LINE = (colors.HexColor(c) for c in
                                        ("#14213D", "#E0A800", "#1F2430", "#5B6170", "#F3F4F7", "#D9DCE3"))
S = {
    "h1": ParagraphStyle("h1", fontName="Head", fontSize=21, leading=25, textColor=colors.white),
    "sub": ParagraphStyle("sub", fontName="Body", fontSize=10.5, leading=14, textColor=colors.HexColor("#D6DAE5")),
    "h2": ParagraphStyle("h2", fontName="Head", fontSize=13.5, leading=17, textColor=NAVY, spaceBefore=12, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="BodyBold", fontSize=10.5, leading=14, textColor=INK, spaceBefore=6, spaceAfter=2),
    "p": ParagraphStyle("p", fontName="Body", fontSize=9.6, leading=13.4, textColor=INK, spaceAfter=4),
    "li": ParagraphStyle("li", fontName="Body", fontSize=9.6, leading=13.2, textColor=INK, leftIndent=12,
                         bulletIndent=2, spaceAfter=2),
    "small": ParagraphStyle("small", fontName="Body", fontSize=8, leading=10.5, textColor=MUTED, alignment=TA_CENTER),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.8, leading=10.2, textColor=INK),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8.8, leading=11.6, textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="BodyBold", fontSize=8.8, leading=11.6, textColor=colors.white),
}


def P(text, style="p"):
    return Paragraph(text, S[style])


def bullets(items):
    return [Paragraph(t, S["li"], bulletText="•") for t in items]


def code(text):
    """Monospace block that wraps long lines (keeps leading indentation)."""
    lines = []
    for line in text.strip("\n").split("\n"):
        stripped = line.lstrip(" ")
        lines.append("&nbsp;" * (len(line) - len(stripped)) + escape(stripped))
    t = Table([[Paragraph("<br/>".join(lines), S["code"])]], colWidths=[174 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CODEBG), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def table(rows, widths):
    data = [[Paragraph(c, S["cellh"]) for c in rows[0]]] + [[Paragraph(c, S["cell"]) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CODEBG]),
                           ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def frames(prefix, captions):
    cells = [[Image(str(ASSETS / f"{prefix}_{i}.jpg"), width=44 * mm, height=78 * mm) for i in (1, 2, 3)],
             [Paragraph(c, S["small"]) for c in captions]]
    t = Table(cells, colWidths=[56 * mm] * 3)
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return t


def header(title, subtitle, tag):
    t = Table([[Paragraph(f'<font color="#E0A800" size="9">{tag}</font>', S["sub"])],
               [Paragraph(title, S["h1"])], [Paragraph(subtitle, S["sub"])]], colWidths=[174 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                           ("TOPPADDING", (0, 0), (0, 0), 12), ("BOTTOMPADDING", (0, -1), (-1, -1), 12)]))
    return t


def footer(name):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(1)
        canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
        canvas.setFont("Body", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 9 * mm, f"VIDEO CREATOR · {name}")
        canvas.drawRightString(192 * mm, 9 * mm, f"página {doc.page}")
        canvas.restoreState()
    return draw


def build(path, name, story):
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=name, author="Video Creator", subject="Framework de roteiro")
    doc.build(story, onFirstPage=footer(name), onLaterPages=footer(name))


# --------------------------------------------------------------------------------------------- metadata
# Post metadata block, after FIM, read by the app (parser.metadata). Empty fields are filled by Ollama.
META_MODEL = """METADADOS
TÍTULO DO POST: <título da publicação; pode ser igual ao TÍTULO>
DESCRIÇÃO: <contexto curto + uma pergunta que convide a comentar>
NOTA EDITORIAL: <opcional: aviso que vai no fim da descrição>
HASHTAGS: <5 a 8 hashtags>"""

META_ROWS = [["Campo", "O que o app faz com ele"],
             ["<b>TÍTULO DO POST</b>", "Título da publicação. Se faltar, o app usa o TÍTULO do roteiro (o mesmo da capa)."],
             ["<b>DESCRIÇÃO</b>", "Texto da publicação. Pode ter mais de uma linha."],
             ["<b>NOTA EDITORIAL</b>", "Opcional. Vai no fim da descrição, separada por uma linha em branco. Se não "
              "tiver, apague a linha."],
             ["<b>HASHTAGS</b>", "Sempre a última linha do bloco, tudo numa linha só."]]

META_HOW = ("O que vier preenchido aparece pronto no card do vídeo. O que faltar, o app completa com a IA (Ollama) "
            "quando o vídeo termina. O botão <b>Novo</b> do card refaz a descrição e as hashtags com a IA.")


def meta_section(title):
    return [P(title, "h3"), P("Depois da linha <b>FIM</b>, no mesmo bloco de código, vem o bloco <b>METADADOS</b> "
                              "com os dados da publicação (não são falados no vídeo):"),
            code(META_MODEL), table(META_ROWS, [40, 134]), P(META_HOW)]


# --------------------------------------------------------------------------------------------- animations
# Smart Motion markers (VIDEO_CREATOR_LAB/smart_motion/marcacoes.py reads them; the app strips them before the voice)
ANIM_ROWS = [
    ["Marcação", "O que aparece na tela", "Quando usar", "Exemplo"],
    ["<b>CONTADOR</b><br/>[CONTADOR: valor | texto]", "Um número que sobe do zero até o valor, com um texto curto "
     "embaixo.", "A fala cita um valor importante: dinheiro, porcentagem, quantidade, anos.",
     "[CONTADOR: US$ 100.000 | por mês]"],
    ["<b>BARRAS</b><br/>[BARRAS: título | Nome = valor | Nome = valor]", "2 a 5 barras horizontais; cada uma "
     "cresce quando o seu número é falado.", "A fala compara dois ou mais valores.",
     "[BARRAS: 10% de margem | Vendas = US$ 1.000.000 | Lucro = US$ 100.000]"],
    ["<b>FLUXO</b><br/>[FLUXO: etapa | etapa | etapa]", "2 a 5 blocos numerados ligados por setas; cada etapa "
     "acende quando as palavras dela são faladas.", "Passo a passo, processo, sequência (\"primeiro... depois... "
     "por fim\").", "[FLUXO: Consciência do padrão | Novo padrão | Ações consistentes]"],
    ["<b>CARDS</b><br/>[CARDS: errado: detalhe | certo: detalhe]", "Dois cartões lado a lado: o 1º com um X (o "
     "que não fazer, o antes, o mito), o 2º com sinal de certo (o que fazer, o depois, a verdade). O 2º entra quando o "
     "título dele é falado. Com um só cartão, ele aparece com o sinal de certo.", "Contraste entre duas ideias.",
     "[CARDS: Só pensamento positivo: não substitui estratégia | Visão clara: orienta o trabalho concreto]"],
    ["<b>DESTAQUE</b><br/>[DESTAQUE: PALAVRA | subtítulo]", "Uma palavra grande com sublinhado dourado e um "
     "subtítulo opcional.", "O conceito-chave que o vídeo quer fixar.",
     "[DESTAQUE: PARADIGMA | hábitos + crenças repetidos]"],
]

ANIM_RULES = [
    "A marcação vai <b>dentro do texto falado</b>, na mesma linha, <b>logo antes da frase</b> em que a animação "
    "deve aparecer. Ela não é falada e não aparece na legenda.",
    "A animação começa na palavra seguinte à marcação e fica na tela até o fim daquela frase (no FLUXO, nos CARDS e "
    "nas BARRAS, até a frase do último item).",
    "Escreva o nome do tipo em MAIÚSCULAS, depois dois-pontos, e separe os campos com <b>|</b>. Não use colchetes "
    "dentro da marcação.",
    "Dentro da marcação, valores em <b>dígitos com símbolo</b> (US$ 100.000, 10%, R$ 1,5 milhão). Na fala, o número "
    "continua <b>por extenso</b> (\"cem mil dólares\").",
    "CONTADOR e BARRAS só aparecem se o mesmo número for dito na fala daquela cena. Se não for, o app ignora a "
    "animação e avisa. Nunca invente um número que a fala não diz.",
    "Textos curtos: etapas e títulos de cards com 1 a 4 palavras; detalhe do card com até 6 palavras; destaque com "
    "1 ou 2 palavras.",
    "Nas etapas do FLUXO e nos títulos dos CARDS, use palavras que aparecem na fala: é assim que o app sabe "
    "quando acender cada uma.",
    "Quantidade: nunca duas na mesma frase. No Personagem falando, no máximo 1 por cena; na Entrevista, até 2 por "
    "resposta do mentor (em frases diferentes). Use as animações onde elas ajudam a entender, não em toda cena.",
    "É opcional: um roteiro sem marcações gera o vídeo normal, sem animações.",
    "A posição é automática: no Personagem falando, abaixo da legenda; na Entrevista, entre o nome de quem fala e a "
    "legenda. Por enquanto, só no formato vertical 9:16.",
]


def anim_section(num, quantos, exemplo):
    rows = [ANIM_ROWS[0]] + [[r[0], r[1], r[2], f"<font name='Mono' size='7.4'>{escape(r[3])}</font>"]
                             for r in ANIM_ROWS[1:]]
    return [P(f"{num}. Animações na tela (Smart Motion)", "h2"),
            P("O app pode mostrar animações sincronizadas com a fala: contadores, gráficos de barras, fluxos, cards de "
              "comparação e palavras em destaque. Para pedir uma, escreva uma <b>marcação</b> entre colchetes no "
              f"meio da fala. <b>Quantidade recomendada: {quantos}.</b>"),
            table(rows, [40, 50, 38, 46]), P("Regras", "h3")] + bullets(ANIM_RULES) + [
            KeepTogether([P("Exemplo de cena com marcação", "h3"), code(exemplo)])]


def anim_md(quantos, exemplo):
    linhas = "\n".join(f"| `{r[0].split('<br/>')[1]}` | {r[1]} | {r[2]} | `{r[3]}` |" for r in ANIM_ROWS[1:])
    regras = "\n".join(f"- {re.sub(r'<[^>]+>', '', r)}" for r in ANIM_RULES)
    return f"""## Animações na tela (Smart Motion)

O app pode mostrar animações sincronizadas com a fala. Para pedir uma, escreva uma marcação entre colchetes
dentro da fala, logo antes da frase em que ela deve aparecer. Quantidade recomendada: {quantos}.

| Marcação | O que aparece na tela | Quando usar | Exemplo |
|---|---|---|---|
{linhas}

{regras}

Exemplo de cena com marcação:

```text
{exemplo}
```"""


# --------------------------------------------------------------------------------------------- F01
F01_EXAMPLE = [
    {"id": "CENA_01", "mode": "fala", "image": "inputs/teste_maquiavel/cena1_maquiavel.png",
     "text": "Você acredita que as pessoas mostram quem realmente são? Maquiavel já alertava: [CARDS: Olhos: o "
             "que parece | Mãos: o que a pessoa faz] os homens julgam mais pelos olhos do que pelas mãos.",
     "descricao_imagem": "Maquiavel em seu escritório renascentista, à luz de velas, olhando para a câmera e gesticulando."},
    {"id": "CENA_02", "mode": "dolly", "image": "inputs/teste_maquiavel/cena2_traicao.png",
     "text": "Alguém pode sorrir na sua frente, jurar lealdade e, pelas suas costas, escolher aquilo que lhe oferece "
             "mais vantagens.",
     "descricao_imagem": "Salão renascentista: uma nobre entrega uma carta selada a um homem, enquanto outro observa "
                         "desconfiado ao fundo.",
     "busca": "secret letter candlelight"},
    {"id": "CENA_03", "mode": "fala", "image": "inputs/teste_maquiavel/cena3_maquiavel.png",
     "text": "Por isso, não julgue alguém pelo que promete. Observe o que faz quando seus interesses estão em jogo. [DESTAQUE: CARÁTER | "
             "aparece nas ações] É aí que o caráter se revela.",
     "descricao_imagem": "Maquiavel sentado à mesa com livros e mapas, inclinado para a câmera, em tom de conselho."},
]

F01_EXAMPLE_TXT = ("TÍTULO: QUEM REALMENTE SÃO AS PESSOAS?\nTEMA: lealdade e caráter segundo Maquiavel\n"
                   "FORMATO: PERSONAGEM_FALANDO\nPERSONAGEM: Maquiavel\n"
                   + "".join(f"\nCENA {c['id'][-2:]} | MODO: {c['mode'].upper()}\nNARRAÇÃO: {c['text']}\n"
                             f"IMAGEM: {c['descricao_imagem']}\n" + (f"BUSCA: {c['busca']}\n" if c.get("busca") else "")
                             for c in F01_EXAMPLE) + "\nFIM\n\n"
                   "METADADOS\nTÍTULO DO POST: Quem realmente são as pessoas?\n"
                   "DESCRIÇÃO: Maquiavel lembra que o caráter aparece nas ações, não nas promessas. Você já confiou "
                   "em alguém só pelo que ele dizia?\n"
                   "HASHTAGS: #maquiavel #carater #lealdade #filosofia #reflexao")

F01_MODEL = """TÍTULO: <frase curta e intrigante>
TEMA: <assunto do vídeo>
FORMATO: PERSONAGEM_FALANDO
PERSONAGEM: <quem fala>
SÉRIE: <nome da série; deixe vazio se o vídeo for avulso>
EPISÓDIO: <posição na série, ex.: 1 de 9; deixe vazio se for avulso>

CENA 01 | MODO: FALA
NARRAÇÃO: <texto integral que será falado>
IMAGEM: <o que aparece na cena>

CENA 02 | MODO: DOLLY
NARRAÇÃO: <texto integral>
IMAGEM: <o que aparece na cena>
BUSCA: <2 a 4 palavras-chave em inglês para o banco de imagens>

CENA 03 | MODO: FALA
NARRAÇÃO: <texto integral>
IMAGEM: <o que aparece na cena>

FIM

""" + META_MODEL

F01_ANIM_EX = """CENA 01 | MODO: FALA
NARRAÇÃO: Você acredita que as pessoas mostram quem realmente são? Maquiavel já alertava: [CARDS: Olhos: o que parece | Mãos: o que a pessoa faz] os homens julgam mais pelos olhos do que pelas mãos.
IMAGEM: Maquiavel em seu escritório renascentista, olhando para a câmera."""
F01_ANIM_QTD = "1 ou 2 por vídeo (no máximo 1 por cena)"

F01_PROMPT = """Anexei o PDF "Framework F01 — Personagem Falando". Siga o item 3 à risca.

TEMA DO VÍDEO: [escreva o tema]
PERSONAGEM QUE FALA: [ex.: Maquiavel, Sêneca, um mentor fictício]
NÚMERO DE CENAS: [3 a 6]
SÉRIE E EPISÓDIO (opcional): [ex.: Playbook Flávio Augusto, episódio 1 de 9; deixe em branco se for avulso]

REGRAS DE ENTREGA (obrigatórias):
- Primeiro, UM ÚNICO bloco de código (```text) com o roteiro, da linha "TÍTULO:" até a linha "FIM",
  seguido do bloco METADADOS (TÍTULO DO POST:, DESCRIÇÃO:, NOTA EDITORIAL: opcional, HASHTAGS: por último).
- Use exatamente as palavras-chave do item 3: TÍTULO:, TEMA:, FORMATO:, PERSONAGEM:, SÉRIE:, EPISÓDIO:,
  "CENA 01 | MODO: FALA", NARRAÇÃO:, IMAGEM:. Escreva "CENA 01" com espaço (nunca CENA_01).
- MODO só pode ser FALA, DOLLY ou ZOOM. Abra e feche com FALA; alterne com DOLLY/ZOOM no meio.
- Nas cenas de FALA aparece o personagem cadastrado no app (as imagens dele, em rodízio).
- Nas cenas DOLLY e ZOOM, inclua a linha BUSCA: com 2 a 4 palavras-chave em inglês (ex.: running sunrise road):
  o app usa essas palavras para buscar a foto da cena no Pixabay.
- Dentro do bloco: sem negrito, sem títulos, sem comentários, sem JSON, sem fontes e sem nenhum <...> sobrando.
- Animações: inclua 1 ou 2 marcações do item 5 ([CONTADOR: ...], [BARRAS: ...], [FLUXO: ...], [CARDS: ...] ou
  [DESTAQUE: ...]) dentro da NARRAÇÃO, logo antes da frase certa. Números da marcação precisam ser ditos na fala.
- Depois do bloco, em texto normal: um PROMPT DE IMAGEM por cena (regras de imagem do item 4), para o caso de
  eu preferir criar as imagens em vez de deixar o app montar.
"""


def f01():
    s = [header("FORMATO 01 — PERSONAGEM FALANDO",
                "Framework de roteiro para criar vídeos em que um personagem fala direto para a câmera.",
                "VIDEO CREATOR · FRAMEWORK DE ROTEIRO · VERSÃO 1.3 · ATUALIZADO EM 07/11/2026"), Spacer(1, 8)]
    s += [P("<b>Para que serve este PDF:</b> anexe este arquivo ao ChatGPT junto com o prompt do item 2. O ChatGPT "
            "devolve o roteiro em texto simples, já no formato que o Video Creator lê. Você cola esse texto no app "
            "(ou salva como .txt). As imagens das cenas são opcionais: com o personagem cadastrado, o app monta as "
            "cenas sozinho (item 3). <b>Não envie este PDF ao app</b>: ele é só o modelo.")]
    s += [P("1. Como o vídeo fica", "h2"),
          P("Vertical 9:16. Nas cenas de <b>fala</b>, a imagem do personagem ganha boca sincronizada, piscadas e "
            "leves movimentos de cabeça, com um zoom lento. Nas cenas <b>sem fala</b>, a imagem ganha profundidade "
            "(efeito 2.5D: o que está perto se move mais que o fundo). Uma voz narra o vídeo inteiro e a legenda "
            "karaokê troca de branco para dourado a cada palavra falada. A duração é automática: cada cena dura o "
            "tempo da sua narração."),
          frames("f01", ["CENA 1 · fala (SadTalker)", "CENA 2 · sem fala (2.5D)", "CENA 3 · fala"]),
          P("Vídeo-exemplo: <b>exemplo_F01_maquiavel.mp4</b> (24 s, 3 cenas), na mesma pasta de downloads.", "small")]
    s += [P("2. Como usar com o ChatGPT (copie e cole)", "h2"),
          P("Abra uma conversa nova, anexe este PDF, cole o texto abaixo e preencha os colchetes."), code(F01_PROMPT)]
    s[-3:] = [KeepTogether(s[-3:])]
    s += [PageBreak(), P("3. Estrutura obrigatória do roteiro", "h2"),
          P("Texto simples: um cabeçalho, um bloco por cena (numeradas 01, 02, 03...), a linha <b>FIM</b> e o "
            "bloco <b>METADADOS</b>. Troque cada &lt;...&gt; pelo texto real e repita o bloco CENA quantas vezes "
            "precisar:"),
          code(F01_MODEL),
          P("Série (opcional)", "h3"),
          P("Se o vídeo faz parte de uma série, preencha <b>SÉRIE:</b> com o nome da série (coleção) e <b>EPISÓDIO:</b> com a posição e o total, no formato <b>1 de 9</b>. Com as duas linhas preenchidas, a capa mostra o nome da série e \"EPISÓDIO 1 DE 9\" acima do título. Vídeo avulso: deixe as duas linhas vazias (sem &lt;...&gt;) ou apague as duas; a capa sai no modelo normal."),
          P("Os três modos de cena", "h3"),
          table([["Modo", "Quando usar", "Exigência da imagem"],
                 ["<b>FALA</b>", "O personagem fala olhando para quem assiste. Use na abertura e no fechamento.",
                  "Um rosto humano realista em destaque, de frente ou 3/4, boca visível, sem mão ou objeto na "
                  "frente do rosto, rosto ocupando ao menos 15% da altura."],
                 ["<b>DOLLY</b>", "Cenas que ilustram a ideia (situações, lugares, ações) sem ninguém falando.",
                  "Cena com profundidade: primeiro plano, meio e fundo bem separados."],
                 ["<b>ZOOM</b>", "Imagens planas: símbolos, objetos isolados, gráficos sem texto.",
                  "Qualquer imagem vertical; sem texto escrito dentro."]], [22, 70, 82]),
          P("Imagens: enviar ou deixar o app montar", "h3"),
          table([["Cena", "Se você enviar cenaN.png", "Se não enviar (automático)"],
                 ["<b>FALA</b>", "O app anima o rosto da imagem enviada.",
                  "O app monta a cena com uma pose recortada do personagem cadastrado sobre um dos fundos dele. "
                  "A pose e o fundo mudam a cada cena."],
                 ["<b>DOLLY / ZOOM</b>", "O app usa a imagem enviada.",
                  "O app busca uma foto no Pixabay pelas palavras da linha <b>BUSCA:</b> (ou, sem ela, pela "
                  "descrição da linha IMAGEM:). Sem resultado, usa um quadro de um fundo do personagem."]],
                [26, 60, 88]),
          P('Cada personagem cadastrado no app tem o seu banco de imagens (poses recortadas, sem fundo) e os seus fundos. Nas cenas de FALA, o app usa essas imagens em rodízio embaralhado: cada cena de FALA mostra uma pose diferente sobre um fundo diferente. Nas cenas DOLLY e ZOOM o personagem não aparece: o app busca no Pixabay uma foto pela linha BUSCA:.'),
          P("Como planejar as cenas", "h3")] + bullets(['Abra e feche com FALA (o personagem aparece). Use DOLLY ou ZOOM no meio para ilustrar exemplos, lugares, objetos e situações; alterne, por exemplo FALA, DOLLY, FALA, ZOOM, FALA.', 'A BUSCA: das cenas DOLLY/ZOOM descreve algo que existe em foto de banco de imagens: objeto, lugar, natureza, ação ou situação (ex.: <i>coins stack</i>, <i>empty office night</i>, <i>man running sunrise</i>). Nunca nomes de pessoas famosas, marcas, épocas muito específicas nem texto escrito.', 'Nas cenas de FALA, a linha IMAGEM: pode ser curta (ex.: "o personagem falando para a câmera"): a imagem vem do cadastro.']) + [
          P("Para o modo automático, o personagem precisa estar cadastrado no app com imagem recortada (sem fundo) e "
            "pelo menos um fundo. Com 2 ou 3 poses diferentes e vários fundos, o vídeo fica mais variado. A linha "
            "<b>BUSCA:</b> é opcional, mas melhora muito a foto encontrada: 2 a 4 palavras-chave em inglês que "
            "descrevem o que aparece (ex.: <i>running sunrise road</i>).")]
    s += meta_section("Metadados da publicação")
    s += [P("4. Regras de escrita", "h2"),
          P("Narração", "h3")] + bullets([
              "De 3 a 6 cenas. Cada narração com <b>12 a 30 palavras</b> (a voz fala cerca de 2,8 palavras por "
              "segundo; 22 palavras ≈ 8 s). Vídeo total de 30 a 60 segundos.",
              "A cena 1 é o <b>gancho</b> (pergunta ou afirmação que prende); a última é a <b>conclusão</b> "
              "(lição prática ou reflexão).",
              "Frases curtas, pontuação clara. Escreva <b>números por extenso</b> (\"cem mil\", não \"100 mil\"), "
              "sem siglas, emojis, hashtags ou abreviações.",
              "Uma única voz narra o vídeo todo. O texto da legenda é exatamente o texto da narração.",
              "Nomes próprios estrangeiros podem ser mal pronunciados pela voz sintética: prefira a forma "
              "aportuguesada e revise ao ouvir.",
              "Não prometa renda, cura ou resultado garantido."]) + [
          P("Imagens", "h3")] + bullets([
              "Vertical 9:16 (ex.: 1080 × 1920 ou 941 × 1672). O assunto principal no centro, longe das bordas.",
              "<b>Sem texto dentro da imagem</b>: a legenda é colocada pelo app.",
              "Mantenha o mesmo personagem (rosto, roupa, cenário) nas cenas de FALA.",
              "Uma imagem pode ser reutilizada em mais de uma cena.",
              "Personagens sem rosto humano (ex.: cabeça cósmica) <b>não podem</b> usar o modo FALA: use DOLLY ou ZOOM.",
              "Nome dos arquivos: cena1.png, cena2.png... dentro da pasta do vídeo.",
              "Pode enviar só algumas: as cenas sem imagem o app monta sozinho (item 3)."])
    s += [PageBreak()] + anim_section(5, F01_ANIM_QTD, F01_ANIM_EX)
    s += [P("6. Como enviar para o app", "h2")] + bullets([
        "Copie o bloco de código que o ChatGPT devolveu e cole em <b>Colar roteiro</b>, na página Criar vídeos "
        "(ou salve como <b>.txt</b> e arraste o arquivo).",
        "Imagens são opcionais. Com o personagem cadastrado (recorte + fundos), basta colar o roteiro: o app monta "
        "as cenas de fala e busca no Pixabay as imagens das cenas sem fala.",
        "Se quiser usar imagens suas, envie junto com o nome <b>cena1.png, cena2.png...</b> (uma por cena, na "
        "ordem; pode ser só algumas). Para isso, coloque o roteiro .txt e as imagens numa pasta e arraste a pasta.",
        "O app mostra o template, o idioma, o título, as cenas e o que estiver faltando antes de gerar.",
        "Roteiro em inglês: mantenha as mesmas palavras-chave do item 3; o app identifica o idioma sozinho e a voz "
        "lê em inglês."])
    s += [P("7. Exemplo completo — Maquiavel", "h2"), code(F01_EXAMPLE_TXT)]
    s += [KeepTogether([P("8. Padrão técnico fixo (não muda de vídeo para vídeo)", "h2"),
          table([["Item", "Padrão aprovado"],
                 ["Saída", "MP4 1080 × 1920, 30 fps, H.264 + AAC, volume −14 LUFS"],
                 ["Fala", "SadTalker 256, corpo parado, sem realce facial (≈1 min por cena falada)"],
                 ["Cenas sem fala", "Profundidade 2.5D (Depth Anything V2 Small) ou zoom suave"],
                 ["Voz", "Kokoro, voz masculina Alex, tratamento de locutor"],
                 ["Legenda", "Karaokê branco → dourado, Poppins Bold, até 3 palavras, maiúsculas"],
                 ["Transição", "Dissolve de 0,5 s entre cenas"],
                 ["Música", "Opcional, escolhida no app (abaixa sozinha quando a voz entra)"],
                 ["Animações", "Smart Motion: marcações do item 5, abaixo da legenda, sincronizadas com a fala"]],
                [40, 134])])]
    return s


# --------------------------------------------------------------------------------------------- T02
T02_SCENES = json.loads((LAB / "inputs" / "entrevista_bob_proctor" / "roteiro.json").read_text(encoding="utf-8"))["cenas"]
T02_MARCAS = [("CENA_02", "O paradigma é", "[DESTAQUE: PARADIGMA | hábitos + crenças repetidos]"),
              ("CENA_02", "Primeiro, tome", "[FLUXO: Consciência do padrão | Novo padrão | Ações consistentes]"),
              ("CENA_03", "Se eu quiser", "[CONTADOR: US$ 100.000 | por mês]"),
              ("CENA_04", "Um milhão de dólares", "[BARRAS: 10% de margem | Vendas = US$ 1.000.000 | "
                                                  "Lucro = US$ 100.000]"),
              ("CENA_04", "Não tente substituir", "[CARDS: Só pensamento positivo: não substitui estratégia | "
                                                  "Visão clara: orienta o trabalho concreto]")]
for _cid, _antes, _marca in T02_MARCAS:  # the example script shows the animation markers in place
    _c = next(c for c in T02_SCENES if c["id"] == _cid)
    _c["text"] = _c["text"].replace(_antes, f"{_marca} {_antes}", 1)
T02_ANIM_EX = "CENA 03 | PERSONAGEM: PAULO\n" + next(c["text"] for c in T02_SCENES if c["id"] == "CENA_03")
T02_ANIM_QTD = "3 a 5 por vídeo"

T02_EXAMPLE_TXT = ("TÍTULO: DESCUBRA O QUE ESTÁ LIMITANDO SUA RENDA\n"
                   "SUBTÍTULO: Minha conversa com Bob Proctor sobre paradigmas financeiros e negócios\n"
                   "FORMATO: ENTREVISTA_COM_MENTOR\n"
                   + "".join(f"\nCENA {c['id'][-2:]} | PERSONAGEM: {c['personagem']}\n{c['text']}\n" for c in T02_SCENES)
                   + "\nFIM\n\n"
                   "METADADOS\nTÍTULO DO POST: Descubra o que está limitando sua renda\n"
                   "DESCRIÇÃO: Paulo pergunta a Bob Proctor como reconhecer o padrão que se repete nos próprios "
                   "resultados financeiros. Qual hábito com dinheiro você repete sem perceber?\n"
                   "NOTA EDITORIAL: Dramatização criada com inteligência artificial, inspirada nas ideias associadas "
                   "a Bob Proctor.\n"
                   "HASHTAGS: #mentalidade #paradigma #financas #negocios #desenvolvimentopessoal")

T02_MODEL = """TÍTULO: <frase intrigante>
SUBTÍTULO: Minha conversa com <MENTOR> sobre <assunto>
FORMATO: ENTREVISTA_COM_MENTOR
SÉRIE: <nome da série; deixe vazio se o vídeo for avulso>
EPISÓDIO: <posição na série, ex.: 1 de 9; deixe vazio se for avulso>

CENA 01 | PERSONAGEM: PAULO
<pergunta de abertura>

CENA 02 | PERSONAGEM: <MENTOR>
<resposta>

CENA 03 | PERSONAGEM: PAULO
<próxima pergunta>

CENA 04 | PERSONAGEM: <MENTOR>
<resposta final com orientação prática>

FIM

""" + META_MODEL

T02_PROMPT = """Anexei o PDF "Framework T02 — Entrevista com Mentor". Siga o item 3 à risca.

MENTOR: [nome do mentor ou autor]
TEMA DA CONVERSA: [assunto]
NÚMERO DE CENAS: [4 a 8, sempre alternando PAULO e MENTOR]
PERGUNTAS QUE EU QUERO FAZER (opcional): [liste, se tiver]
SÉRIE E EPISÓDIO (opcional): [ex.: Playbook Flávio Augusto, episódio 1 de 9; deixe em branco se for avulso]

REGRAS DE ENTREGA (obrigatórias):
- Primeiro, UM ÚNICO bloco de código (```text) com o roteiro, da linha "TÍTULO:" até a linha "FIM",
  seguido do bloco METADADOS (TÍTULO DO POST:, DESCRIÇÃO:, NOTA EDITORIAL: opcional, HASHTAGS: por último).
- Use exatamente as palavras-chave do item 3: TÍTULO:, SUBTÍTULO:, FORMATO:, SÉRIE:, EPISÓDIO:,
  "CENA 01 | PERSONAGEM: NOME". Escreva "CENA 01" com espaço (nunca CENA_01).
- NOME sempre em MAIÚSCULAS e sempre igual: PAULO e o nome do mentor (ex.: BOB PROCTOR).
- A fala vem na linha de baixo, sem repetir o nome.
- PAULO: 15 a 45 palavras. MENTOR: 60 a 100 palavras. Nunca passe de 120 palavras numa fala.
- Dentro do bloco: sem negrito, sem títulos, sem aviso, sem comentários, sem JSON, sem fontes
  e sem nenhum <...> sobrando.
- A DESCRIÇÃO do bloco METADADOS diz que é uma dramatização.
- Animações: inclua de 3 a 5 marcações do item 5 ([CONTADOR: ...], [BARRAS: ...], [FLUXO: ...], [CARDS: ...] ou
  [DESTAQUE: ...]) dentro das falas, logo antes da frase certa. Números da marcação precisam ser ditos na fala.
"""


def t02():
    s = [header("T02 — ENTREVISTA COM MENTOR",
                "Framework de roteiro para conversas alternadas: você pergunta, o mentor responde.",
                "VIDEO CREATOR · FRAMEWORK DE ROTEIRO · VERSÃO 1.3 · ATUALIZADO EM 07/11/2026"), Spacer(1, 8)]
    s += [P("<b>Para que serve este PDF:</b> anexe este arquivo ao ChatGPT junto com o prompt do item 2. Ele "
            "devolve o roteiro em texto simples, já no formato que o Video Creator lê. Você cola esse texto no app "
            "(ou salva como .txt). <b>Não envie este PDF ao app</b>: ele é só o modelo.")]
    s += [P("1. Como o vídeo fica", "h2"),
          P("Vertical 9:16. A cada troca de locutor mudam o <b>retrato</b>, o <b>lado</b>, o <b>fundo</b> e a "
            "<b>voz</b>: o mentor aparece à esquerda sobre o fundo dele; Paulo aparece à direita sobre outro fundo. "
            "Os retratos são PNGs recortados que \"respiram\" (zoom 100% → 106% → 100%), o fundo é um vídeo em loop "
            "escurecido, uma onda sonora reage à voz e a legenda karaokê troca de branco para dourado a cada palavra. "
            "No topo aparece só o nome de quem fala (e, opcionalmente, o logo do canal)."),
          frames("t02", ["PAULO · direita · fundo nuvens", "MENTOR · esquerda · fundo partículas", "PAULO · pergunta"]),
          P("Vídeo-exemplo: <b>exemplo_T02_entrevista.mp4</b> (2 min 16 s, 6 cenas), na mesma pasta de downloads.",
            "small")]
    s += [KeepTogether([P("2. Como usar com o ChatGPT (copie e cole)", "h2"),
          P("Abra uma conversa nova, anexe este PDF, cole o texto abaixo e preencha os colchetes."), code(T02_PROMPT)])]
    s += [PageBreak(), P("3. Estrutura obrigatória do roteiro", "h2"),
          P("Texto simples: um cabeçalho, um bloco por cena (numeradas 01, 02, 03...), a linha <b>FIM</b> e o "
            "bloco <b>METADADOS</b>. Troque cada &lt;...&gt; pelo texto real e repita os blocos alternando até 8 "
            "cenas:"),
          code(T02_MODEL),
          P("Série (opcional)", "h3"),
          P("Se o vídeo faz parte de uma série, preencha <b>SÉRIE:</b> com o nome da série (coleção) e <b>EPISÓDIO:</b> com a posição e o total, no formato <b>1 de 9</b>. Com as duas linhas preenchidas, a capa mostra o nome da série e \"EPISÓDIO 1 DE 9\" acima do título. Vídeo avulso: deixe as duas linhas vazias (sem &lt;...&gt;) ou apague as duas; a capa sai no modelo normal."),
          P("Papéis", "h3"),
          table([["Personagem", "Função", "Tamanho da fala"],
                 ["<b>PAULO</b>", "Pergunta, traz um exemplo real ou uma dúvida concreta do público. Fala em primeira "
                  "pessoa, tom de conversa.", "15 a 45 palavras (5 a 15 s)"],
                 ["<b>MENTOR</b>", "Responde com uma interpretação original das ideias associadas a ele, chama Paulo "
                  "pelo nome, termina com uma orientação prática.", "60 a 100 palavras (20 a 35 s)"]], [26, 100, 48])]
    s += meta_section("Metadados da publicação")
    s += [P("4. Regras de escrita", "h2")] + bullets([
        "De 4 a 8 cenas, <b>sempre alternando</b>; a cena 1 é sempre uma pergunta do PAULO (o gancho) e a última é "
        "sempre uma resposta do MENTOR (a conclusão).",
        "Uma ideia central por resposta. Encadeie: a próxima pergunta nasce da resposta anterior.",
        "Escreva <b>números por extenso</b> (\"cem mil dólares\", \"dez por cento\"), sem siglas, emojis ou "
        "abreviações, com pontuação clara: a voz e a legenda dependem disso.",
        "O nome do personagem no roteiro deve ser sempre o mesmo e em MAIÚSCULAS (ex.: BOB PROCTOR).",
        "Não prometa renda, cura ou resultado garantido; separe reflexão de fato.",
        "Ao publicar: marque \"conteúdo gerado ou alterado por IA\" na plataforma e use a descrição do bloco "
        "METADADOS (o app já a coloca no card do vídeo)."])
    s += [P("Personagens e fundos (cadastrados uma vez)", "h3"),
          table([["Campo", "PAULO (fixo)", "MENTOR (troca por vídeo)"],
                 ["Imagem", "PNG recortado, virado para a esquerda", "PNG recortado, virado para a direita"],
                 ["Lado", "direita", "esquerda"],
                 ["Fundo", "vídeo curto em loop (ex.: nuvens)", "outro vídeo em loop (ex.: partículas douradas)"],
                 ["Voz", "Chatterbox, clone da voz do Paulo", "Kokoro, voz genérica (pm_santa ou pm_alex)"]],
                [26, 74, 74])]
    s += [PageBreak()] + anim_section(5, T02_ANIM_QTD, T02_ANIM_EX)
    s += [P("6. Como enviar para o app", "h2")] + bullets([
        "Copie o bloco de código que o ChatGPT devolveu e cole em <b>Colar roteiro</b>, na página Criar vídeos "
        "(ou salve como <b>.txt</b> e arraste o arquivo).",
        "O app liga cada nome ao personagem cadastrado (imagem, lado, fundo e voz ficam no cadastro, não no roteiro). "
        "Se o mentor ainda não existe, o app mostra \"cadastrar\" ao lado do nome.",
        "O app mostra o template, o idioma, o título, as cenas e o que estiver faltando antes de gerar.",
        "Roteiro em inglês: mantenha as mesmas palavras-chave do item 3; o app identifica o idioma sozinho e as "
        "vozes leem em inglês."])
    s += [P("7. Exemplo completo — Paulo × Bob Proctor", "h2"), code(T02_EXAMPLE_TXT)]
    s += [KeepTogether([P("8. Padrão técnico fixo (não muda de vídeo para vídeo)", "h2"),
          table([["Item", "Padrão aprovado"],
                 ["Saída", "MP4 1080 × 1920, 30 fps, H.264 + AAC, volume −14 LUFS"],
                 ["Retrato", "PNG recortado, largura 1000 px, respiração 100 → 106 → 100%"],
                 ["Fundo", "Vídeo em loop sem emenda, escurecido e levemente desfocado"],
                 ["Onda sonora", "40 barras brancas reagindo à voz, do lado oposto ao rosto"],
                 ["Vozes", "Mesmo volume entre locutores; voz do mentor com redução de ruído"],
                 ["Legenda", "Karaokê branco → dourado, Poppins Bold, até 3 palavras, maiúsculas"],
                 ["Topo", "Só o nome de quem fala; logo do canal opcional"],
                 ["Transição", "Dissolve de 0,4 s na troca de locutor"],
                 ["Música", "Opcional, escolhida no app"],
                 ["Animações", "Smart Motion: marcações do item 5, entre o nome e a legenda, sincronizadas com a fala"]],
                [40, 134])])]
    return s


RULES = """## Regras de entrega

1. Responda com UM ÚNICO bloco de código (```text) contendo o roteiro, da linha "TÍTULO:" até a linha "FIM",
   seguido do bloco METADADOS (veja "Metadados da publicação").
2. Use exatamente as palavras-chave do modelo. Escreva "CENA 01" com espaço, nunca CENA_01. Numere 01, 02, 03...
3. Dentro do bloco: sem negrito, sem títulos, sem aviso, sem comentários, sem JSON, sem fontes, sem emojis e sem
   nenhum <...> sobrando.
4. Escreva números por extenso ("cem mil", "dez por cento"), sem siglas nem abreviações: a voz e a legenda dependem disso.
5. Não prometa renda, cura ou resultado garantido.
6. Se faltar alguma informação, pergunte antes de escrever.
7. Roteiro em inglês: escreva as falas e os metadados em inglês, mas mantenha as palavras-chave do modelo
   (TÍTULO:, CENA 01 | ..., FIM, METADADOS...). O app identifica o idioma sozinho.
8. Série (opcional): se o vídeo faz parte de uma série, preencha SÉRIE: com o nome da série (coleção) e
   EPISÓDIO: com a posição do vídeo e o total, no formato "1 de 9". Com as duas linhas preenchidas, a capa
   mostra o nome da série e "EPISÓDIO 1 DE 9" acima do título. Vídeo avulso: deixe SÉRIE: e EPISÓDIO: vazias
   (sem <...>) ou apague as duas linhas; a capa sai no modelo normal.
9. Animações (opcional, recomendado): marque contadores, barras, fluxos, cards e destaques dentro da fala,
   com a sintaxe da seção "Animações na tela". A marcação não é falada.

## Metadados da publicação

Depois da linha FIM, no mesmo bloco de código, vem o bloco METADADOS (não é falado no vídeo):

- TÍTULO DO POST: título da publicação. Se faltar, o app usa o TÍTULO do roteiro (o mesmo da capa).
- DESCRIÇÃO: texto da publicação. Pode ter mais de uma linha.
- NOTA EDITORIAL: opcional. Vai no fim da descrição. Se não tiver, apague a linha.
- HASHTAGS: sempre a última linha do bloco, tudo numa linha só.

O que vier preenchido aparece pronto no app; o que faltar, o app completa com a IA."""

T02_MD = f"""# Framework T02: Entrevista com mentor (Video Creator)

Você escreve roteiros para o app Video Creator (canal Dobrando a Realidade). O app lê o roteiro automaticamente,
por isso o formato abaixo é obrigatório. Paulo pergunta, o mentor responde, sempre alternando.
Para começar, peça: MENTOR, TEMA DA CONVERSA, NÚMERO DE CENAS (4 a 8) e perguntas que o Paulo quer fazer (opcional).

{RULES}

## Regras do template

- De 4 a 8 cenas. A cena 01 é sempre uma pergunta do PAULO (o gancho); a última é sempre uma resposta do mentor.
- PAULO: 15 a 45 palavras, primeira pessoa, tom de conversa, traz um exemplo ou dúvida concreta.
- MENTOR: 60 a 100 palavras (nunca mais de 120), responde com uma interpretação original das ideias associadas a ele,
  chama Paulo pelo nome, uma ideia central, termina com orientação prática.
- A próxima pergunta nasce da resposta anterior.
- Nome dos personagens sempre igual e em MAIÚSCULAS: PAULO e o nome do mentor (ex.: BOB PROCTOR).
- A fala vem na linha de baixo do cabeçalho da cena, sem repetir o nome.
- A DESCRIÇÃO do bloco METADADOS diz que é uma dramatização criada com IA.

{anim_md(T02_ANIM_QTD, T02_ANIM_EX)}

## Modelo

```text
{T02_MODEL}
```

## Exemplo correto

```text
{T02_EXAMPLE_TXT}
```
"""

F01_MD = f"""# Framework F01: Personagem falando (Video Creator)

Você escreve roteiros para o app Video Creator (canal Dobrando a Realidade). O app lê o roteiro automaticamente,
por isso o formato abaixo é obrigatório. Um personagem fala para a câmera; algumas cenas mostram ilustrações.
Uma voz narra o vídeo todo. Para começar, peça: TEMA, PERSONAGEM QUE FALA e NÚMERO DE CENAS (3 a 6).

{RULES}

## Regras do template

- De 3 a 6 cenas; cada NARRAÇÃO com 12 a 30 palavras; vídeo total de 30 a 60 segundos.
- A cena 01 é o gancho (pergunta ou afirmação que prende); a última é a conclusão (lição prática).
- MODO de cada cena (só estes três):
  - FALA: o personagem fala olhando para a câmera. A imagem precisa de um rosto humano realista em destaque,
    de frente ou 3/4, boca visível, nada na frente do rosto. Use na abertura e no fechamento.
  - DOLLY: cena que ilustra a ideia, sem ninguém falando, com primeiro plano, meio e fundo bem separados.
  - ZOOM: imagem plana (símbolo, objeto isolado), sem texto escrito.
- IMAGEM: uma frase descrevendo o que aparece na cena.
- BUSCA: só nas cenas DOLLY e ZOOM, 2 a 4 palavras-chave em inglês (ex.: running sunrise road). O app usa essas
  palavras para buscar a foto da cena no Pixabay.
- Imagens são opcionais: com o personagem cadastrado no app (recorte + fundos), o app monta as cenas de FALA
  sozinho (pose do personagem sobre um dos fundos dele) e busca no Pixabay as fotos das cenas DOLLY/ZOOM.
- Cada personagem cadastrado no app tem o seu banco de imagens (poses recortadas, sem fundo) e os seus fundos. Nas cenas de FALA, o app usa essas imagens em rodízio embaralhado: cada cena de FALA mostra uma pose diferente sobre um fundo diferente. Nas cenas DOLLY e ZOOM o personagem não aparece: o app busca no Pixabay uma foto pela linha BUSCA:.
- Abra e feche com FALA (o personagem aparece). Use DOLLY ou ZOOM no meio para ilustrar exemplos, lugares, objetos e situações; alterne, por exemplo FALA, DOLLY, FALA, ZOOM, FALA.
- A BUSCA: das cenas DOLLY/ZOOM descreve algo que existe em foto de banco de imagens: objeto, lugar, natureza, ação ou situação (ex.: coins stack, empty office night, man running sunrise). Nunca nomes de pessoas famosas, marcas, épocas muito específicas nem texto escrito.
- Nas cenas de FALA, a linha IMAGEM: pode ser curta (ex.: "o personagem falando para a câmera"): a imagem vem do cadastro.
- Depois do bloco: um prompt de imagem por cena (vertical 9:16, sem texto dentro da imagem, mesmo personagem,
  roupa e cenário nas cenas de FALA), para quando o usuário preferir criar as imagens. Ele salva como
  cena1.png, cena2.png...

{anim_md(F01_ANIM_QTD, F01_ANIM_EX)}

## Modelo

```text
{F01_MODEL}
```

## Exemplo correto

```text
{F01_EXAMPLE_TXT}
```
"""


if __name__ == "__main__":
    DL.mkdir(exist_ok=True)
    build(DL / "Framework_F01_Personagem_Falando.pdf", "Framework F01 — Personagem Falando", f01())
    build(DL / "Framework_T02_Entrevista_com_Mentor.pdf", "Framework T02 — Entrevista com Mentor", t02())
    texts = {"modelo_F01_roteiro.txt": F01_MODEL, "exemplo_F01_roteiro.txt": F01_EXAMPLE_TXT,
             "modelo_T02_roteiro.txt": T02_MODEL, "exemplo_T02_roteiro.txt": T02_EXAMPLE_TXT,
             "Framework_F01_Personagem_Falando.md": F01_MD, "Framework_T02_Entrevista_com_Mentor.md": T02_MD}
    for name, text in texts.items():
        (DL / name).write_text(text + "\n", encoding="utf-8")
    for old in ("modelo_F01_cenas.json", "modelo_T02_roteiro.json",  # replaced by the .txt/.md files
                "Instrucoes_ChatGPT_Video_Creator.md"):
        (DL / old).unlink(missing_ok=True)
    shutil.copy2(LAB / "outputs" / "videos" / "teste_maquiavel" / "teste_maquiavel.mp4", DL / "exemplo_F01_maquiavel.mp4")
    shutil.copy2(LAB / "outputs" / "videos" / "entrevista_bob_proctor" / "entrevista_bob_proctor.mp4",
                 DL / "exemplo_T02_entrevista.mp4")
    app_models = Path(r"D:\Video-Creator\app\static\modelos")  # keep the app's "Modelos de vídeo" section in sync
    if app_models.exists():
        for name in ("Framework_F01_Personagem_Falando.pdf", "Framework_T02_Entrevista_com_Mentor.pdf",
                     "exemplo_F01_maquiavel.mp4", "exemplo_T02_entrevista.mp4", *texts):
            shutil.copy2(DL / name, app_models / name)
        (app_models / "Instrucoes_ChatGPT_Video_Creator.md").unlink(missing_ok=True)
    print("ok")
