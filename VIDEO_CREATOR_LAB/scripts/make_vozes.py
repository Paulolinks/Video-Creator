"""Design one Kokoro voice per character: a weighted mix of the pt-BR voices (pronunciation) with English male
voices (timbre), plus speed and pitch. Writes <id>.pt + <id>.json into the app's data/vozes folder.

These are original synthetic voices that suggest each character's age and temperament; no recording of any
real person is used. Run with the Kokoro runtime python (torch). Usage: make_vozes.py
"""
import json
from pathlib import Path

import torch

PT = Path(r"C:\Users\paulo\.cache\huggingface\hub\models--hexgrad--Kokoro-82M\snapshots"
          r"\f3ff3571791e39611d31c381e3a41a3af07b4987\voices")
EXTRA = Path(r"D:\Video-Creator\VIDEO_CREATOR_LAB\models\kokoro_voices")
OUT = Path(r"D:\Video-Creator\app\data\vozes")

# id: (name, description, mix {voice: weight}, speed, pitch)
RECIPES = {
    "neville_goddard": ("Neville Goddard", "calma, suave, mística",
                        {"pm_alex": 0.6, "am_michael": 0.4}, 0.92, 0.97),
    "napoleon_hill": ("Napoleon Hill", "madura, firme, de orador",
                      {"pm_santa": 0.6, "bm_george": 0.4}, 0.96, 0.95),
    "joseph_murphy": ("Joseph Murphy", "madura, acolhedora",
                      {"pm_santa": 0.55, "bm_lewis": 0.45}, 0.93, 1.0),
    "nicolau_maquiavel": ("Nicolau Maquiavel", "seca, astuta, precisa",
                          {"pm_alex": 0.6, "bm_daniel": 0.4}, 1.0, 1.03),
    "marcus_aurelius": ("Marcus Aurelius", "grave, lenta, serena",
                        {"pm_santa": 0.6, "am_onyx": 0.4}, 0.88, 0.9),
    "alan_watts": ("Alan Watts", "descontraída, bem-humorada",
                   {"pm_alex": 0.55, "bm_fable": 0.45}, 0.95, 1.02),
    "albert_einstein": ("Albert Einstein", "idosa, gentil, curiosa",
                        {"pm_santa": 0.55, "am_eric": 0.45}, 0.9, 1.06),
    "nikola_tesla": ("Nikola Tesla", "leve, rápida, visionária",
                     {"pm_alex": 0.5, "am_puck": 0.3, "am_liam": 0.2}, 1.04, 1.12),
    "viktor_frankl": ("Viktor Frankl", "firme, calorosa",
                      {"pm_alex": 0.55, "am_fenrir": 0.45}, 0.94, 0.95),
    "arthur_schopenhauer": ("Arthur Schopenhauer", "baixa, seca, sombria",
                            {"pm_santa": 0.55, "am_adam": 0.25, "am_echo": 0.2}, 0.95, 0.88),
}


def load(name):
    return torch.load(PT / f"{name}.pt" if name.startswith("p") else EXTRA / f"{name}.pt", weights_only=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for vid, (name, desc, mix, speed, pitch) in RECIPES.items():
        pack = sum(load(v) * w for v, w in mix.items()) / sum(mix.values())
        torch.save(pack, OUT / f"{vid}.pt")
        (OUT / f"{vid}.json").write_text(json.dumps(
            {"nome": name, "descricao": desc, "mistura": mix, "velocidade": speed, "tom": pitch},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print(vid, tuple(pack.shape))
