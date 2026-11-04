# RELATORIO_AUDITORIA.md — Laboratório Video Creator

**Data:** 30/10/2026 · **Fase:** 1 (auditoria) · **Situação:** nada foi instalado nem alterado. O Video Cutter só foi lido.

Legenda: **[MEDIDO]** = verificado por comando nesta sessão · **[DOC]** = dito por documentação do projeto, não verificado · **[ESTIMADO]** = avaliação técnica sem teste.

## 1. Hardware e sistema [MEDIDO]

| Item | Valor | Observação |
|---|---|---|
| SO | Windows 11 Home 10.0.26200 | |
| CPU | Intel i5-13400F (10 núcleos) | Sem vídeo integrado: encode por hardware só via NVENC |
| GPU | RTX 4060 **8 GB** (8188 MiB), desktop | Driver 610.88 |
| CUDA toolkit (nvcc) | **ausente** | Só wheels pré-compiladas funcionam; compilar extensões (mmcv, kernels custom) vai falhar |
| RAM | **48 GB** (16+8+16+8, DDR5-5600) | **O briefing diz 64 GB; a máquina tem 48 GB.** Isso pesa para modelos com offload na RAM |
| Disco C: | **45,7 GB livres** | O cache do Hugging Face fica em C: → risco de lotar |
| Disco D: | 343,6 GB livres | Onde ficam o laboratório e os modelos |
| Python | 3.11.9 (global), 3.12.14 (via uv) | Sem conda |
| FFmpeg | 7.1 essentials (gyan.dev) no PATH | A cópia do PATH vem de `C:\Users\paulo\Projects\ACE-Step-1.5\tools\ffmpeg` e **não inclui ffprobe**. O Cutter traz outra cópia em `bin/ffmpeg`. Para o produto, convém um FFmpeg próprio e versionado |
| Ocupação da GPU | ~6,9 GB de 8 GB em uso durante o Bloco A | Arc Raiders aberto + NVIDIA Broadcast. **Fechar antes dos blocos B–D** |
| Outros | git 2.45, Node 22.19, VS Code CLI | Node já atende o AI Project Starter |
| Ollama | 0.34, só `qwen3-4b-heretic` (2,5 GB) | Durante a auditoria, `ollama list` iniciou o servidor do Ollama |

## 2. Modelos e ferramentas que já existem na máquina [MEDIDO]

**Cache do Hugging Face** (`C:\Users\paulo\.cache\huggingface\hub`):
- Fala/texto: faster-whisper base/small, Kokoro-82M, Chatterbox, bark, opus-mt (en↔pt), NLLB-600M, wav2vec2.
- Áudio/música: HTDemucs (separação), **ACE-Step 1.5** (geração de música), MiniMax-Music3, CLAP, MERT.
- Vídeo: `Lightricks/LTX-2.5` (também está no cache).

**`D:\LTX - Video Creator`**: clone oficial `Lightricks/LTX-2` (commit de 25/08/2026), `.venv` com torch 2.13 + CUDA 13.2 (**CUDA disponível: sim**), e 67 GB de modelos:
- transformer LTX-2.5 22B distilled **bf16: 42,0 GB**, text encoder Gemma-4 12B bf16: 26,3 GB, VAEs de vídeo/áudio, upscaler x2.
- **[ESTIMADO]** Em bf16, transformer + encoder (68 GB) não cabem nem na RAM (48 GB). Não há registro de que tenha rodado nesta máquina. Só seria viável com checkpoint quantizado (FP8/GGUF) e offload. É um candidato do Teste D, não um recurso pronto.

**Nada encontrado** de SadTalker, LivePortrait, MuseTalk, FramePack, Depth Anything ou ComfyUI.

## 3. Video Cutter

**Cópia ativa:** `C:\dev\Video Cutter` (modificada hoje). Há outras sete cópias antigas (`C:\dev\video-cutter-v8`, `V-Cutter v8.1`, `D:\Download\video-cutter-v7-*` e outras). **Não usa git.** Os backups são pastas em `.backups/`.

**O que existe [MEDIDO no código; o funcionamento é DOC]:**
- App Flask + SocketIO (`app.py`, 470 KB, monolito) e pipeline CLI (`main.py`, 1584 linhas): YouTube → Whisper → seleção de trechos → corte 9:16 → legenda → dublagem → metadados por IA → Drive/Sheets. Também inclui um sistema de licença JWT.
- Camada nova e modular "Local AI Studio" (`services/`, `workers/`, out/2026), mais limpa: `captions.py`, `transcription.py`, `speech.py`, `voice_setup.py`, `media.py`, `storage.py`.
- Ambientes: `.venv` (torch 2.8 **CPU**, moviepy 1.0.3, faster-whisper 1.1.1); `.runtime/voices/kokoro` (CPU, teste de síntese OK); `.runtime/voices/chatterbox` (torch 2.6 cu124, **CUDA disponível**, teste de síntese OK).
- Testes: `tests/test_local_services.py` (o README fala em 16 testes; **não rodei**).
- Arquivos sensíveis na pasta: `.env`, `private.pem`, `token.json`, `cookies.txt`. **Não foram lidos e não devem ser copiados.**

### 3.1 O que o Video Creator faz de diferente do Cutter

| Aspecto | Video Cutter | Video Creator |
|---|---|---|
| Entrada | Link/vídeo longo existente | Roteiro com cenas numeradas + mídias aprovadas (imagem IA, foto, clipe) |
| Quem manda no tempo | O vídeo original; a voz é espremida para caber (dublagem com stretch) | **A narração**: a duração de cada cena sai do áudio gerado ou fornecido |
| Visual | Recorta para 9:16 um vídeo que já se move | **Cria movimento** a partir de imagem estática: Ken Burns, 2.5D, IA. Também cuida das transições |
| Legenda | Transcreve fala desconhecida (pode errar palavras) | O texto já é conhecido (roteiro): só **alinha** ao áudio, sem erro de reconhecimento |
| Seleção por IA | Núcleo do produto (escolher trechos) | Não existe: o roteiro já vem aprovado |
| Música | Pós-processamento opcional | Parte da montagem, com ducking sob a voz |
| Saída | Vários cortes de um vídeo | Um vídeo por roteiro, em lote (ex.: 30 por ciclo) |
| Rastreabilidade | — | Manifesto por vídeo: cena → mídia → origem/licença |
| Publicação | Drive + Sheets | Fora do escopo (você posta) |

### 3.2 O que vale levar (copiar e adaptar; o Cutter nunca é importado nem modificado)

| Peça do Cutter | Uso no Creator | Como levar |
|---|---|---|
| `services/captions.py` (ASS + libass via FFmpeg, `ass_time`, `escape_text`, agrupamento por 6 palavras/pontuação) | Legendas queimadas | Copiar a lógica; trocar a fonte das palavras (roteiro + alinhamento) |
| `services/transcription.py` + faster-whisper com timestamps por palavra (modelos já em cache) | Alinhar o texto do roteiro ao áudio narrado | Reaproveitar a chamada; adicionar o casamento texto↔palavras |
| `workers/speech_worker.py`, `services/speech.py`, `voice_setup.py`, `tools/install_voice_runtime.ps1`, `constraints-*.txt` | Narração TTS (Kokoro pt-BR, Chatterbox com clonagem) | **Mesmo padrão**: motor em venv separado, chamado por subprocess. Os dois runtimes já funcionam e podem ser usados como estão no laboratório |
| `audio_tratamento.py` (EQ de locutor, compressor, de-esser, loudnorm −14 LUFS, mistura de música) | Tratamento da voz e mixagem | Levar as cadeias de filtro; reescrever a parte de pastas e registro |
| `workers/device.py`, `services/media.py` | Escolha de CPU/GPU e localização de binários | Copiar |
| Padrão de `utils_paths.py` (dados do usuário em AppData) | Organização de caminhos | Levar o conceito, sem o código de migração |
| `THIRD_PARTY_NOTICES.md`, `tools/collect_notices.py` | Conformidade de licenças | Reutilizar no build futuro |
| Fontes Anton, Montserrat, Poppins (OFL verificadas pelo próprio Cutter) | Legendas | Levar com os `.txt` de licença |
| `voice_refs/paulo_links*.wav` | Referência de clonagem (sua voz) | Usar nos testes com seu consentimento |

### 3.3 O que é melhor reescrever ou deixar de fora

- **`app.py` / `main.py`**: monolito acoplado a corte de YouTube, licença, Drive e status por arquivo. Não serve de base; o Creator começa com um núcleo pequeno e testável.
- **moviepy 1.0.3 + ImageMagick** (`legenda/legendar_video.py`): substituir por FFmpeg puro, que já é o caminho da camada nova.
- **yt-dlp, seleção spaCy, tradução, metadados por IA, Drive/Sheets, JWT, cookies**: fora do escopo atual.
- **`Musicas/`** (16 MP3 sem procedência registrada) e as fontes sem licença verificada (Loucos, THEQUIR, Typo, Wallman, Active_Heart, bold, new): não usar até confirmar os direitos.
- **XTTS** (`dub_xtts.py`): o próprio Cutter já o tirou do pacote por causa da licença dos pesos.

## 4. AI Project Starter

Versão canônica: `C:\Users\paulo\Desktop\ai-project-starter\ai-project-starter-v2` (remoto `github.com/Paulolinks/ai-project-starter`, último commit em 12/10/2026). O template fica em `kit/`: AGENTS/CLAUDE, `context/`, skills `/kickoff` `/spec` `/implement`, `verify.mjs` e hooks. Exige Node 20+ (presente) e git. **Ainda não foi copiado para `D:\Video-Creator`** (aguarda sua decisão; ver a matriz).

## 5. Riscos identificados

1. **RAM de 48 GB**, não 64: limita o offload de modelos de vídeo grandes.
2. **C: com 45 GB livres** e o cache do HF em C:. Proposta: o laboratório usa `HF_HOME` em D:.
3. **Sem CUDA toolkit**: ferramentas que compilam extensões (MuseTalk via mmcv/mmpose) tendem a falhar no Windows.
4. **Personagem sem rosto**: ferramentas de rosto falante dependem de detectar o rosto. A expectativa (a confirmar) é que falhem no personagem oficial. `personagem_referencia.png` não está em `D:\Video-Creator`.
5. O Cutter não tem versionamento: qualquer cópia de código para o Creator sai de um estado sem histórico.
