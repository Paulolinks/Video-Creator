# Video Creator: app local (v0.2)

Roteiros entram, vídeos verticais saem. Roda no seu computador, sem API paga.

## Abrir e fechar
- **Abrir:** dê dois cliques em **`iniciar.bat`**. O navegador abre em http://127.0.0.1:5600. Se o app já estiver aberto, o navegador só é aberto de novo.
- **Fechar:** feche a janela preta ou dê dois cliques em **`parar.bat`**.

Mais detalhes em [`../README.md`](../README.md).

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
Todo vídeo gera uma `capa.png` (1080×1920) ao lado do `.mp4`:
- **Entrevista:** o fundo e o mentor embaixo, o título do roteiro grande em amarelo em cima e o nome do mentor.
- **Formato 01:** a imagem da primeira cena, com o título por cima.

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
