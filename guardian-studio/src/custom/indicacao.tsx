// entrou: 2026-11-10
// campos: titulo, niveis (2 a 4), rotulo, cor
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: titulo, niveis (2 a 4), rotulo, cor
// rodizio: nao
export default function Cena({p, dur, tema}) {
  const f = useCurrentFrame();
  const n = Math.max(2, Math.min(4, parseInt(one(p, 'niveis', '3'), 10) || 3));
  const c = colorOf(one(p, 'cor', ''), tema.blue);
  const s0 = interpolate(f, [0, 10], [0, 1], clamp);
  const W = 900;
  const H = 820;
  const yOf = (l) => 80 + l * (H - 160) / (n - 1);
  const nodes = [];
  const links = [];
  for (let l = 0; l < n; l++) {
    const count = Math.pow(3, l);
    for (let i = 0; i < count; i++) {
      const x = W * (i + 0.5) / count;
      nodes.push({x: x, y: yOf(l), l: l});
      if (l > 0) {
        const px = W * (Math.floor(i / 3) + 0.5) / Math.pow(3, l - 1);
        links.push({x1: px, y1: yOf(l - 1), x2: x, y2: yOf(l), l: l});
      }
    }
  }
  const step = Math.max(12, (dur * 0.6) / n);
  return <div style={{position: 'absolute', top: 640, left: 90, width: W, height: H + 120, opacity: s0}}>
    <div style={{fontFamily: mono, fontSize: 28, color: tema.mute, textAlign: 'center'}}>{one(p, 'titulo', '')}</div>
    <svg width={W} height={H} style={{position: 'absolute', top: 50, left: 0}}>
      {links.map((k, i) => {
        const a = interpolate(f, [8 + k.l * step - step * 0.5, 8 + k.l * step], [0, 1], clamp);
        return <line key={'l' + i} x1={k.x1} y1={k.y1} x2={k.x1 + (k.x2 - k.x1) * a} y2={k.y1 + (k.y2 - k.y1) * a} stroke={tema.line} strokeWidth={4} />;
      })}
      {nodes.map((d, i) => {
        const a = interpolate(f, [8 + d.l * step, 16 + d.l * step], [0, 1], clamp);
        const r = d.l === 0 ? 44 : Math.max(13, 34 - d.l * 7);
        return <circle key={'n' + i} cx={d.x} cy={d.y} r={r * a} fill={d.l === 0 ? tema.ink : c} />;
      })}
    </svg>
    <div style={{position: 'absolute', top: H + 70, width: '100%', textAlign: 'center', fontFamily: font, fontWeight: 800, fontSize: 40, color: c}}>{one(p, 'rotulo', '')}</div>
  </div>;
}
