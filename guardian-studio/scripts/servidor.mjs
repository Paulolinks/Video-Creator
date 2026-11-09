// Tela do Guardian Studio: http://localhost:5610
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const P = (...a) => path.join(ROOT, ...a);
const PORTA = Number(process.env.PORTA || 5610);
const SCENES = ['contador', 'tabela', 'console', 'contato', 'termostato', 'busca', 'barras', 'produto', 'comentario', 'mapa', 'imagem', 'frase'];
const nomeOk = n => /^[A-Za-z0-9_-]{1,60}$/.test(n || '');
let job = {rodando: false, nome: null, log: [], progresso: 0, fim: null, ok: null};

function lerConfig() {
  const cfg = {}; const f = P('config.txt');
  if (fs.existsSync(f)) for (const l of fs.readFileSync(f, 'utf8').split(/\r?\n/)) { const m = l.match(/^\s*([A-Z_]+)\s*=\s*(.*)$/); if (m) cfg[m[1]] = m[2].trim(); }
  return cfg;
}
function salvarConfig(novos) {
  const f = P('config.txt'); let txt = fs.existsSync(f) ? fs.readFileSync(f, 'utf8') : '';
  for (const [k, v] of Object.entries(novos)) {
    if (!/^[A-Z_]+$/.test(k) || /[\r\n]/.test(String(v))) continue;
    const re = new RegExp(`^\\s*${k}\\s*=.*$`, 'm');
    txt = re.test(txt) ? txt.replace(re, `${k}=${v}`) : txt + `\r\n${k}=${v}`;
  }
  fs.writeFileSync(f, txt);
}
function personagens() {
  const d = path.resolve(ROOT, '..', 'app', 'data', 'personagens');
  try { return fs.readdirSync(d, {withFileTypes: true}).filter(e => e.isDirectory()).map(e => e.name); } catch { return []; }
}
const lista = (dir, ext) => { try { return fs.readdirSync(P(dir)).filter(f => ext.some(e => f.toLowerCase().endsWith(e))); } catch { return []; } };

function gerar(nome) {
  job = {rodando: true, nome, log: [], progresso: 0, fim: null, ok: null};
  const ch = spawn(process.execPath, [P('scripts', 'gerar.mjs'), nome], {cwd: ROOT});
  const on = buf => {
    for (const parte of buf.toString().split(/[\r\n]+/)) {
      const s = parte.trim(); if (!s || /memory|CGroup|docker run|lower amount/i.test(s)) continue;
      const m = s.match(/renderizando (\d+)%/); if (m) { job.progresso = Number(m[1]); continue; }
      job.log.push(s); if (job.log.length > 200) job.log.shift();
    }
  };
  ch.stdout.on('data', on); ch.stderr.on('data', on);
  ch.on('close', code => { job.rodando = false; job.ok = code === 0; job.fim = Date.now(); if (code === 0) job.progresso = 100; });
}

const json = (res, obj, code = 200) => { res.writeHead(code, {'Content-Type': 'application/json; charset=utf-8'}); res.end(JSON.stringify(obj)); };
const corpo = req => new Promise(r => { let b = ''; req.on('data', c => { b += c; if (b.length > 2e6) req.destroy(); }); req.on('end', () => { try { r(JSON.parse(b || '{}')); } catch { r({}); } }); });

function mandarArquivo(req, res, f, tipo) {
  if (!fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  const tam = fs.statSync(f).size; const r = req.headers.range;
  if (r) {
    const [a, b] = r.replace('bytes=', '').split('-'); const ini = Number(a), fim = b ? Number(b) : tam - 1;
    res.writeHead(206, {'Content-Type': tipo, 'Content-Range': `bytes ${ini}-${fim}/${tam}`, 'Accept-Ranges': 'bytes', 'Content-Length': fim - ini + 1});
    return fs.createReadStream(f, {start: ini, end: fim}).pipe(res);
  }
  res.writeHead(200, {'Content-Type': tipo, 'Content-Length': tam, 'Accept-Ranges': 'bytes'}); fs.createReadStream(f).pipe(res);
}

http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://x'); const q = u.searchParams;
  try {
    if (u.pathname === '/') return mandarArquivo(req, res, P('ui', 'index.html'), 'text/html; charset=utf-8');
    if (u.pathname === '/api/estado') {
      const cfg = lerConfig();
      const roteiros = lista('roteiros', ['.txt']).map(f => { const n = f.slice(0, -4); const v = P('videos', n + '.mp4'); return {nome: n, video: fs.existsSync(v), quando: fs.existsSync(v) ? fs.statSync(v).mtimeMs : null}; });
      return json(res, {roteiros, musicas: lista('musica', ['.mp3', '.wav', '.m4a']), imagens: lista(path.join('public', 'imagens'), ['.png', '.jpg', '.jpeg', '.webp']), personagens: personagens(), cenas: SCENES,
        config: {VOZ_PERSONAGEM: cfg.VOZ_PERSONAGEM || '', VOLUME_MUSICA: cfg.VOLUME_MUSICA || '0.12', voz: cfg.COMANDO_VOZ ? 'videocreator' : (cfg.ELEVENLABS_API_KEY ? 'elevenlabs' : 'nenhuma')}, job});
    }
    if (u.pathname === '/api/roteiro' && req.method === 'GET') { const n = q.get('nome'); if (!nomeOk(n)) return json(res, {erro: 'nome inválido'}, 400); return json(res, {texto: fs.readFileSync(P('roteiros', n + '.txt'), 'utf8')}); }
    if (u.pathname === '/api/roteiro' && req.method === 'POST') { const b = await corpo(req); if (!nomeOk(b.nome)) return json(res, {erro: 'Use só letras, números, - e _ no nome (ex.: dia02).'}, 400); fs.writeFileSync(P('roteiros', b.nome + '.txt'), String(b.texto || '')); return json(res, {ok: true}); }
    if (u.pathname === '/api/config' && req.method === 'POST') { const b = await corpo(req); const ok = {}; if (b.VOZ_PERSONAGEM !== undefined) ok.VOZ_PERSONAGEM = b.VOZ_PERSONAGEM; if (b.VOLUME_MUSICA !== undefined) ok.VOLUME_MUSICA = b.VOLUME_MUSICA; salvarConfig(ok); return json(res, {ok: true}); }
    if (u.pathname === '/api/gerar' && req.method === 'POST') { const b = await corpo(req); if (!nomeOk(b.nome)) return json(res, {erro: 'nome inválido'}, 400); if (job.rodando) return json(res, {erro: 'Já tem um vídeo sendo gerado.'}, 409); gerar(b.nome); return json(res, {ok: true}); }
    if (u.pathname === '/framework') { res.setHeader('Content-Disposition', 'attachment; filename="Framework_G01_Guardian_Motion.md"'); return mandarArquivo(req, res, P('Framework_G01_Guardian_Motion.md'), 'text/markdown; charset=utf-8'); }
    if (u.pathname.startsWith('/videos/')) { const n = decodeURIComponent(u.pathname.slice(8)); if (!/^[A-Za-z0-9_-]+\.mp4$/.test(n)) { res.writeHead(400); return res.end(); } return mandarArquivo(req, res, P('videos', n), 'video/mp4'); }
    res.writeHead(404); res.end();
  } catch (e) { json(res, {erro: e.message}, 500); }
}).listen(PORTA, '127.0.0.1', () => console.log(`Guardian Studio aberto em http://localhost:${PORTA}  (feche esta janela para parar)`));
