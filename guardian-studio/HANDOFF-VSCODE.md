# Guardian Studio · handoff para integrar no Video Creator

Motor do modelo Guardian em `D:\Video-Creator\guardian-studio`, separado do app. Regra: não quebrar F01, T02 e T03. Integrar como template novo, acionado só pela linha `FORMATO:` própria.

## Como funciona hoje
`node scripts\gerar.mjs <nome>` lê `roteiros\<nome>.txt`, gera a voz por fala, monta a linha do tempo e renderiza com Remotion (`src\`, composição `Video`, 1080x1920, 30 fps, H.264) em `videos\<nome>.mp4`. Sem nome, gera os roteiros que ainda não têm vídeo.

O render é feito pela API do Remotion dentro do `gerar.mjs`, não por `npx remotion render`. O `npx remotion studio src/index.ts` (`estudio.bat`) é só prévia e mostra uma cena de exemplo.

Tela opcional: `abrir-tela.bat` ou `node scripts\servidor.mjs` (http://localhost:5610, só 127.0.0.1).

## Formato do roteiro
Cabeçalho opcional: `TITULO:`, `MUSICA: arquivo.mp3` (pasta `musica`), `VOLUME_MUSICA:`, `VOZ:`. Cada bloco: `FALA: texto`, `CENA: tipo`, `DESTAQUE: a, b` e campos da cena (`chave: valor`; chaves repetidas viram lista). `#` = comentário.

Cenas: contador, tabela, console, contato, termostato, busca, barras, produto, comentario, mapa, imagem, frase. Campos no `LEIA-ME.md` e em `src\scenes.tsx`. Exemplo: `roteiros\dia01.txt`. Parser: `lerRoteiro()` em `scripts\gerar.mjs`.

## Ponto de integração da voz
`config.txt`: `COMANDO_VOZ=<comando> {entrada} {saida}` e `VOZ_PERSONAGEM=<id>`. O motor externo tem prioridade sobre ElevenLabs (`ELEVENLABS_API_KEY`, `VOZ_ID`, `MODELO`).

- `{entrada}`: JSON `{"voz": "<personagem>", "linhas": ["fala 1", ...]}`.
- O comando grava em `{saida}`: `01.wav`, `02.wav`... e `resultado.json` = `[{"audio": "01.wav", "duration": 2.31, "words": [{"w": "You", "t": 0.05}]}]`, uma entrada por fala, na ordem, com `t` relativo ao início da fala.
- Ponte atual: `voz\voz_videocreator.py`, rodada com o python de `VIDEO_CREATOR_LAB\.venvs\lab`. Usa o motor de `scripts\motor_clone.py` (`ATIVO = "qwen3"`), `voz.referencia` de `app\data\personagens\<id>\item.json` e `scripts\align_whisper.py` (faster-whisper). Idioma fixo em inglês (`IDIOMA`). Normaliza cada fala para -14 LUFS com o `ffmpeg` do PATH.
- Outro motor = outra ponte com o mesmo contrato.
- A voz é reaproveitada se `public\gen\<nome>\linhas.json` não mudar. Para refazer com o mesmo texto, apague o `resultado.json` dessa pasta.

## Linha do tempo do Remotion
`inputProps = {timeline: {fps: 30, total, music: {file, volume} | null, lines: [{text, hl, scene, params, start, dur, audio: "gen/<nome>/01.wav", words}]}}`. Tipos em `src\Video.tsx`. `start` e `dur` em frames. Áudios em `public\gen\<nome>\`. Início 0,4 s, pausa 0,35 s entre falas, 1 s no fim. Render: `bundle` → `selectComposition({id: 'Video', inputProps})` → `renderMedia({codec: 'h264'})`.

## Sugestão de integração (ainda não feita)
1. `app\core\parser.py`: incluir o template em `TEMPLATES` (linha 25) e um ramo `FORMATO: G01` antes da linha 197. O `t02 and not f01` só captura blocos `CENA 01 | ...`. Um roteiro Guardian usa `FALA:`/`CENA: tipo`, então hoje sai sem template e sem cenas. O ramo precisa extrair as falas.
2. `app\core\jobs.py`: `ENGINE` (linha 22) chama um script **Python** (`sys.executable`, linha 392) com `<projeto> <template.json> <saida>`, e o app procura o `.mp4` em `<saida>` (linha 414). Criar um wrapper Python que copie o roteiro para `roteiros\`, rode `node scripts\gerar.mjs <nome>` e copie o `.mp4` para `<saida>`. A voz já sai pela ponte, sem etapa extra no app.
3. Isolar o G01 antes dos ramos que tratam tudo que não é F01 como entrevista: `check`, `analyse`, `_build_project` (linha 199), `_run` (linha 371) e `estilos.apply` (o `else` da linha 97 usa `retrato` e `onda`). Também `gdrive.py:144` e os cartões em `static\index.html` e `app.js`.
4. Não rodar junto com outro vídeo: mesma GPU, e a voz clonada usa cerca de 3 a 4 GB de VRAM.

## Pendência
Foi relatado sotaque na voz em inglês do clone Qwen3 (`paulo_maquiavel`). O trecho de referência usado pelo motor está em português, a causa provável. Testar referência em inglês, Chatterbox (`ATIVO` em `motor_clone.py`, muda também o Video Creator) ou ElevenLabs.
