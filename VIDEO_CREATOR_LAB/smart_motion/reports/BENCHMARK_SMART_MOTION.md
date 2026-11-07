# Benchmark Smart Motion Overlay Engine — Fase 1

Data: 2026-11-06. Máquina: a do laboratório (mesma que produz os vídeos). Resultados brutos: `bench_resultados.json`.
Quadros início/meio/fim de cada overlay: `reports/frames/*.png` (ficam só no disco local, o `.gitignore` exclui PNG).

## Vídeos usados (reais, já produzidos pelo Video Creator)
| Caso | Vídeo | Duração | Tempo de produção original |
|---|---|---|---|
| T02 | `entrevista_bob_proctor.mp4` (Paulo x Bob Proctor) | 134,5 s | 445 s |
| F01 | `teste_maquiavel.mp4` (personagem falando) | 24,2 s | 206 s |

Os tempos das palavras vêm do `legenda.ass` que o app já gera (tags karaokê `\K`), então não foi preciso rodar o Whisper de novo.

## Variantes
- **A0**: remux sem overlays (`-c copy`)
- **A**: reencode sem overlays (custo base do encoder)
- **B**: 3 overlays (palavra-chave, contador, barras)
- **C**: 5 overlays (B + fluxo de 3 etapas + 2 cards)
- **F01**: 2 overlays (cards + palavra-chave) na zona abaixo da legenda
- **D** (planejamento com Ollama): não executada, é opcional no plano

## Resultados (tempo total em segundos, medido)
| Variante | Encoder | Total | Render camadas | Compor+encode | RAM Python | RAM sistema Δ | VRAM Δ |
|---|---|---|---|---|---|---|---|
| T02 A0 remux | — | 0,2 | — | — | 23 MB | 19 MB | 0 |
| T02 A | x264 medium crf18 | 39,0 | — | 38,6 | 33 MB | 1,09 GB | 0 |
| T02 B | x264 | 48,9 | 2,1 | 46,5 | 42 MB | 1,15 GB | 0 |
| T02 C | x264 | 52,1 | 5,9 | 45,8 | 43 MB | 1,32 GB | — |
| T02 A | NVENC p6 cq19 | 12,7 | — | 12,3 | 32 MB | 0,76 GB | 451 MB |
| T02 B | NVENC | 14,4 | 2,0 | 12,1 | 42 MB | 0,80 GB | 350 MB |
| T02 C | NVENC | 18,1 | 5,8 | 12,0 | 43 MB | 0,86 GB | 277 MB |
| F01 A | x264 | 6,7 | — | 6,4 | 32 MB | 1,05 GB | — |
| F01 2 overlays | x264 | 9,5 | 1,0 | 8,1 | 41 MB | 1,19 GB | — |

A VRAM usada vem do encoder NVENC, não dos overlays (o render dos overlays roda na CPU, com PIL). Durante os testes a placa estava compartilhada com outros processos.

Velocidade de render: cerca de **0,21 s de CPU por segundo de overlay na tela** (C: 27,7 s de overlays renderizados em 5,8 s).

## Verificação das saídas
| Critério | Resultado |
|---|---|
| Original intacto | sim (a saída é sempre um arquivo novo; a engine recusa sobrescrever a entrada) |
| 1080x1920, 30 fps, H.264/AAC | sim, nas 9 saídas |
| Áudio sem perda e sem dessincronização | **stream de áudio bit a bit idêntico ao original** (MD5) em todas as saídas; duração igual |
| Sincronização dos overlays | presos às palavras do karaokê, arredondados para o quadro (≤ 33 ms); mesma precisão da legenda |
| Zona segura | T02: y 280–680 (entre o nome e a legenda); F01: y 1430–1810 (abaixo da legenda). Os quadros conferidos não mostram colisão com rosto, boca ou legenda |
| Dado não sustentado | bloqueado: um contador com 250.000 foi recusado com a lista dos números realmente ditos no trecho (`configs/bob_invalido.json`) |
| JSON inválido | bloqueado com erro claro (ex.: "flow aceita 2 a 5 etapas") |
| Componentes renderizados | 5 de 5 (contador, barras, fluxo, cards, palavra-chave) |

## Quanto aumenta o tempo de produção
| Modo | T02 (vídeo de 134 s, produção de 445 s) | F01 (vídeo de 24 s, produção de 206 s) |
|---|---|---|
| Pós-processamento separado, NVENC (Fase 1) | +14 a +18 s (**+3 a 4%**) | ~+3 s |
| Pós-processamento separado, x264 | +49 a +52 s (+11 a 12%) | +9,5 s (+4,6%) |
| **Integrado na passada final do app (Fase 2)**, NVENC | **≈ +6 s (+1,3%)**: só o render, porque o overlay no NVENC custou ~0 s | — |
| **Integrado**, x264 | ≈ +13 s (+3%): render + ~7 s do filtro overlay | **≈ +2,7 s (+1,3%)** |

O custo de pós-processar é quase todo um **segundo encode do vídeo inteiro**. Integrado, os overlays entram no mesmo `filter_complex` que já queima a legenda (`compor_video.py:178`, `compor_entrevista.py:302`, `compor_entrevista_rapido.py:250`). Assim não há encode extra; sobra o render das camadas, que cresce com o número de segundos de overlay e não com a duração do vídeo.

## Recomendação: **GO** para a Fase 2
Motivos: custo de +1 a 3% integrado, áudio intocado, validação de dados funcionando e zonas seguras calibradas para F01 e T02.

Pendências antes de ligar por padrão:
1. **Planejador automático**: hoje os overlays são escritos à mão em `overlays.json`, ancorados em palavras. Falta gerar uma sugestão automática por regras (números falados → contador/barras; "primeiro/depois" → fluxo; "não X / sim Y" → cards) e, opcionalmente, pelo Ollama com validação.
2. **T02 com personagem ativo**: a zona de cima serve para os dois falantes nos quadros testados, mas falta conferir os retratos mais altos.
3. **Revisão humana**: assistir aos vídeos `outputs/smart_motion/bench/T02_C_nvenc.mp4` e `F01_2ov_x264.mp4` para avaliar legibilidade e ritmo.
