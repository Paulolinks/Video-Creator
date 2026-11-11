// Linha do tempo da JORNADA, sem desenho: quando cada etapa acende, por onde o boneco anda e para onde a câmera olha.
export type Palavra = {w: string; t: number};
export type Seg = {ini: number; fim: number; x0: number; x1: number};
export type Linha = {ats: number[]; segs: Seg[]; dur: number};

export const LARG = 860, VARANDA = 120, PARADA = 230;
export const centroComodo = (i: number) => VARANDA + (i + 0.5) * LARG;
export const posBoneco = (i: number) => centroComodo(i) - PARADA;

const norm = (s: string) => s.normalize('NFD').replace(/\p{Mn}/gu, '').toUpperCase().replace(/[^A-Z0-9%]/g, '');
const STOP = new Set(['PARA', 'COMO', 'MAIS', 'QUE', 'COM', 'UMA', 'ESSE', 'ESSA', 'ISSO', 'ESTE', 'ESTA', 'SEUS', 'SUAS', 'SOBRE', 'THE', 'AND', 'WITH', 'THAT', 'THIS', 'YOUR', 'FROM', 'INTO', 'MUITO', 'PELO', 'PELA', 'NAO']);
const chaves = (t: string) => [...new Set(t.split(/\s+/).map(norm).filter(w => w.length >= 4 && !STOP.has(w)))];
const bate = (n: string, c: string) => n === c || (c.length >= 5 && n.length >= 5 && n.slice(0, 5) === c.slice(0, 5));

// A primeira posição a partir de "ini" com mais palavras do rótulo logo em seguida (igual às etapas do FLUXO).
const acharItem = (ws: string[], ini: number, ks: string[]) => {
  let melhor = 0, pos: number | null = null;
  for (let j = ini; j < Math.min(ws.length, ini + 80); j++) {
    if (!ks.some(c => bate(ws[j], c))) continue;
    const janela = ws.slice(j, j + ks.length + 2);
    const score = ks.filter(c => janela.some(w => bate(w, c))).length;
    if (score > melhor) { melhor = score; pos = j; }
  }
  return pos;
};

// Em que segundo da fala cada etapa acende. A etapa que não é dita fica no meio das vizinhas, até 85% da cena.
export function tempos(labels: string[], palavras: Palavra[], dur: number): number[] {
  const ws = palavras.map(p => norm(p.w));
  const achados: (number | null)[] = [];
  let cur = 0;
  for (const l of labels) {
    const j = acharItem(ws, cur, chaves(l));
    achados.push(j === null ? null : palavras[j].t);
    if (j !== null) cur = j + 1;
  }
  const n = labels.length, lim = dur * 0.85;
  if (achados[n - 1] === null) achados[n - 1] = Math.max(lim, (achados.filter(a => a !== null).pop() ?? 0) + 0.5);
  let ia = -1, ta = 0;
  for (let i = 0; i < n; i++) {
    if (achados[i] === null) continue;
    for (let k = ia + 1; k < i; k++) achados[k] = ta + ((achados[i] as number) - ta) * (k - ia) / (i - ia);
    ia = i; ta = achados[i] as number;
  }
  return achados as number[];
}

// O boneco chega antes de a voz falar a etapa; se o tempo for curto, ele corre.
export function linhaDoTempo(ats: number[], dur: number): Linha {
  const x0 = -90, chega = Math.min(ats[0], Math.max(0.25, ats[0] - 0.6));
  const dist = posBoneco(0) - x0, v = Math.max(dist / Math.max(chega, 0.01), 180);
  const segs: Seg[] = [{ini: Math.max(0, chega - dist / v), fim: chega, x0, x1: posBoneco(0)}];
  for (let i = 1; i < ats.length; i++) {
    const gap = ats[i] - ats[i - 1];
    let sai = ats[i - 1] + Math.min(1.2, gap * 0.45);
    const fim = ats[i] - Math.min(0.4, gap * 0.15);
    if (LARG / (fim - sai) < 520) sai = fim - LARG / 520;
    segs.push({ini: sai, fim, x0: posBoneco(i - 1), x1: posBoneco(i)});
  }
  return {ats, segs, dur};
}

export const posEm = (l: Linha, t: number) => {
  for (const s of l.segs) {
    if (t < s.ini) return s.x0;
    if (t <= s.fim) return s.x0 + (s.x1 - s.x0) * (s.fim > s.ini ? (t - s.ini) / (s.fim - s.ini) : 1);
  }
  return l.segs[l.segs.length - 1].x1;
};

export const andandoEm = (l: Linha, t: number) => l.segs.some(s => t >= s.ini && t < s.fim);
export const segAtual = (l: Linha, t: number) => l.segs.findIndex(s => t >= s.ini && t < s.fim);

const suave = (p: number) => p * p * (3 - 2 * p);
export const cameraEm = (l: Linha, t: number, tela: number) => {
  const n = l.ats.length, total = 2 * VARANDA + n * LARG;
  const lim = (x: number) => Math.max(tela / 2, Math.min(Math.max(tela / 2, total - tela / 2), x));
  for (let i = 1; i < n; i++) {
    const s = l.segs[i];
    if (t <= s.ini) return lim(centroComodo(i - 1));
    if (t < s.fim) return lim(centroComodo(i - 1)) + (lim(centroComodo(i)) - lim(centroComodo(i - 1))) * suave((t - s.ini) / (s.fim - s.ini));
  }
  return lim(centroComodo(n - 1));
};

export type Acao = 'andar' | 'parado' | 'apontar' | 'surpresa' | 'comemorar';
export const acaoEm = (l: Linha, t: number): Acao => {
  const n = l.ats.length;
  if (t >= l.ats[n - 1]) return 'comemorar';
  if (andandoEm(l, t)) return 'andar';
  let i = -1;
  l.ats.forEach((a, k) => { if (t >= a) i = k; });
  if (i >= 0 && t - l.ats[i] < 0.3) return 'surpresa';
  return t >= l.segs[0].fim ? 'apontar' : 'parado';
};
