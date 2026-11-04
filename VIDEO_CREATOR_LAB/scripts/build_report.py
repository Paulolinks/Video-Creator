"""Build the local HTML page (index.html): every test video, grouped by section, with plain descriptions."""
import html
import json
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent

TOOLS = {
    "ffmpeg": ("FFmpeg 7.1", "Programa de linha de comando que edita, junta e codifica vídeo e áudio.",
               "LGPL/GPL (este build: GPL v3)", "https://ffmpeg.org"),
    "x264": ("x264 (dentro do FFmpeg)", "Codificador H.264 por software, roda no processador.", "GPL v2+",
             "https://www.videolan.org/developers/x264.html"),
    "nvenc": ("NVIDIA NVENC (via FFmpeg)", "Codificador H.264 por hardware, roda no chip da placa de vídeo.",
              "Recurso da placa NVIDIA (gratuito, não é open source)",
              "https://developer.nvidia.com/video-codec-sdk"),
    "pillow": ("Pillow 11.3", "Biblioteca Python de imagens. Aqui desenha cada quadro com recorte fracionado (subpixel).",
               "MIT-CMU (open source)", "https://python-pillow.org"),
    "moviepy": ("MoviePy 2.1.2", "Biblioteca Python de edição de vídeo, muito usada em tutoriais de automação.",
                "MIT (open source)", "https://github.com/Zulko/moviepy"),
    "depth": ("Depth Anything V2 Small", "IA que estima a profundidade de uma foto (o que está perto e o que está longe).",
              "Apache-2.0, conferida no model card (só o Small é comercial)",
              "https://github.com/DepthAnything/Depth-Anything-V2"),
    "opencv": ("OpenCV 5.0", "Biblioteca de visão computacional. Aqui desloca cada pixel conforme a profundidade.",
               "Apache-2.0 (open source)", "https://opencv.org"),
    "kokoro": ("Kokoro-82M", "Voz sintética (TTS) local, com vozes em português. Já estava instalada no Video Cutter.",
               "Apache-2.0 segundo o projeto (não reconferida neste laboratório)",
               "https://huggingface.co/hexgrad/Kokoro-82M"),
    "whisper": ("faster-whisper (modelo small)", "Reconhecimento de fala. Aqui só marca QUANDO cada palavra é dita; "
                "o texto da legenda vem do roteiro. Já estava instalado no Video Cutter.", "MIT (open source)",
                "https://github.com/SYSTRAN/faster-whisper"),
    "libass": ("libass (via FFmpeg)", "Desenha legendas estilizadas (fonte, contorno, karaokê) no vídeo.",
               "ISC (open source)", "https://github.com/libass/libass"),
    "sadtalker": ("SadTalker (Tencent / OpenTalker)", "IA que faz uma foto FALAR: recebe a imagem + o áudio e gera "
                  "boca sincronizada, piscadas e movimentos de cabeça. Rodou na placa de vídeo (RTX 4060).",
                  "Apache-2.0 (o LICENSE cita componentes de terceiros sem listá-los; revisar antes de uso comercial)",
                  "https://github.com/OpenTalker/SadTalker"),
    "gfpgan": ("GFPGAN v1.4", "IA que restaura/realça o rosto quadro a quadro (pele e olhos mais nítidos). "
               "É a etapa lenta: ~1 s por quadro.", "Apache-2.0 (metadados do pacote)",
               "https://github.com/TencentARC/GFPGAN"),
    "chatterbox": ("Chatterbox Multilingual (Resemble AI)", "Voz sintética que CLONA uma voz a partir de uma "
                   "gravação de referência. Aqui: a voz do próprio Paulo, com autorização dele. Insere marca d'água "
                   "inaudível (Perth) indicando áudio sintético. Já estava instalado no Video Cutter.",
                   "MIT segundo o projeto (não reconferida neste laboratório)",
                   "https://github.com/resemble-ai/chatterbox"),
    "poppins": ("Fonte Poppins Bold", "Fonte da legenda, copiada do Video Cutter com o arquivo de licença.",
                "SIL OFL 1.1 (livre, inclusive comercial)", "https://fonts.google.com/specimen/Poppins"),
}

SECTIONS = [
    ("videos/entrevista_bob_proctor", "TEMPLATE APROVADO: T02 Entrevista com mentor (Paulo × Bob Proctor)",
     "Seu roteiro em PDF e seus PNGs. Ao trocar de locutor trocam retrato, lado, voz e fundo: Bob à esquerda nas "
     "partículas douradas (voz sintética genérica, com redução de ruído), Paulo à direita nas nuvens (sua voz "
     "clonada). Retrato com respiração 100→106→100%, fundo em loop sem emenda, onda sonora reagindo à voz, legenda "
     "karaokê de cor (estilo v3), só o nome do locutor no topo. Gerado com: python scripts\\gerar_entrevista.py "
     "inputs\\entrevista_bob_proctor, em 7,4 minutos. Use fones.",
     ["chatterbox", "kokoro", "whisper", "opencv", "ffmpeg", "libass", "poppins"], True),
    ("videos/teste_maquiavel", "TEMPLATE APROVADO: formato_01_personagem_falando",
     "Formato salvo: personagem falando (SadTalker sem realce), 2.5D nas cenas sem fala, voz Kokoro, legenda karaokê, "
     "sem música (você escolhe no app). Gerado do zero com um comando: python scripts\\gerar_video.py "
     "inputs\\teste_maquiavel, em 3,4 minutos.",
     ["sadtalker", "kokoro", "whisper", "depth", "opencv", "ffmpeg", "libass", "poppins"], True),
    ("maquiavel", "NOVO: vídeo do Maquiavel (personagem falando)",
     "Seu roteiro e suas 3 imagens. Cenas 1 e 3: Maquiavel fala (SadTalker) com zoom lento por cima. Cena 2: traição "
     "com profundidade 2.5D. Voz Kokoro (Alex), legenda karaokê com o texto exato do roteiro, música sintética que "
     "abaixa sob a voz. Duas versões: rosto com e sem realce GFPGAN. Use fones.",
     ["sadtalker", "gfpgan", "kokoro", "whisper", "depth", "opencv", "ffmpeg", "libass", "poppins"], True),
    ("sadtalker", "SadTalker: as cenas falando, sozinhas",
     "Saída direta do SadTalker, antes da montagem (com o áudio da cena). Compare o rosto com e sem realce, e o tempo "
     "de cada um.", ["sadtalker", "gfpgan"], True),
    ("comparacoes", "Comparações lado a lado",
     "Os vídeos das seções abaixo, colocados lado a lado e com o nome de cada método escrito em cima. "
     "Como estão reduzidos, para julgar o tremor fino prefira os vídeos individuais.", ["ffmpeg"], True),
    ("montagem", "Montagem completa: o fluxo do Video Creator",
     "Simula o produto final: o texto de cada cena vira voz, a duração da voz define quanto tempo cada imagem fica "
     "na tela, a imagem ganha movimento, entra a transição, a legenda acompanha a fala e a música abaixa quando a "
     "voz entra. Texto técnico de teste, não é roteiro. Fotos do Windows, só para teste. Use fones.",
     ["kokoro", "whisper", "pillow", "ffmpeg", "libass", "poppins"], True),
    ("depth", "Bloco B: profundidade 2.5D",
     "A IA estima a distância de cada ponto da foto, e o programa move a câmera virtual: o que está perto se mexe mais "
     "que o fundo, criando sensação de 3D a partir de uma foto parada. Rodou no processador (CPU). "
     "Fotos da tela de bloqueio do Windows, só para teste interno.", ["depth", "opencv", "ffmpeg"], False),
    ("ffmpeg", "Bloco A: movimento simples (zoom e pan)",
     "Movimento de câmera sobre uma imagem parada (efeito Ken Burns). Compara o FFmpeg sozinho com o desenho quadro a "
     "quadro em Python (Pillow). A imagem é sintética, com grade fina: repare se as linhas tremem ou deslizam lisas.",
     ["ffmpeg", "pillow", "x264", "nvenc"], False),
    ("moviepy", "MoviePy",
     "O mesmo movimento combinado do Bloco A, feito com a receita mais comum de MoviePy.", ["moviepy"], False),
    ("encoder", "Codificadores: x264 × NVENC",
     "O mesmo movimento sobre a foto do lago, salvo de 6 jeitos diferentes. Mede qualidade (SSIM: 1,0 = idêntico ao "
     "original sem perdas), tamanho do arquivo e velocidade.", ["x264", "nvenc", "ffmpeg"], False),
]

FF, PIL_, MP = "FFmpeg (filtro zoompan) + x264", "Pillow (Python) + FFmpeg/x264", "MoviePy 2.1.2"
TALK = "SadTalker + GFPGAN (rosto) · Kokoro (voz) · Depth Anything (cena 2) · FFmpeg + libass (legenda)"
VIDEOS = {
    "entrevista_bob_proctor": ("Entrevista: Paulo × Bob Proctor (dramatização), 2 min 16 s",
                               "gerar_entrevista.py (Chatterbox + Kokoro · Whisper · OpenCV · FFmpeg + libass)",
                               "6 cenas alternadas. Confira: troca de lado/fundo/voz a cada locutor, caixa amarela "
                               "acompanhando a palavra, volume igual entre as duas vozes, onda reagindo à fala."),
    "teste_maquiavel": ("Maquiavel: gerado pelo template aprovado", "gerar_video.py (SadTalker sem realce · "
                        "Kokoro · Depth Anything · FFmpeg + libass)",
                        "Versão oficial do formato: sem música, rosto sem realce. Roteiro → vídeo em 3,4 min."),
    # machiavelli
    "maquiavel_final_com_realce": ("Vídeo completo: rosto COM realce (recomendado)", TALK,
                                   "24 s. Rosto mais nítido. Cada cena falada levou ~4,3 min no SadTalker por causa "
                                   "do realce."),
    "maquiavel_final_sem_realce": ("Vídeo completo: rosto SEM realce", "SadTalker (sem GFPGAN) · Kokoro · Depth "
                                   "Anything · FFmpeg + libass",
                                   "Mesmo vídeo, rosto um pouco mais suave/borrado. Cada cena falada levou só ~1 min."),
    "cena1_sadtalker_com_realce": ("Cena 1 falando: com realce", "SadTalker 256 + GFPGAN v1.4",
                                   "Saída crua do SadTalker (1888×3344, 25 fps)."),
    "cena1_sadtalker_sem_realce": ("Cena 1 falando: sem realce", "SadTalker 256", "Saída crua, sem o realce facial."),
    "cena3_sadtalker_com_realce": ("Cena 3 falando: com realce", "SadTalker 256 + GFPGAN v1.4", "Saída crua."),
    "cena3_sadtalker_sem_realce": ("Cena 3 falando: sem realce", "SadTalker 256", "Saída crua, sem o realce facial."),
    # comparisons
    "01_tremor_zoom_in": ("Tremor no zoom: 3 métodos", "FFmpeg (montagem lado a lado)",
                          "Esquerda: FFmpeg simples (treme mais). Meio: FFmpeg com imagem ampliada 4×. "
                          "Direita: Python subpixel (o mais liso)."),
    "02_tremor_combinado": ("Tremor no zoom + deslocamento: FFmpeg × Python × MoviePy", "FFmpeg (montagem lado a lado)",
                            "O movimento mais usado em vídeos com imagens. O FFmpeg e o MoviePy tremem; o Python "
                            "subpixel desliza liso."),
    "03_profundidade_lago": ("Profundidade no lago: 2D × 2.5D", "FFmpeg (montagem lado a lado)",
                             "Esquerda: zoom comum, tudo se move junto. Meio e direita: com profundidade, a margem e "
                             "a água se movem diferente do céu."),
    "04_profundidade_fitas": ("Profundidade nas fitas: 2D × 2.5D", "FFmpeg (montagem lado a lado)",
                              "Mesmo teste com uma imagem 3D em camadas."),
    "05_legenda_simples_x_karaoke": ("Legenda simples × karaokê", "FFmpeg (montagem lado a lado)",
                                     "Esquerda: blocos de até 3 palavras. Direita: cada palavra fica dourada quando é "
                                     "falada. Com áudio."),
    # montage
    "montagem_v1_sem_ducking_legenda_simples": ("Versão 1: música SEM abaixar", "Kokoro + Whisper + Pillow + FFmpeg + libass",
                                                "A música fica no mesmo volume o tempo todo, competindo com a voz. "
                                                "Serve de referência para ouvir a diferença da versão 2."),
    "montagem_v2_com_ducking_legenda_simples": ("Versão 2: música abaixa sob a voz (ducking)",
                                                "Kokoro + Whisper + Pillow + FFmpeg + libass",
                                                "A música cai cerca de 22 dB enquanto a voz fala e volta nas pausas. "
                                                "Legenda em blocos."),
    "montagem_v3_com_ducking_legenda_karaoke": ("Versão 3: ducking + legenda karaokê",
                                                "Kokoro + Whisper + Pillow + FFmpeg + libass",
                                                "Igual à versão 2, mas a legenda destaca cada palavra no momento em "
                                                "que é dita."),
    # depth
    "lago_flat_zoom": ("Lago: zoom 2D comum (referência)", "OpenCV + FFmpeg (sem IA)",
                       "Zoom sem profundidade, para comparar. A foto inteira cresce por igual."),
    "lago_dolly": ("Lago: aproximação 2.5D (dolly)", "Depth Anything V2 Small + OpenCV + FFmpeg",
                   "A câmera avança: a margem e a água em primeiro plano crescem mais que o céu."),
    "lago_orbit": ("Lago: câmera lateral 2.5D (órbita)", "Depth Anything V2 Small + OpenCV + FFmpeg",
                   "A câmera desliza para o lado: o primeiro plano passa mais rápido que o sol e as montanhas."),
    "fitas_flat_zoom": ("Fitas: zoom 2D comum (referência)", "OpenCV + FFmpeg (sem IA)", "Zoom sem profundidade."),
    "fitas_dolly": ("Fitas: aproximação 2.5D (dolly)", "Depth Anything V2 Small + OpenCV + FFmpeg",
                    "As camadas da frente crescem mais que as de trás."),
    "fitas_orbit": ("Fitas: câmera lateral 2.5D (órbita)", "Depth Anything V2 Small + OpenCV + FFmpeg",
                    "Observe as bordas entre as fitas: é onde aparecem defeitos, se houver."),
    # block A
    "zoom_in_ss1": ("Zoom-in: FFmpeg simples", FF, "Imagem no tamanho final. O jeito mais rápido; as linhas tremem."),
    "zoom_in_ss2": ("Zoom-in: FFmpeg com imagem 2×", FF, "Imagem ampliada 2× antes do zoom: treme menos."),
    "zoom_in_ss4": ("Zoom-in: FFmpeg com imagem 4×", FF, "Ampliada 4×: o melhor resultado possível só com FFmpeg."),
    "zoom_out_ss4": ("Zoom-out: FFmpeg 4×", FF, "Afastamento da câmera."),
    "pan_h_ss4": ("Pan horizontal: FFmpeg 4×", FF, "Câmera desliza da esquerda para a direita."),
    "pan_v_ss4": ("Pan vertical: FFmpeg 4×", FF, "Câmera desliza de baixo para cima."),
    "combined_ss4": ("Zoom + deslocamento: FFmpeg 4×", FF,
                     "Movimento combinado. Mesmo ampliado, o FFmpeg treme aqui."),
    "combined_ss4_nvenc": ("Zoom + deslocamento: FFmpeg 4× salvo com NVENC", "FFmpeg (zoompan) + NVENC",
                           "Igual ao anterior, mas codificado pela placa de vídeo: mais rápido, mesmo tremor."),
    "zoom_in_pil": ("Zoom-in: Python subpixel", PIL_, "Cada quadro é desenhado com posição fracionada: sem tremor."),
    "pan_h_pil": ("Pan horizontal: Python subpixel", PIL_, "Mesmo pan, liso."),
    "combined_pil": ("Zoom + deslocamento: Python subpixel", PIL_,
                     "O método recomendado: liso, cerca de 3× mais lento que o FFmpeg."),
    "transicoes_fade_slide": ("Transições: dissolve e deslize", "FFmpeg (filtro xfade) + x264",
                              "Três clipes unidos: primeiro um dissolve (fade), depois um deslize lateral."),
    # moviepy
    "combined_moviepy": ("Zoom + deslocamento: MoviePy", MP,
                         "Receita clássica de Ken Burns com MoviePy. Foi o mais lento e o mais tremido de todos."),
}
ENC_LABEL = {"x264_crf18_medium": "x264 qualidade 18 (padrão)", "x264_crf23_medium": "x264 qualidade 23 (menor)",
             "x264_crf18_veryfast": "x264 qualidade 18, modo rápido", "nvenc_cq19_p5": "NVENC qualidade 19",
             "nvenc_cq23_p5": "NVENC qualidade 23 (menor)", "nvenc_cq19_p7": "NVENC qualidade 19, modo máximo"}
for key, label in ENC_LABEL.items():
    tool = "NVENC (placa de vídeo) via FFmpeg" if key.startswith("nvenc") else "x264 (processador) via FFmpeg"
    VIDEOS[f"lago_{key}"] = (f"Lago salvo com {label}", tool, "Compare nitidez do céu e da água com os outros.")


def load_bench():
    data = {}
    for p in (LAB / "benchmarks").glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        if "name" in r:
            data[r["name"]] = r
    return data


BENCH = load_bench()


def metrics(stem):
    r = BENCH.get(stem)
    if not r:
        return ""
    wall = r.get("wall_s", r.get("render_wall_s"))
    bits = [f"levou {wall} s para gerar"] if wall is not None else []
    if r.get("smoothness") and r.get("test") == "A":
        bits.append(f"tremor {r['smoothness']['jitter']} (menor = melhor)")
    if r.get("depth_infer_s"):
        bits.append(f"profundidade em {r['depth_infer_s']} s")
    if r.get("ssim"):
        bits += [f"SSIM {r['ssim']:.4f}", f"{r['size_mb']} MB"]
    if r.get("test") == "C":
        bits.append(f"VRAM +{r['gpu_mem_delta_mb']:.0f} MB · RAM sistema +{r['system_ram_delta_mb']:.0f} MB")
    elif r.get("peak_ram_mb"):
        bits.append(f"RAM {r['peak_ram_mb']} MB")
    if r.get("test") == "C+montagem":
        bits.append(f"montagem levou {r['wall_total_s_sem_sadtalker']} s (+ tempo do SadTalker)")
    return " · ".join(bits)


def tool_box(keys):
    rows = "".join(f"""<li><a href="{TOOLS[k][3]}" target="_blank" rel="noopener">{html.escape(TOOLS[k][0])}</a>:
{html.escape(TOOLS[k][1])} <span class="lic">Licença: {html.escape(TOOLS[k][2])}</span></li>""" for k in keys)
    return f'<ul class="tools">{rows}</ul>'


def card(mp4, sound, wide):
    title, made_with, desc = VIDEOS.get(mp4.stem, (mp4.stem, "", ""))
    rel = mp4.relative_to(LAB).as_posix()
    return f"""<figure class="{'wide' if wide else ''}">
<video src="{rel}" controls loop {'' if sound else 'muted'} playsinline preload="metadata"></video>
<figcaption><h3>{html.escape(title)}</h3>
<div class="made">Feito com: <b>{html.escape(made_with)}</b></div>
<p>{html.escape(desc)}</p><div class="m">{metrics(mp4.stem)}</div>
<div class="file">{html.escape(mp4.name)}</div></figcaption></figure>"""


DOWNLOADS = [
    ("Formato 01 — Personagem falando",
     "Um personagem fala para a câmera (cenas de fala + cenas 2.5D), voz única, legenda karaokê.",
     [("Framework do roteiro (PDF)", "Framework_F01_Personagem_Falando.pdf"),
      ("Modelo cenas.json", "modelo_F01_cenas.json"), ("Vídeo-exemplo: Maquiavel", "exemplo_F01_maquiavel.mp4")]),
    ("T02 — Entrevista com mentor",
     "Paulo pergunta, o mentor responde; troca de retrato, lado, fundo e voz a cada fala.",
     [("Framework do roteiro (PDF)", "Framework_T02_Entrevista_com_Mentor.pdf"),
      ("Modelo roteiro.json", "modelo_T02_roteiro.json"), ("Vídeo-exemplo: Bob Proctor", "exemplo_T02_entrevista.mp4")]),
]


def downloads_block():
    cards = []
    for title, desc, files in DOWNLOADS:
        links = "".join(f'<a class="dl{" main" if i == 0 else ""}" href="downloads/{f}" download>{html.escape(label)}</a>'
                        for i, (label, f) in enumerate(files))
        cards.append(f'<div class="tpl"><h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p>{links}</div>')
    return f"""<section id="downloads"><h2>Templates para baixar</h2>
<p class="note">Baixe o PDF do template, anexe no ChatGPT e cole o prompt que está no item 2 do PDF. O ChatGPT devolve o
roteiro e o JSON no formato certo para gerar o vídeo.</p><div class="tpls">{''.join(cards)}</div></section>"""


def page():
    blocks = [downloads_block()]
    for folder, title, note, tools, sound in SECTIONS:
        mp4s = [p for p in sorted((LAB / "outputs" / folder).glob("*.mp4")) if not p.name.startswith("_")]
        cards = "".join(card(p, sound, folder == "comparacoes") for p in mp4s)
        blocks.append(f"""<section id="{folder}"><h2>{title}</h2><p class="note">{note}</p>
<div class="toolhead">Ferramentas testadas nesta seção</div>{tool_box(tools)}
<div class="ctrl"><button onclick="playAll(this)">Tocar todos desta seção</button>
<button class="sec" onclick="pauseAll(this)">Pausar</button>
<span>{len(mp4s)} vídeos · pasta outputs/{folder}/</span></div>
<div class="grid">{cards}</div></section>""")
    nav = '<a href="#downloads">Templates para baixar</a> ' + " ".join(
        f'<a href="#{f}">{t.split(":")[0]}</a>' for f, t, *_ in SECTIONS)
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Laboratório Video Creator</title>
<style>
:root{{--bg:#111318;--fg:#e8e8ec;--muted:#9a9cab;--card:#1b1e26;--line:#2a2e3a;--accent:#5b9bff;--lic:#c9a84a}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}}
main{{max-width:1400px;margin:auto}}
h1{{font-size:24px;margin:0 0 6px}} h2{{font-size:19px;margin:0 0 6px}} h3{{font-size:14px;margin:0 0 4px}}
a{{color:var(--accent)}} nav{{display:flex;flex-wrap:wrap;gap:8px 16px;margin:10px 0 4px}}
.note{{color:var(--muted);max-width:900px;margin:0 0 10px}}
section{{border-top:1px solid var(--line);padding:22px 0}}
.toolhead{{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:4px}}
.tools{{margin:0 0 14px;padding-left:18px;max-width:1000px}} .tools li{{margin:3px 0}}
.lic{{color:var(--lic);font-size:12px}}
.ctrl{{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:14px}} .ctrl span{{color:var(--muted);font-size:12px}}
button{{padding:6px 12px;border:0;border-radius:6px;background:#2d6cdf;color:#fff;cursor:pointer}}
button.sec{{background:#394050}}
.tpls{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}}
.tpl{{background:var(--card);border-radius:10px;padding:14px;border-top:3px solid #e0a800}}
.tpl p{{color:var(--muted);margin:4px 0 12px}}
a.dl{{display:block;margin:6px 0;padding:8px 12px;border-radius:6px;background:#394050;color:#fff;text-decoration:none}}
a.dl.main{{background:#2d6cdf;font-weight:600}} a.dl:hover{{filter:brightness(1.15)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:16px}}
figure{{margin:0;background:var(--card);border-radius:10px;padding:10px;display:flex;flex-direction:column}}
figure.wide{{grid-column:1/-1}} figure.wide video{{aspect-ratio:auto;max-height:78vh;width:auto;max-width:100%;margin:auto}}
video{{width:100%;aspect-ratio:9/16;background:#000;border-radius:6px}}
figcaption{{margin-top:8px}} figcaption p{{color:var(--muted);margin:4px 0}}
.made{{font-size:12px;color:var(--muted)}} .made b{{color:var(--fg)}}
.m{{font-size:12px;color:var(--accent)}} .file{{font-size:11px;color:#6c7080;margin-top:4px;word-break:break-all}}
</style></head><body><main>
<h1>Laboratório Video Creator: vídeos testados</h1>
<p class="note">Cada seção indica qual ferramenta open source foi testada, para que serve, a licença e o link
oficial. Cada vídeo traz o que foi usado para fazê-lo e o que observar. Nenhum material aqui é arte ou roteiro
aprovado. Relatório completo: reports/BENCHMARKS_VIDEO.md.</p>
<nav>{nav}</nav>
{''.join(blocks)}
</main><script>
const vids=b=>b.closest('section').querySelectorAll('video');
function playAll(b){{vids(b).forEach(v=>{{v.currentTime=0;v.play()}})}}
function pauseAll(b){{vids(b).forEach(v=>v.pause())}}
</script></body></html>"""


if __name__ == "__main__":
    (LAB / "index.html").write_text(page(), encoding="utf-8")
    missing = [p.stem for p in (LAB / "outputs").rglob("*.mp4") if not p.name.startswith("_") and p.stem not in VIDEOS]
    print("ok; sem descricao:", missing or "nenhum")
