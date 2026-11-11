# ESPECIFICAÇÃO: Animação JORNADA (bonequinho atravessando a casa em corte)

Repositório: `Paulolinks/Video-Creator`
Para: o assistente de código do VS Code (Claude Code, Copilot ou outro)
Objetivo: criar um novo modo de cena, `MODO: ANIMACAO`, com uma animação de tela cheia chamada **JORNADA**. Um bonequinho entra numa casa vista em corte e passa de cômodo em cômodo. Cada cômodo é uma etapa de um funil ou de uma história (porta = deixar o contato, presente = isca digital, tela = vídeo de vendas, carrinho = oferta...). Cada etapa acende **no momento em que a voz fala a palavra dela**.

Depois de pronta, ela fica no app como o **6º tipo de animação** e qualquer roteiro passa a usar só com uma marcação:

```text
CENA 03 | MODO: ANIMACAO
NARRAÇÃO: [JORNADA: O caminho do cliente | PORTA: deixa o contato | PRESENTE: recebe a isca | ENVELOPE: lê seus e-mails | CARRINHO: compra] Primeiro a pessoa deixa o contato. Em troca, recebe a isca. Depois lê seus e-mails por uma semana. E só então compra, já confiando em você.
IMAGEM: animação da jornada do cliente
```

---

## 0. Leia antes de começar (como o app funciona hoje)

Não reinvente: a JORNADA deve reaproveitar o motor **Smart Motion** que já existe. Arquivos que importam:

| Arquivo | O que faz hoje | O que muda |
|---|---|---|
| `VIDEO_CREATOR_LAB/smart_motion/marcacoes.py` | Lê `[CONTADOR: ...]`, `[FLUXO: ...]` etc. dentro da fala, tira do texto e guarda em que palavra estava (`extrair`, `montar`, `TIPOS`, `NOMES`). | Adicionar o tipo `jornada` (seção 3). |
| `VIDEO_CREATOR_LAB/smart_motion/smart_motion.py` | Desenha cada animação com Pillow quadro a quadro (`DRAW`, `draw_flow`, `frame_overlay`), grava uma camada `.mov` com transparência (`render_camadas`) e encaixa no ffmpeg (`aplicar_no_filtro`). `planejar()` descobre o tempo de cada etapa pela fala (`_achar_item`). | Registrar `draw_jornada`, dar a ela uma zona e uma duração próprias (seção 5). |
| **Novo:** `VIDEO_CREATOR_LAB/smart_motion/jornada.py` | (não existe) | Todo o desenho da casa, do boneco e dos objetos (seções 6 a 9). |
| `app/core/parser.py` | Aceita `MODO: FALA / DOLLY / ZOOM` (regex `_SCENE_F01`, checagem na linha ~238) e chama `_animations()`. | Aceitar `ANIMACAO` / `ANIMATION` e validar a cena (seção 4). |
| `app/core/jobs.py` | `check()` reclama de cena sem imagem; `_auto_images()` busca foto no Pixabay para cenas sem imagem. | Cena `animacao` não precisa de imagem nem de Pixabay (seção 4.3). |
| `VIDEO_CREATOR_LAB/scripts/compor_video.py` | Laço `for i, sc in enumerate(scenes)` (linha ~180) gera um clipe por modo (`fala`, `personagem`, `dolly`, `zoom`). | Novo ramo `animacao`: clipe de fundo liso animado (seção 5.3). |
| `app/static/modelos/Framework_F01_Personagem_Falando.md` e `VIDEO_CREATOR_LAB/scripts/make_framework_pdfs.py` | Ensinam o ChatGPT/Claude a escrever o roteiro. | Documentar o modo e a marcação (seção 11). |

Escopo desta versão: **só o Personagem falando (F01), só vertical 9:16** (1080x1920), igual ao resto do Smart Motion. A Entrevista (T02/T03) fica para depois.

Regra de ouro do app que continua valendo: **qualquer falha na animação nunca derruba o vídeo.** Se der erro, a cena sai com o fundo liso e um aviso, igual ao `aplicar_no_filtro` faz hoje com o `try/except`.

---

## 1. O que o espectador vê (a experiência)

Pense num explainer de funil de vendas, só que vertical e com ritmo de Reels/Shorts.

1. **0,0 s a 0,5 s, quebra de padrão.** A casa aparece em corte com um "pop" de câmera (escala 0,92 → 1,0 com leve overshoot). Os cômodos ainda não visitados estão escuros, com um cadeado ou um "?" dourado pulsando. O cérebro quer saber o que tem atrás de cada porta (curiosidade, alça aberta).
2. **O bonequinho entra pela esquerda andando**, com balanço de corpo. Sempre tem algo se mexendo na tela (ninguém fica parado mais de 1,5 s).
3. **Quando a voz fala a palavra da etapa** (ex.: "contato"), a câmera desliza até aquele cômodo, o boneco caminha até o objeto e **interage**: a porta abre, o presente explode em brilho, a tela acende com um botão de play, o carrinho enche. O rótulo da etapa salta em cima do cômodo num cartão dourado.
4. **Barra de progresso** no topo (bolinhas 1 2 3 4 que viram douradas). Mostrar o progresso prende até o fim (efeito de tarefa incompleta).
5. **Última etapa = recompensa.** Zoom de câmera de 1,0 para 1,12 no cômodo final, partículas douradas, o boneco comemora (braços para cima, pulinho). É o momento de "revelação".
6. Fade de saída de 0,25 s no fim da cena para a transição normal do app.

Paleta: igual ao Smart Motion (`GOLD = (255, 215, 69)`, branco, painel escuro `(12, 12, 16)`), fonte Poppins Bold/ExtraBold que já está em `VIDEO_CREATOR_LAB/inputs/fonts`. Fica com cara do canal, não de clip-art.

---

## 2. Onde fica na tela (zonas)

Tela 1080x1920. No F01 a legenda karaokê fica embaixo (`legenda.margem_inferior`, padrão 560).

```
y=0     ┌──────────────────────────┐
        │  margem 140 (UI da rede) │
y=140   │  BARRA DE PROGRESSO      │  ~70 px
y=230   │  TÍTULO da jornada       │  ~80 px (opcional)
y=330   │                          │
        │      CASA EM CORTE       │  área do palco
        │   (câmera anda aqui)     │
y=~1300 │  chão                    │
        ├──────────────────────────┤
        │  LEGENDA (do app)        │  não desenhar nada aqui
y=1920  └──────────────────────────┘
```

Calcule `palco_y1 = altura - margem_inferior - 60` a partir do template (mesma ideia da função `zona()` em `smart_motion.py`). Se o palco ficar com menos de 800 px de altura, use a casa em escala menor (seção 6.4). Se o vídeo for horizontal, não renderize e devolva o aviso "JORNADA só no vertical 9:16" (igual ao Smart Motion faz hoje).

---

## 3. Marcação no roteiro (`marcacoes.py`)

### 3.1 Sintaxe

```
[JORNADA: título opcional | OBJETO: rótulo | OBJETO: rótulo | ...]
[JOURNEY: optional title | OBJECT: label | ...]          (inglês)
```

- 2 a 5 etapas.
- O primeiro campo é **título** se não tiver `:`. Senão é etapa.
- Cada etapa é `OBJETO: rótulo`. `OBJETO` vem do catálogo abaixo (aceitar sem acento e em inglês). `rótulo` tem 1 a 4 palavras e **essas palavras têm que aparecer na fala** (é assim que o app sabe quando acender, igual o FLUXO).
- Se o `OBJETO` não existir no catálogo, usar `PORTA` e avisar: "Objeto 'X' desconhecido na JORNADA: usei PORTA".

### 3.2 Catálogo de objetos (cada um é um cômodo)

| Objeto (pt) | Aliases (en) | O que representa | Interação quando acende |
|---|---|---|---|
| `PORTA` | `DOOR` | entrada, captura de contato, opt-in | porta abre girando na dobradiça, luz quente sai de dentro, boneco entra |
| `PRESENTE` | `GIFT` | isca digital, brinde, amostra | tampa pula, 12 a 18 partículas douradas, brilho radial |
| `ENVELOPE` | `EMAIL`, `MAIL` | sequência de e-mails, nutrição | 3 envelopes caem em sequência numa caixa de correio, contador +1 +1 +1 |
| `TELA` | `SCREEN`, `VIDEO`, `VSL` | vídeo de vendas, aula, conteúdo | TV acende, ícone de play pulsa, barrinha de progresso do vídeo corre |
| `PALCO` | `STAGE`, `WEBINAR`, `LIVE` | webinário, live, apresentação | holofote acende, microfone, selo "AO VIVO" vermelho piscando |
| `CALENDARIO` | `CALENDAR`, `DATA` | data marcada, lançamento, agendamento | folhas do calendário viram até um dia circulado em dourado |
| `RELOGIO` | `CLOCK`, `TIMER` | urgência, prazo, carrinho fechando | ponteiro gira rápido, relógio treme levemente |
| `CARRINHO` | `CART`, `OFERTA`, `OFFER`, `COMPRA` | oferta, checkout, compra | carrinho recebe caixas que caem, check verde |
| `CHAVE` | `KEY`, `ACESSO` | acesso, área de membros, entrega | chave gira numa fechadura, cadeado abre |
| `ESCADA` | `STAIRS`, `UPSELL` | próximo nível, upsell, ascensão | boneco sobe 3 degraus, cada degrau acende |
| `CORACAO` | `HEART`, `FIDELIDADE` | fidelização, comunidade, indicação | coração bate 2 vezes, mini corações sobem |
| `TROFEU` | `TROPHY`, `RESULTADO` | resultado, conquista, final | troféu sobe do chão, confete, boneco comemora |
| `TELEFONE` | `PHONE`, `LIGACAO` | ligação, WhatsApp, atendimento | telefone vibra com ondinhas, balão de mensagem |
| `CASA` | `HOUSE`, `HOME` | casa do cliente (HVAC, serviço em casa) | luz da casinha acende, termômetro sobe/desce |

Implementar como dicionário `OBJETOS_JORNADA = {"PORTA": "door", "DOOR": "door", ...}` em `marcacoes.py`, usando `norm()` para comparar.

### 3.3 Payload gerado por `montar("jornada", campos)`

```python
{
  "title": "O caminho do cliente",          # "" se não tiver
  "steps": [
    {"obj": "door",    "label": "deixa o contato"},
    {"obj": "gift",    "label": "recebe a isca"},
    {"obj": "mail",    "label": "lê seus e-mails"},
    {"obj": "cart",    "label": "compra"}
  ]
}
```

Adicionar em `TIPOS`: `"JORNADA": "journey", "JOURNEY": "journey", "FUNIL": "journey", "FUNNEL": "journey"`.
Adicionar em `NOMES`: `"journey": "Jornada"`.
Atualizar a mensagem de "Marcação desconhecida" para listar JORNADA também.
Erros (`ValueError`): menos de 2 ou mais de 5 etapas; etapa sem rótulo.

---

## 4. Parser e jobs

### 4.1 `app/core/parser.py`

- Aceitar o modo `ANIMACAO` / `ANIMAÇÃO` / `ANIMATION` → `mode = "animacao"`. Hoje a checagem está em `if c.get("mode") and c["mode"] not in ("fala", "dolly", "zoom")`: incluir `"animacao"` e atualizar a mensagem ("use FALA, DOLLY, ZOOM ou ANIMACAO").
- Normalizar o modo sem acento antes de comparar.
- Regras da cena `animacao` (gerar `problemas` claros, em português):
  - precisa ter **exatamente 1** marcação `[JORNADA: ...]` na NARRAÇÃO. Sem ela: "CENA 03 está no MODO ANIMACAO, mas não tem [JORNADA: ...] na narração."
  - não pode ter outra marcação (CONTADOR etc.) junto: as outras são removidas com aviso.
  - `BUSCA:` é ignorada; `IMAGEM:` é opcional.
  - NARRAÇÃO pode ter **até 45 palavras** nessa cena (as outras continuam 12 a 30), porque a jornada precisa de tempo para andar.
- `[JORNADA: ...]` numa cena que **não** é `animacao`: aceitar, mas converter o modo da cena para `animacao` e avisar ("CENA 02 virou MODO ANIMACAO por causa da JORNADA"). Isso evita erro bobo do roteirista.
- Máximo **2 cenas JORNADA por vídeo**; a terceira em diante vira aviso e é ignorada.

### 4.2 Checagem das palavras

Reaproveitar `_chaves()` e `_bate()` de `smart_motion.py` (ou mover para `marcacoes.py`) e checar no parser, antes de gerar, se cada rótulo tem pelo menos uma palavra-chave presente na fala. Se não tiver, aviso amarelo: "JORNADA da cena 03: a etapa 'recebe a isca' não aparece na fala; ela vai acender sozinha por tempo." (Não bloqueia.)

### 4.3 `app/core/jobs.py`

- `check()`: a lista `missing` não deve contar cenas `animacao` (não precisam de imagem).
- `_auto_images()`: pular cenas `animacao` (não buscar Pixabay nem pose do personagem).
- `_build_project()`: passar `mode: "animacao"` e `animacoes` normalmente para o `cenas.json`.
- O chip "🎬 N animações" em `app/static/app.js` já soma `animacoes_total`; conferir que a jornada entra na conta.

---

## 5. Integração com o Smart Motion e o compositor

### 5.1 Registro

Em `smart_motion.py`:

```python
from jornada import draw_jornada, preparar_jornada   # novo módulo
TYPES = {"counter", "bars", "flow", "cards", "keyword", "journey"}
DRAW["journey"] = draw_jornada
DURACAO["journey"] = (4.0, 30.0)
```

E em `checar_payload()` aceitar o tipo `journey` (2 a 5 steps, cada um com `obj` e `label`).

### 5.2 Tempo e zona (diferente das outras animações)

As 5 animações atuais ficam numa faixa e duram uma frase. A JORNADA:

- **dura a cena inteira**: `start = início da cena`, `end = fim da cena - 0,05 s` (pegar de `timeline`/`starts`/`durations`);
- **ocupa o palco inteiro** (seção 2), não a zona pequena;
- tem `priority = 0` (ganha de qualquer outra animação na mesma janela);
- os tempos de cada etapa (`at_ms`) vêm do mesmo algoritmo do FLUXO em `planejar()`: etapa 1 na palavra onde está a marcação; as próximas por `_achar_item(ws, cur, _chaves(label))`. Se não achar, espaçar igualmente entre o início e 85 % da cena.

Implementar isso dentro de `overlays_do_roteiro()`: se `a["tipo"] == "journey"`, chamar `preparar_jornada(a, ws, cena_inicio, cena_fim, zona_palco)` em vez de `planejar()`, e marcar o overlay com `"_zona": zona_palco`. **Não** deixar a regra "uma por vez: a anterior encurta" cortar a jornada: as outras animações não entram em cena `animacao` (o parser já removeu).

### 5.3 `compor_video.py`

Novo ramo no laço das cenas:

```python
elif sc["mode"] == "animacao":
    c.fundo_animacao(seconds, clip)   # novo método do Composer
```

`fundo_animacao` gera um clipe 1080x1920 com:
- gradiente vertical de `(18, 18, 28)` em cima para `(8, 8, 12)` embaixo;
- vinheta suave nas bordas;
- 30 a 40 partículas de poeira dourada bem fracas (alpha 20 a 40) subindo devagar, para a tela nunca ficar morta;
- nada de texto.

A JORNADA (camada com transparência) entra por cima pelo `aplicar_no_filtro` que já existe, antes da legenda. Não precisa de encode extra.

---

## 6. A casa (cenário) — `jornada.py`

### 6.1 Estrutura

- A casa é uma **faixa horizontal longa**: um cômodo por etapa, cada cômodo com **860 px de largura** e **820 px de altura** (escala 1,0). Largura total = `n_etapas * 860 + 2 * 120` (varanda de entrada e saída).
- **Câmera horizontal**: a janela visível tem 1080 px de largura. A câmera segue o boneco com `ease_in_out` (0,6 s de transição) e mantém o boneco a ~40 % da largura da tela. Nas interações, centraliza o cômodo.
- Corte "dollhouse": telhado triangular em cima (contorno branco de 6 px, sem preenchimento ou preenchimento `(255,255,255,12)`), paredes externas em contorno, divisórias internas como linhas finas com uma passagem (vão de porta) embaixo.
- Chão: linha branca de 6 px + faixa `(255,255,255,18)` de 40 px.
- Cada cômodo tem um **papel de parede sutil** diferente (listras, bolinhas, nada) com alpha 10 a 16, só para diferenciar.

### 6.2 Estados de cada cômodo

| Estado | Visual |
|---|---|
| bloqueado (futuro) | interior escurecido `(0,0,0,110)` por cima, ícone de cadeado ou "?" dourado no centro pulsando escala 1,0 ↔ 1,08 a cada 1,2 s |
| ativo (agora) | escuro some em 0,35 s, contorno do cômodo vira dourado 6 px, luz de teto acende (cone de luz `(255,215,69,40)`), objeto faz a interação |
| visitado (passado) | interior normal, contorno branco, check dourado pequeno no canto superior direito |

### 6.3 Cartão de rótulo

- Aparece em cima do cômodo ativo quando ele acende: retângulo arredondado (raio 28), fundo `GOLD`, texto escuro `(12,12,16)`, Poppins ExtraBold 52 px, em MAIÚSCULAS, quebra em até 2 linhas, largura máx. 760 px.
- Entrada: `ease_back` de escala 0,6 → 1,0 em 0,3 s + leve rotação -3° → 0°.
- Número da etapa num círculo escuro colado à esquerda do cartão ("1", "2"...).
- Quando a etapa vira "visitada", o cartão encolhe para 70 % e fica branco com texto escuro (continua legível quando a câmera passa de volta).

### 6.4 Escala

Se o palco tiver menos de 820 px de altura útil, escalar a casa inteira proporcionalmente (mín. 0,7). Desenhar tudo com coordenadas multiplicadas por `s`.

---

## 7. O bonequinho

Desenhado **por código** (linhas e círculos do Pillow), não por imagem. Assim ele anda, pula e comemora sem precisar de nenhum arquivo e fica igual em todo vídeo.

### 7.1 Proporções (escala 1,0)

- Cabeça: círculo raio 34, preenchimento branco, contorno escuro 4 px.
- Olhos: 2 pontos escuros raio 4; piscam (somem por 0,12 s) a cada 2,5 a 4 s (aleatório com `seed` fixo para o vídeo ser reprodutível).
- Tronco: linha branca 12 px, 110 px.
- Braços: 2 segmentos (ombro → cotovelo 55 px, cotovelo → mão 50 px), 10 px.
- Pernas: 2 segmentos (quadril → joelho 65 px, joelho → pé 62 px), 11 px.
- Pontas arredondadas (`joint="curve"` e círculos nas juntas).
- Sombra elíptica no chão `(0,0,0,90)` que encolhe quando ele pula.
- Um detalhe de cor para personalidade: **cachecol ou gravata dourada** (pequeno triângulo `GOLD` no pescoço). Ajuda a reconhecer o "nosso" boneco.

### 7.2 Animações (esqueleto simples, ângulos em graus)

| Ação | Como |
|---|---|
| andar | frequência 2 passos/s; coxa = `28*sin(φ)`, canela = `max(0, 35*sin(φ+90))`; braços em oposição `22*sin(φ+180)`; corpo sobe e desce `6*|sin(φ)|` |
| parado | respiração: tronco escala 1,0 ↔ 1,015 a cada 1,6 s; braços balançando 3° |
| apontar | ao chegar no objeto, braço do lado do objeto sobe até 60° em 0,25 s e fica |
| surpresa | na interação: cabeça sobe 8 px, braços abrem 40° por 0,3 s |
| comemorar | última etapa: 2 pulinhos de 40 px (`ease_out` subindo, gravidade descendo), braços para cima em V |
| subir escada | `ESCADA`: passos com deslocamento vertical de 60 px por degrau |

Velocidade de caminhada: 520 px/s. Se o tempo entre duas etapas for curto, acelerar até 900 px/s e aumentar a frequência dos passos (fica com cara de "correndo", o que também dá energia).

### 7.3 Roteiro de movimento (o que calcular antes de desenhar)

Antes de renderizar, montar uma linha do tempo de ações a partir dos `at_ms` das etapas:

```
t=0          entra pela esquerda (varanda) andando
at[0]-0.6 s  chega na frente do objeto 1 (andar até lá; se não der tempo, correr)
at[0]        interação 1 começa (objeto + cartão + câmera centraliza)
at[0]+1.2 s  vira para a direita e anda até o objeto 2, chegando em at[1]-0.4 s
...
at[n-1]      interação final + zoom de câmera 1.0 → 1.12 + comemorar
fim-0.25 s   fade de saída
```

Função pura `linha_do_tempo(steps_at, duracao) -> list[dict]` com testes (seção 10). O desenho de cada quadro só consulta essa lista: `estado_em(t)` devolve posição x, pose e ação atual.

---

## 8. Objetos e interações (detalhe de desenho)

Todos com contorno branco 5 px, preenchimento escuro `(30,30,42)` e detalhes em `GOLD`. Tamanho base ~220 px de altura. Cada um tem 3 estados: `idle` (balanço leve 2 px), `acao` (a interação da tabela 3.2, 0,8 a 1,4 s) e `feito` (estado final estático).

Exemplos de implementação:

- **door**: retângulo 180x320 com maçaneta dourada. Na ação, desenhar a folha da porta "girando" encolhendo a largura com `cos(θ)` de 0° a 75°; atrás dela um retângulo de luz `(255,215,69,120)` que cresce. Batida de entrada: tremida de 4 px no primeiro 0,15 s.
- **gift**: caixa 170x140 com fita dourada em cruz e laço. Na ação: tampa sobe 70 px e gira 20°, explosão de 16 partículas (estrelas de 4 pontas e círculos) com velocidade radial 600 px/s, gravidade 900 px/s², alpha caindo até 0 em 0,9 s. Brilho radial atrás (círculos concêntricos de alpha decrescente).
- **screen**: TV 260x170 com pé. Na ação: tela vai de preto a gradiente azul-escuro, triângulo de play dourado pulsa 3 vezes, barrinha de progresso branca embaixo corre de 0 a 100 % até a próxima etapa.
- **cart**: carrinho de mercado em linhas. Na ação: 3 caixinhas caem de cima com quique (`ease_back`), depois um check verde `(80,220,120)` aparece num círculo.
- **mail**: caixa de correio com bandeirinha. Na ação: 3 envelopes entram voando em arco, um a cada 0,25 s, bandeirinha levanta, número "+3" em dourado.
- **trophy**: troféu sobe do chão em 0,5 s com `ease_back`, 40 confetes coloridos (dourado, branco, e 2 cores de destaque) caindo com rotação.

Partículas: uma classe pequena `Particulas(seed)` determinística (mesmo vídeo, mesma animação).

Antisserrilhado: desenhar o boneco e os objetos num buffer 2x e reduzir com `Image.LANCZOS`, ou desenhar a cena inteira em 2x se o tempo de render permitir (ver seção 9).

---

## 9. Desempenho e qualidade

- Meta: renderizar a camada da JORNADA em **no máximo 1,5x a duração da cena** num PC comum (cena de 12 s em até 18 s).
- Cachear o que não muda: o cenário da casa inteira (sem objetos e sem boneco) é desenhado **uma vez** numa imagem larga e só recortado pela câmera a cada quadro. Objetos parados também em cache por estado.
- Só o boneco, os objetos em ação, partículas e cartões são redesenhados por quadro.
- 30 fps (usar `tpl["video"]["fps"]`).
- Saída igual às outras camadas: `.mov` `qtrle` com alpha, via `render_camadas()`.
- Determinístico: sem `random` global; usar `random.Random(seed)` com seed vinda do id da cena.

---

## 10. Testes e demo

Criar `VIDEO_CREATOR_LAB/smart_motion/tests/test_jornada.py` (pytest):

1. `extrair()` com `[JORNADA: Título | PORTA: deixa o contato | PRESENTE: recebe a isca]` devolve tipo `journey`, 2 steps, título certo, e o texto limpo sem a marcação.
2. Objeto desconhecido vira `door` com aviso.
3. 1 etapa ou 6 etapas → `ValueError`.
4. Inglês: `[JOURNEY: DOOR: leave your email | GIFT: free guide]` funciona.
5. `linha_do_tempo()` com 4 etapas em 12 s: o boneco chega em cada objeto antes do `at` dele; nunca anda para trás; a última ação é `comemorar`.
6. Parser: cena `MODO: ANIMACAO` sem JORNADA gera problema; cena DOLLY com JORNADA vira `animacao` com aviso.
7. `jobs.check()` não pede imagem para cena `animacao`.

Comando de demonstração (para olhar o resultado sem gerar um vídeo inteiro):

```bash
cd VIDEO_CREATOR_LAB
python smart_motion/jornada.py demo --etapas "PORTA: deixa o contato | PRESENTE: recebe a isca | TELA: assiste o vídeo | CARRINHO: compra" --duracao 12 --out outputs/smart_motion/jornada_demo.mp4
```

Ele deve gerar um MP4 com o fundo da seção 5.3 + a jornada, com as etapas acendendo a cada 2,5 s, e salvar também 4 PNGs (um por etapa) em `outputs/smart_motion/jornada_frames/` para revisão rápida.

### Critérios de aceite

- [ ] Um roteiro F01 com uma cena `MODO: ANIMACAO` + `[JORNADA: ...]` gera o vídeo sem nenhum passo manual.
- [ ] Cada etapa acende no máximo 0,2 s depois da palavra falada.
- [ ] Nada é desenhado sobre a área da legenda.
- [ ] Se o `jornada.py` lançar exceção, o vídeo sai normal (fundo liso) e o aviso aparece no app.
- [ ] Roteiros antigos (sem JORNADA) geram exatamente o mesmo vídeo de antes.
- [ ] O chip de animações do app conta a jornada.
- [ ] Framework F01 atualizado (seção 11) e PDF dos frameworks regenerado com `make_framework_pdfs.py`.

---

## 11. Texto para adicionar ao Framework F01

Adicionar em `app/static/modelos/Framework_F01_Personagem_Falando.md` (e na geração do PDF em `make_framework_pdfs.py`), na lista de MODO e na tabela de animações:

```markdown
  - ANIMACAO: cena de tela cheia com a animação JORNADA (um bonequinho atravessa uma casa em corte; cada cômodo
    é uma etapa). Sem pessoa falando na imagem e sem BUSCA. A NARRAÇÃO tem de 20 a 45 palavras e precisa ter
    uma marcação [JORNADA: ...]. Use no meio do vídeo para explicar um processo, um funil ou a jornada do cliente.
    No máximo 2 cenas ANIMACAO por vídeo.

| `[JORNADA: título | OBJETO: rótulo | OBJETO: rótulo]` | Um bonequinho entra numa casa em corte e passa de cômodo em cômodo; cada cômodo acende quando o seu rótulo é falado, com uma interação (porta abre, presente brilha, carrinho enche). | Funil de vendas, passo a passo, jornada do cliente, antes e depois de um processo. Só em cena MODO: ANIMACAO. | `[JORNADA: O caminho do cliente | PORTA: deixa o contato | PRESENTE: recebe a isca | CARRINHO: compra]` |

Objetos: PORTA (contato, entrada), PRESENTE (isca, brinde), ENVELOPE (e-mails), TELA (vídeo, VSL, aula),
PALCO (webinário, live), CALENDARIO (data, lançamento), RELOGIO (prazo, urgência), CARRINHO (oferta, compra),
CHAVE (acesso), ESCADA (próximo nível, upsell), CORACAO (fidelização, indicação), TROFEU (resultado),
TELEFONE (ligação, WhatsApp), CASA (casa do cliente).
- 2 a 5 etapas. O rótulo tem 1 a 4 palavras e essas palavras precisam ser ditas na fala, na ordem.
- Escreva a fala de modo que cada etapa tenha a sua frase curta ("Primeiro... Depois... Em seguida... No fim...").
```

---

## 12. Como a JORNADA usa as fórmulas narrativas (para escrever roteiros que prendem)

A animação é o "corpo" e a fórmula é o "ritmo". Mapa de uso com as fórmulas do plano editorial (FN01 a FN12):

| Fórmula | Como usar a JORNADA | Objetos sugeridos |
|---|---|---|
| FN02 Lista progressiva | cada item da lista é um cômodo; o melhor fica no último (troféu) | PORTA → ... → TROFEU |
| FN03 PAS (problema → consequência → solução) | 1º cômodo é o problema (RELOGIO tremendo), 2º a consequência, 3º a solução brilhando | RELOGIO → TELEFONE → CHAVE |
| FN05 Storytelling | o boneco é o personagem da história; cada cômodo é uma virada | CASA → TELEFONE → TELA → CORACAO |
| FN07 Antes/depois operacional | duas jornadas em duas cenas: a lenta (sem o produto) e a rápida (com o produto) | — |
| FN09 Curiosidade progressiva | os cadeados com "?" são a alça aberta; a revelação vem no último cômodo | CHAVE como última etapa |
| FN10 Oferta de valor | dor → benefício → próximo passo | PRESENTE → TELA → CARRINHO |
| FN12 Checklist | cada critério um cômodo com check dourado | 3 a 5 etapas |

Funis prontos (para os vídeos sobre tipos de funil):

| Funil | Marcação |
|---|---|
| Isca digital | `[JORNADA: Funil de isca digital | PORTA: deixa o contato | PRESENTE: recebe a isca | ENVELOPE: e-mails | CARRINHO: oferta]` |
| VSL | `[JORNADA: Funil de VSL | PORTA: clica no anúncio | TELA: assiste o vídeo | CARRINHO: compra]` |
| Webinário | `[JORNADA: Funil de webinário | ENVELOPE: se inscreve | CALENDARIO: data marcada | PALCO: aula ao vivo | CARRINHO: oferta]` |
| Lançamento | `[JORNADA: Lançamento | PRESENTE: conteúdo gratuito | CALENDARIO: abertura | RELOGIO: carrinho fechando | CARRINHO: compra]` |
| Perpétuo | `[JORNADA: Funil perpétuo | PORTA: entra todo dia | TELA: assiste | CARRINHO: compra | CORACAO: indica]` |
| Guardian HVAC (exemplo) | `[JORNADA: Depois da instalação | CASA: sistema instalado | TELA: monitoramento | TELEFONE: alerta | CORACAO: cliente fiel]` |

Regras de retenção que a animação já cumpre (não remover na implementação):
- algo novo na tela a cada 1,5 a 3 s;
- curiosidade visível (cômodos trancados) desde o primeiro quadro;
- progresso visível (bolinhas no topo);
- recompensa no fim (troféu/partículas/comemoração);
- a fala manda no ritmo: a animação nunca adianta uma etapa antes de a voz dizer.

---

## 13. Ordem de implementação sugerida

1. `marcacoes.py`: tipo `journey`, catálogo, `montar()` + testes 1 a 4.
2. `jornada.py`: `linha_do_tempo()` + teste 5 (sem desenho ainda).
3. `jornada.py`: boneco andando sobre fundo liso + comando `demo`. Olhar o MP4.
4. Casa, câmera, estados dos cômodos, cartões.
5. Objetos e interações (comece por PORTA, PRESENTE, TELA, CARRINHO; depois os outros).
6. Integração: `smart_motion.py` (registro, zona do palco, duração da cena), `compor_video.py` (`fundo_animacao`).
7. `parser.py` e `jobs.py` + testes 6 e 7.
8. Frameworks (seção 11) e PDF.
9. Gerar um vídeo real de ponta a ponta com o roteiro de exemplo do topo e conferir os critérios de aceite.

---

## 14. Bibliotecas open source (se quiser mais animações prontas depois)

Recomendação para esta versão: **desenhar por código com Pillow**, como o app já faz. Não precisa instalar nada, roda no Windows e fica com o visual do canal. Para crescer o catálogo depois:

| Opção | O que é | Encaixe no app | Cuidado |
|---|---|---|---|
| Lottie + `rlottie-python` | Lottie é o formato de animação vetorial mais usado; `rlottie-python` renderiza um `.json` Lottie em quadros (Pillow) | Bom: daria para criar um tipo `[LOTTIE: arquivo]` que vira camada do Smart Motion | Conferir a licença de cada animação baixada |
| LottieFiles | Milhares de animações Lottie gratuitas (gente, ícones, objetos) | Fonte de arquivos para a opção acima | Cada animação tem a sua licença; ler a política de uso comercial antes |
| Open Peeps (Pablo Stanley) | Biblioteca de pessoas desenhadas à mão, montáveis (corpo, rosto, pose) | Trocar o boneco de palitinho por um personagem desenhado | São ilustrações paradas: a animação continua por código |
| Manim | Biblioteca Python de animação por código (licença MIT) | Possível, mas pesada e com outra forma de renderizar | Exagero para este caso |
| Remotion / Motion Canvas | Animação de vídeo com JavaScript/React | Exigiria Node no app | Remotion exige licença paga para empresas acima de certo tamanho |

Links:
- rlottie-python: https://pypi.org/project/rlottie-python/
- Política de uso comercial do LottieFiles: https://help.lottiefiles.com/commercial-use-guide
- Open Peeps: https://openpeeps.com
