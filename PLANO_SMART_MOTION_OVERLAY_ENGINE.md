# SMART MOTION OVERLAY ENGINE — Plano e benchmark isolado V1.0

Status: FASE 1 EXECUTADA (2026-11-06) — ver VIDEO_CREATOR_LAB/smart_motion/reports/BENCHMARK_SMART_MOTION.md. Recomendação: GO para Fase 2. Responsável: Departamento de Vídeo. Intensidade: EQUILIBRADA.

## Objetivo
Adicionar motion graphics sincronizados com a fala em vídeos 9:16 já produzidos, preservando personagem, áudio e legendas. Começar com MP4 pronto, sem alterar o Video Creator, e integrar ao renderizador apenas após aprovação.

## Base existente
Framework F01: personagem falando, cenas FALA/DOLLY/ZOOM, MP4 1080x1920 30fps H.264/AAC, legendas karaokê. Framework T02: entrevistas alternadas, retratos laterais, fundos em loop e legendas karaokê. Ambos exigem evitar colisão com rosto e legendas.

## Limites da Fase 1
- Não editar D:\Video-Creator nem o Video Cutter; não instalar dependências dentro desses projetos.
- Não alterar MP4 original; criar cópia de saída em diretório de laboratório.
- Não chamar API paga; usar roteiro/transcrição local. Primeiro benchmark pode usar timings manuais para isolar custo de composição.
- Nenhum dado financeiro inventado; apenas animar valores expressos na fala ou fornecidos no roteiro.

## Estrutura sugerida
lab-smart-motion/
  inputs/ (video_original.mp4, roteiro.txt ou transcript.json)
  configs/ (overlays.json)
  assets/ (ícones SVG e fontes licenciadas)
  renders/ (camadas temporárias)
  outputs/ (video_motion.mp4)
  reports/ (BENCHMARK_SMART_MOTION.md)

## Componentes MVP
1. Contador (valor, unidade, separadores, início/fim).
2. Barras comparativas (rótulos e valores verificáveis).
3. Fluxo de 2–5 etapas (nós, setas, realce).
4. Cards comparativos (até dois simultâneos).
5. Palavra-chave destacada (uma ou duas linhas).

## Contrato de overlays.json (proposta)
```json
{
  "version": "1.0",
  "canvas": {"width": 1080, "height": 1920, "fps": 30},
  "intensity": "balanced",
  "safe_zone": {"x": 80, "y": 150, "width": 920, "height": 630},
  "overlays": [
    {"id": "ov01", "type": "counter", "start_ms": 2400, "end_ms": 5400,
     "payload": {"from": 0, "to": 10000, "prefix": "$", "suffix": ""},
     "animation": "ease_out", "priority": 1}
  ]
}
```
A safe_zone é inicial e deve ser calibrada com um frame real; nunca assumir que todos os vídeos têm rosto/legenda nas mesmas posições.

## Fluxo técnico
1. ffprobe inspeciona codec, dimensões, FPS, duração, canais e taxa de áudio.
2. Alinhamento da fala: usar timestamps existentes do app quando disponíveis; caso contrário Whisper local; na primeira medição, permitir timestamps manuais.
3. Planejamento: regras determinísticas primeiro; Ollama local opcional gera apenas JSON validado por schema. Nunca executar código arbitrário produzido pelo modelo.
4. Renderizar animações SVG/HTML/CSS por frames com Chromium/Remotion ou motor local equivalente, ou produzir diretamente com FFmpeg para contadores simples. Comparar implementações.
5. Compor a camada visual sobre o MP4 com FFmpeg, preservando áudio e codificando vídeo final. Preferir evitar sobreposição com rosto e legendas; se a legenda já estiver queimada no vídeo, não há como movê-la independentemente.
6. Inspecionar quadros em início/meio/fim de cada overlay e ouvir pontos de sincronização.

## Benchmark controlado
Usar 1 MP4 real autorizado de 30–60s com personagem na metade inferior, preferencialmente acompanhado do roteiro e timestamps. Não há MP4 fornecido neste ambiente: execução depende desse insumo.
- A: controle, remux sem overlays (referência de overhead).
- B: 3 overlays simples (contador, palavra-chave, barras).
- C: 5 overlays mistos (adicionar fluxo e cards).
- D: opcional, mesmo vídeo com planejamento Ollama local e validação de JSON.
Para cada variante: tempo total e tempo por etapa; pico RAM/VRAM/CPU; tamanho MP4; FPS, resolução, codec, sincronização de áudio, legibilidade e colisões; verificar ausência de cortes indevidos. Medir no hardware-alvo, não extrapolar números de outra máquina.

## Critérios de aceite sugeridos
- Original intacto e nenhuma mudança no aplicativo.
- Saída 1080x1920, 30fps, H.264/AAC, sem perda de áudio e sem dessincronização perceptível (meta: erro <= 100 ms nos eventos auditados).
- 100% dos overlays dentro da zona segura aprovada; sem ocultar rosto, boca ou legendas.
- JSON inválido ou dados não sustentados bloqueados com erro claro.
- Pelo menos 3 componentes renderizados corretamente em vídeo de teste.
- Comparativo medido de tempo e recursos entre A, B e C, com capturas de frames.

## Entregáveis da Fase 1
outputs/video_motion_B.mp4 e video_motion_C.mp4; configs/overlays.json; reports/BENCHMARK_SMART_MOTION.md; 3–5 capturas de quadros; recomendação GO/NO-GO para integração.

## Fase 2 — Integração proposta (não executar antes de aprovar)
- Módulo isolado `smart-motion` consumindo roteiro, timestamps e configuração; exporta overlays.json.
- UI: ativar/desativar, intensidade mínima/equilibrada/dinâmica, prévia, ajustar overlays manualmente.
- Pipeline integrado: gerar cenas e motion layers na mesma composição quando suportado, reutilizando biblioteca do benchmark.
- Suporte F01 e T02 por perfis de safe zones; em T02, a posição deve adaptar-se ao personagem ativo.
- Fallback: se Ollama ou render de overlay falhar, entregar vídeo normal sem interromper a geração, registrando o erro.
- Testes regressivos: F01 sem overlays, T02 sem overlays, F01 com overlays, T02 com overlays.

## Próxima ação
Obter MP4 real, roteiro/transcrição e, se disponível, timestamps; inspecionar layout e rodar primeiro A/B/C fora do app. Sem esses arquivos, este documento é plano, não resultado de benchmark.
