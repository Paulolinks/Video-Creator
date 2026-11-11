// entrou: 2026-11-10
// campos: titulo, entra, sai, nivel, furos (sim/nao), cor
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: titulo, entra, sai, nivel, furos (sim/nao), cor
// rodizio: nao
export default function Cena({p, dur, tema}) {
  const f = useCurrentFrame();
  const s0 = interpolate(f, [0, 10], [0, 1], clamp);
  const nivel = Math.max(0, Math.min(100, parseFloat(one(p, 'nivel', '20')) || 0));
  const furos = one(p, 'furos', 'sim') !== 'nao';
  const agua = interpolate(f, [5, 45], [0, nivel], clamp);
  const c = colorOf(one(p, 'cor', ''), tema.blue);
  const gotas = [0, 1, 2, 3, 4, 5];
  return <div style={{position: 'absolute', top: 640, left: 0, right: 0, height: 1000, opacity: s0}}>
    <div style={{position: 'absolute', top: 0, width: '100%', textAlign: 'center', fontFamily: mono, fontSize: 28, color: tema.mute}}>{one(p, 'titulo', '')}</div>
    <div style={{position: 'absolute', top: 60, width: '100%', textAlign: 'center', fontFamily: font, fontWeight: 800, fontSize: 40, color: tema.green}}>↓ {one(p, 'entra', '')}</div>
    {gotas.map(i => {
      const y = (f * 9 + i * 45) % 260;
      return <div key={'a' + i} style={{position: 'absolute', left: 470 + (i % 3) * 50, top: 130 + y, width: 24, height: 24, borderRadius: 12, background: c, opacity: y < 240 ? 1 : 0}} />;
    })}
    <div style={{position: 'absolute', left: 290, top: 390, width: 500, height: 380, border: `10px solid ${tema.ink}`, borderTop: 'none', borderRadius: '0 0 60px 60px', overflow: 'hidden', boxSizing: 'border-box'}}>
      <div style={{position: 'absolute', bottom: 0, left: 0, right: 0, height: `${agua}%`, background: c, opacity: 0.85}} />
    </div>
    {furos && gotas.map(i => {
      const y = (f * 7 + i * 40) % 200;
      return <div key={'b' + i} style={{position: 'absolute', left: 380 + i * 60, top: 780 + y * 0.5, width: 18, height: 18, borderRadius: 9, background: c, opacity: interpolate(y, [0, 200], [1, 0], clamp)}} />;
    })}
    {furos && <div style={{position: 'absolute', top: 900, width: '100%', textAlign: 'center', fontFamily: font, fontWeight: 800, fontSize: 40, color: tema.red}}>{one(p, 'sai', '')} ↓</div>}
  </div>;
}
