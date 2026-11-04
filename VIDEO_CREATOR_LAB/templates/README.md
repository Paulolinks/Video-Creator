# Templates aprovados

## formato_01_personagem_falando (v1.0, aprovado em 30/10/2026)

Personagem falando a partir de uma imagem, narração local e legenda karaokê.

| Parte | Como é feito |
|---|---|
| Cena `fala` | SadTalker 256, `--still`, **sem realce** (o realce GFPGAN custava 4× mais tempo sem diferença visível para a direção) + zoom lento 1,00→1,07 |
| Cena `dolly` | Profundidade 2.5D (Depth Anything V2 Small) com aproximação |
| Cena `zoom` | Zoom 2D subpixel, sem profundidade |
| Voz | Kokoro `pm_alex` (CPU), tratamento "locutor", −14 LUFS |
| Legenda | Karaokê, texto exato do roteiro, tempos via faster-whisper |
| Transição | Dissolve de 0,5 s |
| Música | **Nenhuma por padrão.** O usuário escolhe no app; com arquivo definido em `musica.arquivo`, entra com ducking |

### Como gerar um vídeo

1. Crie uma pasta em `inputs/` com as imagens e um `cenas.json`:
   ```json
   [
     {"id": "CENA_01", "text": "Texto exato da narração.", "image": "inputs/MEU_VIDEO/cena1.png", "mode": "fala"},
     {"id": "CENA_02", "text": "...", "image": "inputs/MEU_VIDEO/cena2.png", "mode": "dolly"}
   ]
   ```
   `mode`: `fala` (rosto humano visível, que vai falar), `dolly` (cena sem fala, com profundidade) ou `zoom`.
2. Rode:
   ```text
   cd D:\Video-Creator\VIDEO_CREATOR_LAB
   python scripts\gerar_video.py inputs\MEU_VIDEO
   ```
3. O vídeo sai em `outputs\videos\MEU_VIDEO\MEU_VIDEO.mp4`, com `relatorio.json` (tempo de cada etapa) e `logs\`.

**Tempo medido** (teste do Maquiavel, 3 cenas, 2 faladas, 24 s de vídeo): **3,4 min**. Voz 12 s, alinhamento 10 s, cada cena falada ~1 min, composição ~1 min.

**Requisitos:** GPU livre (o SadTalker usa ~3 GB de VRAM; feche jogos). Por enquanto usa os motores de voz/Whisper do Video Cutter só para leitura; no app definitivo eles serão empacotados no próprio Creator.
