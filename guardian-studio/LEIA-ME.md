# Cool Season Videos · modelo Guardian

App que transforma um roteiro de texto num vídeo vertical (1080×1920) no estilo Guardian: texto grande que acompanha a fala, painéis de sistema, transição em blocos.

## Primeira vez
1. Precisa do Node.js (nodejs.org, versão LTS).
2. Dois cliques em `instalar.bat`.
3. Preencha a voz no `config.txt` (veja as opções lá dentro).

## Tela (recomendado)
Dois cliques em `abrir-tela.bat`. Abre o Guardian Studio no navegador (http://localhost:5610): escolha ou suba o roteiro, escolha a voz e a música, clique em "Salvar e gerar vídeo" e assista ali mesmo. Para fechar, feche a janela preta.

## Para cada vídeo (sem a tela)
1. Salve o roteiro em `roteiros\diaNN.txt` (use `roteiros\dia01.txt` como modelo).
2. Dois cliques em `gerar-video.bat`. Ele gera todos os roteiros que ainda não têm vídeo.
   Para refazer um só: abra o terminal na pasta e rode `gerar-video.bat dia01`.
3. O vídeo sai em `videos\diaNN.mp4`.

A voz de cada fala fica guardada. Se você mudar só uma cena e gerar de novo, a voz não é refeita.

## Formato do roteiro
Cabeçalho (opcional): `TITULO:`, `MUSICA: arquivo.mp3` (na pasta musica), `VOLUME_MUSICA: 0.12`.
Cada fala começa com `FALA:` e pode ter `CENA:`, `DESTAQUE:` (palavras em azul, separadas por vírgula) e os campos da cena.
Linhas que começam com `#` são comentários. Campos repetidos (linha, item, resultado, barra, info) viram listas.

## Cenas disponíveis
| CENA | Campos |
| --- | --- |
| contador | numero, rotulo, titulo, canto, antes, depois, pontos (sim/nao) |
| tabela | titulo, canto, colunas "A \| B \| C", linha (repetir) "a \| b \| c" |
| console | titulo, canto, item (repetir) "calls = 0", meses (sim/nao), cor |
| contato | titulo, canto, nome, detalhe, aviso, borrar (sim/nao) |
| termostato | titulo, canto, de, para, alvo, aviso |
| busca | titulo, termo, resultado (repetir) "Nome \| detalhe", escolhido (1, 2, 3...), selo, aviso |
| barras | titulo, canto, barra (repetir) "Rótulo \| valor \| cor" |
| produto | imagem (pasta public\imagens), info (repetir) "chave \| valor \| cor", rotulo |
| comentario | usuario, palavra, resposta, autor |
| mapa | numero, titulo, canto, rotulo |
| imagem | arquivo (pasta public\imagens), legenda |
| frase | grande (número ou palavra enorme no centro, opcional), cor |

Cores: azul, laranja, verde, vermelho, cinza, amarelo.

## Pré-visualizar e mexer no visual
`estudio.bat` abre o Remotion Studio no navegador.

Licença do Remotion: grátis para pessoa física e empresa de até 3 pessoas (remotion.dev/license).


## Variação visual (rodízio) e biblioteca de animações

Cada vídeo sai com tema, estilo de texto, transições, câmera e capa diferentes, sem precisar escrever nada no roteiro.
O histórico fica em `rodizio.json` (evita repetir tema e capa dos últimos 3 vídeos). `RODIZIO: nao` no roteiro volta ao visual antigo.

- Temas: claro, noite, blueprint, papel, terminal, alerta.
- Texto: topo, centro, baixo, palavra, caixa.
- Transições: blocos, deslizar, zoom, cortina, circulo, flash, mista.
- Capas: gigante, numero, pergunta, alerta, produto, dividida, moldura, faixas. `node scripts/gerar.mjs dia01 --so-capa` gera só a capa.
- Cenas: as 12 originais mais celular, mapapins, painel, linha, linhadotempo, comparar, medidor, checklist, relatorio, formulario, fluxo, guardian3d.
- Animação nova: bloco `CODIGO: nome` ... `FIM_CODIGO` no roteiro. Ela é testada, guardada em `src/custom/` e listada em `biblioteca.md`. A que falhar vai para `src/custom/_quebradas/` e a fala usa `frase`.
