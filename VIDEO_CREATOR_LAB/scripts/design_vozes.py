"""Design a distinct Kokoro voice for every catalog character that has none yet.

  candidatos <work>  (Kokoro runtime)     K random mixes per character, shaped by its profile; one sample each
  escolher   <work>  (Chatterbox runtime) speaker embeddings; greedy + local search for the most distinct set
  finalizar  <work>  (Kokoro runtime)     write the chosen packs to app/data/vozes with a treated sample

The voices are original mixes (pt-BR base + other Kokoro voices, speed, pitch); no recording of anyone is used.
"""
import json
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalogo_personagens import CATALOG  # noqa: E402

KOKORO_W = Path(r"C:\Users\paulo\.cache\huggingface\hub\models--hexgrad--Kokoro-82M\snapshots"
                r"\f3ff3571791e39611d31c381e3a41a3af07b4987")
EXTRA = Path(r"D:\Video-Creator\VIDEO_CREATOR_LAB\models\kokoro_voices")
VOZES = Path(r"D:\Video-Creator\app\data\vozes")
TEMPLATE = Path(r"D:\Video-Creator\VIDEO_CREATOR_LAB\templates\T02_entrevista.json")
PAULO_REF = Path(r"C:\dev\Video Cutter\voice_refs\paulo_links_fixed_optimized.wav")
K = 6
SENTENCE = ("A verdadeira transformação começa quando você decide observar os próprios pensamentos "
            "e agir com coragem todos os dias.")
MALE_EN = ["am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa",
           "bm_daniel", "bm_fable", "bm_george", "bm_lewis"]
MALE_OTHER = ["em_alex", "em_santa", "im_nicola", "hm_omega", "hm_psi", "jm_kumo", "zm_yunjian", "zm_yunxi",
              "zm_yunxia", "zm_yunyang"]
FEMALE_EN = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova",
             "af_river", "af_sarah", "af_sky", "bf_alice", "bf_emma", "bf_isabella", "bf_lily"]
FEMALE_OTHER = ["ef_dora", "if_sara", "ff_siwis"]


def vid_of(name):
    import unicodedata, re
    t = "".join(c for c in unicodedata.normalize("NFD", name.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def todo():
    return [c for c in CATALOG if not (VOZES / f"{vid_of(c[0])}.pt").exists()]


def recipe(profile, rng, wide=False):
    """wide: second round for voices still too close to another one (more foreign timbre, wider pitch)."""
    gender, age, energy = profile
    if gender == "m":
        base = rng.uniform(0.5, 0.65)
        a = rng.random()
        mix = {"pm_alex": base * a, "pm_santa": base * (1 - a)}
        rest = 1 - base
        if wide or rng.random() < 0.5:
            other = rng.choice(MALE_OTHER)
            w = rng.uniform(0.1, 0.2) if wide else rng.uniform(0.05, 0.12)
            mix[other] = w
            rest -= w
        en = rng.sample(MALE_EN, rng.choice([1, 2]))
    else:
        base = rng.uniform(0.5, 0.65)
        mix = {"pf_dora": base}
        rest = 1 - base
        if rng.random() < 0.5:
            other = rng.choice(FEMALE_OTHER)
            w = rng.uniform(0.05, 0.15)
            mix[other] = w
            rest -= w
        en = rng.sample(FEMALE_EN, rng.choice([1, 2]))
    split = [rng.uniform(0.3, 1) for _ in en]
    for v, s in zip(en, split):
        mix[v] = rest * s / sum(split)
    speed = {"c": (0.86, 0.93), "m": (0.94, 1.0), "e": (1.03, 1.1)}[energy]
    pitch = ({"j": (1.04, 1.12), "m": (0.92, 1.08), "i": (0.85, 0.96)} if wide else
             {"j": (1.02, 1.08), "m": (0.96, 1.03), "i": (0.9, 0.97)})[age]
    sp = rng.uniform(*speed) - (0.02 if age == "i" else 0)
    return {k: round(v, 4) for k, v in mix.items() if v > 0.005}, round(sp, 3), round(rng.uniform(*pitch), 3)


def _kokoro():
    import torch
    from kokoro import KModel, KPipeline
    pipe = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M", device="cpu",
                     model=KModel(config=str(KOKORO_W / "config.json"), model=str(KOKORO_W / "kokoro-v1_0.pth")))

    def load(v):
        return torch.load(KOKORO_W / "voices" / f"{v}.pt" if v.startswith("p") else EXTRA / f"{v}.pt",
                          weights_only=True)

    def pack(mix):
        return sum(load(v) * w for v, w in mix.items()) / sum(mix.values())

    def say(text, pack_path, speed, pitch, out):
        import numpy as np, wave
        audio = np.concatenate([a.detach().cpu().numpy() for _, _, a in pipe(text, voice=str(pack_path), speed=speed)])
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        if abs(pitch - 1) > 0.005:
            tmp = out.with_suffix(".tom.wav")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out), "-af",
                            f"rubberband=pitch={pitch}:formant=preserved", str(tmp)], check=True)
            tmp.replace(out)
    return torch, pack, say


def candidatos(work, extra=False):
    torch, pack, say = _kokoro()
    cand = work / "cand"
    cand.mkdir(parents=True, exist_ok=True)
    refs = {}  # voices that already exist: registered packs + Bob Proctor's pm_santa
    for meta in VOZES.glob("*.json"):
        info = json.loads(meta.read_text(encoding="utf-8"))
        refs[meta.stem] = (str(meta.with_suffix(".pt")), info.get("velocidade", 1), info.get("tom", 1))
    refs["bob_proctor_pm_santa"] = (str(KOKORO_W / "voices" / "pm_santa.pt"), 1.0, 1.0)
    for rid, (pt, sp, tom) in refs.items():
        out = cand / f"REF__{rid}.wav"
        if not out.exists():
            say(SENTENCE, pt, sp, tom, out)
    chars = todo()
    ks = range(K)
    if extra:  # second round only for the voices that ended up too close to another
        close = set(json.loads((work / "escolha.json").read_text(encoding="utf-8"))["proximos"])
        chars = [c for c in chars if vid_of(c[0]) in close]
        ks = range(K, 2 * K + 2)
    for i, (name, _, _, _, _, profile, _) in enumerate(chars, 1):
        vid = vid_of(name)
        rng = random.Random(vid + ("_extra" if extra else ""))
        for k in ks:
            out = cand / f"{vid}__{k}.wav"
            if out.exists():
                continue
            mix, sp, tom = recipe(profile, rng, wide=extra)
            pt = cand / f"{vid}__{k}.pt"
            torch.save(pack(mix), pt)
            say(SENTENCE, pt, sp, tom, out)
            (cand / f"{vid}__{k}.json").write_text(json.dumps({"mistura": mix, "velocidade": sp, "tom": tom}),
                                                   encoding="utf-8")
        print(f"[{i}/{len(chars)}] {name}", flush=True)


def escolher(work):
    import librosa
    import numpy as np
    import torch
    from chatterbox.models.voice_encoder import VoiceEncoder
    ve = VoiceEncoder()
    ve.load_state_dict(torch.load(Path(r"C:\Users\paulo\.cache\huggingface\hub\models--ResembleAI--chatterbox"
                                       r"\snapshots\5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18\ve.pt"),
                                  map_location="cpu"))
    ve.eval()
    cand = work / "cand"
    files = sorted(cand.glob("*.wav"))
    wavs = [librosa.load(str(f), sr=16000)[0] for f in files] + [librosa.load(str(PAULO_REF), sr=16000)[0]]
    names = [f.stem for f in files] + ["REF__paulo_clone"]
    emb = ve.embeds_from_wavs(wavs, sample_rate=16000)
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    E = dict(zip(names, emb))
    fixed = [n for n in names if n.startswith("REF__")]
    chars = sorted({n.split("__")[0] for n in names if not n.startswith("REF__")})
    options = {c: [n for n in names if n.split("__")[0] == c] for c in chars}

    def min_dist(n, chosen):
        others = [E[o] for o in chosen if o != n and o.split("__")[0] != n.split("__")[0]]
        return 1 - max(float(E[n] @ o) for o in others) if others else 1.0

    rng = random.Random(7)
    order = chars[:]
    rng.shuffle(order)
    pick = {}
    for c in order:
        chosen = fixed + list(pick.values())
        pick[c] = max(options[c], key=lambda n: min_dist(n, chosen))
    for _ in range(4):  # local search: re-pick each with everyone else fixed
        changed = 0
        for c in order:
            chosen = fixed + [v for k, v in pick.items() if k != c]
            best = max(options[c], key=lambda n: min_dist(n, chosen))
            if best != pick[c]:
                pick[c], changed = best, changed + 1
        if not changed:
            break
    final = fixed + list(pick.values())
    pairs = sorted(((float(E[a] @ E[b]), a, b) for i, a in enumerate(final) for b in final[i + 1:]), reverse=True)
    nearest = {c: 1 - min_dist(pick[c], final) for c in chars}
    report = {"escolha": pick, "proximos": [c for c, s in nearest.items() if s > 0.955],
              "vizinho_mais_proximo": {c: round(s, 3) for c, s in sorted(nearest.items(), key=lambda x: -x[1])},
              "pares_mais_parecidos": [(round(s, 3), a, b) for s, a, b in pairs[:15]],
              "similaridade_media": round(float(np.mean([s for s, _, _ in pairs])), 3)}
    (work / "escolha.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["pares_mais_parecidos"][:10], ensure_ascii=False))
    print("similaridade média:", report["similaridade_media"], "| ainda próximos (>0.955):", len(report["proximos"]))


def finalizar(work):
    import shutil
    torch, pack, say = _kokoro()
    fx = json.loads(TEMPLATE.read_text(encoding="utf-8"))["voz"]["tratamento"]["kokoro"]
    pick = json.loads((work / "escolha.json").read_text(encoding="utf-8"))["escolha"]
    by_vid = {vid_of(c[0]): c for c in CATALOG}
    for vid, cname in pick.items():
        name, _, _, categoria, _, profile, _ = by_vid[vid]
        rec = json.loads((work / "cand" / f"{cname}.json").read_text(encoding="utf-8"))
        shutil.copy2(work / "cand" / f"{cname}.pt", VOZES / f"{vid}.pt")
        g, a, e = profile
        desc = ", ".join([{"m": "masculina", "f": "feminina"}[g], {"j": "jovem", "m": "adulta", "i": "madura"}[a],
                          {"c": "calma", "m": "equilibrada", "e": "enérgica"}[e]])
        (VOZES / f"{vid}.json").write_text(json.dumps({"nome": name, "descricao": desc, **rec}, indent=2,
                                                      ensure_ascii=False), encoding="utf-8")
        raw = work / f"{vid}_raw.wav"
        say(f"Olá, eu sou {name}. {SENTENCE}", VOZES / f"{vid}.pt", rec["velocidade"], rec["tom"], raw)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-af",
                        f"{fx},loudnorm=I=-16:TP=-2:LRA=11,aresample=48000", "-ac", "1",
                        str(VOZES / f"{vid}_amostra.wav")], check=True)
        print("ok", name, flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "extra":
        candidatos(Path(sys.argv[2]), extra=True)
    else:
        {"candidatos": candidatos, "escolher": escolher, "finalizar": finalizar}[sys.argv[1]](Path(sys.argv[2]))
