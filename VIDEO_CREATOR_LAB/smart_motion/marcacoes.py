"""Marcações de animação dentro do roteiro (só biblioteca padrão: o parser do app também importa este módulo).

O ChatGPT escreve a marcação logo antes da frase em que a animação deve aparecer:
    Se eu quiser [CONTADOR: US$ 100.000 | por mês] ganhar cem mil dólares por mês...
A marcação não é falada nem aparece na legenda: extrair() tira ela do texto e guarda em que palavra estava.

Tipos (português / inglês):
    [CONTADOR: valor | texto]                      [COUNTER: value | text]
    [BARRAS: título | Nome = valor | Nome = valor] [BARS: title | Name = value | Name = value]
    [FLUXO: etapa 1 | etapa 2 | etapa 3]           [FLOW: step 1 | step 2 | step 3]
    [CARDS: errado: detalhe | certo: detalhe]      [CARDS: wrong: detail | right: detail]
    [DESTAQUE: PALAVRA | subtítulo]                [HIGHLIGHT: WORD | subtitle]
"""
import re
import unicodedata

TIPOS = {"CONTADOR": "counter", "COUNTER": "counter", "BARRAS": "bars", "BARS": "bars", "GRAFICO": "bars",
         "FLUXO": "flow", "FLOW": "flow", "ETAPAS": "flow", "STEPS": "flow", "CARDS": "cards", "CARD": "cards",
         "COMPARACAO": "cards", "DESTAQUE": "keyword", "HIGHLIGHT": "keyword", "PALAVRACHAVE": "keyword",
         "KEYWORD": "keyword"}
NOMES = {"counter": "Contador", "bars": "Barras", "flow": "Fluxo", "cards": "Cards", "keyword": "Destaque"}
# [NOME: conteúdo] com NOME em maiúsculas (evita apagar colchetes comuns do texto)
_MARCA = re.compile(r"\[\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ _\-]{1,24})\s*:\s*([^\[\]]*)\]")


def norm(s):
    s = unicodedata.normalize("NFD", str(s).upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9%]", "", s)


def extrair(texto):
    """-> (texto_sem_marcacoes, [animação...], [aviso...]). 'palavra' = índice da palavra (no texto limpo)
    em que a animação começa; o alinhamento da voz usa texto.split(), então os índices batem."""
    palavras, anims, avisos, pos = [], [], [], 0
    for m in _MARCA.finditer(texto):
        palavras += texto[pos:m.start()].split()
        pos = m.end()
        nome = norm(m.group(1))
        if nome not in TIPOS:
            avisos.append(f"Marcação desconhecida removida: {m.group(0)[:60]} (use CONTADOR, BARRAS, FLUXO, "
                          "CARDS ou DESTAQUE).")
            continue
        tipo = TIPOS[nome]
        campos = [c.strip() for c in m.group(2).split("|")]
        try:
            payload = montar(tipo, campos)
        except ValueError as ex:
            avisos.append(f"{NOMES[tipo]} ignorado ({m.group(0)[:60]}): {ex}")
            continue
        anims.append({"tipo": tipo, "palavra": len(palavras), "payload": payload, "marcacao": m.group(0)})
    palavras += texto[pos:].split()
    return " ".join(palavras), anims, avisos


# ------------------------------------------------------------------ valores na tela
_MULT_TXT = {"MIL": 1e3, "K": 1e3, "THOUSAND": 1e3, "MI": 1e6, "MILHAO": 1e6, "MILHOES": 1e6, "MILLION": 1e6,
             "MILLIONS": 1e6, "BI": 1e9, "BILHAO": 1e9, "BILHOES": 1e9, "BILLION": 1e9, "BILLIONS": 1e9}
_NUM = re.compile(r"(\d[\d.,]*)\s*([A-Za-zÀ-ú]+)?")


def ler_valor(s):
    """'US$ 100.000' -> (100000, 'US$ ', '', 0); '10%' -> (10, '', '%', 0); 'R$ 1,5 milhão' -> (1500000, 'R$ ', '', 0)."""
    m = _NUM.search(s)
    if not m:
        raise ValueError(f"sem número em '{s}'")
    raw = m.group(1).rstrip(".,")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", raw) and not re.fullmatch(r"\d[.,]\d{3}", raw) or \
            re.fullmatch(r"\d{1,3}(\.\d{3}){2,}|\d{1,3}(,\d{3}){2,}", raw):
        num, dec = float(re.sub(r"[.,]", "", raw)), 0
    elif re.fullmatch(r"\d[.,]\d{3}", raw):  # '1.000' ou '1,000' = mil
        num, dec = float(re.sub(r"[.,]", "", raw)), 0
    else:
        t = raw.replace(",", ".")
        num, dec = float(t), len(t.split(".")[1]) if "." in t else 0
    fim = m.end(1)
    mult = _MULT_TXT.get(norm(m.group(2) or ""))
    if mult:
        num, dec, fim = num * mult, 0, m.end(2)
    prefixo = s[:m.start()].strip()
    unidade = s[fim:].strip()
    if prefixo and prefixo[-1].isalnum() or prefixo.endswith("$"):
        prefixo += " "
    if unidade and unidade[0].isalnum():
        unidade = " " + unidade
    return round(num, 6), prefixo, unidade, dec


def montar(tipo, campos):
    campos = [c for c in campos if c]
    if not campos:
        raise ValueError("marcação vazia")
    if tipo == "counter":
        valor, prefixo, unidade, dec = ler_valor(campos[0])
        return {"to": valor, "from": 0, "prefix": prefixo, "unit": unidade, "decimals": dec,
                "suffix": campos[1] if len(campos) > 1 else ""}
    if tipo == "bars":
        titulo = "" if "=" in campos[0] else campos[0]
        itens = [c for c in campos if "=" in c]
        if not 2 <= len(itens) <= 5:
            raise ValueError("precisa de 2 a 5 barras no formato Nome = valor")
        bars, prefixo, unidade, dec = [], "", "", 0
        for i, c in enumerate(itens):
            nome, val = c.split("=", 1)
            v, p, u, d = ler_valor(val)
            if i == 0:
                prefixo, unidade = p, u
            dec = max(dec, d)
            bars.append({"label": nome.strip(), "value": v})
        return {"title": titulo, "prefix": prefixo, "suffix": unidade, "decimals": dec, "bars": bars}
    if tipo == "flow":
        if not 2 <= len(campos) <= 5:
            raise ValueError("precisa de 2 a 5 etapas separadas por |")
        return {"steps": [{"label": c} for c in campos]}
    if tipo == "cards":
        if len(campos) > 2:
            raise ValueError("no máximo 2 cards")
        cards = []
        for i, c in enumerate(campos):
            titulo, _, texto = c.partition(":")
            tom = "positive" if (len(campos) == 1 or i == 1) else "negative"
            cards.append({"title": titulo.strip(), "text": texto.strip(), "tone": tom})
        return {"cards": cards}
    if tipo == "keyword":
        return {"text": campos[0], "subtitle": campos[1] if len(campos) > 1 else ""}
    raise ValueError(f"tipo {tipo}")


# ------------------------------------------------------------------ números falados (pt e en)
UNID = {"ZERO": 0, "UM": 1, "UMA": 1, "DOIS": 2, "DUAS": 2, "TRES": 3, "QUATRO": 4, "CINCO": 5, "SEIS": 6,
        "SETE": 7, "OITO": 8, "NOVE": 9, "DEZ": 10, "ONZE": 11, "DOZE": 12, "TREZE": 13, "CATORZE": 14,
        "QUATORZE": 14, "QUINZE": 15, "DEZESSEIS": 16, "DEZESSETE": 17, "DEZOITO": 18, "DEZENOVE": 19,
        "VINTE": 20, "TRINTA": 30, "QUARENTA": 40, "CINQUENTA": 50, "SESSENTA": 60, "SETENTA": 70,
        "OITENTA": 80, "NOVENTA": 90, "CEM": 100, "CENTO": 100, "DUZENTOS": 200, "DUZENTAS": 200,
        "TREZENTOS": 300, "TREZENTAS": 300, "QUATROCENTOS": 400, "QUINHENTOS": 500, "SEISCENTOS": 600,
        "SETECENTOS": 700, "OITOCENTOS": 800, "NOVECENTOS": 900,
        "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9,
        "TEN": 10, "ELEVEN": 11, "TWELVE": 12, "THIRTEEN": 13, "FOURTEEN": 14, "FIFTEEN": 15, "SIXTEEN": 16,
        "SEVENTEEN": 17, "EIGHTEEN": 18, "NINETEEN": 19, "TWENTY": 20, "THIRTY": 30, "FORTY": 40, "FIFTY": 50,
        "SIXTY": 60, "SEVENTY": 70, "EIGHTY": 80, "NINETY": 90}
MULT = {"MIL": 1000, "MILHAO": 10**6, "MILHOES": 10**6, "BILHAO": 10**9, "BILHOES": 10**9,
        "THOUSAND": 1000, "MILLION": 10**6, "MILLIONS": 10**6, "BILLION": 10**9, "BILLIONS": 10**9}
_E = {"E", "AND"}


def numeros_falados(words):
    """words: [{'w' ou 'word', 'start', 'end'}]. Valores ditos (dígitos ou por extenso) com seus tempos."""
    ws = [{"w": w.get("w", w.get("word", "")), "start": w.get("start", 0), "end": w.get("end", 0)} for w in words]
    for w in ws:
        w["n"] = norm(w["w"])
    out, i = [], 0
    while i < len(ws):
        n, bruto = ws[i]["n"], ws[i]["w"].strip(".,;:!?\"'()")
        if re.fullmatch(r"\d[\d.,]*%?", bruto):
            try:
                v = ler_valor(bruto)[0]
                out.append({"valor": v, "start": ws[i]["start"], "end": ws[i]["end"], "texto": ws[i]["w"]})
            except ValueError:
                pass
            i += 1
            continue
        if n in ("CENTO", "CENT") and i > 0 and ws[i - 1]["n"] in ("POR", "PER"):  # "dez por cento"
            i += 1
            continue
        if n in UNID or n == "HUNDRED":
            total, cur, j, fim = 0, 0, i, ws[i]["end"]
            while j < len(ws):
                nj = ws[j]["n"]
                if nj in UNID:
                    cur += UNID[nj]
                elif nj == "HUNDRED":
                    cur = max(cur, 1) * 100
                elif nj in MULT:
                    total += max(cur, 1) * MULT[nj]
                    cur = 0
                elif nj in _E and j + 1 < len(ws) and (ws[j + 1]["n"] in UNID or ws[j + 1]["n"] in MULT):
                    pass
                else:
                    break
                fim = ws[j]["end"]
                j += 1
            out.append({"valor": float(total + cur), "start": ws[i]["start"], "end": fim,
                        "texto": " ".join(w["w"] for w in ws[i:j])})
            i = j
            continue
        i += 1
    return out


def valores_da_animacao(tipo, payload):
    if tipo == "counter":
        return [payload["to"]]
    if tipo == "bars":
        return [b["value"] for b in payload["bars"]]
    return []


def checar_no_texto(anim, texto_limpo):
    """Checagem rápida (no app, antes de gerar): os números da animação aparecem na fala da cena?"""
    ditos = {round(n["valor"], 6) for n in numeros_falados([{"w": w} for w in texto_limpo.split()])}
    faltam = [v for v in valores_da_animacao(anim["tipo"], anim["payload"]) if round(v, 6) not in ditos]
    return faltam
