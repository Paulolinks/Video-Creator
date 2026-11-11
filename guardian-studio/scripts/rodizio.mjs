// Rodízio: quando o roteiro não escolhe, cada vídeo sai com tema, texto, transições, câmera e capa diferentes.
// Sorteio fixo por roteiro (mesmo roteiro = mesmo vídeo). Só mexe no visual; o que está escrito no roteiro vence.
import fs from 'node:fs';
import path from 'node:path';

const semente = (s) => { let h = 2166136261; for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
export function sorteio(s) { let a = semente(s); return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const pega = (r, a) => a[Math.floor(r() * a.length)];

const TEMAS = ['claro', 'noite', 'blueprint', 'papel', 'terminal'];
const TEXTOS = ['topo', 'centro', 'baixo', 'caixa'];
const TRANSICOES = ['blocos', 'deslizar', 'zoom', 'cortina', 'circulo'];
const CAMERAS = ['zoom-in', 'zoom-out', 'pan-esquerda', 'pan-direita'];
export const DESENHOS = ['seta', 'circulo', 'sublinhado', 'exclamacao', 'relogio', 'casa', 'telefone'];

const alerta = (l) => /\balert/i.test(l.text) || Object.values(l.params).flat().some(v => /^(laranja|orange|vermelho|red|check)$/i.test(String(v)) || /\|\s*(check|laranja|orange|vermelho|red)\s*$/i.test(String(v)));
const palavras = (t) => t.split(/\s+/).filter(Boolean).length;

function lerHist(arq) { try { return {ultimos: [], feitos: {}, ...JSON.parse(fs.readFileSync(arq, 'utf8'))}; } catch { return {ultimos: [], feitos: {}}; } }

function estiloCapa(r, head, linhas, evitar, titulo) {
  const pool = ['gigante', 'dividida', 'moldura', 'faixas'];
  if (/\?\s*$/.test(titulo)) pool.push('pergunta', 'pergunta');
  if (/\d/.test(titulo)) pool.push('numero', 'numero');
  if (linhas.some(alerta)) pool.push('alerta');
  if (linhas.some(l => l.scene === 'produto' || l.scene === 'guardian3d')) pool.push('produto');
  const livres = pool.filter(e => !evitar.includes(e));
  return pega(r, livres.length ? livres : pool);
}

// Preenche head e linhas com o que o roteiro não definiu. Devolve os valores do vídeo.
export function aplicarRodizio(root, nome, head, linhas, customRodizio = []) {
  const titulo = head.capa_titulo || head.titulo || head['título'] || nome;
  const desligado = (head.rodizio || 'sim').toLowerCase() === 'nao' || (head.rodizio || '').toLowerCase() === 'não';
  const capaBase = {titulo, destaque: (head.capa_destaque || '').split(',').map(s => s.trim()).filter(Boolean), numero: head.capa_numero || (titulo.match(/[\d][\d.,]*/) || [''])[0], selo: head.capa_selo || ''};
  if (desligado) return {tema: head.tema || 'claro', texto: head.texto || 'topo', capa: {...capaBase, estilo: head.capa_estilo || 'gigante', desenho: 'seta'}, padrao: head.transicao || 'blocos'};

  const arq = path.join(root, 'rodizio.json'), hist = lerHist(arq);
  const r = sorteio('nome-' + nome);
  let esc = hist.feitos[nome];
  if (!esc) {
    const ult3 = hist.ultimos.slice(-3);
    const usadosTema = ult3.map(u => u.tema);
    const pool = TEMAS.concat(linhas.filter(l => /\balert/i.test(l.text)).length >= 3 ? ['alerta'] : []);
    const livres = pool.filter(t => !usadosTema.includes(t));
    const ultTexto = hist.ultimos.slice(-1).map(u => u.texto);
    const txtLivres = TEXTOS.filter(t => !ultTexto.includes(t));
    esc = {tema: pega(r, livres.length ? livres : pool), texto: pega(r, txtLivres), capa: estiloCapa(r, head, linhas, ult3.map(u => u.capa), titulo), desenho: pega(r, DESENHOS)};
    hist.feitos[nome] = esc;
    hist.ultimos = hist.ultimos.concat({nome, ...esc}).slice(-5);
    fs.writeFileSync(arq, JSON.stringify(hist, null, 2));
  }
  const tema = head.tema || esc.tema, texto = head.texto || esc.texto;
  const fixa = head.transicao && head.transicao.toLowerCase() !== 'mista' ? head.transicao.toLowerCase() : null;

  // Cada fala tem o seu próprio sorteio: mudar uma fala não embaralha as outras.
  let anterior = null;
  linhas.forEach((l, i) => {
    const q = sorteio(`nome-${nome}-fala-${i}`);
    const al = alerta(l);
    if (!l.transicao && !fixa) {
      const op = TRANSICOES.concat(al ? ['flash'] : []).filter(t => t !== anterior);
      l.transicao = pega(q, op);
    }
    anterior = l.transicao || fixa;
    const c = q();
    if (!l.camera && c < 0.4) l.camera = pega(q, al ? CAMERAS.concat('tremer') : CAMERAS);
    if (!l.texto && !head.texto && l.scene === 'frase' && palavras(l.text) <= 6 && q() < 0.25) l.texto = 'palavra';
    l.variante = Math.floor(q() * 3);
    if (l.scene === 'frase' && !l.params.grande && !l.params._desenho && l.texto !== 'palavra' && q() < 0.6) {
      const extras = customRodizio.map(n => 'custom:' + n);
      l.params._desenho = pega(q, DESENHOS.concat(extras));
    }
  });
  return {tema, texto, capa: {...capaBase, estilo: (head.capa_estilo || esc.capa).toLowerCase(), desenho: esc.desenho}, padrao: fixa};
}
