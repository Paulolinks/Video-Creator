import React from 'react';
import {Easing, Img, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, Params, statusColor} from './theme';
import {Card, fadeIn, num} from './scenes';

type P = {p: Params; dur: number};
const line2 = (a: number, b: number, f: number) => interpolate(f, [a, b], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});

// celular: titulo, hora, notificacao "App | texto" (repetir), msg "eu | texto" ou "eles | texto" (repetir), canto
const Celular: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const s = spring({frame: f - 4, fps, config: {damping: 16}});
  const nots = many(p, 'notificacao').map(cells), msgs = many(p, 'msg').map(cells);
  const total = nots.length + msgs.length, passo = Math.min(28, (dur - 30) / Math.max(1, total));
  return <div style={{position: 'absolute', top: 620, left: 0, right: 0, display: 'flex', justifyContent: 'center', transform: `translateY(${(1 - s) * 900}px)`}}>
    <div style={{width: 640, height: 1120, borderRadius: 74, background: '#0B0E14', padding: 18, boxShadow: '0 40px 80px -20px #0008'}}>
      <div style={{width: '100%', height: '100%', borderRadius: 58, background: C.solid, position: 'relative', overflow: 'hidden', fontFamily: font, color: C.ink}}>
        <div style={{position: 'absolute', top: 18, left: '50%', marginLeft: -80, width: 160, height: 36, borderRadius: 20, background: '#0B0E14'}} />
        <div style={{padding: '74px 34px 22px', borderBottom: `2px solid ${C.line}`, textAlign: 'center'}}>
          <div style={{fontFamily: mono, fontSize: 22, color: C.mute}}>{one(p, 'hora', '')}{one(p, 'canto') ? ` · ${one(p, 'canto')}` : ''}</div>
          <div style={{fontSize: 36, fontWeight: 800}}>{one(p, 'titulo', 'Messages')}</div>
        </div>
        <div style={{padding: 22, display: 'flex', flexDirection: 'column', gap: 14}}>
          {nots.map(([a, t], i) => { const at = 16 + i * passo; const o = spring({frame: f - at, fps, config: {damping: 12}}); const buzz = f > at && f < at + 8 ? Math.sin(f * 3) * 4 : 0;
            return <div key={'n' + i} style={{background: C.soft, border: `2px solid ${C.line}`, borderRadius: 24, padding: '16px 20px', opacity: o, transform: `translate(${buzz}px, ${(1 - o) * -90}px)`}}>
              <div style={{fontSize: 20, fontWeight: 800, color: C.blue}}>{a}</div><div style={{fontSize: 27, lineHeight: 1.2}}>{t}</div></div>; })}
          {msgs.map(([quem, t], i) => { const at = 16 + (nots.length + i) * passo; const eu = quem.toLowerCase() === 'eu' || quem.toLowerCase() === 'me'; const o = fadeIn(f, at + 9, at + 15); const dig = fadeIn(f, at, at + 3) * (1 - fadeIn(f, at + 8, at + 9));
            return <div key={'m' + i} style={{alignSelf: eu ? 'flex-end' : 'flex-start', maxWidth: '82%', position: 'relative'}}>
              {dig > 0 && <div style={{position: 'absolute', [eu ? 'right' : 'left']: 8, fontFamily: mono, fontSize: 24, color: C.mute, opacity: dig}}>{'•'.repeat(1 + (Math.floor(f / 5) % 3))}</div>}
              <div style={{opacity: o, transform: `scale(${0.9 + 0.1 * o})`, background: eu ? C.blue : C.soft2, color: eu ? C.onAccent : C.ink, borderRadius: 26, padding: '14px 22px', fontSize: 28, lineHeight: 1.2}}>{t}</div></div>; })}
        </div>
      </div>
    </div>
  </div>;
};

// mapapins: titulo, canto, pino "Nome | status" (repetir: ok/check/off), foco, rotulo
const MapaPins: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const pinos = many(p, 'pino').map(cells); const foco = pinos.findIndex(x => x[0] === one(p, 'foco'));
  const W = 900, H = 820;
  const pos = pinos.map((_, i) => ({x: 110 + random('px' + i) * (W - 220), y: 130 + (((i + 0.5) / Math.max(1, pinos.length)) * (H - 240)) + random('py' + i) * 40 - 20}));
  const zT = foco >= 0 ? line2(dur * 0.62, dur * 0.8, f) : 0, z = 1 + zT * 0.9, alvo = pos[foco] ?? {x: W / 2, y: H / 2};
  return <Card title={one(p, 'titulo', 'service area')} right={one(p, 'canto', '')}>
    <div style={{height: H, margin: -34, position: 'relative', overflow: 'hidden', background: C.soft}}>
      <div style={{position: 'absolute', inset: 0, transformOrigin: '0 0', transform: `translate(${(W / 2 - alvo.x * z) * (zT ? 1 : 0)}px, ${(H / 2 - alvo.y * z) * (zT ? 1 : 0)}px) scale(${z})`}}>
        {[0, 1, 2, 3, 4].flatMap(x => [0, 1, 2, 3, 4, 5].map(y => <div key={`${x}-${y}`} style={{position: 'absolute', left: 16 + x * 182, top: 14 + y * 138, width: 164, height: 118, borderRadius: 10, background: C.soft2}} />))}
        <div style={{position: 'absolute', left: -60, top: 590, width: 1100, height: 56, background: C.blue2, opacity: 0.35, transform: 'rotate(-9deg)'}} />
        {pinos.map(([n, st], i) => { const at = 10 + i * 12; const s = spring({frame: f - at, fps, config: {damping: 10}}); const c = statusColor(st); const pulso = (f - at) % 34 / 34;
          return <div key={i} style={{position: 'absolute', left: pos[i].x, top: pos[i].y}}>
            {st === 'check' && f > at && <div style={{position: 'absolute', left: -44, top: -44, width: 88, height: 88, borderRadius: 88, border: `4px solid ${c}`, opacity: 1 - pulso, transform: `scale(${0.5 + pulso * 1.2})`}} />}
            <div style={{position: 'absolute', left: -20, top: -50, width: 40, height: 40, borderRadius: '50% 50% 50% 0', background: c, transform: `translateY(${(1 - s) * -200}px) rotate(-45deg)`, opacity: Math.min(1, s * 2)}} />
            <div style={{position: 'absolute', [pos[i].x > W * 0.5 ? 'right' : 'left']: 30, top: -56, whiteSpace: 'nowrap', background: C.solid, color: C.ink, border: `2px solid ${C.line}`, borderRadius: 10, padding: '4px 12px', fontFamily: font, fontSize: 24, fontWeight: 700, opacity: fadeIn(f, at + 12, at + 20)}}>{n}</div>
          </div>; })}
      </div>
      {foco >= 0 && <div style={{position: 'absolute', left: 24, right: 24, bottom: 24, background: C.solid, color: C.ink, border: `2px solid ${statusColor(pinos[foco][1])}`, borderRadius: 18, padding: '20px 28px', fontFamily: font, opacity: fadeIn(f, dur * 0.75, dur * 0.85), display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <span style={{fontSize: 36, fontWeight: 800}}>{pinos[foco][0]}</span><span style={{fontFamily: mono, fontSize: 26, color: statusColor(pinos[foco][1])}}>{pinos[foco][1]}</span></div>}
      {foco < 0 && one(p, 'rotulo') && <div style={{position: 'absolute', left: 24, bottom: 24, background: C.solid, color: C.ink, borderRadius: 14, padding: '12px 22px', fontFamily: font, fontSize: 32, fontWeight: 800}}>{one(p, 'rotulo')}</div>}
    </div>
  </Card>;
};

// painel: titulo, canto, total, alerta "Nome | sinal" (repetir), observar, normal
const Painel: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const alertas = many(p, 'alerta').map(cells); const total = Math.min(100, num(one(p, 'total', '100'), 100));
  const obs = num(one(p, 'observar', '0'), 0), norm = num(one(p, 'normal', String(total - alertas.length - obs)), 0);
  const ordem = Array.from({length: total}, (_, i) => i).sort((a, b) => random('pn' + a) - random('pn' + b));
  const alertI = new Set(ordem.slice(0, alertas.length)); const obsI = new Set(ordem.slice(alertas.length, alertas.length + obs));
  const k = line2(8, 48, f); const passo = Math.min(34, (dur - 56) / Math.max(1, alertas.length));
  const Num: React.FC<{n: number; l: string; c: string}> = ({n, l, c}) => <div style={{flex: 1, textAlign: 'center'}}><div style={{fontFamily: font, fontWeight: 900, fontSize: 76, color: c, lineHeight: 1}}>{Math.round(n * k)}</div><div style={{fontFamily: mono, fontSize: 22, color: C.mute}}>{l}</div></div>;
  return <Card top={600} title={one(p, 'titulo', 'monitoring')} right={one(p, 'canto', '')}>
    <div style={{display: 'flex', marginBottom: 26}}><Num n={norm} l="NORMAL" c={C.green} /><Num n={obs} l="WATCH" c={C.amber} /><Num n={alertas.length} l="ALERT" c={C.orange} /></div>
    <div style={{display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 9}}>{Array.from({length: total}).map((_, i) => { const on = fadeIn(f, 8 + ((i % 10) + Math.floor(i / 10)) * 2.2, 16 + ((i % 10) + Math.floor(i / 10)) * 2.2);
      return <div key={i} style={{aspectRatio: '1', borderRadius: 7, background: alertI.has(i) ? C.orange : obsI.has(i) ? C.amber : C.green, opacity: 0.15 + on * 0.85}} />; })}</div>
    <div style={{marginTop: 24, display: 'flex', flexDirection: 'column', gap: 12}}>{alertas.map(([n, s], i) => { const at = 50 + i * passo; const q = spring({frame: f - at, fps, config: {damping: 12}});
      return <div key={i} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: C.soft, border: `2px solid ${C.orange}`, borderRadius: 16, padding: '14px 24px', opacity: Math.min(1, q), transform: `scale(${0.7 + 0.3 * q})`, fontFamily: font}}><span style={{fontSize: 34, fontWeight: 800, color: C.ink}}>{n}</span><span style={{fontFamily: mono, fontSize: 24, color: C.orange}}>{s}</span></div>; })}</div>
  </Card>;
};

// linha: titulo, canto, ponto "rótulo | valor" (repetir), limite, marcar
const Linha: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame();
  const pts = many(p, 'ponto').map(cells).map(([l, v]) => ({l, v: num(v, 0)}));
  if (pts.length < 2) return null;
  const W = 840, H = 520, lim = one(p, 'limite') ? num(one(p, 'limite'), 0) : null;
  const vs = pts.map(x => x.v).concat(lim ?? []), min = Math.min(...vs), max = Math.max(...vs), amp = max - min || 1;
  const X = (i: number) => (i / (pts.length - 1)) * W, Y = (v: number) => H - 30 - ((v - min) / amp) * (H - 80);
  const d = pts.map((q, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(q.v).toFixed(1)}`).join(' ');
  const k = interpolate(f, [8, Math.max(30, dur * 0.65)], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const mi = pts.findIndex(q => q.l === one(p, 'marcar')); const yLim = lim === null ? H : Y(lim);
  return <Card title={one(p, 'titulo', 'trend')} right={one(p, 'canto', '')}>
    <svg viewBox={`-10 0 ${W + 20} ${H}`} width="100%" style={{overflow: 'visible', display: 'block'}}>
      <defs>
        <linearGradient id="la" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={C.blue} stopOpacity={0.35} /><stop offset="1" stopColor={C.blue} stopOpacity={0} /></linearGradient>
        <clipPath id="lc"><rect x={-10} y={-20} width={(W + 20) * k} height={H + 40} /></clipPath>
        <clipPath id="lh"><rect x={-10} y={-20} width={W + 20} height={yLim + 20} /></clipPath>
        <clipPath id="lb"><rect x={-10} y={yLim} width={W + 20} height={H} /></clipPath>
      </defs>
      <g clipPath="url(#lc)"><path d={`${d} L${W} ${H} L0 ${H} Z`} fill="url(#la)" />
        <g clipPath="url(#lh)"><path d={d} fill="none" stroke={C.blue} strokeWidth={9} strokeLinejoin="round" strokeLinecap="round" /></g>
        {lim !== null && <g clipPath="url(#lb)"><path d={d} fill="none" stroke={C.orange} strokeWidth={9} strokeLinejoin="round" strokeLinecap="round" /></g>}
      </g>
      {lim !== null && <line x1={0} x2={W} y1={yLim} y2={yLim} stroke={C.mute} strokeWidth={3} strokeDasharray="14 12" opacity={fadeIn(f, 4, 12)} />}
      {mi >= 0 && k * (pts.length - 1) >= mi && <circle cx={X(mi)} cy={Y(pts[mi].v)} r={16 + ((f % 24) / 24) * 22} fill="none" stroke={C.orange} strokeWidth={5} opacity={1 - (f % 24) / 24} />}
      {mi >= 0 && k * (pts.length - 1) >= mi && <circle cx={X(mi)} cy={Y(pts[mi].v)} r={13} fill={C.orange} />}
    </svg>
    <div style={{display: 'flex', justifyContent: 'space-between', fontFamily: mono, fontSize: 21, color: C.mute, marginTop: 12}}>{pts.map((q, i) => <span key={i}>{q.l}</span>)}</div>
  </Card>;
};

// linhadotempo: titulo, canto, evento "data | texto | status" (repetir), vertical (sim/nao)
const LinhaDoTempo: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const ev = many(p, 'evento').map(cells); const passo = Math.min(40, (dur - 26) / Math.max(1, ev.length));
  const k = line2(6, 14 + ev.length * passo, f);
  return <Card title={one(p, 'titulo', 'timeline')} right={one(p, 'canto', '')}>
    <div style={{position: 'relative', paddingLeft: 66}}>
      <div style={{position: 'absolute', left: 24, top: 18, bottom: 18, width: 6, borderRadius: 6, background: C.line}}><div style={{width: '100%', height: `${k * 100}%`, background: C.blue, borderRadius: 6}} /></div>
      {ev.map(([d, t, s], i) => { const at = 10 + i * passo; const q = spring({frame: f - at, fps, config: {damping: 9, stiffness: 200}}); const o = fadeIn(f, at, at + 9);
        return <div key={i} style={{position: 'relative', padding: '24px 0', minHeight: 110}}>
          <div style={{position: 'absolute', left: -62, top: 30, width: 46, height: 46, borderRadius: 46, background: statusColor(s), transform: `scale(${q})`, border: `6px solid ${C.solid}`}} />
          <div style={{opacity: o, transform: `translateX(${(1 - o) * 60}px)`}}><div style={{fontFamily: mono, fontSize: 26, color: C.mute}}>{d}</div><div style={{fontFamily: font, fontSize: 46, fontWeight: 800, color: C.ink}}>{t}</div></div>
        </div>; })}
    </div>
  </Card>;
};

// comparar: esquerda, direita, item "texto esquerda | texto direita" (repetir), vence (esquerda/direita)
const Comparar: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame();
  const itens = many(p, 'item').map(cells); const vDir = one(p, 'vence', 'direita').toLowerCase() !== 'esquerda';
  const fim = line2(dur * 0.72, dur * 0.86, f); const passo = Math.min(30, (dur * 0.6) / Math.max(1, itens.length));
  const Lado: React.FC<{tit: string; idx: 0 | 1; bom: boolean}> = ({tit, idx, bom}) => <div style={{flex: 1 + (bom ? fim * 0.12 : -fim * 0.12), padding: '30px 22px', background: bom ? C.soft : 'transparent', opacity: bom ? 1 : 1 - fim * 0.45}}>
    <div style={{fontFamily: font, fontWeight: 800, fontSize: 38, lineHeight: 1.08, color: bom ? C.blue : C.mute, marginBottom: 22, minHeight: 86}}>{tit}</div>
    {itens.map((it, i) => { const o = fadeIn(f, 18 + i * passo, 26 + i * passo); return <div key={i} style={{display: 'flex', gap: 12, alignItems: 'flex-start', fontFamily: font, fontSize: 31, lineHeight: 1.15, fontWeight: 600, color: bom ? C.ink : C.mute, padding: '16px 0', opacity: o, transform: `translateY(${(1 - o) * 26}px)`}}><span style={{color: bom ? C.green : C.red, fontWeight: 900}}>{bom ? '✓' : '✕'}</span><span>{it[idx]}</span></div>; })}
  </div>;
  const s = line2(4, 18, f);
  return <Card top={640}><div style={{display: 'flex', margin: -34, minHeight: 640, position: 'relative'}}>
    <Lado tit={one(p, 'esquerda', 'Before')} idx={0} bom={!vDir} /><div style={{width: 4, background: C.blue, transform: `scaleY(${s})`, flexShrink: 0}} /><Lado tit={one(p, 'direita', 'After')} idx={1} bom={vDir} />
  </div></Card>;
};

// medidor: titulo, valor, min, max, faixa "de | até | cor" (repetir), unidade, rotulo
const Medidor: React.FC<P> = ({p}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const mi = num(one(p, 'min', '0'), 0), ma = num(one(p, 'max', '100'), 100), v = num(one(p, 'valor', '50'), 50);
  const faixas = many(p, 'faixa').map(cells); const R = 330, cx = 420, cy = 410;
  const ang = (x: number) => -180 + ((Math.min(ma, Math.max(mi, x)) - mi) / (ma - mi || 1)) * 180;
  const pt = (a: number, r = R) => [cx + r * Math.cos((a * Math.PI) / 180), cy + r * Math.sin((a * Math.PI) / 180)];
  const arco = (a: number, b: number) => { const [x1, y1] = pt(a), [x2, y2] = pt(b); return `M${x1} ${y1} A${R} ${R} 0 0 1 ${x2} ${y2}`; };
  const s = spring({frame: f - 8, fps, config: {damping: 7, stiffness: 55}}); const atual = mi + (v - mi) * s;
  return <Card title={one(p, 'titulo', 'gauge')} right={one(p, 'canto', '')}>
    <svg viewBox="0 0 840 500" width="100%" style={{display: 'block'}}>
      {(faixas.length ? faixas : [[String(mi), String(ma), 'azul']]).map(([a, b, c], i) => <path key={i} d={arco(ang(num(a, mi)), ang(num(b, ma)))} fill="none" stroke={colorOf(c, C.blue)} strokeWidth={46} opacity={fadeIn(f, 2 + i * 4, 10 + i * 4)} />)}
      <g transform={`rotate(${ang(atual) + 90} ${cx} ${cy})`}><path d={`M${cx - 15} ${cy} L${cx} ${cy - R + 34} L${cx + 15} ${cy} Z`} fill={C.ink} /></g>
      <circle cx={cx} cy={cy} r={30} fill={C.ink} />
    </svg>
    <div style={{textAlign: 'center', fontFamily: font, fontWeight: 900, fontSize: 120, letterSpacing: -4, color: C.ink, lineHeight: 1}}>{Math.round(atual)}<span style={{fontSize: 56, color: C.mute}}> {one(p, 'unidade')}</span></div>
    {one(p, 'rotulo') && <div style={{textAlign: 'center', fontFamily: mono, fontSize: 26, color: C.mute, marginTop: 10}}>{one(p, 'rotulo')}</div>}
  </Card>;
};

// checklist: titulo, canto, item "texto | ok/nao" (repetir)
const Checklist: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const itens = many(p, 'item').map(cells); const passo = Math.min(32, (dur - 30) / Math.max(1, itens.length));
  return <Card title={one(p, 'titulo', 'checklist')} right={one(p, 'canto', '')}>{itens.map(([t, s], i) => { const ok = !['nao', 'não', 'no'].includes((s || 'ok').toLowerCase()); const at = 8 + i * passo; const o = fadeIn(f, at, at + 7); const m = line2(at + 9, at + 19, f); const pop = spring({frame: f - (at + 9), fps, config: {damping: 8, stiffness: 240}}); const cor = ok ? C.green : C.orange;
    return <div key={i} style={{display: 'flex', alignItems: 'center', gap: 28, padding: '22px 0', borderBottom: `2px solid ${C.line}`, opacity: o, transform: `translateX(${(1 - o) * 50}px)`}}>
      <svg viewBox="0 0 70 70" width={70} height={70} style={{transform: `scale(${0.9 + 0.1 * pop})`, flexShrink: 0}}><rect x={5} y={5} width={60} height={60} rx={12} fill="none" stroke={m > 0 ? cor : C.mute} strokeWidth={5} />
        {ok ? <path d="M18 37 L31 50 L53 22" pathLength={1} fill="none" stroke={cor} strokeWidth={8} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={1} strokeDashoffset={1 - m} /> : <path d="M21 21 L49 49 M49 21 L21 49" pathLength={1} fill="none" stroke={cor} strokeWidth={8} strokeLinecap="round" strokeDasharray={1} strokeDashoffset={1 - m} />}
      </svg><div style={{fontFamily: font, fontSize: 44, fontWeight: 700, color: C.ink}}>{t}</div></div>; })}</Card>;
};

// relatorio: titulo, para, secao "Título | linha 1 ; linha 2" (repetir), rodape
const Relatorio: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const secoes = many(p, 'secao').map(cells).map(([t, r]) => ({t, ls: (r || '').split(';').map(x => x.trim()).filter(Boolean)}));
  const abre = spring({frame: f - 4, fps, config: {damping: 14}}); const passo = Math.min(42, (dur - 40) / Math.max(1, secoes.length));
  const desce = interpolate(f, [30, dur], [0, -Math.max(0, 230 + secoes.length * 230 - 1030)], clamp);  // só desce se a folha não couber
  return <div style={{position: 'absolute', top: 620, left: 110, right: 110, height: 1120, perspective: 1600}}>
    <div style={{background: C.solid, borderRadius: 10, height: '100%', overflow: 'hidden', transformOrigin: '50% 0', transform: `rotateX(${(1 - abre) * -70}deg)`, boxShadow: '0 40px 70px -25px #000a', padding: '46px 46px', fontFamily: font, color: C.ink, opacity: Math.min(1, abre * 2)}}>
      <div style={{transform: `translateY(${desce}px)`}}>
        <div style={{fontWeight: 900, fontSize: 48, letterSpacing: -1, color: C.blue, lineHeight: 1.05}}>{one(p, 'titulo', 'REPORT')}</div>
        <div style={{fontFamily: mono, fontSize: 25, color: C.mute, paddingBottom: 22, borderBottom: `3px solid ${C.line}`}}>{one(p, 'para')}</div>
        {secoes.map((s, i) => { const at = 22 + i * passo, o = fadeIn(f, at, at + 11);
          return <div key={i} style={{padding: '24px 0', borderBottom: `2px solid ${C.line}`, opacity: o, transform: `translateY(${(1 - o) * 24}px)`}}>
            <div style={{fontSize: 36, fontWeight: 800}}>{s.t}</div>
            {i === 1 && <div style={{display: 'flex', alignItems: 'flex-end', gap: 14, height: 110, margin: '14px 0'}}>{s.ls.map((_, j) => <div key={j} style={{flex: 1, background: C.blue, borderRadius: 6, height: `${(35 + random(`rb${j}`) * 65) * line2(at + 8, at + 26, f)}%`}} />)}</div>}
            {s.ls.map((l, j) => <div key={j} style={{fontSize: 29, color: C.mute, lineHeight: 1.4}}>{l}</div>)}
          </div>; })}
        {one(p, 'rodape') && <div style={{paddingTop: 22, fontFamily: mono, fontSize: 24, color: C.mute, opacity: fadeIn(f, 22 + secoes.length * passo, 32 + secoes.length * passo)}}>{one(p, 'rodape')}</div>}
      </div>
    </div>
  </div>;
};

// formulario: titulo, campo "Rótulo | valor" (repetir), botao
const Formulario: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame();
  const campos = many(p, 'campo').map(cells); const tempo = Math.min(44, (dur - 46) / Math.max(1, campos.length));
  const fimT = 8 + campos.length * tempo; const press = fadeIn(f, fimT, fimT + 3) * (1 - fadeIn(f, fimT + 5, fimT + 9)); const sent = fadeIn(f, fimT + 6, fimT + 11);
  return <Card title={one(p, 'titulo', 'form')}>{campos.map(([l, v], i) => { const at = 8 + i * tempo; const n = Math.max(0, Math.floor(interpolate(f, [at, at + tempo * 0.72], [0, v.length], clamp))); const ativo = f >= at && f < at + tempo; const pronto = f >= at + tempo * 0.8;
    return <div key={i} style={{marginBottom: 24}}><div style={{fontFamily: mono, fontSize: 24, color: C.mute, marginBottom: 8}}>{l}</div>
      <div style={{height: 88, borderRadius: 14, border: `3px solid ${ativo ? C.blue : C.line}`, background: C.soft, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px', fontFamily: font, fontSize: 40, fontWeight: 600, color: C.ink}}><span>{v.slice(0, n)}<span style={{opacity: ativo && f % 16 < 8 ? 1 : 0, color: C.blue}}>|</span></span>{pronto && <span style={{color: C.green, fontWeight: 900, opacity: fadeIn(f, at + tempo * 0.8, at + tempo * 0.8 + 6)}}>✓</span>}</div></div>; })}
    <div style={{height: 100, borderRadius: 16, background: sent ? C.green : C.blue, color: C.onAccent, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: font, fontWeight: 800, fontSize: 44, transform: `scale(${1 - press * 0.05}) translateY(${press * 6}px)`}}>{sent > 0.5 ? 'Sent ✓' : one(p, 'botao', 'Send')}</div>
  </Card>;
};

const ICONES: Record<string, React.ReactNode> = {
  sinal: <path d="M18 44 A24 24 0 0 1 46 44 M10 32 A36 36 0 0 1 54 32 M32 50 L32 51" />,
  alerta: <path d="M32 10 L58 54 L6 54 Z M32 26 L32 40 M32 47 L32 48" />,
  escritorio: <path d="M12 56 L12 12 L38 12 L38 56 M38 28 L54 28 L54 56 M6 56 L60 56 M20 22 L30 22 M20 34 L30 34 M20 46 L30 46" />,
  telefone: <path d="M16 10 L26 8 L31 22 L24 27 C 27 36, 32 41, 41 45 L46 38 L60 44 L57 54 C 32 60, 10 36, 16 10" />,
  tecnico: <path d="M44 8 C 36 8, 32 16, 36 23 L10 49 L16 55 L42 29 C 49 33, 58 28, 58 20 L49 26 L42 21 L47 11 Z" />,
  casa: <path d="M8 32 L32 10 L56 32 M15 26 L15 56 L49 56 L49 26 M26 56 L26 38 L38 38 L38 56" />,
  relatorio: <path d="M14 6 L42 6 L52 16 L52 58 L14 58 Z M22 26 L44 26 M22 36 L44 36 M22 46 L36 46" />,
  check: <path d="M10 34 L26 50 L56 16" />,
};
// fluxo: titulo, etapa "ícone | texto" (repetir: sinal, alerta, escritorio, telefone, tecnico, casa, relatorio, check), ativo
const Fluxo: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const et = many(p, 'etapa').map(cells); const ativo = num(one(p, 'ativo', '0'), 0) - 1; const passo = Math.min(20, (dur * 0.45) / Math.max(1, et.length));
  const pulso = (((f - 12 - et.length * passo) % 50) + 50) % 50 / 50; const corre = f > 12 + et.length * passo;
  return <Card title={one(p, 'titulo', 'flow')} right={one(p, 'canto', '')}>{et.map(([ic, t], i) => { const q = spring({frame: f - (8 + i * passo), fps, config: {damping: 13}}); const on = i === ativo; const seg = corre && Math.floor(pulso * et.length) === i;
    return <div key={i}><div style={{display: 'flex', alignItems: 'center', gap: 28, padding: '12px 22px', borderRadius: 18, background: on || seg ? C.soft2 : C.soft, border: `3px solid ${on ? C.blue : C.line}`, opacity: Math.min(1, q), transform: `scale(${0.85 + 0.15 * q})`}}>
      <svg viewBox="0 0 64 64" width={76} height={76} fill="none" stroke={on ? C.blue : C.ink} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">{ICONES[(ic || '').toLowerCase()] ?? ICONES.check}</svg>
      <div style={{fontFamily: font, fontSize: 44, fontWeight: 700, color: C.ink}}>{t}</div></div>
      {i < et.length - 1 && <svg width="100%" height={46} viewBox="0 0 100 46" preserveAspectRatio="xMidYMid meet" style={{display: 'block', opacity: fadeIn(f, 12 + i * passo, 20 + i * passo)}}><path d="M50 2 L50 38" stroke={C.blue} strokeWidth={4} strokeDasharray="8 7" strokeDashoffset={-f * 1.4} /><path d="M41 31 L50 42 L59 31" fill="none" stroke={C.blue} strokeWidth={4} strokeLinejoin="round" /></svg>}
    </div>; })}</Card>;
};

// guardian3d: imagem, sinal "nome | valor" (repetir), rotulo
const Guardian3D: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const sinais = many(p, 'sinal').map(cells); const s = spring({frame: f - 6, fps, config: {damping: 14}});
  const lugares = [[80, 700], [640, 720], [60, 1290], [650, 1310], [340, 1420], [350, 640]];
  const cx = 540, cy = 1040; const passo = Math.min(20, (dur - 34) / Math.max(1, sinais.length));
  return <>
    <div style={{position: 'absolute', top: 1270, left: 200, width: 680, height: 90, borderRadius: '50%', background: C.blue, filter: 'blur(60px)', opacity: 0.45}} />
    {[0, 1, 2].map(i => { const k = (((f + i * 22) % 66) / 66); return <div key={i} style={{position: 'absolute', left: cx - 400, top: cy - 400, width: 800, height: 800, borderRadius: 800, border: `4px solid ${C.blue}`, opacity: (1 - k) * 0.55, transform: `scale(${0.35 + k * 0.85})`}} />; })}
    <svg style={{position: 'absolute', left: 0, top: 0}} width={1080} height={1920}>{sinais.map((_, i) => { const [x, y] = lugares[i % lugares.length]; const o = fadeIn(f, 22 + i * passo, 32 + i * passo); return <line key={i} x1={cx} y1={cy} x2={cx + (x + 150 - cx) * o} y2={cy + (y + 44 - cy) * o} stroke={C.blue} strokeWidth={3} strokeDasharray="8 8" opacity={0.75} />; })}</svg>
    <div style={{position: 'absolute', top: 760, left: 0, right: 0, display: 'flex', justifyContent: 'center', perspective: 1400}}>
      <Img src={staticFile('imagens/' + one(p, 'imagem', 'guardian.png'))} style={{width: 640, height: 540, objectFit: 'contain', opacity: s, transform: `rotateY(${Math.sin(f / 26) * 12}deg) translateY(${Math.sin(f / 18) * 12 + (1 - s) * 90}px) scale(${0.8 + 0.2 * s})`}} />
    </div>
    {sinais.map(([n, v], i) => { const [x, y] = lugares[i % lugares.length]; const q = spring({frame: f - (22 + i * passo), fps, config: {damping: 13}});
      return <div key={i} style={{position: 'absolute', left: cx - 150 + (x + 150 - cx) * q, top: cy - 44 + (y + 44 - cy) * q, width: 300, background: C.solid, border: `2px solid ${C.blue}`, borderRadius: T.raio ? 16 : 0, padding: '12px 18px', textAlign: 'center', opacity: Math.min(1, q)}}><div style={{fontFamily: mono, fontSize: 22, color: C.mute}}>{n}</div><div style={{fontFamily: font, fontWeight: 800, fontSize: 40, color: C.ink}}>{v}</div></div>; })}
    {one(p, 'rotulo') && <div style={{position: 'absolute', top: 1560, width: '100%', textAlign: 'center', fontFamily: mono, fontSize: 22, color: C.mute}}>{one(p, 'rotulo')}</div>}
  </>;
};

export const SCENES2: Record<string, React.FC<P>> = {celular: Celular, mapapins: MapaPins, painel: Painel, linha: Linha, linhadotempo: LinhaDoTempo, comparar: Comparar, medidor: Medidor, checklist: Checklist, relatorio: Relatorio, formulario: Formulario, fluxo: Fluxo, guardian3d: Guardian3D};
