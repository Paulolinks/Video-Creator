import React, {useEffect, useState} from 'react';
import {AbsoluteFill, continueRender, delayRender, random, staticFile, useCurrentFrame} from 'remotion';
import {C, T} from './theme';

const FONTS: [string, string, string][] = [['Inter', 'Inter-Regular.otf', '400'], ['Inter', 'Inter-Medium.otf', '500'], ['Inter', 'Inter-SemiBold.otf', '600'], ['Inter', 'Inter-Bold.otf', '700'], ['Inter', 'Inter-ExtraBold.otf', '800'], ['Inter', 'Inter-Black.otf', '900'], ['DejaVuMono', 'DejaVuSansMono.ttf', '400'], ['DejaVuMono', 'DejaVuSansMono-Bold.ttf', '700'], ['Poppins', 'Poppins-Bold.ttf', '700'], ['Poppins', 'Poppins-ExtraBold.ttf', '800'], ['Poppins', 'Poppins-ExtraBold.ttf', '900']];
export const useFonts = () => {
  const [h] = useState(() => delayRender('fonts'));
  useEffect(() => {
    Promise.all(FONTS.map(([fam, file, w]) => new FontFace(fam, `url(${staticFile('fonts/' + file)})`, {weight: w}).load().then(ff => (document.fonts as any).add(ff))))
      .then(() => continueRender(h)).catch(() => continueRender(h));
  }, [h]);
};

const RUIDO = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3'/%3E%3CfeColorMatrix values='0 0 0 0 .35 0 0 0 0 .28 0 0 0 0 .18 0 0 0 .14 0'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)'/%3E%3C/svg%3E")`;

export const Fundo: React.FC = () => {
  const g = C.grid;
  const estilos: Record<string, React.CSSProperties> = {
    grade: {backgroundImage: `linear-gradient(${g} 2px, transparent 2px), linear-gradient(90deg, ${g} 2px, transparent 2px)`, backgroundSize: '90px 90px'},
    pontos: {backgroundImage: `radial-gradient(circle at 50% 42%, ${C.blue}2E 0, transparent 58%), radial-gradient(${g} 3px, transparent 3px)`, backgroundSize: '100% 100%, 54px 54px'},
    linhas: {backgroundImage: `linear-gradient(${g} 2px, transparent 2px), linear-gradient(90deg, ${g} 2px, transparent 2px), linear-gradient(${g} 1px, transparent 1px), linear-gradient(90deg, ${g} 1px, transparent 1px)`, backgroundSize: '180px 180px, 180px 180px, 36px 36px, 36px 36px'},
    ruido: {backgroundImage: RUIDO},
    varredura: {backgroundImage: `repeating-linear-gradient(0deg, ${g} 0 2px, transparent 2px 7px)`},
    gradiente: {backgroundImage: 'linear-gradient(170deg, #120A0A 18%, #3A0F18 100%)'},
  };
  return <AbsoluteFill style={{background: C.bg, ...estilos[T.fundo]}} />;
};

const tri = 'polygon(50% 0, 100% 100%, 0 100%)';
export const Flutuantes: React.FC = () => {
  const f = useCurrentFrame();
  if (T.flut === 'nenhum') return null;
  if (T.flut === 'cotas') return <AbsoluteFill>{Array.from({length: 6}).map((_, i) => {
    const x = 60 + random('cx' + i) * 620, y = 60 + i * 310, w = 180 + random('cw' + i) * 220, k = ((f + i * 40) % 140) / 140;
    return <svg key={i} style={{position: 'absolute', left: x, top: y, opacity: 0.4}} width={w + 20} height={40}><line x1={10} x2={10 + w * Math.min(1, k * 2)} y1={20} y2={20} stroke={C.ink} strokeWidth={2} /><line x1={10} x2={10} y1={8} y2={32} stroke={C.ink} strokeWidth={2} /><line x1={10 + w * Math.min(1, k * 2)} x2={10 + w * Math.min(1, k * 2)} y1={8} y2={32} stroke={C.ink} strokeWidth={2} /></svg>;
  })}</AbsoluteFill>;
  if (T.flut === 'caracteres') return <AbsoluteFill style={{fontFamily: 'DejaVuMono, monospace', fontSize: 30, color: C.blue}}>{Array.from({length: 18}).map((_, i) => {
    const x = random('tx' + i) * 1040, sp = 0.5 + random('ts' + i) * 1.2, y = ((random('ty' + i) * 1920 + f * sp) % 2000) - 40;
    return <div key={i} style={{position: 'absolute', left: x, top: y, opacity: 0.16, whiteSpace: 'pre', lineHeight: 1.1}}>{Array.from({length: 5}).map((_, j) => String(Math.floor(random(`td${i}${j}${Math.floor(f / 12)}`) * 16).toString(16))).join('\n')}</div>;
  })}</AbsoluteFill>;
  const n = T.flut === 'circulos' ? 12 : 14;
  return <AbsoluteFill>{Array.from({length: n}).map((_, i) => {
    const x = random('fx' + i) * 1080, y0 = random('fy' + i) * 1920, sp = 0.3 + random('fs' + i) * 0.8, s = 14 + random('fz' + i) * 26;
    const y = ((y0 - f * sp) % 1920 + 1920) % 1920;
    if (T.flut === 'circulos') return <div key={i} style={{position: 'absolute', left: x, top: y, width: s * 3, height: s * 3, borderRadius: '50%', background: C.blue, opacity: 0.2, filter: 'blur(18px)'}} />;
    if (T.flut === 'sinais') return <div key={i} style={{position: 'absolute', left: x, top: y, width: s, height: s, background: C.blue, opacity: 0.32, clipPath: tri, transform: `rotate(${f * sp * 0.4}deg)`}} />;
    return <div key={i} style={{position: 'absolute', left: x, top: y, width: s, height: s, background: i % 3 ? C.blue : C.blue2, opacity: 0.55, borderRadius: 3, transform: `rotate(${f * sp * 0.6}deg)`}} />;
  })}</AbsoluteFill>;
};
