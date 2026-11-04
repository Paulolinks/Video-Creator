# Video Creator: como iniciar

## Abrir o app
1. Feche jogos ou programas pesados: as falas usam cerca de 4 GB da placa de vídeo.
2. Abra a pasta `D:\Video-Creator\app` e dê dois cliques em **`iniciar.bat`**.
3. O navegador abre sozinho em **http://127.0.0.1:5600**. Se não abrir, copie esse endereço no navegador.

Deixe a janela preta aberta enquanto usa o app: ela é o app rodando.

Se o app já estiver aberto, o `iniciar.bat` só abre o navegador. Não tem problema clicar duas vezes.

## Fechar o app
- Feche a janela preta, **ou**
- dê dois cliques em **`parar.bat`** (na mesma pasta). Use esse quando não houver janela preta, por exemplo quando o app foi iniciado em segundo plano.

Se um vídeo estiver sendo gerado quando você fechar, ele recomeça do início na próxima vez que o app abrir.

## Pelo terminal (alternativa)
```
cd D:\Video-Creator\app
D:\Video-Creator\VIDEO_CREATOR_LAB\.venvs\lab\Scripts\python.exe app.py
```
Acrescente `--sem-navegador` para não abrir o navegador.

## Se algo der errado
| Problema | O que fazer |
|---|---|
| A página não abre | Veja se a janela preta está aberta e sem erro. Feche tudo com `parar.bat` e abra de novo com `iniciar.bat`. |
| A tela não mostra uma mudança | Aperte **Ctrl+F5** no navegador. |
| Aviso de placa de vídeo cheia | Feche jogos e programas pesados e gere de novo. |
| O vídeo não sai | Na aba **Fila**, a mensagem de erro aparece embaixo do vídeo. O log completo fica em `execucao.log`, na pasta do vídeo. |

## O que fica onde
- **`app\`**: o app. O guia de uso está em [`app\LEIA-ME.md`](app/LEIA-ME.md).
- **`app\data\`**: personagens, fundos, músicas, vozes e os lotes com os vídeos prontos (`lotes\<data>\videos\...\saida\`, com o `.mp4` e a `capa.png`).
- **`VIDEO_CREATOR_LAB\`**: os motores que geram voz, rosto e montagem. Não mexa nessa pasta.
- **`C:\dev\Video Cutter`**: o app usa as vozes dessa pasta só para leitura. Não apague essa pasta.
