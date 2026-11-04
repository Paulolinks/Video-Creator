# MATRIZ_OPEN_SOURCE.md — Matriz de testes (rascunho para autorização)

**Data:** 30/10/2026 · **Fase:** 2 (pesquisa) — versão inicial.

> **Importante:** nada aqui foi medido ainda. Licenças, requisitos e tamanhos vêm da documentação oficial **conforme meu conhecimento prévio** e precisam ser reconfirmados no repositório/model card **no momento de cada instalação**. Isso será registrado em BENCHMARKS_VIDEO.md. Nenhuma ferramenta foi escolhida como vencedora.

## 1. Matriz

| Teste | Ferramenta | O que faz de verdade | Licença código / pesos | VRAM documentada | Download | Risco no Windows/8 GB | Já instalado? |
|---|---|---|---|---|---|---|---|
| A | **FFmpeg** (`zoompan`, `crop`, `xfade`) | Zoom, pan e transições sobre imagem estática | LGPL/GPL (build gyan é GPL) / — | 0 (CPU; NVENC opcional) | 0 | Baixo. `zoompan` treme sem supersampling; testar escala 2–4× antes | **Sim** |
| A | **MoviePy** | O mesmo via Python, quadro a quadro | MIT / — | 0 | ~0 (1.0.3 no Cutter) | Mais lento que FFmpeg. Só entra se trouxer vantagem medida | Sim (no Cutter) |
| B | **Depth Anything V2 Small** | Mapa de profundidade de uma imagem | Apache-2.0 / **Small: Apache-2.0; Base/Large/Giant: CC-BY-NC-4.0 (não comercial)** | ~1–2 GB | ~100 MB | Baixo | Não |
| B | Parallax 2.5D próprio (numpy/OpenCV ou shader) | Deslocamento por camadas de profundidade + câmera virtual | nosso código | ~0–1 GB | 0 | Médio: bordas e "buracos" atrás de objetos exigem inpainting/estiramento | — |
| B | DepthFlow (alternativa pronta) | Parallax 2.5D a partir de profundidade | **AGPL-3.0 (verificar)**: incompatível com app fechado; só como referência | baixa | pequeno | — | Não |
| C | **SadTalker** | Foto + **áudio** → cabeça falante (lábios + movimento de cabeça) | Apache-2.0 / checkpoints próprios + GFPGAN (verificar cada um) | ~4–6 GB | ~2–3 GB | Médio: dependências antigas (torch 1.x/2.0), tem histórico de uso no Windows | Não |
| C | **LivePortrait** | Foto + **vídeo-guia** → transfere expressão/cabeça. **Não faz lip-sync a partir de áudio** | MIT / **detector InsightFace (buffalo_l) é não comercial** | ~4–6 GB | ~1 GB | Baixo/médio. Licença comercial bloqueia sem trocar o detector | Não |
| C | **MuseTalk** | **Vídeo** + áudio → refaz a região da boca. A partir de foto, precisa de um vídeo-base antes | MIT / pesos próprios + sd-vae, whisper, DWPose (verificar) | ~4–8 GB | ~5 GB | **Alto**: mmcv/mmpose precisam de compilação e não há CUDA toolkit | Não |
| D | **FramePack** | Imagem → vídeo (personagem/objeto/ambiente), geração progressiva | Apache-2.0 / **HunyuanVideo: Tencent Hunyuan Community License** (exclui UE/Reino Unido/Coreia; limite de MAU) | **6 GB mínimo** (offload) | ~30–40 GB | Médio: tem pacote Windows; lento em GPU de 8 GB [ESTIMADO: minutos por segundo de vídeo]. Usa bastante RAM | Não |
| D | **LTX-2.5 22B** (já baixado) | Imagem/texto → vídeo com áudio | **LTX-2 Community License** (gratuita abaixo de um teto de receita anual; verificar valor e termos) | bf16 não cabe; precisa FP8/quantizado + offload | 0 já baixados; + checkpoint quantizado (~20+ GB, verificar) | **Alto**: 68 GB bf16 > 48 GB RAM | Parcial (bf16) |
| D | LTX-Video 2B distilled (0.9.x) | Imagem → vídeo, versão leve | LTXV Open Weights License (verificar) | ~8 GB c/ offload | ~6 GB | Médio | Não |
| D | Wan2.2 TI2V-5B | Imagem/texto → vídeo 720p | Apache-2.0 / Apache-2.0 | Oficial ~24 GB; comunidade roda em 8 GB com GGUF/offload | ~10–20 GB | Médio/alto em 8 GB | Não |

**Expectativa para o personagem cósmico (cabeça sem rosto) [ESTIMADO]:** SadTalker, LivePortrait e MuseTalk precisam de landmarks faciais e devem falhar na detecção. Isso será testado à parte e registrado como resultado, não presumido. As alternativas para ele estão no Teste D (movimento de corpo/ambiente) e em efeitos 2.5D (nebulosa pulsando na cabeça).

## 2. Clipes de teste (3–5 s, 9:16, 1080×1920 ou o máximo suportado)

| Piloto | Material | Testes |
|---|---|---|
| VIDEO_001 (Modelo A) | **Uma única imagem-base** IA para todos os motores | A, B, D (C só se houver rosto humano) |
| VIDEO_007 (Modelo B) | 2–3 fotos de banco com licença registrada | A + montagem: narração, legenda, música, exportação |
| VIDEO_019 (Modelo C) | 2–3 clipes de banco | Montagem, corte, sincronia, exportação |
| Rosto | Foto humana autorizada | C (os três) |
| Personagem | `personagem_referencia.png` | C (compatibilidade) e D |

Nenhum roteiro aprovado será inventado: a narração de teste é um texto técnico neutro, identificado como tal.

## 3. Ordem de instalação proposta (cada bloco pede autorização)

| Bloco | O que instala | Disco [ESTIMADO] | Onde |
|---|---|---|---|
| **3a** | venv do laboratório (uv, Python 3.11), opencv, numpy, pillow, psutil, pynvml; script de medição (VRAM/RAM/tempo) | ~1 GB | `D:\Video-Creator\VIDEO_CREATOR_LAB\.venvs\core` |
| **3b** | Depth Anything V2 **Small** (+ torch CUDA) | ~3 GB | `.venvs\depth`, `HF_HOME` em D: |
| **4a** | SadTalker | ~5 GB | `.venvs\sadtalker` |
| **4b** | LivePortrait | ~4 GB | `.venvs\liveportrait` |
| **4c** | MuseTalk (pode falhar por compilação; tempo limitado) | ~8 GB | `.venvs\musetalk` |
| **5** | **um** motor generativo por vez (FramePack, LTX quantizado ou Wan2.2) | 20–40 GB cada | D: |

Regras: um ambiente por ferramenta; nada é instalado no Python global nem nos ambientes do Cutter/LTX; cache de modelos em D:; o Teste A usa só o FFmpeg já existente e não precisa de instalação.

## 4. Medição

Cada execução gera um JSON em `benchmarks/` com: ferramenta, versão/commit, licenças, resolução de entrada/saída, FPS, duração, tempo de processamento, pico de VRAM (amostragem via NVML a cada 0,5 s), pico de RAM (psutil, processo + filhos), GPU/CPU, erros e observação visual. O BENCHMARKS_VIDEO.md é gerado a partir desses JSON, e uma página HTML local mostra os MP4 lado a lado.
