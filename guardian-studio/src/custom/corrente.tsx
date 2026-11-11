// entrou: 2026-11-10
// campos: esquerda, direita, quebrar (sim/nao), rotulo
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: esquerda, direita, quebrar (sim/nao), rotulo
// rodizio: nao
export default function Cena({p, dur, tema}) {
  const f = useCurrentFrame();
  const quebra = one(p, 'quebrar', 'nao').toLowerCase() === 'sim';
  const tq = Math.max(45, dur * 0.55);
  const cai = quebra ? interpolate(f, [tq, tq + 18], [0, 1], clamp) : 0;
  const s0 = interpolate(f, [4, 14], [0, 1], clamp);
  const caixa = (txt, lado) => <div style={{width: 230, minHeight: 150, borderRadius: 24, background: tema.card, border: `4px solid ${tema.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: 16, boxSizing: 'border-box', fontFamily: font, fontWeight: 800, fontSize: 34, color: tema.ink, opacity: s0, transform: `translateX(${(1 - s0) * lado * 80}px)`}}>{txt}</div>;
  const elos = [0, 1, 2, 3, 4].map(i => {
    const s = interpolate(f, [10 + i * 5, 18 + i * 5], [0, 1], clamp);
    const meio = i === 2;
    const y = meio ? cai * 520 : cai * 30 * Math.abs(i - 2);
    const r = meio ? cai * 120 : (i < 2 ? -1 : 1) * cai * 10;
    const cor = cai > 0 ? tema.orange : tema.blue;
    return <div key={i} style={{width: 86, height: 56, border: `12px solid ${cor}`, borderRadius: 30, marginLeft: i ? -18 : 0, boxSizing: 'border-box', opacity: s * (meio ? 1 - cai : 1), transform: `translateY(${y}px) rotate(${r}deg) scale(${0.5 + 0.5 * s})`}} />;
  });
  return <AbsoluteFill>
    <div style={{position: 'absolute', top: 820, left: 40, right: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10}}>
      {caixa(one(p, 'esquerda', 'Customer'), -1)}
      <div style={{display: 'flex', alignItems: 'center'}}>{elos}</div>
      {caixa(one(p, 'direita', 'Your company'), 1)}
    </div>
    <div style={{position: 'absolute', top: 1180, width: '100%', textAlign: 'center', fontFamily: mono, fontSize: 32, color: cai > 0.5 ? tema.orange : tema.mute, opacity: s0}}>{one(p, 'rotulo')}</div>
  </AbsoluteFill>;
}
