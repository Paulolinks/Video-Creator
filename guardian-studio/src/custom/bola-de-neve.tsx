// entrou: 2026-11-10
// campos: titulo, canto, anos, por_ano, rotulo
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: titulo, canto, anos, por_ano, rotulo
// rodizio: nao
export default function Cena({p, dur, tema}) {
  const f = useCurrentFrame();
  const n = Math.max(1, Math.min(8, parseInt(one(p, 'anos', '5'), 10) || 5));
  const por = parseFloat(one(p, 'por_ano', '300')) || 300;
  const cores = [tema.blue, tema.green, tema.amber, tema.orange, tema.red, tema.blue, tema.green, tema.amber];
  const s0 = interpolate(f, [0, 10], [0, 1], clamp);
  const step = Math.max(10, (dur * 0.7) / n);
  const H = 520;
  return <div style={{position: 'absolute', top: 640, left: 90, right: 90, background: tema.card, borderRadius: 26, padding: 34, border: `2px solid ${tema.line}`, opacity: s0, transform: `translateY(${(1 - s0) * 50}px)`}}>
    <div style={{display: 'flex', justifyContent: 'space-between', fontFamily: mono, fontSize: 26, color: tema.mute}}><span>{one(p, 'titulo', '')}</span><span>{one(p, 'canto', '')}</span></div>
    <div style={{display: 'flex', alignItems: 'flex-end', gap: 18, height: H + 90, marginTop: 20}}>
      {Array.from({length: n}, (_, i) => {
        const g = interpolate(f, [8 + i * step, 18 + i * step], [0, 1], clamp);
        const total = Math.round(por * (i + 1) * g);
        return <div key={i} style={{flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
          <div style={{fontFamily: font, fontWeight: 800, fontSize: 30, color: tema.ink, opacity: g, marginBottom: 8}}>{total.toLocaleString('en-US')}</div>
          <div style={{display: 'flex', flexDirection: 'column-reverse', width: '100%'}}>
            {Array.from({length: i + 1}, (_, j) => <div key={j} style={{height: (H / n) * g, background: cores[j % cores.length], borderTop: `3px solid ${tema.card}`, borderRadius: j === i ? '10px 10px 0 0' : 0}} />)}
          </div>
          <div style={{fontFamily: mono, fontSize: 24, color: tema.mute, marginTop: 10}}>Y{i + 1}</div>
        </div>;
      })}
    </div>
    <div style={{textAlign: 'center', fontFamily: font, fontWeight: 700, fontSize: 32, color: tema.blue, marginTop: 16}}>{one(p, 'rotulo', '')}</div>
  </div>;
}
