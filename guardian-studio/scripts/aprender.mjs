// Ensina animações novas ao motor a partir de um arquivo separado dos roteiros.
// Uso: node scripts/aprender.mjs arquivo.txt pasta_saida
// Cada animação é testada sozinha numa cópia do projeto, então uma cena com defeito nunca atrapalha um vídeo em andamento.
// Só a que renderiza inteira entra em src/custom. Grava pasta_saida/resultado.json e pasta_saida/<nome>.mp4 (vídeo de exemplo).
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {arquivoDaCena, nomeDoArquivo, sincronizar, validarNome} from './biblioteca.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const QUADROS = 180;

// CODIGO: nome ... FIM_CODIGO, seguido (opcional) de EXEMPLO ... FIM_EXEMPLO com os campos do vídeo de teste.
export function lerArquivo(txt) {
  const blocos = []; let cur = null, ex = null;
  for (const raw of txt.replace(/^﻿/, '').split(/\r?\n/)) {
    const t = raw.trim();
    if (cur) {
      if (/^FIM_CODIGO\s*$/i.test(t)) { blocos.push(cur); cur = null; }
      else if (!/^```/.test(t)) cur.linhas.push(raw);
      continue;
    }
    const m = t.match(/^CODIGO\s*:\s*(.+)$/i);
    if (m) { ex = null; cur = {nome: nomeDoArquivo(m[1]), linhas: [], exemplo: {}}; continue; }
    if (/^EXEMPLO\s*:?\s*$/i.test(t) && blocos.length) { ex = blocos[blocos.length - 1].exemplo; continue; }
    if (/^FIM_EXEMPLO\s*$/i.test(t)) { ex = null; continue; }
    if (!ex) continue;
    const i = t.indexOf(':'); if (i < 0) continue;
    const k = t.slice(0, i).trim().toLowerCase(), v = t.slice(i + 1).trim();
    ex[k] = ex[k] === undefined ? v : [].concat(ex[k], v);
  }
  if (cur) blocos.push({...cur, semFim: true});
  return blocos;
}

async function main() {
  const [arquivo, saida] = process.argv.slice(2);
  fs.mkdirSync(saida, {recursive: true});
  const blocos = lerArquivo(fs.readFileSync(arquivo, 'utf8'));
  const resultado = [];
  const copia = path.join(ROOT, '.aprender', String(process.pid));
  const browserExecutable = process.env.REMOTION_CHROME || null;
  try {
    fs.cpSync(path.join(ROOT, 'src'), path.join(copia, 'src'), {recursive: true, filter: f => !f.includes('_quebradas')});
    const custom = path.join(copia, 'src', 'custom');
    const {bundle} = await import('@remotion/bundler');
    const {renderMedia, selectComposition} = await import('@remotion/renderer');
    for (const b of blocos) {
      const destino = path.join(custom, b.nome + '.tsx'), oficial = path.join(ROOT, 'src', 'custom', b.nome + '.tsx');
      const existia = fs.existsSync(oficial);
      try {
        if (b.semFim) throw new Error('falta a linha FIM_CODIGO');
        validarNome(b.nome);
        fs.writeFileSync(destino, arquivoDaCena(b.nome, b.linhas.join('\n')));
        sincronizar(copia);
        console.log(`[${b.nome}] testando...`);
        const serveUrl = await bundle({entryPoint: path.join(copia, 'src', 'index.ts'), publicDir: path.join(ROOT, 'public')});
        const inputProps = {cena: b.nome, params: b.exemplo, words: [], inicio: 0, total: QUADROS, tema: 'claro', texto: 'topo', idioma: 'pt'};
        const composition = await selectComposition({serveUrl, id: 'CenaSolta', inputProps, browserExecutable});
        await renderMedia({composition, serveUrl, codec: 'h264', muted: true, outputLocation: path.join(saida, b.nome + '.mp4'), inputProps, browserExecutable});
        fs.copyFileSync(destino, oficial);
        sincronizar(ROOT);
        resultado.push({nome: b.nome, ok: true, substituiu: existia});
        console.log(`[${b.nome}] aprendida`);
      } catch (e) {
        fs.rmSync(destino, {force: true});
        if (existia) fs.copyFileSync(oficial, destino);  // a cena que já funcionava continua valendo
        resultado.push({nome: b.nome, ok: false, erro: String(e.message || e).slice(0, 400)});
        console.log(`[${b.nome}] RECUSADA: ${e.message}`);
      }
    }
  } finally {
    fs.rmSync(path.join(ROOT, '.aprender'), {recursive: true, force: true});
    fs.writeFileSync(path.join(saida, 'resultado.json'), JSON.stringify(resultado));
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch(e => { console.error('ERRO:', e.message); process.exit(1); });
