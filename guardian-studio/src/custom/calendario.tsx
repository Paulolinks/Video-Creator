// entrou: 2026-11-10
// campos: titulo, ano, marcar (repetir) "Mes | texto | cor"
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: titulo, ano, marcar (repetir) "Mes | texto | cor"
// rodizio: nao
export default function Cena({p, dur, tema}) {
  const f = useCurrentFrame();
  const meses = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const marcas = many(p, 'marcar').map(cells);
  const achar = (m) => marcas.find(x => (x[0] || '').toLowerCase().slice(0, 3) === m.toLowerCase());
  const t0 = Math.min(55, dur * 0.4);
  const s0 = interpolate(f, [2, 12], [0, 1], clamp);
  return <div style={{position: 'absolute', top: 640, left: 90, right: 90, background: tema.card, borderRadius: 26, padding: 34, border: `2px solid ${tema.line}`, opacity: s0, transform: `translateY(${(1 - s0) * 50}px)`}}>
    <div style={{fontFamily: mono, fontSize: 26, color: tema.mute, marginBottom: 24}}>{one(p, 'titulo', 'this year')} {one(p, 'ano', '')}</div>
    <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18}}>
      {meses.map((m, i) => {
        const s = interpolate(f, [6 + i * 3, 14 + i * 3], [0, 1], clamp);
        const mk = achar(m);
        const c = mk ? colorOf(mk[2] || '', tema.orange) : tema.line;
        const on = mk ? interpolate(f, [t0 + i * 2, t0 + 10 + i * 2], [0, 1], clamp) : 0;
        return <div key={i} style={{height: 168, borderRadius: 18, background: on > 0.3 ? c : tema.soft, border: `3px solid ${mk ? c : tema.line}`, padding: 16, boxSizing: 'border-box', opacity: s, transform: `scale(${(0.85 + 0.15 * s) * (1 + 0.06 * Math.sin(on * Math.PI))})`}}>
          <div style={{fontFamily: font, fontWeight: 800, fontSize: 38, color: on > 0.3 ? '#FFFFFF' : tema.ink}}>{m}</div>
          {mk && <div style={{fontFamily: font, fontWeight: 600, fontSize: 24, lineHeight: 1.15, color: '#FFFFFF', opacity: on, marginTop: 8}}>{mk[1]}</div>}
        </div>;
      })}
    </div>
  </div>;
}
