import React, {useContext} from 'react';
import {Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig, Easing, random} from 'remotion';
import {C, T, font, mono, clamp, Params, one, many, cells, colorOf, tagColor} from './theme';
import {Desenho} from './Desenho';
import {CUSTOM} from './custom';

// Qual dos jeitos de entrar esta fala usa (0 = o original); vem do rodízio.
export const VarCtx = React.createContext(0);

type P = {p: Params; dur: number};
const TOP = 640;

export const Card: React.FC<{top?: number; dark?: boolean; title?: string; right?: string; children: React.ReactNode; delay?: number}> = ({top = TOP, dark, title, right, children, delay = 6}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const s = spring({frame: f - delay, fps, config: {damping: 16}});
  const v = useContext(VarCtx);
  const entra = v === 1 ? `translateX(${(1 - s) * 340}px)` : v === 2 ? `translateY(${(1 - s) * -260}px)` : `translateY(${(1 - s) * 60}px) scale(${0.94 + 0.06 * s})`;
  const linha = dark ? C.dark2 : C.line;
  const borda = T.pulso ? `${C.orange}${Math.round(120 + 90 * (0.5 + 0.5 * Math.sin(f / 9))).toString(16).padStart(2, '0')}` : linha;
  return <div style={{position: 'absolute', top, left: 90, right: 90, background: dark ? C.dark : C.card, borderRadius: T.raio, boxShadow: T.sombra, border: `2px solid ${borda}`, overflow: 'hidden', opacity: s, transform: entra}}>
    {title !== undefined && <div style={{height: 70, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20, padding: '0 30px', borderBottom: `2px solid ${dark ? C.dark2 : C.line}`, fontFamily: mono, fontSize: 24, color: dark ? '#9AA6C0' : C.mute, whiteSpace: 'nowrap'}}>
      <span style={{overflow: 'hidden', textOverflow: 'ellipsis'}}>{T.barra && <><span style={{color: C.red}}>●</span> <span style={{color: C.amber}}>●</span> <span style={{color: C.green}}>●</span>&nbsp;&nbsp;</>}{title}</span><span>{right}</span>
    </div>}
    <div style={{padding: 34}}>{children}</div>
  </div>;
};
export const Tag: React.FC<{c: string; children: React.ReactNode}> = ({c, children}) => <span style={{fontFamily: mono, fontSize: 22, color: c, background: c + '1A', padding: '6px 14px', borderRadius: 8, fontWeight: 700, whiteSpace: 'nowrap'}}>{children}</span>;
export const fadeIn = (f: number, a: number, b: number) => interpolate(f, [a, b], [0, 1], clamp);
export const num = (s: string, d: number) => { const n = parseFloat((s || '').replace(/[^0-9.\-]/g, '')); return isNaN(n) ? d : n; };

// contador: numero, rotulo, titulo, canto, pontos (sim/nao)
const Contador: React.FC<P> = ({p}) => {
  const f = useCurrentFrame();
  const n = num(one(p, 'numero', '300'), 300);
  const v = Math.round(interpolate(f, [8, 55], [0, n], {...clamp, easing: Easing.out(Easing.cubic)}));
  const dots = one(p, 'pontos', 'sim').toLowerCase() !== 'nao' && n <= 500;
  const pre = one(p, 'antes', ''), pos = one(p, 'depois', '');
  const jeito = useContext(VarCtx);
  const pop = jeito === 2 ? 1 + interpolate(f, [48, 58, 70], [0, 0.14, 0], clamp) : 1;
  const rolo = jeito === 1 ? v.toLocaleString('en-US').split('').map((d, i) => /\d/.test(d) ? <span key={i} style={{display: 'inline-block', transform: `translateY(${f < 50 ? Math.sin(f * 2 + i) * 14 : 0}px)`, filter: f < 50 ? 'blur(2px)' : undefined}}>{d}</span> : d) : v.toLocaleString('en-US');
  return <Card title={one(p, 'titulo', 'total')} right={one(p, 'canto', '')}>
    <div style={{display: 'flex', alignItems: 'baseline', gap: 20, flexWrap: 'wrap'}}>
      <div style={{fontFamily: font, fontWeight: 900, fontSize: 170, color: C.ink, letterSpacing: -8, lineHeight: 1, transform: `scale(${pop})`, transformOrigin: 'left center'}}>{pre}{rolo}{pos}</div>
      <div style={{fontFamily: font, fontSize: 40, color: C.mute}}>{one(p, 'rotulo', '')}</div>
    </div>
    {dots && <div style={{display: 'grid', gridTemplateColumns: 'repeat(25, 1fr)', gap: 8, marginTop: 30}}>
      {Array.from({length: n}).map((_, i) => <div key={i} style={{aspectRatio: '1', borderRadius: 4, background: i < v ? C.blue : C.line}} />)}
    </div>}
  </Card>;
};

// tabela: titulo, canto, colunas "A | B | C", linha (repetir) "a | b | c"  (última coluna vira etiqueta)
const Tabela: React.FC<P> = ({p}) => {
  const f = useCurrentFrame();
  const cols = cells(one(p, 'colunas', 'Name | Status'));
  const rows = many(p, 'linha').map(cells);
  const fl = (i: number) => (i === 0 ? 1.4 : 1);
  const jeito = useContext(VarCtx);
  return <Card title={one(p, 'titulo', 'list')} right={one(p, 'canto', '')}>
    <div style={{display: 'flex', fontFamily: mono, fontSize: 22, color: C.mute, paddingBottom: 14, borderBottom: `2px solid ${C.line}`}}>{cols.map((c, i) => <span key={i} style={{flex: fl(i), textAlign: i === cols.length - 1 && i > 0 ? 'right' : 'left'}}>{c.toUpperCase()}</span>)}</div>
    {rows.map((r, i) => {
      const o = fadeIn(f, 10 + i * 5, 18 + i * 5); const q = fadeIn(f, 40 + i * 4, 47 + i * 4);
      const mov = jeito === 1 ? `translateX(${(1 - o) * -120}px)` : jeito === 2 ? `translateY(${(1 - o) * -70}px)` : undefined;
      return <div key={i} style={{display: 'flex', alignItems: 'center', height: 86, borderBottom: `2px solid ${C.line}`, opacity: o, transform: mov, fontFamily: font, fontSize: 32}}>
        {r.map((c, j) => j === r.length - 1 && j > 0
          ? <span key={j} style={{flex: fl(j), textAlign: 'right', opacity: q}}><Tag c={tagColor(c)}>{c}</Tag></span>
          : <span key={j} style={{flex: fl(j), fontWeight: j === 0 ? 600 : 400, color: j === 0 ? C.ink : C.mute}}>{c}</span>)}
      </div>;
    })}
  </Card>;
};

// console: titulo, canto, item (repetir) "calls = 0", meses (sim/nao)
const Console: React.FC<P> = ({p}) => {
  const f = useCurrentFrame();
  const items = many(p, 'item').map(s => s.split('=').map(x => x.trim()));
  const jeito = useContext(VarCtx);
  const escreve = (txt: string, i: number) => jeito === 2 ? txt.slice(0, Math.max(0, Math.floor((f - 8 - i * 8) / 1.2))) : txt;
  const months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  return <Card dark title={one(p, 'titulo', 'console')} right={one(p, 'canto', '')}>
    {items.map(([k, v], i) => <div key={i} style={{display: 'flex', justifyContent: 'space-between', fontFamily: mono, fontSize: 36, color: '#C9D2E6', padding: '16px 0', borderBottom: '2px solid #1E2944', opacity: fadeIn(f, 8 + i * 8, 16 + i * 8)}}>
      <span>&gt; {escreve(k, i)}</span><span style={{color: colorOf(one(p, 'cor', ''), C.orange), fontWeight: 700}}>{escreve(v ?? '', i + 1)}</span></div>)}
    {one(p, 'meses', 'nao').toLowerCase() === 'sim' && <div style={{display: 'flex', gap: 10, marginTop: 40}}>{months.map((m, i) => <div key={m} style={{flex: 1, textAlign: 'center', opacity: fadeIn(f, 40 + i * 3, 46 + i * 3)}}>
      <div style={{height: 70, borderRadius: 8, background: i === 0 ? C.blue : '#1E2944'}} />
      <div style={{fontFamily: mono, fontSize: 18, color: '#7B88A8', marginTop: 8}}>{m}</div></div>)}</div>}
  </Card>;
};

// contato: titulo, canto, nome, detalhe, aviso, borrar (sim/nao)
const Contato: React.FC<P> = ({p}) => {
  const f = useCurrentFrame();
  const doBlur = one(p, 'borrar', 'sim').toLowerCase() !== 'nao';
  const blur = doBlur ? interpolate(f, [20, 70], [0, 16], clamp) : 0;
  const nome = one(p, 'nome', 'Your Company');
  const ini = nome.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  return <Card title={one(p, 'titulo', 'contacts')} right={one(p, 'canto', '')}>
    <div style={{display: 'flex', alignItems: 'center', gap: 30}}>
      <div style={{width: 130, height: 130, borderRadius: 130, background: C.blue2, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: font, fontWeight: 800, fontSize: 56, color: C.onAccent, filter: `blur(${blur}px)`, flexShrink: 0}}>{ini}</div>
      <div style={{filter: `blur(${blur}px)`, opacity: doBlur ? interpolate(f, [20, 80], [1, 0.4], clamp) : 1}}>
        <div style={{fontFamily: font, fontWeight: 800, fontSize: 56, color: C.ink}}>{nome}</div>
        <div style={{fontFamily: font, fontSize: 34, color: C.mute}}>{one(p, 'detalhe', '')}</div>
      </div>
    </div>
    {one(p, 'aviso') && <div style={{marginTop: 40, fontFamily: mono, fontSize: 28, color: C.red, opacity: fadeIn(f, 60, 72)}}>{one(p, 'aviso')}</div>}
  </Card>;
};

// termostato: titulo, canto, de, para, alvo, aviso
const Termostato: React.FC<P> = ({p}) => {
  const f = useCurrentFrame();
  const a = num(one(p, 'de', '72'), 72), b = num(one(p, 'para', '88'), 88);
  const t = interpolate(f, [5, 80], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const deg = Math.round(a + t * (b - a)); const hot = b > a && t > 0.55;
  const acc = hot ? C.orange : C.blue;
  return <Card title={one(p, 'titulo', 'thermostat')} right={one(p, 'canto', '')}>
    <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
      <div>
        <div style={{fontFamily: mono, fontSize: 24, color: C.mute}}>INDOOR</div>
        <div style={{fontFamily: font, fontWeight: 900, fontSize: 190, letterSpacing: -8, lineHeight: 1, color: hot ? C.orange : C.ink}}>{deg}°</div>
        <div style={{fontFamily: mono, fontSize: 26, color: C.mute}}>{one(p, 'alvo', 'set to 72° · cooling')}</div>
      </div>
      <div style={{width: 300, height: 300, borderRadius: 300, border: `22px solid ${C.line}`, borderTopColor: acc, borderRightColor: t > 0.3 ? acc : C.line, transform: `rotate(${t * 200}deg)`}} />
    </div>
    {one(p, 'aviso') && <div style={{marginTop: 30, opacity: hot ? 1 : 0}}><Tag c={C.red}>{one(p, 'aviso')}</Tag></div>}
  </Card>;
};

// busca: termo, resultado (repetir) "Company A | 4.6 ★ · Free estimate", escolhido (1..n), selo, aviso
const Busca: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame();
  const termo = one(p, 'termo', 'ac repair near me');
  const typed = termo.slice(0, Math.max(0, Math.floor((f - 6) / 2)));
  const res = many(p, 'resultado').map(cells);
  const pickI = num(one(p, 'escolhido', '0'), 0) - 1;
  const pick = interpolate(f, [dur * 0.7, dur * 0.7 + 12], [0, 1], clamp);
  return <Card top={600} title={one(p, 'titulo', 'search')} right="">
    <div style={{height: 90, borderRadius: 45, border: `2px solid ${C.line}`, display: 'flex', alignItems: 'center', gap: 20, padding: '0 34px', fontFamily: font, fontSize: 36, color: C.ink}}>
      <div style={{width: 30, height: 30, borderRadius: 30, border: `5px solid ${C.mute}`, flexShrink: 0}} />{typed}<span style={{opacity: f % 20 < 10 ? 1 : 0}}>|</span></div>
    {res.map(([n, d], i) => {
      const o = fadeIn(f, 30 + i * 10, 40 + i * 10); const win = i === pickI;
      return <div key={i} style={{marginTop: 22, padding: '22px 26px', borderRadius: 18, border: `3px solid ${win && pick ? C.blue : C.line}`, opacity: win || pickI < 0 ? o : o * (1 - pick * 0.5), display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontFamily: font}}>
        <div><div style={{fontSize: 36, fontWeight: 700, color: C.ink}}>{n}</div><div style={{fontSize: 26, color: C.mute}}>{d}</div></div>
        {win && pick > 0.2 && <Tag c={C.blue}>{one(p, 'selo', 'CALLING ✓')}</Tag>}
      </div>;
    })}
    {one(p, 'aviso') && <div style={{marginTop: 26, fontFamily: mono, fontSize: 24, color: C.red, opacity: pickI >= 0 ? pick : fadeIn(f, 60, 70)}}>{one(p, 'aviso')}</div>}
  </Card>;
};

// barras: titulo, canto, barra (repetir) "Rótulo | valor | cor"
const Barras: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame();
  const bars = many(p, 'barra').map(cells);
  const max = Math.max(1, ...bars.map(b => num(b[1], 1)));
  const step = Math.min(50, (dur - 30) / Math.max(1, bars.length));
  const jeito = useContext(VarCtx); const {fps} = useVideoConfig();
  if (jeito === 1) return <Card title={one(p, 'titulo', 'chart')} right={one(p, 'canto', '')}>{bars.map(([l, v, c], i) => { const k = interpolate(f, [10 + i * step, 40 + i * step], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)}); return <div key={i} style={{marginBottom: 30}}><div style={{fontFamily: font, fontSize: 34, fontWeight: 700, color: C.ink, marginBottom: 10}}>{l}</div><div style={{height: 56, width: `${Math.max(2, k * (num(v, 1) / max) * 100)}%`, background: colorOf(c, i % 2 ? C.orange : C.blue), borderRadius: 12}} /></div>; })}</Card>;
  return <Card title={one(p, 'titulo', 'chart')} right={one(p, 'canto', '')}>
    <div style={{display: 'flex', gap: 30}}>{bars.map(([l, v, c], i) => {
      const k = jeito === 2 ? spring({frame: f - (10 + i * step), fps, config: {damping: 9, stiffness: 120}}) : interpolate(f, [10 + i * step, 40 + i * step], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
      const col = colorOf(c, i % 2 ? C.orange : C.blue);
      return <div key={i} style={{flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
        <div style={{height: 440, width: '70%', display: 'flex', alignItems: 'flex-end'}}><div style={{width: '100%', height: `${k * (num(v, 1) / max) * 100}%`, background: col, borderRadius: 14}} /></div>
        <div style={{fontFamily: font, fontSize: 30, fontWeight: 700, color: C.ink, textAlign: 'center'}}>{l}</div></div>;
    })}</div>
  </Card>;
};

// produto: imagem (pasta imagens), info (repetir) "status | online | verde", rotulo
const Produto: React.FC<P> = ({p}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const s = spring({frame: f - 10, fps, config: {damping: 15}});
  const info = many(p, 'info').map(cells);
  return <>
    <div style={{position: 'absolute', top: 600, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
      <div style={{position: 'absolute', top: 140, width: 640, height: 300, borderRadius: '50%', background: C.blue, filter: 'blur(110px)', opacity: 0.25}} />
      <Img src={staticFile('imagens/' + one(p, 'imagem', 'guardian.png'))} style={{width: 820, maxHeight: 560, objectFit: 'contain', transform: `scale(${0.75 + 0.25 * s}) translateY(${(1 - s) * 80}px)`, opacity: s}} />
    </div>
    <div style={{position: 'absolute', top: 1180, left: 90, right: 90, display: 'flex', flexDirection: 'column', gap: 16}}>
      {info.map(([k, v, c], i) => { const o = fadeIn(f, 40 + i * 10, 50 + i * 10);
        return <div key={i} style={{background: C.card, borderRadius: 18, border: `2px solid ${C.line}`, padding: '20px 30px', display: 'flex', justifyContent: 'space-between', fontFamily: mono, fontSize: 28, color: C.mute, opacity: o, transform: `translateX(${(1 - o) * 80}px)`}}>
          <span>{k}</span><span style={{color: colorOf(c, C.blue), fontWeight: 700}}>{v}</span></div>; })}
      <div style={{textAlign: 'center', fontFamily: mono, fontSize: 22, color: C.mute, marginTop: 6}}>{one(p, 'rotulo', 'ILLUSTRATION')}</div>
    </div>
  </>;
};

// comentario: usuario, palavra, resposta, autor
const Comentario: React.FC<P> = ({p}) => {
  const f = useCurrentFrame();
  const word = one(p, 'palavra', 'MONITOR');
  const typed = word.slice(0, Math.max(0, Math.floor((f - 20) / 3)));
  const rT = 25 + word.length * 3;
  const reply = fadeIn(f, rT, rT + 10);
  return <Card top={660} title="comments" right="">
    <div style={{display: 'flex', gap: 22, alignItems: 'flex-start'}}>
      <div style={{width: 80, height: 80, borderRadius: 80, background: C.blue2, flexShrink: 0}} />
      <div><div style={{fontFamily: font, fontSize: 28, color: C.mute}}>{one(p, 'usuario', 'hvac_owner')}</div>
        <div style={{fontFamily: font, fontSize: 64, fontWeight: 900, color: C.ink, letterSpacing: 2}}>{typed}<span style={{opacity: f % 20 < 10 && typed.length < word.length ? 1 : 0, color: C.blue}}>|</span></div></div>
    </div>
    {one(p, 'resposta') && <div style={{display: 'flex', gap: 22, alignItems: 'flex-start', marginTop: 34, marginLeft: 100, opacity: reply, transform: `translateY(${(1 - reply) * 20}px)`}}>
      <div style={{width: 64, height: 64, borderRadius: 64, background: C.blue, flexShrink: 0}} />
      <div style={{background: C.soft, borderRadius: 20, padding: '18px 26px'}}><div style={{fontFamily: font, fontSize: 26, color: C.mute}}>{one(p, 'autor', 'you')}</div>
        <div style={{fontFamily: font, fontSize: 36, color: C.ink}}>{one(p, 'resposta')}</div></div>
    </div>}
  </Card>;
};

// mapa: numero, titulo, canto, rotulo
const Mapa: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame();
  const n = Math.min(400, num(one(p, 'numero', '300'), 300));
  const zoom = interpolate(f, [0, Math.min(60, dur * 0.5)], [2.6, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const cols = 22, rows = 20, cell = 40;
  const lit = Math.round(interpolate(f, [15, Math.max(30, dur - 25)], [1, n], clamp));
  const order = Array.from({length: cols * rows}, (_, i) => i).sort((a, b) => random('m' + a) - random('m' + b)).slice(0, n);
  const rank = new Map(order.map((v, i) => [v, i]));
  return <Card title={one(p, 'titulo', 'service area')} right={one(p, 'canto', '')}>
    <div style={{height: 820, overflow: 'hidden', position: 'relative', borderRadius: 16, background: C.soft}}>
      <div style={{position: 'absolute', left: '50%', top: '50%', width: cols * cell, height: rows * cell, marginLeft: -cols * cell / 2, marginTop: -rows * cell / 2, transform: `scale(${zoom})`}}>
        {Array.from({length: cols * rows}).map((_, i) => {
          const x = i % cols, y = Math.floor(i / cols);
          const street = x % 5 === 4 || y % 4 === 3;
          const r = rank.get(i); const on = r !== undefined && r < lit;
          return <div key={i} style={{position: 'absolute', left: x * cell, top: y * cell, width: cell - 6, height: cell - 6, borderRadius: 5, background: street ? 'transparent' : on ? C.blue : C.soft2, boxShadow: on ? `0 0 12px ${C.blue}` : 'none'}} />;
        })}
      </div>
      <div style={{position: 'absolute', left: 24, bottom: 24, background: C.card, borderRadius: 16, padding: '14px 24px', fontFamily: font, fontSize: 34, fontWeight: 800, color: C.ink, boxShadow: '0 8px 20px #0002'}}>
        <span style={{color: C.blue}}>{lit}</span> {one(p, 'rotulo', 'homes connected')}</div>
    </div>
  </Card>;
};

// imagem: arquivo (pasta imagens), legenda
const Imagem: React.FC<P> = ({p}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const s = spring({frame: f - 6, fps, config: {damping: 15}});
  return <div style={{position: 'absolute', top: 620, left: 90, right: 90, opacity: s, transform: `scale(${0.92 + 0.08 * s})`}}>
    <Img src={staticFile('imagens/' + one(p, 'arquivo', 'guardian.png'))} style={{width: '100%', maxHeight: 900, objectFit: 'contain', borderRadius: 26}} />
    {one(p, 'legenda') && <div style={{textAlign: 'center', fontFamily: mono, fontSize: 24, color: C.mute, marginTop: 16}}>{one(p, 'legenda')}</div>}
  </div>;
};

// frase: só o texto grande (opcional: numero grande no centro)
const Frase: React.FC<P> = ({p, dur}) => {
  const f = useCurrentFrame();
  const big = one(p, 'grande');
  const desenho = one(p, '_desenho');
  if (!big && desenho.startsWith('custom:')) { const S = CUSTOM[desenho.slice(7)]; return S ? <S p={p} dur={dur} tema={C} /> : null; }
  if (!big && desenho) return <div style={{position: 'absolute', top: 820, width: '100%', display: 'flex', justifyContent: 'center'}}><Desenho tipo={desenho} /></div>;
  if (!big) return null;
  const s = fadeIn(f, 8, 20);
  return <div style={{position: 'absolute', top: 760, width: '100%', textAlign: 'center', fontFamily: font, fontWeight: 900, fontSize: 260, letterSpacing: -10, color: colorOf(one(p, 'cor'), C.blue), opacity: s, transform: `scale(${0.8 + 0.2 * s})`}}>{big}</div>;
};

export const SCENES: Record<string, React.FC<P>> = {contador: Contador, tabela: Tabela, console: Console, contato: Contato, termostato: Termostato, busca: Busca, barras: Barras, produto: Produto, comentario: Comentario, mapa: Mapa, imagem: Imagem, frase: Frase};
