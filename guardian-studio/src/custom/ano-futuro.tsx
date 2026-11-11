// entrou: 2026-11-10
// campos: de, para, rotulo, cor
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: de, para, rotulo, cor
// rodizio: nao
export default function Cena({p, dur, tema}) {
  const f = useCurrentFrame();
  const de = parseInt(one(p, 'de', '2026'), 10) || 2026;
  const para = parseInt(one(p, 'para', '2031'), 10) || 2031;
  const n = Math.max(1, para - de);
  const t = interpolate(f, [8, Math.max(20, dur * 0.6)], [0, 1], clamp);
  const ano = Math.round(de + n * t);
  const c = colorOf(one(p, 'cor', ''), tema.blue);
  const s0 = interpolate(f, [0, 10], [0, 1], clamp);
  const anos = Array.from({length: n + 1}, (_, i) => de + i);
  return <div style={{position: 'absolute', top: 640, left: 90, right: 90, opacity: s0, transform: `translateY(${(1 - s0) * 50}px)`}}>
    <div style={{textAlign: 'center', fontFamily: font, fontWeight: 900, fontSize: 260, color: c, lineHeight: 1}}>{ano}</div>
    <div style={{display: 'flex', gap: 12, marginTop: 40}}>
      {anos.map((a, i) => {
        const on = interpolate(t * n, [i - 0.5, i], [0, 1], clamp);
        return <div key={i} style={{flex: 1, height: 90, borderRadius: 16, background: on > 0.5 ? c : tema.soft, border: `3px solid ${on > 0.5 ? c : tema.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: mono, fontSize: 28, color: on > 0.5 ? '#FFFFFF' : tema.mute, transform: `scale(${1 + 0.08 * Math.sin(on * Math.PI)})`}}>{a}</div>;
      })}
    </div>
    <div style={{textAlign: 'center', fontFamily: mono, fontSize: 30, color: tema.mute, marginTop: 36}}>{one(p, 'rotulo', '')}</div>
  </div>;
}
