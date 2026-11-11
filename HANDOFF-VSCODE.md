# Guardian Studio · handoff para integrar no Video Creator

> A versão conferida contra os arquivos reais está em `D:\Video-Creator\guardian-studio\HANDOFF-VSCODE.md`. Use aquela.

Motor de vídeo do modelo Guardian (estilo "kinetic typography" + painéis de UI + transição em blocos). Fica em `D:\Video-Creator\guardian-studio`, separado do app. **Regra do Paulo: não quebrar F01, T02 e T03.** Integrar como template novo, acionado só pela linha FORMATO própria.

## Como funciona hoje
`node scripts\gerar.mjs <nome>` → lê `roteiros\<nome>.txt` → gera voz por fala → monta a linha do tempo → renderiza com Remotion (`src\`, composição `Video`, 1080×1920, 30 fps, H.264) → `videos\<nome>.mp4`.
Tela opcional: `node scripts\servidor.mjs` (http://localhost:5610).

## Formato do roteiro
Cabeçalho opcional: `TITULO:`, `MUSICA: arquivo.mp3` (pasta `musica`), `VOLUME_MUSICA: 0.12`, `VOZ:`.
Cada bloco começa com `FALA: <texto falado>`, seguido de `CENA: <tipo>`, `DESTAQUE: palavra, outra` (ficam azuis) e campos da cena (`chave: valor`; chaves repetidas viram lista). `#` = comentário.
Cenas: contador, tabela, console, contato, termostato, busca, barras, produto, comentario, mapa, imagem, frase. Campos de cada uma: `LEIA-ME.md` e `src\scenes.tsx`. Exemplo completo: `roteiros\dia01.txt`.
Parser: `lerRoteiro()` em `scripts\gerar.mjs` (fácil de portar para Python).

## Onde entra a voz (o ponto de integração)
`config.txt` → `COMANDO_VOZ=<comando> {entrada} {saida}`.
- `{entrada}`: JSON `{"voz": "<personagem>", "linhas": ["fala 1", "fala 2", ...]}`
- O comando deve gravar em `{saida}`: um áudio por fala (`01.wav`, `02.wav`...) e `resultado.json`:
  `[{"audio": "01.wav", "duration": 2.31, "words": [{"w": "You", "t": 0.05}, ...]}, ...]` — uma entrada por fala, na ordem; `t` em segundos, relativo ao início daquela fala.
Ponte atual: `voz\voz_videocreator.py` (Qwen3 clone do Video Creator + faster-whisper). Para trocar de motor de voz, basta outra ponte com o mesmo contrato. Também aceita ElevenLabs direto (`ELEVENLABS_API_KEY`, `VOZ_ID`).

## Linha do tempo (o que o Remotion recebe)
`inputProps = {timeline}`:
```
{fps: 30, total: <frames>, music: {file: "gen/<nome>/musica.mp3", volume: 0.12} | null,
 lines: [{text, hl: [..], scene, params: {..}, start: <frame>, dur: <frames>, audio: "gen/<nome>/01.wav", words: [{w, t}]}]}
```
Arquivos de áudio/música ficam em `public\gen\<nome>\` (caminhos relativos a `public`). Início em 0,4 s, 0,35 s de pausa entre falas, 1 s no fim.
Render: `bundle({entryPoint: 'src/index.ts', publicDir: 'public'})` → `selectComposition({id: 'Video', inputProps})` → `renderMedia({codec: 'h264', ...})`. Por linha de comando: `npx remotion render src/index.ts Video out.mp4 --props=timeline.json` (o JSON deve ser `{"timeline": {...}}`).

## Sugestão de integração (sem risco para F01/T02/T03)
1. No parser do app: um ramo novo `FORMATO: G01`. O parser atual só reconhece blocos `CENA 01 | ...`, então o roteiro G01 (com `FALA:`/`CENA:`) precisa de um caminho próprio.
2. Em `jobs.py`: ENGINE `G01` aponta para um wrapper Python, que gera a voz com o sistema de dublagem do app, grava `resultado.json` no contrato acima e chama `node scripts\gerar.mjs`.
3. Não mexer nos ramos `else` que hoje tratam tudo como entrevista sem antes isolar o G01.
4. Não rodar ao mesmo tempo que outro vídeo do app (mesma GPU).

## Pendência conhecida
A voz em inglês pelo clone Qwen3 saiu com sotaque. Provável causa: referência gravada em português. Testar referência gravada em inglês, outro motor (Chatterbox) ou ElevenLabs.
