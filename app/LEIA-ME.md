# Video Creator: app local (v0.2)

Roteiros entram, vídeos verticais saem. Roda no seu computador, sem API paga.

## Abrir e fechar
- **Abrir:** dê dois cliques em **`iniciar.bat`**. O navegador abre em http://127.0.0.1:5600. Se o app já estiver aberto, o navegador só é aberto de novo.
- **Fechar:** feche a janela preta ou dê dois cliques em **`parar.bat`**.

Mais detalhes em [`../README.md`](../README.md).

## Tela inicial (Social Video Creator)
O painel em forma de placa tem 4 passos e o botão redondo **Iniciar criação** embaixo. O botão **⏻ Modo tradicional**, no topo da placa, desliga a placa e mostra a tela antiga (enviar roteiros, lista **Identificado** com música e fundos logo abaixo, botão **Gerar vídeos**). Para voltar, clique em **Ligar a placa**. O app lembra o último modo usado. No modo tradicional os vídeos saem no formato aprovado (vertical, legenda Poppins dourada).
1. **Template**: escolha um (Personagem falando ou Entrevista com mentor). Um roteiro do outro template aparece na lista, mas fica desmarcado.
2. **Roteiro**:
   - **Personagem falando:** **Escolher pasta**, com o roteiro e as imagens numeradas (`cena1.png`, `cena2.png`...). Cada pasta é um episódio. Escolha outra pasta para somar mais episódios, ou uma pasta com várias pastas dentro.
   - **Entrevista com mentor:** **Escolher arquivos** ou colar o texto. Cada roteiro vira um vídeo.

   O que você escolhe se soma à lista até clicar em Iniciar criação (**Limpar lista** começa de novo). Assim que os roteiros são lidos, abre a janela **Roteiros identificados**: template, título, cenas, personagens (verde = cadastrado; vermelho = falta cadastrar, com o botão **cadastrar**) e pendências. Depois de fechar, o botão **Ver roteiros** abre a janela de novo.
3. **Formato**: **Vertical 9:16** (Shorts, Reels, TikTok; 1080×1920) ou **Horizontal 16:9** (YouTube; 1920×1080). No horizontal a capa também sai 16:9, com o título à esquerda e o mentor à direita. As imagens das cenas do Personagem falando devem ser deitadas (16:9); imagens em pé são cortadas no meio.
4. **Legenda**: tipo de letra, tamanho, cor da palavra falada e cor do resto do texto, com prévia ao lado. **Voltar ao padrão** volta para Poppins 84, dourado sobre branco. As escolhas ficam salvas no navegador.

Em **⚙️ Opções avançadas** ficam a música de fundo, o volume e o fundo de cada personagem. Durante a geração a placa acende, e a barra embaixo dela mostra o vídeo e a etapa atual.

**Processos em andamento:** enquanto algo está sendo feito, um retângulo neon flutua no pé da página, em todas as abas, com a engrenagem girando. Ele mostra, por exemplo, "Criando vídeo 2 de 5 · título · etapa", "Enviando para o Drive 1 de 3" ou "Gerando metadados 1 de 4". Ele não trava a tela: dá para mudar de aba e continuar usando o app. Clique nele para abrir Vídeos criados. Quando o processo termina, ele mostra "✓ concluído" por alguns segundos e some. Enquanto houver processo, a bolinha **Iniciar criação** fica girando e pulsando.

**Gerar metadados** (em cada lote, na aba Vídeos criados) preenche a descrição e as hashtags que estiverem vazias. Se todos os vídeos já tiverem, ele pergunta se deve gerar de novo para todos.

## Fluxo
1. **Criar vídeos**: cole o roteiro que o ChatGPT devolveu em **Colar roteiro**, ou arraste roteiros `.txt`/`.md`/`.pdf` (ou uma pasta). Cada roteiro vira um vídeo. O formato recomendado é o texto simples do framework (`TÍTULO:` ... `CENA 01 | ...` ... `FIM`); o PDF do framework é só o modelo e não deve ser enviado. O app identifica:
   - o template, pela linha `FORMATO:` (`PERSONAGEM_FALANDO` = Formato 01; `ENTREVISTA_COM_MENTOR` = T02);
   - o título, as cenas e os personagens;
   - pendências: personagem não cadastrado, imagens faltando, roteiro fora do padrão ou com campos `<...>` não preenchidos.
2. Escolha a **música de fundo** e o **fundo de cada personagem** (Entrevista). Clique em **Gerar vídeos**.
   - **Música:** sem música (padrão), **Música do personagem** (rodízio entre as 3 dele), uma específica ou uma aleatória. O volume padrão é 10%, e a música abaixa sozinha durante as falas.
   - **Fundo:** **Rodízio automático** (cada vídeo usa o próximo dos 3 fundos do personagem) ou um fundo fixo.
3. **Fila**: os vídeos são gerados um por vez, com a etapa atual. Quando terminam, aparecem as opções **Assistir**, **Abrir pasta** e **Baixar capa**. Quando o vídeo tem música, aparece também o crédito para colar na descrição.

## Capa (thumbnail)
Todo vídeo gera uma `capa.png` no tamanho do vídeo (1080×1920 ou 1920×1080) ao lado do `.mp4`. Há dois modelos de capa, escolhidos sozinhos pelo roteiro:
- **Modelo 1 (vídeo avulso):** o de sempre. Vale quando o roteiro não tem as linhas `SÉRIE:` e `EPISÓDIO:`, quando elas estão vazias ou quando só uma está preenchida.
- **Modelo 2 (série):** quando `SÉRIE:` e `EPISÓDIO:` estão preenchidas (ex.: `SÉRIE: Playbook Flávio Augusto` e `EPISÓDIO: 1 de 9`; também aceita `1/9`). A capa ganha, acima do título, o nome da série em branco e a etiqueta amarela "EPISÓDIO 1 DE 9". O título fica um pouco menor para caber. A janela de roteiros identificados mostra 📺 com a série e o episódio, e os vídeos avulsos aparecem como "Vídeo avulso (capa normal)".

Os dois modelos de capa seguem estas regras de layout:
- **Entrevista:** o fundo e o mentor embaixo, o título do roteiro grande em cima (na cor escolhida) e o nome do mentor.
- **Formato 01:** a imagem da primeira cena, com o título por cima.

**Cor e letra do título (passo 5 da página inicial, "Título da capa"):** escolha o tipo de letra e as cores. Em **Sequência**, cada vídeo novo pega a próxima cor da lista (ex.: amarelo, verde, branco, vermelho, azul neon e volta ao começo); em **Uma cor só**, todas saem na primeira cor. A etiqueta do nome do mentor e a do episódio seguem a mesma cor. A escolha vale para todos os canais e fica em `data/capa.json`; cada vídeo guarda a cor que recebeu, então refazer o vídeo mantém a mesma cor.

## Imagens do Formato 01 (personagem falando)
Use uma destas formas:
- coloque as imagens **dentro do PDF**, na ordem das cenas; ou
- envie junto com o roteiro, na mesma pasta, arquivos `cena1.png`, `cena2.png`... (ou `NOMEDOPDF_cena1.png` se houver vários PDFs na pasta).

## Personagens (Entrevista)
O nome no roteiro (`CENA 02 | PERSONAGEM: BOB PROCTOR`) é ligado ao cadastro pelo nome ou pelos "outros nomes". Na aba **Personagens**:
- **Filtro e busca:** filtre por nicho, ou busque por nome, categoria ou tema.
- **✎ editar:** fica ao lado do nome. Muda o nome, os outros nomes, o nicho, a categoria e as especialidades.
- **Imagem:** envie em **Enviar/Trocar imagem**. Se a imagem tiver fundo (branco, colorido ou xadrez "pintado"), o app **remove o fundo sozinho** em cerca de 30 s. O arquivo enviado fica guardado como `original.*` na pasta do personagem.
- **Voz:** escolha outra voz da lista, ou use uma gravação: um arquivo de áudio ou um trecho de vídeo do YouTube (link + início/fim). A clonagem exige confirmar que a voz é sua ou que você tem autorização do dono dela.
- **Fundos e músicas:** cada personagem tem até 3 de cada, que se revezam a cada vídeo. Troque em **Escolher fundos** / **Escolher músicas**. Quando você escolhe à mão, sua escolha não é mais alterada pelo app.

## Onde ficam as coisas
- `data/personagens`, `data/fundos`, `data/musicas`, `data/vozes`: bibliotecas.
- `data/lotes/<data_hora>/`: cada lote, com os roteiros enviados (`entrada/`) e os vídeos (`videos/<id>_<titulo>/saida/`, com o `.mp4` e a `capa.png`).

## Requisitos e limites desta versão
- **Placa de vídeo livre:** feche jogos. As falas usam ~4 GB de VRAM.
- **Motores do laboratório:** usa os motores do laboratório (`D:\Video-Creator\VIDEO_CREATOR_LAB`) e as vozes do Video Cutter, só para leitura. Ainda não é um instalador independente.
- **Tempos:** ~3,5 min para um vídeo do Formato 01 de 25 s; ~7 min para uma entrevista de 2 min.
- **Fila:** um vídeo por vez. Fechar o app no meio de um vídeo faz ele recomeçar quando o app abrir de novo.
- **Música:** use apenas músicas com licença conhecida. O campo de origem é obrigatório. As músicas que vieram com o app são do Incompetech (Kevin MacLeod, CC BY 4.0) e exigem o crédito na descrição do vídeo. A aba Fila mostra o texto pronto do crédito.
- **Fundos que vieram com o app:** são do Pixabay (Pixabay Content License).
