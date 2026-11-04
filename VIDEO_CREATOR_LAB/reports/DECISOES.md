# DECISOES.md — Registro de decisões da direção (Departamento 4)

| Data | Decisão | Base | Consequência |
|---|---|---|---|
| 30/10/2026 | Movimentos de câmera puros (zoom, pan, variações de FFmpeg/Python/MoviePy) **parecem iguais entre si**: não são o diferencial | Avaliação visual dos Blocos A e B | Não investir mais em comparar motores de movimento; o Python subpixel continua como implementação |
| 30/10/2026 | Estilos aprovados: **legenda karaokê**, **zoom 2D** e **2.5D dolly** | Avaliação visual | Entram no template |
| 30/10/2026 | **Formato aprovado: `formato_01_personagem_falando` v1.0**: personagem falando (SadTalker), narração Kokoro, legenda karaokê | Vídeo do Maquiavel | Salvo em `templates/`; gerado com `scripts/gerar_video.py` |
| 30/10/2026 | **SadTalker sem realce (GFPGAN)**: com e sem realce ficaram iguais aos olhos da direção; sem realce leva ~1 min por cena contra ~4,3 min | Comparação `maquiavel_final_com_realce` × `sem_realce` | `realce: null` no template |
| 30/10/2026 | **Música: decisão adiada para o app.** O usuário seleciona a trilha de fundo no aplicativo pronto | Pedido da direção | Template sem música por padrão; o suporte a ducking já está implementado para quando houver arquivo |

| 31/10/2026 | **Template T02 Entrevista implementado (v0.1, aguardando aprovação)** conforme `Video_Creator_Templates_Narrador_Entrevista.pdf`: cada locutor tem fundo, lado e voz próprios; Bob à esquerda/partículas, Paulo à direita/nuvens | Pedido da direção + roteiro `Roteiro_Bob_Proctor_Formato_Padrao.pdf` | `templates/T02_entrevista.json`; `scripts/gerar_entrevista.py`; 2 min 16 s em 7,7 min |
| 31/10/2026 | Voz do Paulo = **clone da voz do próprio Paulo** (Chatterbox, referência do Cutter); voz do mentor = **voz sintética genérica** (Kokoro `pm_santa`), sem imitar a pessoa real; aviso fixo "Dramatização ficcional · vozes sintéticas" + "(DRAMATIZAÇÃO)" no nome do mentor | Regras do PDF e do roteiro | Nunca clonar a voz de terceiros sem autorização |

| 31/10/2026 | **T02 Entrevista aprovado (v1.0)** com ajustes: legenda **karaokê de cor** (estilo da montagem v3, palavra fica dourada ao ser falada) no lugar da caixa amarela | Feedback da direção | `legenda.estilo = karaoke_cor`; o estilo "caixa" continua disponível como opção |
| 31/10/2026 | **Sem aviso de dramatização na tela** e sem "(DRAMATIZAÇÃO)" no nome; só o nome do locutor. Espaço para o **logo do canal** no topo (`rotulos.logo`) | Decisão da direção | Recomendação registrada: marcar "conteúdo gerado/alterado por IA" na plataforma e citar a dramatização na descrição do post |
| 31/10/2026 | Vozes Kokoro recebem **redução de ruído + gate** (o chiado vinha da própria voz `pm_santa`); a voz clonada do Paulo mantém o tratamento original | Medição: SNR da voz do Bob passou de 26 para 35 dB | `voz.tratamento` por motor no template |
| 31/10/2026 | **Não clonar a voz de Bob Proctor** (pessoa real; direitos do espólio/Proctor Gallagher Institute). Upload de voz para clonagem só com autorização do dono da voz | Regra do próprio PDF de especificação | Mentor usa voz genérica, locutor contratado com consentimento ou áudio licenciado |
| — | **Próximos pipelines** (depois): música de fundo escolhida pelo usuário e tratamento de voz configurável no app | Direção | Ducking já implementado no formato 01 |

**Pendências abertas:** pronúncia de "Maquiavel" pelo Kokoro (confirmar com a direção); licença dos componentes de terceiros do SadTalker; próximo teste a definir pela direção.
