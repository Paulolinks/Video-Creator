"""PDF of the A01 framework from its .md, with the same look as the other two frameworks."""
import re
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_framework_pdfs as m  # noqa: E402

M = Path(r"D:\Video-Creator\app\static\modelos")
lines = [x for x in (M / "Framework_A01_So_Animacao.md").read_text(encoding="utf-8").splitlines() if not x.startswith("<!--")]


def inline(t):
    t = escape(t.replace("\\|", "|"), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"`([^`]+)`", r'<font face="Mono">\1</font>', t)


story, i = [m.header("Framework A01 — Só animação", "Framework de roteiro para vídeos só com animações, sem personagem.",
                     "VIDEO CREATOR · FRAMEWORK DE ROTEIRO · VERSÃO 2.2"), m.Spacer(1, 8)], 2
while i < len(lines):
    x = lines[i]
    if x.startswith("```"):
        j = i + 1
        while not lines[j].startswith("```"):
            j += 1
        story.append(m.code("\n".join(lines[i + 1:j])))
        i = j + 1
        continue
    if x.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            rows.append([c.strip() for c in re.split(r"(?<!\\)\|", lines[i])[1:-1]])
            i += 1
        rows = [[inline(c) for c in r] for k, r in enumerate(rows) if k != 1]
        story.append(m.table(rows, [28, 72, 74] if rows[0][0] == "CENA" else [20, 60, 94]))
        continue
    if x.startswith("## "):
        story.append(m.P(inline(x[3:]), "h2"))
    elif x.startswith(("- [ ] ", "- ")):
        story += m.bullets([inline(x.split(" ", 3)[3] if x.startswith("- [ ]") else x[2:])])
    elif re.match(r"\d+\. ", x):
        n, t = x.split(". ", 1)
        story.append(m.Paragraph(inline(t), m.S["li"], bulletText=f"{n}."))
    elif x.strip():
        story.append(m.P(inline(x)))
    i += 1
m.build(M / "Framework_A01_So_Animacao.pdf", "Framework A01 — Só animação", story)
