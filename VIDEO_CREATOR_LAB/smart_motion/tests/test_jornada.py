"""JORNADA and animation scenes in the scripts. Runs with pytest, or alone with the lab Python: python test_jornada.py"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "app"), str(ROOT / "VIDEO_CREATOR_LAB" / "smart_motion")]
import marcacoes  # noqa: E402
from core import jobs, parser  # noqa: E402

FALA = "Primeiro a pessoa deixa o contato. Em troca, recebe a isca."


def script(body, name="r.txt"):
    p = Path(tempfile.mkdtemp()) / name
    p.write_text(body, encoding="utf-8")
    return parser.parse_script(p)


F01 = "TÍTULO: Teste\nFORMATO: PERSONAGEM_FALANDO\nPERSONAGEM: Paulo\n\n{}\n\nFIM\n"
T02 = "TÍTULO: Teste\nFORMATO: ENTREVISTA_COM_MENTOR\n\nCENA 01 | PERSONAGEM: PAULO\nOlá, tudo bem?\n\n{}\n\nFIM\n"


def test_extrair():
    txt, anims, avisos = marcacoes.extrair(f"[JORNADA: Título | PORTA: deixa o contato | PRESENTE: recebe a isca] {FALA}")
    assert txt == FALA and not avisos and anims[0]["tipo"] == "journey"
    p = anims[0]["payload"]
    assert p["title"] == "Título" and [s["obj"] for s in p["steps"]] == ["door", "gift"]


def test_objeto_desconhecido():
    _, anims, avisos = marcacoes.extrair("[JORNADA: FOGUETE: decola | PORTA: entra] texto")
    assert anims[0]["payload"]["steps"][0]["obj"] == "door" and any("FOGUETE" in a for a in avisos)


def test_quantidade_de_etapas():
    for n in (1, 6):
        marca = " | ".join(f"PORTA: e{i}" for i in range(n))
        assert not marcacoes.extrair(f"[JORNADA: {marca}] x")[1]


def test_ingles():
    _, anims, _ = marcacoes.extrair("[JOURNEY: DOOR: leave your email | GIFT: free guide] text")
    assert [s["obj"] for s in anims[0]["payload"]["steps"]] == ["door", "gift"]


def test_cena_sem_jornada():
    r = script(F01.format(f"CENA 01 | MODO: ANIMACAO\nNARRAÇÃO: {FALA}\nIMAGEM: x"))
    assert any("MODO ANIMACAO" in p for p in r["problemas"])


def test_dolly_vira_animacao():
    r = script(F01.format(f"CENA 01 | MODO: DOLLY\nNARRAÇÃO: [JORNADA: PORTA: deixa o contato | PRESENTE: recebe a isca] {FALA}\nIMAGEM: x"))
    c = r["cenas"][0]
    assert c["mode"] == "animacao" and c["animacao"]["cena"] == "jornada" and c["text"] == FALA and not r["problemas"]
    assert any("virou MODO ANIMACAO" in a for a in r["avisos_animacao"])


def test_bloco_no_template_1():
    r = script(F01.format("CENA 01 | MODO: ANIMACAO\nNARRAÇÃO: Trezentos sistemas instalados.\nANIMACAO: contador\nnumero: 300\n"
                          "rotulo: sistemas\nIMAGEM: x\nBUSCA: y"))
    c = r["cenas"][0]
    assert c["text"] == "Trezentos sistemas instalados." and c["descricao_imagem"] == "x" and not r["problemas"]
    assert c["animacao"] == {"cena": "contador", "params": {"numero": "300", "rotulo": "sistemas"}}


def test_bloco_no_template_2():
    r = script(T02.format(f"CENA 02 | PERSONAGEM: BOB\n{FALA}\nANIMACAO: jornada\netapa: PORTA | deixa o contato\netapa: CASA | recebe a isca"))
    c = r["cenas"][1]
    assert c["text"] == FALA and c["animacao"]["params"]["etapa"][1] == "CASA | recebe a isca" and not r["problemas"]


def test_animacao_inexistente():
    r = script(F01.format("CENA 01 | MODO: ANIMACAO\nNARRAÇÃO: Texto.\nANIMACAO: nao-existe"))
    assert any("não existe" in p for p in r["problemas"])


def test_template_3():
    r = script(f"TITULO: T\nFORMATO: SO_ANIMACAO\n\nFALA: {FALA}\nCENA: jornada\netapa: PORTA | deixa o contato\netapa: TROFEU | ganha um trofeu\n")
    assert r["template"] == "A01" and not r["problemas"] and any("trofeu" in a for a in r["avisos_animacao"])
    assert any("2 a 5" in p for p in script(f"TITULO: T\nFALA: {FALA}\nCENA: jornada\netapa: PORTA | x\n")["problemas"])


def test_template_3_com_marcacao():
    r = script(f"TITULO: T\nFORMATO: SO_ANIMACAO\n\nFALA: [JORNADA: Funil | PORTA: deixa o contato | PRESENTE: recebe a isca] {FALA}\n")
    assert r["cenas"][0]["cena"] == "jornada" and r["cenas"][0]["text"] == FALA and len(r["cenas"][0]["etapas"]) == 2


def test_check_nao_pede_imagem():
    r = script(F01.format(f"CENA 01 | MODO: ANIMACAO\nNARRAÇÃO: [JORNADA: PORTA: deixa o contato | PRESENTE: recebe a isca] {FALA}\nIMAGEM: x"))
    v = {"template": "F01", "problemas_pdf": [], "cenas": r["cenas"], "personagens": [], "imagens": [""]}
    assert not jobs.check(v)["problemas"]


if __name__ == "__main__":
    tests = [(k, f) for k, f in sorted(globals().items()) if k.startswith("test_")]
    for name, f in tests:
        f()
        print("ok", name)
    print(len(tests), "testes passaram")
