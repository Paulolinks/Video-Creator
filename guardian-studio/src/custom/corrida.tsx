// entrou: 2026-11-10
// campos: titulo, canto, a, b, ano (repetir) "rótulo | valor A | valor B"
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: titulo, canto, a, b, ano (repetir) "rótulo | valor A | valor B"
// rodizio: nao
export default function Cena({p, dur, tema}) {
  const f = useCurrentFrame();
  const rows = many(p, 'ano').map(cells);
  const max = Math.max(1, ...rows.map(r => Math.max(parseFloat(r[1]) || 0, parseFloat(r[2]) || 0)));
  const s0 = interpolate(f, [0, 10], [0, 1], clamp);
  return <div style={{position: 'absolute', top: 640, left: 90, right: 90, background: tema.card, borderRadius: 26, padding: 34, border: `2px solid ${tema.line}`, opacity: s0, transform: `translateY(${(1 - s0) * 50}px)`}}>
    <div style={{display: 'flex', justifyContent: 'space-between', fontFamily: mono, fontSize: 26, color: tema.mute}}><span>{one(p, 'titulo', '')}</span><span>{one(p, 'canto', '')}</span></div>
    <div style={{display: 'flex', gap: 30, margin: '20px 0', fontFamily: font, fontWeight: 700, fontSize: 30}}>
      <span style={{color: tema.mute}}>■ {one(p, 'a', 'A')}</span>
      <span style={{color: tema.blue}}>■ {one(p, 'b', 'B')}</span>
    </div>
    <div style={{display: 'flex', alignItems: 'flex-end', gap: 22, height: 560}}>
      {rows.map((r, i) => {
        const g = interpolate(f, [10 + i * 8, 30 + i * 8], [0, 1], clamp);
        const va = (parseFloat(r[1]) || 0) / max;
        const vb = (parseFloat(r[2]) || 0) / max;
        return <div key={i} style={{flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
          <div style={{display: 'flex', alignItems: 'flex-end', gap: 8, height: 500}}>
            <div style={{width: 40, height: 500 * va * g, background: tema.mute, borderRadius: 10}} />
            <div style={{width: 40, height: 500 * vb * g, background: tema.blue, borderRadius: 10}} />
          </div>
          <div style={{fontFamily: mono, fontSize: 24, color: tema.mute, marginTop: 12}}>{r[0]}</div>
        </div>;
      })}
    </div>
  </div>;
}
