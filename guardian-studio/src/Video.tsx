import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig, random} from 'remotion';
import {C, T, clamp, Params, setTema} from './theme';
import {SCENES, VarCtx} from './scenes';
import {SCENES2} from './scenes2';
import {CUSTOM} from './custom';
import {Jornada} from './jornada';
import {CapaFrame, CapaInfo} from './Capa';
import {Fundo, Flutuantes, useFonts} from './Fundo';

export type Line = {text: string; hl: string[]; scene: string; params: Params; start: number; dur: number; audio: string | null; words: {w: string; t: number}[]; transicao?: string; camera?: string; texto?: string; variante?: number};
export type Timeline = {fps: number; total: number; music: {file: string; volume: number} | null; logo?: string | null; lines: Line[]; tema?: string; texto?: string; capa?: CapaInfo | null; capaNoVideo?: boolean};

const OVER = 10;  // quadros em que a cena antiga e a nova convivem nas transições deslizar e zoom
const TODAS: Record<string, React.FC<any>> = {...SCENES, ...SCENES2, jornada: Jornada, ...CUSTOM};
export const cenaPorNome = (n: string) => TODAS[n];

// Uma cena da biblioteca com defeito em algum quadro some, e o vídeo segue.
class Protege extends React.Component<{children: React.ReactNode}, {erro: boolean}> {
  state = {erro: false};
  static getDerivedStateFromError() { return {erro: true}; }
  render() { return this.state.erro ? null : this.props.children; }
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9à-ú$%#]/g, '');
const tamanho = (n: number) => n > 14 ? 68 : n > 11 ? 76 : n > 8 ? 86 : 98;

// A jornada tem fala longa: a manchete mostra só a frase que está sendo dita, para não invadir a casa.
const fraseAtual = <W extends {w: string; t: number}>(ws: W[], t: number): W[] => {
  const frases: W[][] = [[]];
  ws.forEach((w, i) => { frases[frases.length - 1].push(w); if (/[.!?…]['")]*$/.test(w.w) && i < ws.length - 1) frases.push([]); });
  return frases.filter(fr => fr[0].t <= t + 0.05).pop() ?? frases[0];
};

const Headline: React.FC<{tl: Timeline}> = ({tl}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const L = tl.lines;
  const line = L.find(l => f >= l.start && f < l.start + l.dur) ?? (f >= L[0].start ? L[L.length - 1] : null);
  if (!line) return null;
  const todas = line.words.length ? line.words : line.text.split(' ').map((w, i, a) => ({w, t: (i / a.length) * (line.dur / fps) * 0.85}));
  const words = line.scene === 'jornada' ? fraseAtual(todas, (f - line.start) / fps) : todas;
  const hl = new Set(line.hl.flatMap(h => h.split(/\s+/)).map(norm));
  const local = f - line.start;
  const estilo = line.texto ?? tl.texto ?? 'topo';
  const size = tamanho(words.length);
  const base: React.CSSProperties = {position: 'absolute', left: 60, right: 60, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', fontFamily: T.fonte, fontWeight: T.peso, lineHeight: 1.04};

  if (estilo === 'palavra') {
    let i = 0; words.forEach((w, j) => { if (local / fps >= w.t) i = j; });
    const w = words[i]; const on = hl.has(norm(w.w));
    const s = spring({frame: local - w.t * fps, fps, config: {damping: 11, stiffness: 240}});
    const sz = Math.min(200, 950 / Math.max(1, w.w.length * 0.66));
    const semPainel = line.scene === 'frase' && !line.params.grande;
    return <div style={{...base, top: semPainel ? 760 : 250, height: 300, alignItems: 'center'}}>
      <span style={{fontSize: sz, letterSpacing: sz * -0.03, color: on ? C.blue : C.ink, transform: `scale(${0.72 + 0.28 * s}) translateX(${on ? Math.sin(local * 1.7) * 3 : 0}px)`, opacity: Math.min(1, s * 1.6)}}>{w.w}</span>
    </div>;
  }
  const top = estilo === 'centro' ? 330 : estilo === 'baixo' ? 1340 : 150;
  return <div style={{...base, top, columnGap: size * (estilo === 'caixa' ? 0.14 : 0.26), rowGap: estilo === 'caixa' ? 12 : 0, fontSize: size * (estilo === 'caixa' ? 0.86 : 1), letterSpacing: size * T.esp}}>
    {words.map((w, i) => {
      const s = spring({frame: local - w.t * fps + 2, fps, config: {damping: 15, stiffness: 180}});
      const on = hl.has(norm(w.w));
      if (estilo === 'caixa') return <span key={i} style={{background: on ? C.blue : C.solid, color: on ? C.onAccent : C.ink, padding: '8px 18px 10px', borderRadius: T.raio ? 12 : 0, opacity: s, transform: `translateY(${(1 - s) * 30}px) scale(${0.85 + 0.15 * s})`, display: 'inline-block'}}>{w.w}</span>;
      return <span key={i} style={{color: on ? C.blue : C.ink, opacity: s, transform: `translateY(${(1 - s) * 30}px) scale(${0.9 + 0.1 * s})`, filter: `blur(${(1 - s) * 8}px)`, display: 'inline-block'}}>{w.w}</span>;
    })}
  </div>;
};

// Onde o painel fica conforme o estilo do texto (o painel original começa em y = 640).
const lugar = (texto: string, line: Line): {dy: number; k: number} => {
  if (texto === 'centro') return {dy: 400, k: 0.72};
  if (texto === 'baixo') return {dy: -480, k: 0.95};
  if (texto === 'legenda-baixo') return {dy: -325, k: 0.9};  // Template 1: entre a faixa da série e a legenda
  return {dy: 0, k: 1};
};

const Movimento: React.FC<{entra?: string; sai?: string; saiEm: number; dur: number; camera?: string; dy: number; k: number; children: React.ReactNode}> = ({entra, sai, saiEm, dur, camera, dy, k, children}) => {
  const f = useCurrentFrame();
  const inK = interpolate(f, [0, OVER], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const outK = interpolate(f, [saiEm, saiEm + OVER], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  let tr = '', op = 1, blur = 0;
  if (entra === 'deslizar') { tr += ` translateX(${(1 - inK) * 1080}px)`; blur = (1 - inK) * 6; }
  if (entra === 'zoom') { tr += ` scale(${0.85 + 0.15 * inK})`; op = inK; }
  if (entra === 'flash' && f < 10) tr += ` translate(${Math.sin(f * 7) * 8}px, ${Math.cos(f * 5) * 8}px)`;
  if (sai === 'deslizar' && f >= saiEm) { tr += ` translateX(${-outK * 1080}px)`; blur = outK * 6; }
  if (sai === 'zoom' && f >= saiEm) { tr += ` scale(${1 + outK * 0.35})`; op = 1 - outK; }
  const c = interpolate(f, [0, Math.max(1, dur)], [0, 1], {...clamp, easing: Easing.inOut(Easing.sin)});
  let cam = '';
  if (camera === 'zoom-in') cam = `scale(${1 + 0.12 * c})`;
  else if (camera === 'zoom-out') cam = `scale(${1.12 - 0.12 * c})`;
  else if (camera === 'pan-esquerda') cam = `translateX(${30 - 60 * c}px)`;
  else if (camera === 'pan-direita') cam = `translateX(${-30 + 60 * c}px)`;
  else if (camera === 'subir') cam = `translateY(${25 - 50 * c}px)`;
  else if (camera === 'tremer' && f < 10) cam = `translate(${Math.sin(f * 6) * 3}px, ${Math.cos(f * 7) * 3}px)`;
  return <AbsoluteFill style={{transform: tr || undefined, opacity: op, filter: blur ? `blur(${blur}px)` : undefined}}>
    <AbsoluteFill style={{transformOrigin: '50% 640px', transform: `translateY(${dy}px) scale(${k}) ${cam}`}}>{children}</AbsoluteFill>
  </AbsoluteFill>;
};

const Transicao: React.FC<{L: Line[]}> = ({L}) => {
  const f = useCurrentFrame();
  const line = L.slice(1).find(l => Math.abs(f - l.start) <= 12);
  if (!line) return null;
  const t = f - line.start; const tipo = line.transicao ?? 'blocos';
  if (tipo === 'blocos') {
    if (Math.abs(t) > 9) return null;
    const cols = 9, s = 120;
    return <AbsoluteFill style={{top: 600}}>{Array.from({length: cols * 9}).map((_, i) => {
      const r = random(`b${line.start}-${i}`);
      const inT = -9 + r * 7, outT = 2 + r * 7;
      const k = t < 0 ? interpolate(t, [inT, inT + 3], [0, 1], clamp) : interpolate(t, [outT, outT + 3], [1, 0], clamp);
      const col = r < 0.45 ? C.solid : r < 0.8 ? C.blue2 : C.blue;
      return <div key={i} style={{position: 'absolute', left: (i % cols) * s, top: Math.floor(i / cols) * s, width: s - 4, height: s - 4, background: col, transform: `scale(${k})`, borderRadius: 4, boxShadow: '0 2px 6px #0001'}} />;
    })}</AbsoluteFill>;
  }
  if (tipo === 'cortina') {
    if (Math.abs(t) > 9) return null;
    return <div style={{position: 'absolute', left: -900, top: -500, width: 2880, height: 2920, background: C.blue, transform: `translateX(${interpolate(t, [-9, 9], [-3000, 3000], clamp)}px) rotate(-18deg)`}} />;
  }
  if (tipo === 'circulo') {
    if (t < -8 || t > 8) return null;
    if (t < 0) { const R = interpolate(t, [-8, -1], [0, 1250], clamp); return <div style={{position: 'absolute', left: 540 - R, top: 960 - R, width: R * 2, height: R * 2, borderRadius: '50%', background: C.blue}} />; }
    const r = interpolate(t, [0, 8], [0, 1250], clamp);
    return <AbsoluteFill style={{background: `radial-gradient(circle at 50% 50%, transparent ${r}px, ${C.blue} ${r + 1}px)`}} />;
  }
  if (tipo === 'flash' && t >= 0 && t < 4) return <AbsoluteFill style={{background: '#FFFFFF', opacity: 1 - t / 4}} />;
  return null;
};

export const Video: React.FC<{timeline: Timeline}> = ({timeline: tl}) => {
  setTema(tl.tema);
  useFonts();
  const f = useCurrentFrame();
  const L = tl.lines;
  return <AbsoluteFill style={{fontFamily: T.fonte}}>
    <Fundo /><Flutuantes />
    {tl.music && <Audio src={staticFile(tl.music.file)} loop volume={(fr) => tl.music!.volume * interpolate(fr, [0, 15, tl.total - 30, tl.total], [0, 1, 1, 0], clamp)} />}
    {L.map((l, i) => {
      const S = TODAS[l.scene] ?? SCENES.frase;
      const from = i === 0 ? 0 : l.start;
      const end = L[i + 1] ? L[i + 1].start : tl.total;
      const sai = L[i + 1]?.transicao;
      const extra = sai === 'deslizar' || sai === 'zoom' ? OVER : 0;
      const {dy, k} = lugar(l.texto ?? tl.texto ?? 'topo', l);
      return <Sequence key={i} from={from} durationInFrames={Math.max(1, end - from + extra)}>
        <VarCtx.Provider value={l.variante ?? 0}>
          <Movimento entra={i ? l.transicao : undefined} sai={sai} saiEm={end - from} dur={end - from} camera={l.camera} dy={dy} k={k}>
            <Protege><S p={l.params} dur={end - from} tema={C} fala={{words: l.words, inicio: l.start - from, idioma: tl.capa?.idioma}} /></Protege>
          </Movimento>
        </VarCtx.Provider>
        {l.audio && <Sequence from={l.start - from}><Audio src={staticFile(l.audio)} /></Sequence>}
      </Sequence>;
    })}
    <Headline tl={tl} />
    <Transicao L={L} />
    {tl.logo && <Img src={staticFile(tl.logo)} style={{position: 'absolute', top: 18, left: '50%', transform: 'translateX(-50%)', maxWidth: 460, maxHeight: 126, objectFit: 'contain', filter: 'drop-shadow(0 0 1px #0b1f40) drop-shadow(0 0 2px #0b1f40) drop-shadow(0 1px 3px #0b1f40aa)'}} />}
    <div style={{position: 'absolute', bottom: 0, left: 0, height: 10, width: `${(f / tl.total) * 100}%`, background: C.blue}} />
    {tl.capaNoVideo && tl.capa && f < 6 && <AbsoluteFill style={{background: C.bg}}><CapaFrame capa={tl.capa} /></AbsoluteFill>}
  </AbsoluteFill>;
};

// Uma cena sozinha, sem manchete nem voz: os Templates 1 e 2 encaixam este clipe no vídeo deles e põem a própria legenda.
export type Solta = {cena: string; params: Params; words: {w: string; t: number}[]; inicio: number; total: number; tema: string; texto: string; idioma: string};
export const CenaSolta: React.FC<Solta> = ({cena, params, words, inicio, total, tema, texto, idioma}) => {
  setTema(tema);
  useFonts();
  const S = TODAS[cena];
  if (!S) throw new Error('cena não registrada: ' + cena);
  const {dy, k} = lugar(texto, {} as Line);
  return <AbsoluteFill style={{fontFamily: T.fonte}}><Fundo /><Flutuantes />
    <Movimento saiEm={total} dur={total} dy={dy} k={k}><S p={params} dur={total} tema={C} fala={{words, inicio, idioma}} /></Movimento>
  </AbsoluteFill>;
};

// Usada só para testar uma cena nova da biblioteca antes de deixá-la entrar nos vídeos (sem proteção: o erro tem de aparecer).
export const TesteCena: React.FC<{cena: string; p: Params}> = ({cena, p}) => {
  setTema('claro');
  useFonts();
  const S = TODAS[cena];
  if (!S) throw new Error('cena não registrada: ' + cena);
  return <AbsoluteFill><Fundo /><S p={p} dur={90} tema={C} /></AbsoluteFill>;
};
