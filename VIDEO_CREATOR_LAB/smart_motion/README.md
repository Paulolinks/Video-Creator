# Smart Motion Overlay Engine (laboratório, Fase 1)

Coloca motion graphics sincronizados com a fala sobre um MP4 já pronto do Video Creator, sem mexer no original.
Plano: `../../PLANO_SMART_MOTION_OVERLAY_ENGINE.md`. Resultado: `reports/BENCHMARK_SMART_MOTION.md`.

## Uso
```bash
cd VIDEO_CREATOR_LAB
V=outputs/videos/entrevista_bob_proctor
python smart_motion/smart_motion.py palavras --ass $V/legenda.ass --de 40 --ate 60   # tempos de cada palavra
python smart_motion/smart_motion.py numeros  --ass $V/legenda.ass                     # números ditos na fala
python smart_motion/smart_motion.py validar  --config smart_motion/configs/bob_C.json --ass $V/legenda.ass --video $V/entrevista_bob_proctor.mp4
python smart_motion/smart_motion.py render   --config smart_motion/configs/bob_C.json --ass $V/legenda.ass --video $V/entrevista_bob_proctor.mp4 --out outputs/smart_motion/bob_C.mp4 --encoder nvenc
python smart_motion/bench.py   # benchmark A/B/C completo
```

## overlays.json
- `profile`: `F01` (zona abaixo da legenda) ou `T02` (zona entre o nome e a legenda), ou uma `safe_zone` explícita.
- `intensity`: `minimal` | `balanced` | `dynamic`.
- Tempo de cada overlay: `start_ms`/`end_ms`, **ou** uma âncora na fala:
  `"start_at": {"word": "CEM MIL", "after_ms": 60000, "occurrence": 1, "offset_ms": -150, "edge": "start"}`.
- Tipos e payload:
  - `counter`: `from`, `to`, `prefix`, `suffix`, `label`, `decimals`, `count_ms`
  - `bars`: `title`, `prefix`, `bars: [{label, value, at}]` (2 a 5 barras)
  - `flow`: `steps: [{label, at}]` (2 a 5 etapas; cada etapa acende na palavra `at`)
  - `cards`: `cards: [{title, text, tone: positive|negative, at}]` (até 2)
  - `keyword`: `text` (1 ou 2 linhas com `\n`), `subtitle`
- Números de `counter` e `bars` precisam ter sido ditos na fala (em dígitos ou por extenso) até 3 s antes ou depois do overlay. Se não foram, a renderização é bloqueada.
- Overlays que se sobrepõem no tempo: fica o de menor `priority`.

## Integração futura (Fase 2)
`aplicar_com_fallback()` devolve o vídeo normal se algo falhar. Para não pagar um segundo encode, a ideia é chamar
`render_camadas()` e encadear os `overlay=` no filtro final do compositor, antes do `subtitles=`.
