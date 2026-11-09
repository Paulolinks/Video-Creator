// Gera os vídeos a partir dos roteiros da pasta "roteiros".
// Uso: node scripts/gerar.mjs            -> gera todos os roteiros que ainda não têm vídeo
//      node scripts/gerar.mjs dia01       -> gera (ou refaz) só o dia01
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execSync} from 'node:child_process';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const P = (...a) => path.join(ROOT, ...a);
const FPS = 30, GAP = 0.35, LEAD = 0.4, TAIL = 1.0;

// ---------- config ----------
function lerConfig() {
  const cfg = {};
  const f = P('config.txt');
  if (fs.existsSync(f)) for (const l of fs.readFileSync(f, 'utf8').split(/\r?\n/)) {
    const m = l.match(/^\s*([A-Z_]+)\s*=\s*(.*)\s*$/); if (m) cfg[m[1]] = m[2].trim();
  }
  return cfg;
}

// ---------- roteiro ----------
export function lerRoteiro(txt) {
  const head = {}; const linhas = []; let cur = null;
  for (const raw of txt.split(/\r?\n/)) {
    const l = raw.trim(); if (!l || l.startsWith('#')) continue;
    const i = l.indexOf(':'); if (i < 0) continue;
    const k = l.slice(0, i).trim().toLowerCase(); const v = l.slice(i + 1).trim();
    if (k === 'fala') { cur = {text: v, scene: 'frase', hl: [], params: {}}; linhas.push(cur); continue; }
    if (!cur) { head[k] = v; continue; }
    if (k === 'cena') cur.scene = v.toLowerCase();
    else if (k === 'destaque') cur.hl = v.split(',').map(s => s.trim()).filter(Boolean);
    else if (cur.params[k] === undefined) cur.params[k] = v;
    else cur.params[k] = [].concat(cur.params[k], v);
  }
  return {head, linhas};
}

// ---------- voz ----------
function palavrasDoAlinhamento(al) {
  const words = []; let w = null;
  al.characters.forEach((ch, i) => {
    if (/\s/.test(ch)) { w = null; return; }
    if (!w) { w = {w: '', t: al.character_start_times_seconds[i]}; words.push(w); }
    w.w += ch;
  });
  return words;
}
function estimar(text) {
  const ws = text.split(/\s+/).filter(Boolean); let t = 0; const words = [];
  for (const w of ws) { words.push({w, t}); t += 0.33 + (/[,.;?!]$/.test(w) ? 0.18 : 0); }
  return {words, duration: t + 0.2};
}
async function falar({text, prev, next, voz, modelo, chave, destino}) {
  const meta = destino.replace(/\.mp3$/, '.json');
  if (fs.existsSync(meta) && fs.existsSync(destino)) {
    const m = JSON.parse(fs.readFileSync(meta, 'utf8'));
    if (m.text === text && m.voz === voz && m.modelo === modelo) return m;
  }
  const url = `${process.env.ELEVENLABS_BASE || 'https://api.elevenlabs.io'}/v1/text-to-speech/${encodeURIComponent(voz)}/with-timestamps?output_format=mp3_44100_128`;
  const body = {text, model_id: modelo, previous_text: prev || undefined, next_text: next || undefined, voice_settings: {stability: 0.5, similarity_boost: 0.8, style: 0.2, use_speaker_boost: true}};
  const r = await fetch(url, {method: 'POST', headers: {'xi-api-key': chave, 'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!r.ok) throw new Error(`ElevenLabs respondeu ${r.status}: ${(await r.text()).slice(0, 300)}`);
  const j = await r.json();
  fs.writeFileSync(destino, Buffer.from(j.audio_base64, 'base64'));
  const al = j.alignment || j.normalized_alignment;
  const ends = al.character_end_times_seconds;
  const m = {text, voz, modelo, words: palavrasDoAlinhamento(al), duration: ends[ends.length - 1]};
  fs.writeFileSync(meta, JSON.stringify(m));
  return m;
}

// ---------- monta a linha do tempo ----------
async function montar(nome, cfg) {
  // GUARDIAN_*: enviados pelo Video Creator (template "Só animação"); sem eles, tudo funciona como antes
  const app = process.env;
  const {head, linhas} = lerRoteiro(fs.readFileSync(app.GUARDIAN_ROTEIRO || P('roteiros', nome + '.txt'), 'utf8'));
  if (!linhas.length) throw new Error('o roteiro não tem nenhuma linha FALA:');
  const chave = cfg.ELEVENLABS_API_KEY, voz = head.voz || cfg.VOZ_ID, modelo = cfg.MODELO || 'eleven_multilingual_v2';
  const externo = cfg.COMANDO_VOZ && cfg.COMANDO_VOZ.trim();
  const comVoz = Boolean(chave && voz);
  const gen = P('public', 'gen', nome); fs.mkdirSync(gen, {recursive: true});
  let ext = null;
  if (externo) {
    // Motor de voz externo (ex.: a voz clonada do Video Creator).
    // Recebe {entrada} = JSON {"voz": "...", "linhas": ["texto 1", ...]} e {saida} = pasta.
    // Deve gravar em {saida}/resultado.json: [{"audio": "01.wav", "duration": 2.3, "words": [{"w": "Hello", "t": 0.05}, ...]}, ...]
    const entrada = path.join(gen, 'linhas.json');
    const novo = JSON.stringify({voz: app.GUARDIAN_VOZ || head.voz || cfg.VOZ_PERSONAGEM || '', linhas: linhas.map(l => l.text), ...(app.GUARDIAN_IDIOMA ? {idioma: app.GUARDIAN_IDIOMA} : {})});
    const res = path.join(gen, 'resultado.json');
    const igual = fs.existsSync(entrada) && fs.readFileSync(entrada, 'utf8') === novo && fs.existsSync(res);
    if (!igual) {
      fs.writeFileSync(entrada, novo);
      if (fs.existsSync(res)) fs.unlinkSync(res);
      console.log('  gerando a voz pelo motor externo...');
      execSync(externo.replaceAll('{entrada}', `"${entrada}"`).replaceAll('{saida}', `"${gen}"`), {stdio: 'inherit', cwd: ROOT});
    } else console.log('  voz já gerada antes, reaproveitando');
    ext = JSON.parse(fs.readFileSync(res, 'utf8'));
    if (ext.length !== linhas.length) throw new Error(`o motor de voz devolveu ${ext.length} áudios para ${linhas.length} falas`);
  } else if (!comVoz) console.log('  ! Sem voz configurada no config.txt: o vídeo sai SEM VOZ, só para conferir o visual.');
  let t = LEAD; const out = [];
  for (let i = 0; i < linhas.length; i++) {
    const l = linhas[i];
    let audio = null, words, duration;
    if (ext) {
      ({words, duration} = ext[i]); audio = `gen/${nome}/${ext[i].audio}`;
    } else if (comVoz) {
      process.stdout.write(`  voz ${i + 1}/${linhas.length}... `);
      const file = String(i + 1).padStart(2, '0') + '.mp3';
      const m = await falar({text: l.text, prev: linhas[i - 1]?.text, next: linhas[i + 1]?.text, voz, modelo, chave, destino: path.join(gen, file)});
      ({words, duration} = m); audio = `gen/${nome}/${file}`; console.log('ok');
    } else ({words, duration} = estimar(l.text));
    out.push({text: l.text, hl: l.hl, scene: l.scene, params: l.params, start: Math.round(t * FPS), dur: Math.round((duration + GAP) * FPS), audio, words});
    t += duration + GAP;
  }
  let music = null;
  const mus = app.GUARDIAN_MUSICA || head.musica;
  if (mus) {
    const src = path.isAbsolute(mus) ? mus : P('musica', mus);
    if (fs.existsSync(src)) { const dst = 'musica' + path.extname(mus); fs.copyFileSync(src, path.join(gen, dst)); music = {file: `gen/${nome}/${dst}`, volume: parseFloat(app.GUARDIAN_VOLUME || head.volume_musica || cfg.VOLUME_MUSICA || '0.12')}; }
    else console.log(`  ! Música "${mus}" não encontrada na pasta musica. Seguindo sem música.`);
  }
  let logo = null;
  if (app.GUARDIAN_LOGO) { const dst = 'logo' + path.extname(app.GUARDIAN_LOGO); fs.copyFileSync(app.GUARDIAN_LOGO, path.join(gen, dst)); logo = `gen/${nome}/${dst}`; }
  return {fps: FPS, total: Math.round((t + TAIL) * FPS), music, logo, lines: out};
}

// ---------- principal ----------
async function main() {
  const cfg = lerConfig();
  const pedidos = process.argv.slice(2).map(a => path.basename(a).replace(/\.txt$/i, ''));
  const todos = fs.readdirSync(P('roteiros')).filter(f => f.toLowerCase().endsWith('.txt')).map(f => f.slice(0, -4));
  const fila = pedidos.length ? pedidos : todos.filter(n => !fs.existsSync(P('videos', n + '.mp4')));
  if (!fila.length) { console.log('Nada para gerar: todos os roteiros já têm vídeo na pasta "videos".\nPara refazer um, apague o vídeo ou rode: gerar-video.bat dia01'); return; }
  fs.mkdirSync(P('videos'), {recursive: true});
  const tls = {};
  for (const n of fila) {
    console.log(`\n[${n}] lendo roteiro e gerando voz`);
    try { tls[n] = await montar(n, cfg); } catch (e) { console.log(`  ERRO: ${e.message}`); }
  }
  const prontos = Object.keys(tls); if (!prontos.length) process.exit(1);
  console.log('\nPreparando o projeto de vídeo (só demora na primeira vez)...');
  const {bundle} = await import('@remotion/bundler');
  const {renderMedia, selectComposition} = await import('@remotion/renderer');
  const serveUrl = await bundle({entryPoint: P('src', 'index.ts'), publicDir: P('public')});
  const browserExecutable = process.env.REMOTION_CHROME || null;
  for (const n of prontos) {
    const inputProps = {timeline: tls[n]};
    const composition = await selectComposition({serveUrl, id: 'Video', inputProps, browserExecutable});
    const saida = process.env.GUARDIAN_SAIDA || P('videos', n + '.mp4');
    let last = -1;
    await renderMedia({composition, serveUrl, codec: 'h264', outputLocation: saida, inputProps, browserExecutable,
      onProgress: ({progress}) => { const p = Math.floor(progress * 10); if (p !== last) { last = p; process.stdout.write(`\r[${n}] renderizando ${p * 10}%  `); } }});
    console.log(`\n[${n}] pronto: videos\\${n}.mp4 (${(tls[n].total / FPS).toFixed(1)} s)`);
  }
}
main().catch(e => { console.error('\nERRO:', e.message); process.exit(1); });
