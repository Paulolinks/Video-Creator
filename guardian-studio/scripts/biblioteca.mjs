// Biblioteca de animações: cenas novas que chegam escritas dentro do roteiro (CODIGO: nome ... FIM_CODIGO).
// Cada uma vira um arquivo em src/custom/, é testada num quadro antes de valer, e entra em biblioteca.md.
import fs from 'node:fs';
import path from 'node:path';

export const INTERNAS = ['contador', 'tabela', 'console', 'contato', 'termostato', 'busca', 'barras', 'produto', 'comentario', 'mapa', 'imagem', 'frase',
  'celular', 'mapapins', 'painel', 'linha', 'linhadotempo', 'comparar', 'medidor', 'checklist', 'relatorio', 'formulario', 'fluxo', 'guardian3d', 'jornada'];
const CABECALHO = `import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';
`;
const PROIBIDO = /\b(require|fetch|process|child_process|eval|Function|XMLHttpRequest|WebSocket|globalThis|importScripts)\b|\bfs\b|\bimport\s*\(/;
export const nomeDoArquivo = (s) => s.trim().toLowerCase().replace(/\s+/g, '-');

// Separa os blocos de código do resto do roteiro (o texto das falas não enxerga o código).
export function separarCodigo(txt) {
  const fora = [], blocos = []; let cur = null;
  for (const raw of txt.split(/\r?\n/)) {
    const t = raw.trim();
    const m = !cur && t.match(/^CODIGO\s*:\s*(.+)$/i);
    if (m) { cur = {nome: nomeDoArquivo(m[1]), linhas: []}; continue; }
    if (cur) {
      if (/^FIM_CODIGO\s*$/i.test(t)) { blocos.push({nome: cur.nome, codigo: cur.linhas.filter(l => !/^\s*```/.test(l)).join('\n')}); cur = null; }
      else cur.linhas.push(raw);
      continue;
    }
    fora.push(raw);
  }
  return {texto: fora.join('\n'), blocos};
}

// Só react, remotion, @remotion/* e ../theme. Os imports de react/remotion/tema saem: o cabeçalho já traz todos.
export function validar(codigo) {
  const linhas = [];
  for (const l of codigo.split('\n')) {
    const m = l.match(/^\s*import\s.*?from\s+['"]([^'"]+)['"]|^\s*import\s+['"]([^'"]+)['"]/);
    if (!m) { linhas.push(l); continue; }
    const mod = m[1] || m[2];
    if (mod === 'react' || mod === 'remotion' || mod === '../theme') continue;
    if (!mod.startsWith('@remotion/')) throw new Error(`import não permitido: ${mod}`);
    linhas.push(l);
  }
  const corpo = linhas.join('\n');
  const semTexto = corpo.replace(/\/\/.*$/gm, '').replace(/'[^'\n]*'|"[^"\n]*"/g, "''");
  const proibido = semTexto.match(PROIBIDO);
  if (proibido) throw new Error(`comando não permitido: ${proibido[0]}`);
  if (!/export\s+default/.test(corpo)) throw new Error('falta "export default function Cena({p, dur, tema})"');
  return corpo;
}

export function validarNome(nome) {
  if (INTERNAS.includes(nome)) throw new Error('já existe uma animação interna com esse nome');
  if (!/^[a-z0-9][a-z0-9-]*$/.test(nome)) throw new Error('use só letras minúsculas, números e hífen no nome');
}

// O arquivo da cena em src/custom: cabeçalho + código já conferido.
export function arquivoDaCena(nome, codigo) {
  const corpo = validar(codigo);
  const campos = (corpo.match(/\/\/\s*campos\s*:\s*(.*)$/m) || [, ''])[1].trim();
  const rodizio = /\/\/\s*rodizio\s*:\s*sim/i.test(corpo);
  return `// entrou: ${new Date().toISOString().slice(0, 10)}\n// campos: ${campos}\n// rodizio: ${rodizio ? 'sim' : 'nao'}\n${CABECALHO}\n${corpo}\n`;
}

export function pastaCustom(root) { return path.join(root, 'src', 'custom'); }
const listar = (dir) => fs.readdirSync(dir).filter(f => f.endsWith('.tsx')).map(f => f.slice(0, -4)).sort();
const quebrar = (root, nome, motivo) => {
  const dir = pastaCustom(root), q = path.join(dir, '_quebradas'); fs.mkdirSync(q, {recursive: true});
  const de = path.join(dir, nome + '.tsx');
  if (fs.existsSync(de)) fs.renameSync(de, path.join(q, nome + '.tsx'));
  fs.writeFileSync(path.join(q, nome + '.erro.txt'), motivo);
  console.log(`  ! Animação "${nome}" com defeito (${motivo.slice(0, 200)}). Ficou em src/custom/_quebradas e a fala usa "frase".`);
};

// Guarda os blocos novos. Devolve os nomes que precisam ser testados e os recusados.
export function registrar(root, blocos) {
  const dir = pastaCustom(root); fs.mkdirSync(dir, {recursive: true});
  const novos = [], recusados = [];
  for (const {nome, codigo} of blocos) {
    if (INTERNAS.includes(nome)) { console.log(`  ! Animação "${nome}" recusada: já existe uma cena interna com esse nome.`); recusados.push(nome); continue; }
    if (!/^[a-z0-9][a-z0-9-]*$/.test(nome)) { console.log(`  ! Animação "${nome}" recusada: use só letras, números e hífen.`); recusados.push(nome); continue; }
    const arq = path.join(dir, nome + '.tsx');
    if (fs.existsSync(arq)) { console.log(`  Animação "${nome}" já está na biblioteca: usando a que está guardada (para trocar, use "${nome} v2").`); continue; }
    if (fs.existsSync(path.join(dir, '_quebradas', nome + '.tsx'))) { console.log(`  ! Animação "${nome}" já falhou antes e continua em _quebradas.`); recusados.push(nome); continue; }
    let corpo;
    try { corpo = validar(codigo); } catch (e) { quebrar(root, nome, e.message); fs.writeFileSync(path.join(dir, '_quebradas', nome + '.tsx'), codigo); recusados.push(nome); continue; }
    const primeira = (corpo.split('\n').find(l => l.trim()) || '').trim();
    const campos = (corpo.match(/\/\/\s*campos\s*:\s*(.*)$/m) || [, ''])[1].trim();
    const rodizio = /\/\/\s*rodizio\s*:\s*sim/i.test(corpo);
    void primeira;
    fs.writeFileSync(arq, `// entrou: ${new Date().toISOString().slice(0, 10)}\n// campos: ${campos}\n// rodizio: ${rodizio ? 'sim' : 'nao'}\n${CABECALHO}\n${corpo}\n`);
    novos.push(nome); console.log(`  Animação nova registrada: ${nome}`);
  }
  return {novos, recusados};
}

const meta = (dir, nome) => {
  const t = fs.readFileSync(path.join(dir, nome + '.tsx'), 'utf8');
  return {nome, entrou: (t.match(/^\/\/ entrou: (.*)$/m) || [, ''])[1].trim(), campos: (t.match(/^\/\/ campos: (.*)$/m) || [, ''])[1].trim(), rodizio: /^\/\/ rodizio: sim/m.test(t)};
};

// src/custom/index.ts e biblioteca.md sempre refletem a pasta. ignorar = nomes em teste que ainda não entram.
export function sincronizar(root, ignorar = []) {
  const dir = pastaCustom(root); fs.mkdirSync(dir, {recursive: true});
  const todas = listar(dir).filter(n => !ignorar.includes(n)).map(n => meta(dir, n));
  const imports = todas.map((c, i) => `import C${i} from './${c.nome}';`).join('\n');
  const mapa = todas.map((c, i) => `'${c.nome}': C${i}`).join(', ');
  const rod = todas.filter(c => c.rodizio).map(c => `'${c.nome}'`).join(', ');
  fs.writeFileSync(path.join(dir, 'index.ts'), `// Gerado sozinho pelo scripts/gerar.mjs: não edite.\n${imports}\nexport const CUSTOM: Record<string, any> = {${mapa}};\nexport const CUSTOM_RODIZIO: string[] = [${rod}];\n`);
  const linhas = todas.map(c => `| ${c.nome} | ${c.campos || '(sem campos)'} | ${c.entrou} | ${c.rodizio ? 'sim' : 'não'} |`);
  fs.writeFileSync(path.join(root, 'biblioteca.md'), `# Biblioteca de animações\n\nGerado sozinho. Cenas que chegaram escritas dentro de um roteiro e já podem ser usadas em qualquer outro.\n\n| Cena | Campos | Entrou em | Rodízio |\n| --- | --- | --- | --- |\n${linhas.join('\n')}\n`);
  return todas;
}

// Testa cada cena nova sozinha (empacota e desenha um quadro). A que falhar vai para _quebradas.
export async function testarNovas(root, novos, bundle, renderStill, selectComposition, browserExecutable, publicDir) {
  for (const nome of novos) {
    sincronizar(root, novos.filter(n => n !== nome));
    try {
      const serveUrl = await bundle({entryPoint: path.join(root, 'src', 'index.ts'), publicDir});
      const inputProps = {cena: nome, p: {}};
      const composition = await selectComposition({serveUrl, id: 'TesteCena', inputProps, browserExecutable});
      const out = path.join(pastaCustom(root), `_teste_${nome}.png`);
      await renderStill({composition, serveUrl, output: out, frame: 45, inputProps, browserExecutable});
      fs.rmSync(out, {force: true});
      console.log(`  Animação "${nome}" testada: ok`);
    } catch (e) { quebrar(root, nome, String(e.message || e)); }
  }
  sincronizar(root);
}
