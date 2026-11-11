// Desenha cenas do motor de animação como clipes soltos, para os Templates 1 e 2 usarem no meio do vídeo.
// Uso: node scripts/cena_solta.mjs pedido.json
// pedido.json: {"tema", "texto", "idioma", "cenas": [{"id", "cena", "params", "words", "inicio", "total", "saida"}]}
// Grava pedido.resultado.json: {"<id>": true} ou {"<id>": "motivo da falha"}. Uma cena que falha não atrapalha as outras.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {sincronizar} from './biblioteca.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const arquivo = process.argv[2];
const pedido = JSON.parse(fs.readFileSync(arquivo, 'utf8'));
const resultado = {};
const browserExecutable = process.env.REMOTION_CHROME || null;

sincronizar(ROOT);
const {bundle} = await import('@remotion/bundler');
const {renderMedia, selectComposition} = await import('@remotion/renderer');
const serveUrl = await bundle({entryPoint: path.join(ROOT, 'src', 'index.ts'), publicDir: path.join(ROOT, 'public')});

for (const c of pedido.cenas) {
  const parcial = c.saida.replace(/\.mp4$/i, '_parcial.mp4');
  try {
    const inputProps = {cena: c.cena, params: c.params, words: c.words, inicio: c.inicio, total: c.total, tema: pedido.tema, texto: pedido.texto, idioma: pedido.idioma};
    const composition = await selectComposition({serveUrl, id: 'CenaSolta', inputProps, browserExecutable});
    await renderMedia({composition, serveUrl, codec: 'h264', crf: 16, muted: true, outputLocation: parcial, inputProps, browserExecutable});
    fs.renameSync(parcial, c.saida);
    resultado[c.id] = true;
    console.log(`[${c.id}] animação pronta`);
  } catch (e) {
    fs.rmSync(parcial, {force: true});
    resultado[c.id] = String(e.message || e).slice(0, 300);
    console.log(`[${c.id}] FALHOU: ${resultado[c.id]}`);
  }
}
fs.writeFileSync(arquivo.replace(/\.json$/i, '.resultado.json'), JSON.stringify(resultado));
