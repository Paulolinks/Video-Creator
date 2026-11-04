# RELATORIO_ARTE.md

**Projeto:** Dobrando a Realidade + Video Creator  
**Departamento:** 3 — Arte e Criação de Imagens  
**Versão:** 1.0 — planejamento aprovado, contrato técnico provisório  
**Data:** 30 de outubro de 2026

## 1. Missão e limites
Transformar as cenas numeradas dos roteiros aprovados em instruções visuais executáveis: prompts em português para IA, orientações de seleção de fotografias e clipes, referências de continuidade e registro de aprovação. A direção gera ou seleciona as mídias manualmente. Arte não reescreve roteiros, não monta vídeos, não define a tecnologia do aplicativo nem altera a estratégia editorial.

## 2. Bases e decisões
- Plano-Mestre: página piloto Dobrando a Realidade, conteúdo original, mídia aprovada, fluxo Marketing → Roteiro → Arte → Direção → Vídeo.
- Relatório de Roteiro v1.0: 30 vídeos por ciclo, 15–60 segundos, cinco pilares (Manifestação, Mentalidade, Prosperidade, Leis universais, Espiritualidade); 10 vídeos do modelo A (imagens IA animadas depois), 10 do B (fotos de banco), 10 do C (clipes de banco), com dois de cada modelo por pilar. Três pilotos propostos: VIDEO_001 (A), VIDEO_007 (B), VIDEO_019 (C). Ainda não há roteiros finais desses pilotos.
- Decisão da direção: estética **realista predominante**, com tratamento cinematográfico e elementos cósmicos apenas quando agregarem significado; prompts **em português**; revisão **em grupos de vídeos**; personagem cósmico **oficial e recorrente, mas não obrigatório**.
- Formato de composição proposto: vertical 9:16, com área visual livre para legendas e interface da plataforma. Dimensões, codecs e arquivos de ingestão são definidos com Vídeo.
- Primeiro ciclo: descoberta da audiência, sem CTA comercial, conforme relatório de Roteiro.

## 3. Direção de arte
### 3.1 Linguagem
Preferir cenários críveis, iluminação natural ou cinematográfica moderada, texturas realistas, expressões e gestos legíveis, profundidade visual e composição simples. Não confundir consistência com uniformidade: adaptar cenário, ritmo visual e grau de simbolismo à mensagem. Evitar excesso de brilho, saturação artificial, elementos espaciais gratuitos, texto gerado dentro da imagem, alegorias vagas e repetição do mesmo enquadramento.

### 3.2 Personagem oficial
**Referência canônica:** imagem enviada pela direção, preservada como `IDENTIDADE_VISUAL/personagem_referencia.png` (nome provisório). Humanoide de proporções naturais; cabeça oval lisa sem feições, com aparência de galáxias e nebulosas; terno preto elegante com detalhes futuristas discretos; presença enigmática e contemplativa. Cores cósmicas concentradas principalmente na cabeça e em detalhes. Cubo transparente é **acessório opcional**, não traço obrigatório. A referência original deve acompanhar pedidos de geração quando a ferramenta permitir. Descrições textuais isoladas não garantem identidade exata: conferir cada resultado com a imagem canônica.

**Fixos:** silhueta, cabeça sem rosto, textura cósmica, terno preto e proporções. **Variáveis:** local, pose, câmera, ação, objetos e luz. Não inserir o personagem se desviar o foco da cena.

### 3.3 Fotografia e clipes
Nos modelos B e C, buscar cenas reais que transmitam o conceito narrado sem forçar o personagem cósmico. Preferir enquadramentos verticais ou recortáveis; registrar fonte, autor quando disponível, URL, licença/termos, data de consulta e restrições. Não presumir que todo resultado de banco pode ser usado comercialmente. Fotos pessoais e outras mídias autorizadas podem ser incorporadas mediante confirmação de direitos e, quando necessário, consentimento das pessoas retratadas.

## 4. Procedimento por vídeo e cena
1. Receber do Roteiro o ID, pilar, modelo, cenas, narração exata, descrição visual, reuso e movimento sugerido; conferir versão aprovada.
2. Mapear cada cena para um **recurso de mídia** novo ou já existente. Uma imagem pode cobrir várias cenas; não gerar uma mídia por cena automaticamente.
3. Produzir ficha por recurso e mapear todas as cenas que o utilizam. Modelo A: prompt em português, referência canônica se necessária, enquadramento e restrições. Modelo B: termos de busca e critérios fotográficos. Modelo C: termos de busca, movimento e características do clipe.
4. Direção gera ou seleciona manualmente e armazena candidatos. Arte verifica fidelidade ao roteiro, continuidade, composição, qualidade e direitos.
5. Revisar em grupos de vídeos, registrar aprovado/revisar/rejeitado, motivo, versão e mídia selecionada. O tamanho do grupo é operacional e pode variar; não muda a produção mensal em lote único.
6. Entregar apenas mídias aprovadas e seu mapeamento ao Departamento de Vídeo. Se a descrição de roteiro for inviável, devolver a questão à direção/Roteiro; não reescrever silenciosamente.

## 5. Ficha mínima de recurso visual
- `video_id`, `cena_ids` (uma ou várias), `modelo_visual`, `roteiro_versao`;
- `recurso_id` (provisório), `objetivo_visual`, `descricao_visual_original`;
- `tipo_recurso`: imagem_ia | fotografia | clipe | foto_propria | outro_autorizado;
- `personagem_oficial`: sim/não; `referencia_visual`;
- `prompt_pt` (IA) **ou** `termos_busca_pt` (banco); `criterios_selecao`, `restricoes`;
- `composicao_9_16`, `area_legenda`, `movimento_sugerido_do_roteiro`;
- `arquivo_candidato`, `arquivo_aprovado`, `origem`, `licenca_ou_permissao`, `status`, `revisor`, `versao`, `observacoes`.

## 6. Convenção provisória de arquivos
```text
DOBRANDO_A_REALIDADE/
  IDENTIDADE_VISUAL/
    personagem_referencia.png
    GUIA_VISUAL.md
  VIDEO_001/
    prompts/
    referencias/
    candidatos/
    aprovados/
    mapa_midias.md
  VIDEO_007/
    ...
  VIDEO_019/
    ...
  controle_midias.md
```
Identificadores sugeridos: `VIDEO_001`, `CENA_01`, `MIDIA_001`; candidato `VIDEO_001_MIDIA_001_v01.png` e aprovado `VIDEO_001_MIDIA_001_APROVADA.png`. **Não são contrato técnico final.** Vídeo/Programação deve confirmar extensões, dimensões, semântica de versões, localização, estrutura legível por máquina e resolução de referências antes da implementação. Nunca supor que `MIDIA_001` equivale necessariamente a `CENA_01`.

## 7. Aprovação e critérios de aceite
- Cena e mensagem correspondem ao roteiro aprovado, sem acrescentar alegações visuais enganosas.
- Personagem preserva características da referência, quando presente.
- Composição comporta 9:16, legendas e movimentos futuros sem cortar o assunto principal.
- Imagem nítida, coerente e sem deformações, texto acidental ou marcas indevidas.
- Reuso é registrado; não há duplicações desnecessárias.
- Fonte, licença ou permissão de uso estão documentadas.
- Cada cena aponta para mídia aprovada ou reuso explicitamente indicado; não há lacunas.
- Alterações e rejeições ficam registradas; direção aprova o grupo antes do repasse.

## 8. Interfaces entre departamentos
**Marketing:** define pauta, ordem, objetivo, CTA; Arte não altera. **Roteiro:** fornece cenas e intenção; Arte não modifica narração nem duração. **Direção:** escolhe, gera e aprova mídias. **Vídeo/Programação:** confirma formato de entrada/saída, aceita mapeamento cena→recurso, ajusta movimentos, legendas, voz e montagem. O movimento sugerido é orientação, não instrução técnica executável até validação do Vídeo.

## 9. Pilotos e pendências
1. Aguardar roteiros/cenas efetivamente redigidos e aprovados para `VIDEO_001` (A), `VIDEO_007` (B), `VIDEO_019` (C); os títulos e tempos no relatório de Roteiro são propostas, não cenas finais.
2. Validar com Vídeo o contrato de pastas, arquivos, formatos, identificadores, metadados e tratamento de reuso.
3. Definir ferramenta de geração e bancos de mídia durante a execução; verificar termos de uso e disponibilidade, sem exigir API paga.
4. Criar ficha canônica do personagem com a imagem enviada; testar consistência em ângulos/cenários diferentes antes de escalar.
5. Após pilotos, produzir instruções visuais para o restante do lote aprovado; revisar por grupos e entregar o pacote mensal consolidado.

**Estado:** plano operacional consolidado. A produção de prompts definitivos depende dos roteiros aprovados; o contrato técnico depende de Vídeo/Programação.
