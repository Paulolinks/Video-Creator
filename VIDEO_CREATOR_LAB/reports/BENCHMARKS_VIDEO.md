# BENCHMARKS_VIDEO.md

**Projeto:** Video Creator — Laboratório · **Executor:** Claude (VS Code) · **Especificação:** `RELATORIO_VIDEO.md` §6

Legenda: **[MEDIDO]** número saído de execução real nesta máquina · **[OBSERVADO]** inspeção visual do executor (não substitui a avaliação da direção) · **[ESTIMADO]** projeção sem teste.

| Bloco | Situação |
|---|---|
| A — animação simples | **Concluído** (12 MP4 + MoviePy) |
| B — profundidade 2.5D | **Concluído em CPU** (6 MP4). Repetir em GPU com o jogo fechado |
| Codificadores x264 × NVENC | **Concluído** (6 MP4) |
| Montagem completa (voz, legenda, música) | **Concluído** com material de teste (3 MP4) |
| C — rosto falante | **SadTalker concluído** com o roteiro e as imagens do Maquiavel enviados pela direção (2 vídeos finais + 4 clipes). MuseTalk e LivePortrait não testados |
| D — vídeo generativo | Bloqueado: falta escolher o motor e autorizar o download |

**Para assistir:** abra `D:\Video-Creator\VIDEO_CREATOR_LAB\index.html`. Os vídeos estão separados por teste em `outputs/<teste>/`, e as comparações lado a lado, rotuladas, em `outputs/comparacoes/`.

## Ambiente comum [MEDIDO]

| Item | Valor |
|---|---|
| Data | 30/10/2026, 19:10–19:55 |
| CPU/GPU | i5-13400F (10 núcleos/16 threads); RTX 4060 8 GB, driver 610.88; 48 GB RAM |
| **Carga** | **Arc Raiders aberto o tempo todo** (~7 GB de VRAM, GPU em 100%) + NVIDIA Broadcast. Por isso tudo rodou em **CPU**, e os tempos podem estar pessimistas |
| FFmpeg | 7.1 essentials (gyan.dev), cópia do PATH em `C:\Users\paulo\Projects\ACE-Step-1.5\tools\ffmpeg`, sem ffprobe. Licença do build: GPL v3 |
| Python | 3.11.9 global (Bloco A); venv do laboratório `.venvs/lab` (torch 2.15.0+cpu, transformers 4.57.6, OpenCV 5.0.0, MoviePy 2.1.2, Pillow 11.3.0, numpy 2.4.6), com 924 MB |
| Reuso do Cutter | runtime Kokoro e `.venv` (faster-whisper 1.1.1) do Video Cutter, chamados **só para leitura** (`PYTHONDONTWRITEBYTECODE=1`, HF offline). Nada no Cutter foi alterado |
| Medição | `scripts/measure.py`: tempo de parede, CPU, pico de RAM (API do Windows), VRAM (nvidia-smi a cada 0,25 s) |

> **Correção de medição:** na primeira rodada, o pico de RAM do **próprio processo Python** saía errado (os handles do Windows eram truncados no ctypes). O bug foi corrigido, e as linhas do Pillow, do Bloco B e do MoviePy foram **medidas de novo**. As medições do FFmpeg (processos filhos) não foram afetadas.

---

## Bloco A — Animação simples

Entradas: `inputs/teste_*.png`, imagens **sintéticas** 2160×3840 (grade fina + texto). Saída: 1080×1920, 30 fps, 5 s, H.264, sem áudio. Easing smoothstep.

| Clipe | Método | Enc. | Render (s) | s render / s vídeo | CPU (núcleos) | Pico RAM (MB) | Tremor ↓ |
|---|---|---|---|---|---|---|---|
| `zoom_in_ss1` | zoompan 1× | x264 | 2,86 | 0,57 | 7,6 | 824 | 0,153 |
| `zoom_in_ss2` | zoompan 2× | x264 | 3,50 | 0,70 | 7,2 | 815 | 0,093 |
| `zoom_in_ss4` | zoompan 4× | x264 | 5,39 | 1,08 | 5,9 | 847 | 0,054 |
| `zoom_out_ss4` | zoompan 4× | x264 | 5,38 | 1,08 | 5,2 | 846 | 0,054 |
| `pan_h_ss4` | zoompan 4× | x264 | 4,05 | 0,81 | 5,2 | 966 | 0,086 |
| `pan_v_ss4` | zoompan 4× | x264 | 3,83 | 0,77 | 5,4 | 959 | 0,039 |
| `combined_ss4` | zoompan 4× | x264 | 4,87 | 0,97 | 6,4 | 851 | 0,138 |
| `combined_ss4_nvenc` | zoompan 4× | NVENC | 3,22 | 0,64 | 0,9 | 477 | 0,140 |
| `zoom_in_pil` | **Python subpixel** (Pillow Lanczos) | x264 | 14,92 | 2,98 | — | 855* | **0,016** |
| `pan_h_pil` | Python subpixel | x264 | 12,13 | 2,43 | — | 954* | **0,015** |
| `combined_pil` | Python subpixel | x264 | 13,43 | 2,69 | — | 847* | **0,014** |
| `combined_moviepy` | **MoviePy 2.1.2** (`resized(lambda)` + `with_position`) | x264 | **38,05** | 7,61 | 0,9 | 307** | **0,262** |
| `transicoes_fade_slide` | xfade (dissolve + slide), 14 s | x264 | 10,14 | 0,72 | 7,3 | 1594 | — |

\* Soma dos picos do Python e do ffmpeg. \*\* Só o processo Python; o ffmpeg interno do MoviePy não foi incluído.  
**Tremor** (`scripts/jitter_metric.py`): irregularidade da diferença entre quadros consecutivos; **menor = mais suave**. Compara métodos sobre a mesma imagem.  
**Bordas pretas:** nenhuma (luminância mínima das bordas > 26 em todos os clipes).

**Conclusões do bloco A:**
1. O zoompan treme por arredondar o recorte para pixels inteiros. O supersampling ameniza o zoom puro, mas **não resolve zoom + deslocamento** (0,138). **[MEDIDO]**
2. O **recorte subpixel em Python é 3,5 a 10× mais suave** que o zoompan 4×, por ~2,7 s de render por segundo de vídeo, usando poucos núcleos (dá para paralelizar cenas). **[MEDIDO]**
3. **O MoviePy foi o pior em tudo:** o mais lento (38 s) e o mais tremido (0,262), porque posiciona a imagem em pixels inteiros. **Descartado como motor de movimento.** **[MEDIDO]**

---

## Bloco B — Profundidade 2.5D

| Item | Valor |
|---|---|
| Modelo | `depth-anything/Depth-Anything-V2-Small-hf`, 99 MB, snapshot `5426e4f` |
| Licença | **Apache-2.0, conferida no model card baixado** (os modelos Base/Large/Giant são CC-BY-NC, não comerciais, e não foram usados) |
| Dispositivo | **CPU** (a GPU estava ocupada pelo jogo) |
| Entradas | `img102.jpg` (lago, foto) e `img103.jpg` (fitas 3D), da tela de bloqueio do Windows. **Direitos da Microsoft: uso apenas interno de teste**, não usar em conteúdo |
| Técnica | profundidade normalizada, depois dilatação + desfoque nas bordas, depois remapeamento subpixel (OpenCV `remap`, 2 iterações de ponto fixo); pixels próximos se movem/ampliam mais |
| Movimentos | `dolly` (aproximação com profundidade), `orbit` (câmera lateral), `flat_zoom` (referência 2D sem profundidade) |

| Clipe | Profundidade (s) | Render 5 s (s) | Pico RAM (MB)† | Tremor ↓ |
|---|---|---|---|---|
| `lago_dolly` | 1,01 | 14,81 | 1709 | 0,072 |
| `lago_orbit` | 1,01 | 14,99 | 2170 | 0,125 |
| `lago_flat_zoom` | 1,01 | 14,79 | 2116 | 0,041 |
| `fitas_dolly` | 0,95 | 14,26 | 1619 | 0,020 |
| `fitas_orbit` | 0,95 | 16,02 | 2169 | 0,067 |
| `fitas_flat_zoom` | 0,95 | 15,13 | 2071 | 0,017 |

† Pico acumulado do processo (modelo + render) + ffmpeg. Os mapas de profundidade estão em `outputs/depth/*_profundidade.png`.

**Observações:**
- A estimativa de profundidade é **rápida mesmo em CPU** (~1 s por imagem). O custo está na renderização, comparável ao subpixel do Bloco A. **[MEDIDO]**
- Os mapas fazem sentido nas duas imagens: no lago, o céu fica distante e a água se aproxima gradualmente; nas fitas, as camadas aparecem separadas. Na órbita, a margem se desloca em relação ao sol, e não vi rasgos nas miniaturas. **[OBSERVADO]**
- Nas cenas 2.5D, o "tremor" mede outra coisa: partes da imagem se movem em velocidades diferentes de propósito. **Não compare esse número com o do Bloco A.** O valor mais alto do lago vem das áreas lisas (céu e água), onde a diferença entre quadros é pequena e ruidosa.
- **Pendente:** avaliação visual da direção nas bordas (montanha contra céu, fita contra fundo); repetir em GPU; testar com o personagem e com fotos de pessoas, onde os halos nas bordas costumam aparecer.

---

## Codificadores — x264 × NVENC

Referência sem perdas (FFV1) do mesmo movimento sobre a foto do lago; SSIM e PSNR contra ela. 150 quadros 1080×1920.

| Variante | Tempo (s) | Velocidade (fps) | CPU (núcleos) | Tamanho (MB) | SSIM ↑ | PSNR (dB) ↑ |
|---|---|---|---|---|---|---|
| x264 CRF18 medium | 2,16 | 69 | 9,2 | 1,00 | 0,9945 | 50,35 |
| x264 CRF23 medium | 1,75 | 86 | 8,8 | 0,46 | 0,9932 | 49,46 |
| x264 CRF18 veryfast | 1,13 | 133 | 7,3 | 0,62 | 0,9940 | 49,86 |
| **NVENC CQ19 p5** | 1,22 | 123 | **3,8** | 1,14 | **0,9949** | 50,52 |
| NVENC CQ23 p5 | 1,42 | 106 | 4,1 | 0,58 | 0,9942 | 50,12 |
| NVENC CQ19 p7 hq | 2,22 | 68 | 2,6 | 1,16 | 0,9949 | 50,56 |

**Conclusão:** nesta foto (lisa, com gradientes), **todos ficaram visualmente equivalentes** (SSIM ≥ 0,993). O NVENC CQ19 teve qualidade igual ou melhor com metade da CPU. No conteúdo com textura fina do Bloco A, porém, o NVENC gerou um arquivo 67% maior (9,7 MB contra 5,8 MB). **Recomendação provisória:** NVENC CQ19 p5 para a exportação final, quando a GPU estiver livre, e x264 CRF18 como alternativa garantida. **[MEDIDO]**

---

## Montagem completa — fluxo do Video Creator

Material: 4 cenas com **texto técnico neutro, identificado como teste** (`inputs/cenas_teste_montagem.json`), sem roteiro aprovado. Imagens: fotos do Windows (uso interno). Música: **pad sintético gerado pelo próprio FFmpeg** (direitos próprios), porque as músicas do Cutter não têm procedência verificada.

| Etapa | Ferramenta | Resultado [MEDIDO] |
|---|---|---|
| Narração | Kokoro 82M, voz `pf_dora`, CPU, runtime existente do Cutter | 4 frases em **8,7 s** (carga do modelo 4,0 s + ~1,2 s por frase); 12,7 s de áudio; pico de 1247 MB |
| Alinhamento | faster-whisper small int8, CPU, texto do roteiro casado com os tempos reconhecidos | **34 de 37 palavras casadas**, o restante interpolado; 12,2 s; 868 MB. O Whisper ouviu "videocreator" e "Fela" (no lugar de "fala"), mas a legenda usa o texto do roteiro, então o erro não aparece. **Verificar se o Kokoro pronunciou "fala" corretamente** |
| Tempo das cenas | duração da narração + 0,45 s de respiro (+0,25 s antes da 1ª frase) | 3,43 / 3,98 / 3,63 / 3,70 s, total de **14,73 s** |
| Movimento | Python subpixel (zoom-in, pan vertical, combinado, zoom-out) | 43,8 s para as 4 cenas, em série, sem paralelismo |
| Transições | xfade dissolve de 0,4 s, iniciando no limite de cada cena | 5,5 s |
| Voz | cadeia "locutor" do `audio_tratamento.py` do Cutter + loudnorm −14 LUFS | — |
| Ducking | `sidechaincompress` (limiar 0,02, razão 8) | **Música −22,0 dB durante a fala**, −5,8 dB nos intervalos (trilhas isoladas, janelas de 50 ms) |
| Legenda | ASS/libass, Poppins Bold (OFL) 84 px, até 3 palavras, maiúsculas, a ~70% da altura | Simples e karaokê (palavra fica dourada ao ser falada) renderizaram com acentos corretos **[OBSERVADO]** |
| Exportação | x264 CRF18 + AAC 192k | ~6,5 s por versão; **−14,0 / −14,1 / −14,1 LUFS**, pico de −0,8 dBFS |
| **Total** | | **~70 s de processamento para 14,7 s de vídeo** (sem contar o TTS e o alinhamento, que somam ~21 s) |

Versões para comparar (`outputs/montagem/`):
- `montagem_v1_sem_ducking_legenda_simples.mp4`: música no mesmo volume o tempo todo.
- `montagem_v2_com_ducking_legenda_simples.mp4`: música abaixa sob a voz.
- `montagem_v3_com_ducking_legenda_karaoke.mp4`: idem, com destaque palavra a palavra.

**Projeção [ESTIMADO, não testado]:** com as cenas renderizadas em paralelo (4 processos), um vídeo de 60 s levaria ~1,5–2 min, e um lote de 30 vídeos, ~1 hora.

---

## Bloco C — Personagem falando (SadTalker) + vídeo do Maquiavel

**Feedback da direção (30/10):** os movimentos de câmera ficaram parecidos entre si; o que interessa é o personagem **falando**. A legenda karaokê, o zoom 2D e o 2.5D dolly foram aprovados como estilo.

| Item | Valor [MEDIDO] |
|---|---|
| Ferramenta | SadTalker, commit `cd4c046` (11/10/2023), `github.com/OpenTalker/SadTalker`. Licença Apache-2.0; o LICENSE cita componentes de terceiros sem listá-los. Realce: GFPGAN v1.4 (Apache-2.0). Dependências: basicsr e facexlib (Apache-2.0), face-alignment (BSD) |
| Ambiente | `.venvs/sadtalker`: Python 3.10, torch 2.1.2 + CUDA 12.1, numpy 1.23.5, setuptools < 70. **5,0 GB** + modelos 2,4 GB em `tools/SadTalker` |
| Problemas de instalação | Uma conexão caiu num download (refeito); faltava `pkg_resources` (corrigido com setuptools). Nenhuma compilação foi necessária |
| Entradas | Imagens da direção (941×1672, geradas por IA) + narração Kokoro `pm_alex` com o texto exato do roteiro |
| Configuração | `--preprocess full --still --size 256`; com e sem `--enhancer gfpgan` |
| GPU | Jogo **fechado** neste teste (baseline de 2,3 GB de VRAM) |

| Clipe | Fala | Tempo | VRAM | RAM do sistema |
|---|---|---|---|---|
| Cena 1, sem realce | 7,75 s | **54,9 s** | +2,9 GB (pico 5,3 GB) | +2,8 GB |
| Cena 1, com realce | 7,75 s | **262 s** | +3,1 GB (pico 5,4 GB) | +5,5 GB |
| Cena 3, sem realce | 7,45 s | 59,0 s | +2,9 GB | +2,4 GB |
| Cena 3, com realce | 7,45 s | 254 s | +3,1 GB | +5,4 GB |

Dentro do SadTalker, a animação do rosto leva ~28 s; o GFPGAN leva ~1 s por quadro e responde por ~80% do tempo. A saída com realce vem ampliada 2× (1888×3344, 25 fps).

**Observado:** boca abre e fecha acompanhando a fala, há piscadas e leves movimentos de cabeça, e a identidade do rosto se mantém. Com `--still`, o corpo e a mão ficam parados. **Falta a avaliação da direção:** naturalidade da boca, sincronia e qualidade com e sem realce.

**Vídeo final** (`outputs/maquiavel/`): 24,1 s, 1080×1920 30 fps. Cenas 1 e 3: SadTalker com zoom lento subpixel. Cena 2: 2.5D dolly. Transições dissolve de 0,5 s, legenda karaokê, ducking. Loudness: −13,5 LUFS. A montagem levou ~61 s, mais o tempo do SadTalker (2 × ~1 min sem realce, ou 2 × ~4,3 min com realce).

**Alertas:**
- O Whisper reconheceu "Maquiavel" como "mas que a véu". A legenda está certa (vem do roteiro), mas é preciso **ouvir se o Kokoro pronuncia bem o nome**.
- A música ainda é o pad sintético, porque não há biblioteca licenciada.

## Decisões provisórias (aguardam sua avaliação visual e sonora)

| Tema | Recomendação | Base |
|---|---|---|
| Motor de movimento | Python subpixel (Pillow/OpenCV) + FFmpeg só para codificar | Bloco A |
| MoviePy | Não usar | Bloco A: mais lento e mais tremido |
| Profundidade 2.5D | Viável e leve (Small, Apache-2.0); módulo opcional por cena | Bloco B, pendente de avaliação das bordas |
| Transições | FFmpeg xfade | Bloco A / montagem |
| Exportação | NVENC CQ19 com GPU livre; x264 CRF18 como alternativa | Codificadores |
| Voz | Kokoro (CPU) já serve para o MVP; Chatterbox (clonagem, GPU) a testar com a GPU livre | Montagem |
| Legenda | Texto do roteiro + tempos do Whisper; ASS/libass | Montagem |
| Ducking | sidechaincompress; ajustar intensidade depois de ouvir (−22 dB pode ser demais) | Montagem |

## Limitações

- Uma execução por variante, com o jogo aberto; tempos sem média de repetições.
- Bloco A com imagens sintéticas; Bloco B e montagem com fotos do Windows, **que não podem ir para conteúdo publicado**.
- Chatterbox, GPU para profundidade, rosto falante (C) e vídeo generativo (D) **não foram testados**.

## Reprodução

```text
cd D:\Video-Creator\VIDEO_CREATOR_LAB
python scripts\make_test_images.py inputs
python scripts\run_test_a.py
cd scripts && python pil_motion.py combined A_azul combined_pil && cd ..
python scripts\jitter_metric.py benchmarks outputs\ffmpeg\<clipe>.mp4
set HF_HOME=D:\Video-Creator\VIDEO_CREATOR_LAB\.cache\hf
.venvs\lab\Scripts\python.exe scripts\run_test_b.py C:\Windows\Web\Screen\img102.jpg lago 0.5
python scripts\run_encoder_test.py
"C:\dev\Video Cutter\.runtime\voices\kokoro\Scripts\python.exe" scripts\tts_kokoro.py inputs\cenas_teste_montagem.json outputs\montagem\audio pf_dora
"C:\dev\Video Cutter\.venv\Scripts\python.exe" scripts\align_whisper.py inputs\cenas_teste_montagem.json outputs\montagem\audio\tts.json outputs\montagem\audio\alinhamento.json
.venvs\lab\Scripts\python.exe scripts\montagem.py inputs\cenas_teste_montagem.json
python scripts\make_comparisons.py && python scripts\build_report.py
```
Dados brutos: `benchmarks/*.json`. Logs: `outputs/*/*.log`.
