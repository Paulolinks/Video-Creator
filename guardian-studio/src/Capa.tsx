import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {C, T, setTema} from './theme';
import {Fundo, Flutuantes, useFonts} from './Fundo';
import {Desenho} from './Desenho';

export type CapaInfo = {titulo: string; destaque: string[]; estilo: string; numero?: string; selo?: string; marca?: string; logo?: string | null; desenho?: string; idioma?: string};
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9à-ú$%#]/g, '');

// Título em até 4 linhas, do maior tamanho que couber na largura (estimativa por caracteres, sem medir no navegador).
const ajustar = (titulo: string, largura: number, max = 170, min = 74) => {
  const ws = titulo.toUpperCase().split(/\s+/).filter(Boolean);
  for (let size = max; size >= min; size -= 4) {
    const cap = largura / (size * (T.fonte.includes('Mono') ? 0.62 : 0.66));
    const out: string[][] = [[]]; let n = 0, ok = true;
    for (const w of ws) {
      if (w.length > cap) { ok = false; break; }
      if (n && n + 1 + w.length > cap) { out.push([]); n = 0; }
      out[out.length - 1].push(w); n += (n ? 1 : 0) + w.length;
    }
    if (ok && out.length <= 4) return {size, linhas: out};
  }
  return {size: min, linhas: [ws]};
};

const Titulo: React.FC<{c: CapaInfo; largura?: number; cor?: string; max?: number; alinhar?: 'center' | 'left'}> = ({c, largura = 920, cor, max, alinhar = 'center'}) => {
  const {size, linhas} = ajustar(c.titulo, largura, max);
  const hl = new Set(c.destaque.flatMap(d => d.split(/\s+/)).map(norm));
  return <div style={{fontFamily: T.fonte, fontWeight: 900, fontSize: size, lineHeight: 1.04, letterSpacing: size * Math.max(T.esp, -0.03), textAlign: alinhar, width: largura}}>
    {linhas.map((l, i) => <div key={i}>{l.map((w, j) => { const on = hl.has(norm(w)); return <React.Fragment key={j}>{j > 0 && ' '}<span style={{color: on ? C.blue : cor ?? C.ink, position: 'relative', display: 'inline-block'}}>{w}{on && c.estilo === 'gigante' && <svg viewBox="0 0 200 20" preserveAspectRatio="none" style={{position: 'absolute', left: 0, right: 0, bottom: -size * 0.1, width: '100%', height: size * 0.14}}><path d="M2 14 C 60 2, 130 20, 198 6" fill="none" stroke={C.blue} strokeWidth={7} strokeLinecap="round" /></svg>}</span></React.Fragment>; })}</div>)}
  </div>;
};
const Centro: React.FC<{top?: number; h?: number; children: React.ReactNode}> = ({top = 420, h = 930, children}) => <div style={{position: 'absolute', top, height: h, left: 0, right: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{children}</div>;

const Estilos: Record<string, React.FC<{c: CapaInfo}>> = {
  gigante: ({c}) => <Centro><Titulo c={c} /></Centro>,
  numero: ({c}) => <>
    <Centro><div style={{fontFamily: T.fonte, fontWeight: 900, fontSize: Math.min(640, 1800 / Math.max(2, (c.numero || '').length)), color: C.blue, opacity: 0.2, letterSpacing: -20}}>{c.numero}</div></Centro>
    <Centro top={980} h={370}><div style={{display: 'grid', gridTemplateColumns: 'repeat(22, 26px)', gap: 12, opacity: 0.55}}>{Array.from({length: 88}).map((_, i) => <div key={i} style={{width: 26, height: 26, borderRadius: 26, background: i % 7 === 0 ? C.line : C.blue}} />)}</div></Centro>
    <Centro top={420} h={560}><Titulo c={c} max={150} /></Centro>
  </>,
  pergunta: ({c}) => <>
    <div style={{position: 'absolute', top: 240, right: -40, fontFamily: T.fonte, fontWeight: 900, fontSize: 1100, color: C.blue, opacity: 0.16, lineHeight: 1}}>?</div>
    <Centro><div style={{background: C.solid, border: `6px solid ${C.blue}`, borderRadius: 60, padding: '56px 40px', position: 'relative'}}><Titulo c={c} largura={860} max={130} /><div style={{position: 'absolute', left: 130, bottom: -70, width: 0, height: 0, borderLeft: '42px solid transparent', borderRight: '42px solid transparent', borderTop: `76px solid ${C.blue}`}} /></div></Centro>
  </>,
  alerta: ({c}) => <>
    <div style={{position: 'absolute', top: 270, left: -120, width: 1400, height: 130, background: C.orange, transform: 'rotate(-7deg)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: T.fonte, fontWeight: 900, fontSize: 84, color: '#120A0A', letterSpacing: 16}}>{c.idioma === 'pt' ? 'ALERTA · ALERTA · ALERTA' : 'ALERT · ALERT · ALERT'}</div>
    <Centro top={460} h={700}><Titulo c={c} max={150} /></Centro>
    <div style={{position: 'absolute', top: 1170, left: 150, right: 150, height: 170, background: C.solid, border: `4px solid ${C.orange}`, borderRadius: 22, transform: 'rotate(-2.5deg)', display: 'flex', alignItems: 'center', gap: 30, padding: '0 34px'}}><svg viewBox="0 0 64 64" width={100} height={100} fill="none" stroke={C.orange} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round"><path d="M32 10 L58 54 L6 54 Z M32 26 L32 40 M32 47 L32 48" /></svg><div style={{flex: 1}}><div style={{height: 22, width: '82%', borderRadius: 12, background: C.ink, opacity: 0.8}} /><div style={{height: 22, width: '56%', borderRadius: 12, background: C.mute, marginTop: 16}} /></div></div>
  </>,
  produto: ({c}) => <>
    <Centro top={330} h={560}><Titulo c={c} max={130} /></Centro>
    <div style={{position: 'absolute', top: 1180, left: 190, width: 700, height: 160, borderRadius: '50%', background: C.blue, filter: 'blur(90px)', opacity: 0.55}} />
    <div style={{position: 'absolute', top: 870, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}><Img src={staticFile('imagens/guardian.png')} style={{width: 760, height: 470, objectFit: 'contain'}} /></div>
  </>,
  dividida: ({c}) => <>
    <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 885, background: C.dark}} /><div style={{position: 'absolute', top: 885, left: 0, right: 0, bottom: 0, background: C.solid}} />
    <div style={{position: 'absolute', top: 455, left: 70, fontSize: 130, color: C.red, fontWeight: 900, fontFamily: T.fonte}}>✕</div><div style={{position: 'absolute', top: 1190, right: 70, fontSize: 130, color: C.green, fontWeight: 900, fontFamily: T.fonte}}>✓</div>
    <Centro top={560} h={650}><div style={{background: C.blue, padding: '40px 34px', transform: 'rotate(-2deg)', boxShadow: '0 30px 60px -20px #000a'}}><Titulo c={{...c, destaque: []}} largura={900} cor={C.onAccent} max={124} /></div></Centro>
  </>,
  moldura: ({c}) => <>
    <div style={{position: 'absolute', top: 400, bottom: 550, left: 50, right: 50, border: `10px solid ${C.blue}`, borderRadius: T.raio}} />
    <Centro><Titulo c={c} largura={860} max={140} /></Centro>
    <div style={{position: 'absolute', top: 1280, right: 96, opacity: 0.95}}><Desenho tipo={c.desenho ?? 'seta'} tam={210} inicio={-40} fim={-20} /></div>
  </>,
  faixas: ({c}) => <>
    {Array.from({length: 7}).map((_, i) => <div key={i} style={{position: 'absolute', top: 420 + i * 134, left: i % 2 ? 0 : -90, right: i % 2 ? -90 : 0, height: 118, background: i % 2 ? C.blue2 : C.blue, opacity: 0.16 + (i % 3) * 0.05, transform: 'skewY(-3deg)'}} />)}
    <Centro><Titulo c={c} /></Centro>
    <div style={{position: 'absolute', top: 160, left: 60, opacity: 0.9}}><Desenho tipo={c.desenho ?? 'exclamacao'} tam={230} inicio={-40} fim={-20} /></div>
  </>,
};

export const CapaFrame: React.FC<{capa: CapaInfo}> = ({capa}) => {
  const E = Estilos[capa.estilo] ?? Estilos.gigante;
  return <AbsoluteFill><Fundo /><Flutuantes /><E c={capa} />
    {capa.selo && <div style={{position: 'absolute', top: 430, left: 60, background: C.blue, color: C.onAccent, fontFamily: T.fonte, fontWeight: 900, fontSize: 40, padding: '10px 28px', borderRadius: 12, transform: 'rotate(-4deg)'}}>{capa.selo}</div>}
    {capa.logo ? <Img src={staticFile(capa.logo)} style={{position: 'absolute', top: 1370, left: '50%', transform: 'translateX(-50%)', maxWidth: 420, maxHeight: 120, objectFit: 'contain', filter: 'drop-shadow(0 0 1px #0b1f40) drop-shadow(0 0 2px #0b1f40)'}} />
      : capa.marca ? <div style={{position: 'absolute', top: 1385, width: '100%', textAlign: 'center', fontFamily: T.fonte, fontWeight: 800, fontSize: 34, letterSpacing: 8, color: C.mute}}>{capa.marca}</div> : null}
  </AbsoluteFill>;
};

export const Capa: React.FC<{capa: CapaInfo; tema: string}> = ({capa, tema}) => {
  setTema(tema);
  useFonts();
  return <AbsoluteFill style={{background: C.bg}}><CapaFrame capa={capa} /></AbsoluteFill>;
};
