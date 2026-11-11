// entrou: 2026-11-10
// campos: valor, rotulo, cor
// rodizio: sim
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: valor, rotulo, cor
// rodizio: sim
export default function Cena({p, dur, tema}) {
  const f = useCurrentFrame();
  const c = colorOf(one(p, 'cor'), tema.blue);
  const s = interpolate(f, [4, 16], [0, 1], clamp);
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 540, top: 1120}}>
      {[0, 1, 2, 3].map(i => {
        const k = ((f + i * 15) % 60) / 60;
        return <div key={i} style={{position: 'absolute', width: 640 * k, height: 640 * k, left: -320 * k, top: -320 * k, borderRadius: '50%', border: `6px solid ${c}`, opacity: (1 - k) * s}} />;
      })}
      <div style={{position: 'absolute', width: 230, height: 230, left: -115, top: -115, borderRadius: '50%', background: c, opacity: s, transform: `scale(${0.7 + 0.3 * s})`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: font, fontWeight: 900, fontSize: 56, color: '#FFFFFF'}}>{one(p, 'valor')}</div>
    </div>
    <div style={{position: 'absolute', top: 1480, width: '100%', textAlign: 'center', fontFamily: mono, fontSize: 34, color: tema.mute, opacity: s}}>{one(p, 'rotulo')}</div>
  </AbsoluteFill>;
}
