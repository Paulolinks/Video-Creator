# RELATORIO_VIDEO.md

**Projeto:** Dobrando a Realidade — Video Creator  
**Departamento:** 4 — Vídeo e Programação  
**Data:** 30 de outubro de 2026  
**Status:** Plano técnico para aprovação; implementação e benchmarks pendentes  
**Documento-base:** PLANO-MESTRE FINAL — DOBRANDO A REALIDADE + VIDEO CREATOR (30/10/2026)

## 1. Missão e limites

O Departamento 4 é responsável por especificar, testar e desenvolver o **Video Creator**: um aplicativo que recebe roteiros com cenas numeradas e mídias aprovadas, gera ou importa a narração, determina o tempo das cenas pelo áudio, aplica movimentos às imagens ou utiliza clipes, insere legendas e música, e exporta vídeos verticais prontos para revisão humana. A primeira versão prioriza processamento **local**, sem API paga obrigatória.

**Não compete a este departamento:** definir temas e calendário (Marketing), escrever roteiros (Roteiro), criar/aprovar imagens (Arte e direção), vender o produto (Vendas), nem publicar os vídeos. A direção aprova prioridades, materiais e resultados.

**Entregas deste departamento:** este `RELATORIO_VIDEO.md` (especificação, plano e critérios de teste); `BENCHMARKS_VIDEO.md` com medições reais; arquivos MP4 de teste; posteriormente, aplicativo funcional e manual de uso. O `RELATORIO_VENDAS.md` pertence exclusivamente ao Departamento 5.

## 2. Entradas e três modelos de vídeo

O sistema deverá suportar três modelos já previstos no fluxo editorial:

| Modelo | Referência de piloto | Entrada visual | Processamento pretendido |
|---|---|---|---|
| A — imagens geradas por IA | `VIDEO_001` | Imagens criadas e aprovadas manualmente | Movimentos simples, profundidade 2.5D e, se viável, animação generativa opcional |
| B — fotografias selecionadas | `VIDEO_007` | Fotos obtidas de fontes autorizadas, inclusive bancos gratuitos | Enquadramento, movimentos, cortes e transições |
| C — clipes existentes | `VIDEO_019` | Vídeos autorizados e selecionados | Corte, ajuste de duração, enquadramento, transições, voz, legenda e música |

Os IDs acima identificam os **pilotos**, não constituem roteiros finais aprovados. Não presumir temas, textos de narração ou mídias que ainda não tenham sido entregues por Roteiro e Arte. Uma imagem pode ser reutilizada em mais de uma cena, se aprovada.

### Contrato mínimo entre departamentos

Cada vídeo terá `VIDEO_XXX`; cada cena, `CENA_XX`. O pacote de produção deverá conter: ID do vídeo; cenas em ordem; texto exato da narração por cena; referência a arquivos visuais aprovados; tipo de mídia (imagem/clipe); indicação opcional de movimento e de palavras em destaque; referências de licença/procedência; e configurações gerais de saída. **O esquema definitivo de arquivos/JSON será alinhado conjuntamente com Roteiro e Arte**, sem impor um formato incompatível com as entregas já aprovadas.

A duração real da cena deriva da narração gerada/importada e de seu alinhamento, não apenas da duração estimada no roteiro. O aplicativo deve permitir pré-visualização e ajustes antes do lote final.

## 3. Capacidades do produto

### MVP obrigatório

1. Importar pacote de roteiro/cenas e imagens ou clipes aprovados.
2. Validar entradas, formatos, arquivos ausentes e ordem das cenas.
3. Gerar voz em português brasileiro por motor local já validado ou importar áudio gravado.
4. Alinhar narração e texto de cada cena para calcular tempos e legendas.
5. Aplicar movimentos básicos: zoom-in, zoom-out, pan horizontal/vertical, movimento combinado e transições.
6. Montar o modelo C com clipes de vídeo existentes, sem geração de quadros por IA.
7. Inserir legendas legíveis, com estilos configuráveis e margens seguras em 9:16.
8. Escolher música automaticamente de uma biblioteca **com licença/procedência verificada**, com opção de troca, silêncio, volume, fades e redução automática de volume durante a fala (ducking).
9. Exportar MP4 vertical 1080 × 1920, preferencialmente H.264/AAC, e oferecer prévia para revisão.
10. Registrar erros, tempos de renderização e arquivos utilizados; permitir refazer um vídeo sem reconstruir todo o lote.

### Módulos opcionais sujeitos a benchmark

- Profundidade/parallax 2.5D a partir de imagem.
- Retrato humano falante com áudio e movimento facial.
- Geração de clipes a partir de imagem (image-to-video).
- Processamento em lote de aproximadamente 30 vídeos por ciclo, após validação do MVP.

Esses recursos **não são requisitos bloqueantes do MVP**. Se o hardware não entregar desempenho aceitável, o produto continua funcional com o pipeline leve.

## 4. Auditoria informada pelo Claude no VS Code — não verificada independentemente

O executor local informou:

- Windows 11, RTX 4060 com 8 GB VRAM e **48 GB RAM medidos**, divergindo da estimativa anterior de 64 GB.
- Apenas cerca de 45 GB livres em C:, recomendando armazenamento de modelos e caches em D:.
- FFmpeg já instalado; CUDA Toolkit ausente.
- Modelos LTX-2.5 existentes em `D:\LTX - Video Creator` (~67 GB), aparentemente inviáveis em formato integral nesse hardware.
- Video Cutter disponível para leitura, sem alterações; componentes potencialmente reutilizáveis: `services/captions.py`, faster-whisper, Kokoro, Chatterbox, `audio_tratamento.py` e fontes, **sujeitos a testes e verificação de licença**.
- Código e componentes que não devem ser copiados automaticamente: aplicação principal do Cutter, dependência antiga de MoviePy/ImageMagick, músicas sem procedência, recursos de seleção de trechos, Drive, JWT e yt-dlp.
- LivePortrait exige movimento de referência, não recebe apenas áudio para gerar sincronização labial; licenças de dependências faciais exigem auditoria.
- Depth Anything V2 Small foi indicado como candidato comercialmente viável; confirmar licença do código e dos pesos antes de distribuir.

**Fonte dessas observações:** texto da auditoria do Claude reproduzido pelo usuário nesta conversa. O relatório integral `RELATORIO_AUDITORIA.md`, a matriz local e as medições não foram disponibilizados aqui. Não tratar esses itens como testes concluídos ou licenças confirmadas.

## 5. Arquitetura proposta

```text
PACOTE APROVADO (roteiro + cenas + mídias + licenças)
                       |
                       v
              Validação e importação
                       |
                       v
             Voz local / áudio importado
                       |
                       v
           Alinhamento e tempos das cenas
                       |
             +---------+----------+
             |                    |
             v                    v
       Pipeline leve         Módulos opcionais
       FFmpeg/clipes         depth / fala / I2V
             |                    |
             +---------+----------+
                       v
          Composição + legendas + música
                       |
                       v
              Prévia e revisão humana
                       |
                       v
             MP4 vertical + relatório
```

**Separação de responsabilidades no código:** `importacao_validacao`, `narracao`, `alinhamento`, `animacao_basica`, `motores_ia`, `legendas`, `musica_mixagem`, `renderizacao`, `previsualizacao` e `fila_lotes`. Cada motor de animação deverá receber entradas padronizadas e devolver clipes compatíveis com o compositor, para que possa ser substituído sem reescrever o aplicativo.

**Stack inicial proposta:** Python para orquestração; FFmpeg como mecanismo principal de vídeo e áudio; aproveitar motores de voz já instalados quando testados; faster-whisper ou alinhador equivalente para marcação temporal; legendas ASS/libass ou solução equivalente; interface local simples a escolher depois dos benchmarks. MoviePy é opcional, não dependência central. Não exigir serviço externo nem conta paga.

## 6. Laboratório de benchmarks — obrigatório antes da escolha dos motores

### Regras

- Usar ambiente isolado em `D:\Video-Creator\VIDEO_CREATOR_LAB` e preservar o Video Cutter original.
- Testar clipes curtos de **3–5 segundos** antes de produzir vídeos inteiros.
- Reutilizar a mesma imagem-base nos métodos compatíveis, para comparação justa.
- Para ferramentas faciais, usar fotografia **humana autorizada**. O personagem oficial cósmico sem boca deve ser avaliado separadamente, sem inventar feições.
- Confirmar licença de código, pesos, dependências e ativos antes de distribuição comercial.
- Registrar sucesso, falha, comandos, versões, logs e custos de armazenamento.
- Não instalar modelos grandes sem autorização explícita da direção.

### Matriz de testes

| Bloco | Ferramenta candidata | Hipótese a validar | Saída exigida |
|---|---|---|---|
| A | FFmpeg | Movimento simples suficiente para cenas comuns | MP4 com zoom-in, zoom-out, pan e transições |
| B | Depth Anything V2 Small + compositor 2.5D | Parallax agrega profundidade sem custo generativo alto | MP4 parallax e comparação com A |
| C1 | SadTalker | Retrato humano falando a partir de foto + áudio | MP4 com fala, se compatível |
| C2 | MuseTalk | Sincronia labial sobre retrato/vídeo compatível | MP4 e registro de requisitos |
| C3 | LivePortrait | Movimento facial transferido de vídeo de referência | MP4, se licenças e requisitos permitirem |
| D1 | LTX quantizado | Reaproveitar arquivos locais ou pipeline comprimido | MP4 generativo e memória medida, se viável |
| D2 | FramePack | Image-to-video em 8 GB VRAM | MP4 generativo e memória medida, se autorizado |
| D3 | Wan 2.2 5B | Alternativa posterior, somente após checagem de compatibilidade | Pesquisa de viabilidade; teste opcional |

**Ordem:** A → B → C (testes individuais) → D (um motor por vez). A e B são prioritários. A compatibilidade de LTX quantizado não está comprovada; a existência de arquivos grandes em D: não garante que sejam reaproveitáveis.

### Campos de `BENCHMARKS_VIDEO.md`

Para cada execução: data; ferramenta e versão/commit; URL do repositório; licença verificada; GPU/driver; Python/CUDA; arquivo de entrada e direitos; resolução e FPS; duração de saída; tempo total e tempo por segundo de vídeo; pico de VRAM; pico de RAM; armazenamento adicional; resultado/erro; problemas visuais; link/caminho do MP4; observações de instalação; decisão provisória.

**Avaliação visual:** nitidez, fluidez, fidelidade à imagem, preservação do personagem, consistência temporal, sincronização de boca quando aplicável, artefatos e legibilidade em celular. Registrar observação humana separadamente dos números de desempenho.

### Critérios de aceite dos testes

- Todo teste declarado concluído deve ter MP4 reproduzível **ou** registro explícito de falha com logs.
- O bloco A deve demonstrar pelo menos zoom-in, zoom-out e pan, sem cortes pretos ou deformação indevida.
- O bloco B deve demonstrar parallax e registrar artefatos em bordas/oclusões.
- Os blocos faciais devem distinguir sincronização labial por áudio de transferência de movimento por vídeo de referência.
- Os blocos generativos devem registrar a diferença entre tempo real de geração e duração do clipe.
- Nenhum número de tempo, VRAM ou qualidade pode ser preenchido por estimativa como se fosse medição.

## 7. Plano de implementação após os benchmarks

**Fase 0 — Planejamento e aprovação:** validar este relatório, contrato mínimo com Roteiro/Arte, diretórios e material de teste. **Saída:** plano aprovado.

**Fase 1 — Laboratório:** auditoria local, matriz de licenças, testes A–D por prioridade e MP4s. **Saída:** `BENCHMARKS_VIDEO.md`, vídeos e recomendação baseada em medições.

**Fase 2 — Núcleo do MVP:** importação, validação, narração, tempos das cenas, FFmpeg, legendas, música licenciada e exportação. **Saída:** vídeo A e vídeo C completos com mídias aprovadas.

**Fase 3 — Três modelos:** validar também o modelo B; criar prévia e controles mínimos de edição. **Saída:** pilotos A/B/C revisáveis e reproduzíveis.

**Fase 4 — Módulos avançados:** integrar apenas motores que passaram no benchmark, mantendo fallback leve. **Saída:** comparação do mesmo trecho com e sem animação avançada.

**Fase 5 — Lote e robustez:** fila, logs, recuperação de falhas, presets e execução de lote de ~30 vídeos, sem exigir supervisão técnica constante. **Saída:** lote de homologação e instruções de uso.

A aprovação da direção é necessária entre as fases; a fase de laboratório **não autoriza** implementar todo o aplicativo.

## 8. Critérios de aceite do Video Creator

1. Receber um roteiro aprovado com cenas numeradas e mídias correspondentes, sem alterar o texto.
2. Gerar ou importar voz e sincronizar duração das cenas à narração.
3. Produzir MP4 1080 × 1920, 9:16, H.264/AAC, com reprodução correta em celular.
4. Aplicar movimentos de imagem sem deformar o enquadramento principal.
5. Legendas sincronizadas e dentro da área segura.
6. Música de origem autorizada, audível nos intervalos e abaixo da voz durante a fala.
7. Funcionar localmente sem API paga obrigatória.
8. Manter o Video Cutter original intacto.
9. Permitir revisão humana antes da publicação.
10. Registrar dependências e licenças para futura distribuição comercial.
11. Concluir pilotos dos modelos A, B e C com os roteiros e arquivos realmente aprovados.
12. Em lote, falhas de um vídeo não devem invalidar os demais; deve haver opção de repetir apenas os itens com erro.

## 9. Riscos e decisões pendentes

| Questão | Situação | Decisão/ação necessária |
|---|---|---|
| Imagem oficial do personagem | Caminho local não fornecido | Direção indicar `personagem_referencia.png` |
| Imagem-base de `VIDEO_001` | Não fornecida | Arte/direção selecionar arquivo aprovado |
| Foto humana para testes faciais | Não fornecida | Direção fornecer foto com autorização |
| Roteiros finais dos três pilotos | Não disponíveis neste relatório | Receber pacotes aprovados de Roteiro |
| Biblioteca de música | Arquivos existentes sem procedência verificada | Não reutilizar até confirmar direitos; montar biblioteca licenciada |
| Fontes | Licenças locais ainda não verificadas | Conferir antes de empacotar o produto |
| LTX quantizado | Compatibilidade não demonstrada | Pesquisar pipeline e consumo antes de baixar |
| FramePack | Download grande e desempenho desconhecido nesta máquina | Aprovar separadamente após testes leves |
| CUDA/compilação | Toolkit ausente segundo auditoria | Verificar exigências por ferramenta, evitar instalação global desnecessária |
| Esquema final de pacote de vídeo | A alinhar | Acordo Roteiro + Arte + Vídeo |
| Interface e distribuição | Ainda não escolhidas | Definir após MVP e resultados de benchmark |

## 10. Instruções ao executor local (Claude no VS Code)

1. Tratar este arquivo como a **especificação do Departamento 4**.
2. Manter relatórios locais de auditoria e matriz de licenças atualizados.
3. Não atribuir a Vendas a responsabilidade por `RELATORIO_VIDEO.md` ou benchmarks.
4. Executar os testes leves primeiro; obter autorização para downloads pesados.
5. Gerar `BENCHMARKS_VIDEO.md` e MP4s reais; não inventar resultados.
6. Informar caminhos exatos dos arquivos produzidos, tempos e picos de memória.
7. Depois dos benchmarks, apresentar opções técnicas e solicitar escolha/aprovação antes de integrar motores avançados.
8. Preservar os limites dos demais departamentos e não modificar roteiros ou identidade visual sem aprovação.

## 11. Estado atual e próxima decisão

**Concluído segundo a auditoria comunicada:** inspeção inicial e estrutura de laboratório; relatórios locais de auditoria e matriz preliminar. **Não concluído:** benchmarks, MP4s, validação de licenças, escolha de motor e aplicativo funcional.

**Próximo passo recomendado:** autorizar testes A e B, com os materiais disponíveis e direitos verificados; receber `BENCHMARKS_VIDEO.md` inicial e MP4s; só então decidir quais testes avançados e downloads executar. A aprovação deste plano não equivale à aprovação de todos os downloads.

---

**Responsável pela especificação:** Departamento 4 — Vídeo e Programação.  
**Executor técnico local:** Claude no VS Code, sob orientação e aprovação da direção.  
**Responsável por revisão e aprovação:** direção do projeto.
