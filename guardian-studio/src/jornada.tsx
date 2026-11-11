// JORNADA: um bonequinho atravessa uma casa em corte; cada cômodo acende quando a voz fala a etapa dele.
// campos: titulo, etapa (repetir) "OBJETO | rótulo"
import React from 'react';
import {Easing, interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, Params, cells, clamp, many, one} from './theme';
import {LARG, Linha, Palavra, VARANDA, acaoEm, andandoEm, cameraEm, centroComodo, linhaDoTempo, posBoneco, posEm, segAtual, tempos} from './jornada_tempo';

const TELA = 1020, ALTURA = 1100, PISO = 1010, TETO = 310, TOPO = 185, DX_OBJ = 80;
const P01 = (a: number, b: number, v: number): number => a < b ? interpolate(v, [a, b], [0, 1], clamp) : 1 - interpolate(v, [b, a], [0, 1], clamp);  // a > b: desce de 1 a 0
const volta = (v: number) => Easing.out(Easing.back(1.7))(Math.max(0, Math.min(1, v)));
const ALIAS: Record<string, string> = {
  PORTA: 'door', DOOR: 'door', PRESENTE: 'gift', GIFT: 'gift', ENVELOPE: 'mail', EMAIL: 'mail', MAIL: 'mail', TELA: 'screen', SCREEN: 'screen', VIDEO: 'screen', VSL: 'screen',
  PALCO: 'stage', STAGE: 'stage', WEBINAR: 'stage', LIVE: 'stage', CALENDARIO: 'calendar', CALENDAR: 'calendar', DATA: 'calendar', RELOGIO: 'clock', CLOCK: 'clock', TIMER: 'clock',
  CARRINHO: 'cart', CART: 'cart', OFERTA: 'cart', OFFER: 'cart', COMPRA: 'cart', CHAVE: 'key', KEY: 'key', ACESSO: 'key', ESCADA: 'stairs', STAIRS: 'stairs', UPSELL: 'stairs',
  CORACAO: 'heart', HEART: 'heart', FIDELIDADE: 'heart', TROFEU: 'trophy', TROPHY: 'trophy', RESULTADO: 'trophy', TELEFONE: 'phone', PHONE: 'phone', LIGACAO: 'phone', CASA: 'house', HOUSE: 'house', HOME: 'house',
};
const nomeObjeto = (s: string) => ALIAS[s.normalize('NFD').replace(/\p{Mn}/gu, '').toUpperCase().replace(/[^A-Z]/g, '')] ?? 'door';
const lerEtapas = (p: Params) => {
  const e = many(p, 'etapa').map(cells).filter(c => c.length > 1 && c[1]).slice(0, 5).map(c => ({obj: nomeObjeto(c[0]), label: c[1]}));
  return e.length >= 2 ? e : [{obj: 'door', label: 'entrada'}, {obj: 'trophy', label: 'resultado'}];
};

const L = {stroke: '#FFFFFF', strokeWidth: 5, strokeLinejoin: 'round', strokeLinecap: 'round'} as const;

const Particulas: React.FC<{a: number; seed: string; n?: number; y?: number; vel?: number; dur?: number; conf?: boolean}> = ({a, seed, n = 16, y = -120, vel = 600, dur = 0.9, conf}) => {
  if (a < 0 || a > dur + (conf ? 1.3 : 0)) return null;
  const cores = [C.amber, '#FFFFFF', C.blue, C.green];
  return <>{Array.from({length: n}).map((_, i) => {
    const r = (k: string) => random(`${seed}-${i}-${k}`);
    if (conf) {
      const px = (r('x') - 0.5) * 780, py = -620 - r('y') * 220 + a * (360 + r('v') * 300) + a * a * 90;
      return <rect key={i} x={px} y={py} width={18} height={11} fill={cores[i % cores.length]} opacity={P01(dur + 1.3, dur + 0.7, a)} transform={`rotate(${r('g') * 360 + a * 420} ${px} ${py})`} />;
    }
    const ang = r('a') * Math.PI * 2, v = vel * (0.5 + r('v') * 0.5);
    const px = Math.cos(ang) * v * a, py = y + Math.sin(ang) * v * a + 450 * a * a, op = 1 - a / dur;
    return i % 2
      ? <circle key={i} cx={px} cy={py} r={9} fill={cores[i % 2]} opacity={op} />
      : <path key={i} d={`M${px} ${py - 18} L${px + 5} ${py - 5} L${px + 18} ${py} L${px + 5} ${py + 5} L${px} ${py + 18} L${px - 5} ${py + 5} L${px - 18} ${py} L${px - 5} ${py - 5} Z`} fill={C.amber} opacity={op} />;
  })}</>;
};

type O = {a: number; s: string; ao: string};
const OBJ: Record<string, React.FC<O>> = {
  door: ({a}) => {
    const th = interpolate(a, [0, 0.7], [0, 75], {...clamp, easing: Easing.out(Easing.cubic)}), w = 180 * Math.cos(th * Math.PI / 180), tr = a >= 0 && a < 0.15 ? Math.sin(a * 120) * 4 : 0;
    return <g transform={`translate(${tr} 0)`}><rect x={-100} y={-335} width={200} height={335} fill={C.dark2} {...L} />
      <rect x={-90} y={-325} width={180} height={325} fill={C.amber} opacity={P01(0, 0.7, a) * 0.75} />
      {a > 0 && <path d="M90 -325 L300 -30 L300 0 L90 0 Z" fill={C.amber} opacity={P01(0, 0.7, a) * 0.22} />}
      <rect x={-90} y={-325} width={w} height={325} fill={C.dark2} {...L} /><circle cx={-90 + w * 0.85} cy={-160} r={10} fill={C.amber} /></g>;
  },
  gift: ({a, s}) => {
    const k = P01(0, 0.3, a), g = P01(0, 0.2, a) * P01(1.2, 0.5, a);
    return <g>{[150, 110, 70].map((r, i) => <circle key={r} cx={0} cy={-160} r={r} fill={C.amber} opacity={g * (0.08 + i * 0.06)} />)}
      <rect x={-85} y={-140} width={170} height={140} fill={C.dark2} {...L} /><rect x={-14} y={-140} width={28} height={140} fill={C.amber} />
      <g transform={`translate(0 ${-k * 75}) rotate(${k * 20} 0 -155)`}><rect x={-98} y={-172} width={196} height={36} fill={C.dark2} {...L} /><rect x={-14} y={-172} width={28} height={36} fill={C.amber} /><ellipse cx={-30} cy={-188} rx={30} ry={15} fill="none" stroke={C.amber} strokeWidth={8} /><ellipse cx={30} cy={-188} rx={30} ry={15} fill="none" stroke={C.amber} strokeWidth={8} /></g>
      <Particulas a={a - 0.1} seed={s} y={-170} /></g>;
  },
  mail: ({a}) => {
    const n = [0, 1, 2].filter(i => a - i * 0.25 >= 0.5).length, flag = P01(0, 0.3, a);
    return <g><rect x={-12} y={-150} width={24} height={150} fill="#FFFFFF" /><path d="M-100 -150 L-100 -240 Q-100 -300 -40 -300 L100 -300 L100 -150 Z" fill={C.dark2} {...L} /><path d="M-40 -300 Q20 -300 20 -240 L20 -150" fill="none" {...L} />
      <g transform={`rotate(${-flag * 90} 100 -180)`}><rect x={98} y={-180} width={80} height={10} fill={C.amber} /><rect x={158} y={-210} width={32} height={34} fill={C.amber} /></g>
      {[0, 1, 2].map(i => { const q = P01(0, 0.5, a - i * 0.25); if (q <= 0 || q >= 1) return null; const x = -320 + q * 300, y = -440 - Math.sin(q * Math.PI) * 120 + q * 220; return <g key={i} transform={`translate(${x} ${y}) rotate(${(1 - q) * -25})`}><rect x={-46} y={-30} width={92} height={60} fill="#FFFFFF" /><path d="M-46 -30 L0 6 L46 -30" fill="none" stroke={C.amber} strokeWidth={6} /></g>; })}
      {n > 0 && <text x={140} y={-320} fontSize={84} fontWeight={900} fontFamily={T.fonte} fill={C.amber} textAnchor="middle">+{n}</text>}</g>;
  },
  screen: ({a}) => {
    const on = P01(0, 0.35, a), bat = a > 0 ? 1 + Math.max(0, Math.sin(Math.min(a, 2.4) * Math.PI * 2.5)) * 0.22 : 1;
    return <g><rect x={-14} y={-105} width={28} height={70} fill="#FFFFFF" /><rect x={-90} y={-35} width={180} height={35} rx={10} fill={C.dark2} {...L} /><rect x={-170} y={-335} width={340} height={230} rx={14} fill="#05060A" {...L} />
      <rect x={-158} y={-323} width={316} height={206} rx={8} fill="#1D3F86" opacity={on} />
      <g opacity={on} transform={`translate(0 -230) scale(${bat})`}><circle r={52} fill="#00000055" /><path d="M-20 -32 L36 0 L-20 32 Z" fill={C.amber} /></g>
      <rect x={-140} y={-140} width={280} height={9} fill="#FFFFFF44" opacity={on} /><rect x={-140} y={-140} width={280 * P01(0.2, 2.6, a)} height={9} fill="#FFFFFF" opacity={on} /></g>;
  },
  stage: ({a, ao}) => {
    const on = P01(0, 0.35, a), blink = a > 0 && Math.floor(a * 3) % 2 === 0;
    return <g><path d="M-30 -600 L30 -600 L230 -55 L-230 -55 Z" fill={C.amber} opacity={on * 0.28} /><rect x={-250} y={-55} width={500} height={55} fill={C.dark2} {...L} />
      <line x1={0} y1={-55} x2={0} y2={-250} {...L} /><rect x={-22} y={-315} width={44} height={75} rx={22} fill={C.amber} />
      <g opacity={on}><rect x={-150} y={-440} width={300} height={68} rx={34} fill={blink ? C.red : '#7A1E24'} /><circle cx={-116} cy={-406} r={11} fill="#FFFFFF" /><text x={20} y={-391} textAnchor="middle" fontSize={44} fontWeight={900} fontFamily={T.fonte} fill="#FFFFFF">{ao}</text></g></g>;
  },
  calendar: ({a}) => {
    const dia = a < 0 ? 1 : Math.min(15, 1 + Math.floor(a / 0.075)), folha = a >= 0 && a < 1.05 ? Math.abs(Math.cos(a * Math.PI / 0.075)) : 1, feito = P01(1.05, 1.4, a);
    return <g><rect x={-135} y={-320} width={270} height={320} rx={18} fill={C.dark2} {...L} /><rect x={-135} y={-320} width={270} height={75} rx={18} fill={C.amber} />{[-70, 70].map(x => <rect key={x} x={x - 8} y={-345} width={16} height={50} rx={8} fill="#FFFFFF" />)}
      <g transform={`translate(0 -125) scale(1 ${folha})`}><text textAnchor="middle" y={45} fontSize={130} fontWeight={900} fontFamily={T.fonte} fill="#FFFFFF">{dia}</text></g>
      <circle cx={0} cy={-125} r={92} fill="none" stroke={C.amber} strokeWidth={10} strokeDasharray={578} strokeDashoffset={578 * (1 - feito)} /></g>;
  },
  clock: ({a}) => {
    const rot = a > 0 ? Math.min(a, 1.3) * 900 : 0, sh = a > 0 && a < 1.3 ? Math.sin(a * 70) * 4 : 0;
    return <g transform={`translate(${sh} 0)`}><line x1={-80} y1={-30} x2={-105} y2={0} {...L} /><line x1={80} y1={-30} x2={105} y2={0} {...L} /><circle cx={0} cy={-165} r={140} fill={C.dark2} {...L} />{Array.from({length: 12}).map((_, i) => <rect key={i} x={-4} y={-290} width={8} height={22} fill="#FFFFFF" transform={`rotate(${i * 30} 0 -165)`} />)}
      <line x1={0} y1={-165} x2={0} y2={-260} stroke={C.amber} strokeWidth={10} strokeLinecap="round" transform={`rotate(${rot} 0 -165)`} /><line x1={0} y1={-165} x2={60} y2={-165} stroke="#FFFFFF" strokeWidth={10} strokeLinecap="round" transform={`rotate(${rot / 12} 0 -165)`} /><circle cx={0} cy={-165} r={13} fill={C.amber} /></g>;
  },
  cart: ({a}) => <g><path d="M-205 -285 L-160 -285 L-110 -80 L150 -80 L190 -235 L-145 -235" fill={C.dark2} {...L} /><circle cx={-85} cy={-38} r={32} fill={C.dark2} {...L} /><circle cx={125} cy={-38} r={32} fill={C.dark2} {...L} />
    {[0, 1, 2].map(i => { const q = volta((a - i * 0.25) / 0.45); if (a - i * 0.25 < 0) return null; const x = -80 + i * 90; return <rect key={i} x={x - 36} y={-175 - (i === 1 ? 28 : 0) - (1 - q) * 460} width={72} height={80} rx={6} fill={C.amber} stroke="#FFFFFF" strokeWidth={4} />; })}
    {a >= 0.95 && <g transform={`translate(195 -335) scale(${volta((a - 0.95) / 0.3)})`}><circle r={62} fill="#50DC78" /><path d="M-30 2 L-8 26 L32 -24" fill="none" stroke="#FFFFFF" strokeWidth={13} strokeLinecap="round" strokeLinejoin="round" /></g>}</g>,
  key: ({a}) => {
    const entra = P01(0, 0.45, a), gira = P01(0.45, 0.8, a), abre = P01(0.8, 1.15, a);
    return <g><path d="M-85 -205 L-85 -275 Q-85 -365 0 -365 Q85 -365 85 -275 L85 -205" fill="none" stroke="#FFFFFF" strokeWidth={24} strokeLinecap="round" transform={`translate(0 ${-abre * 62}) rotate(${abre * 18} -85 -205)`} /><rect x={-135} y={-215} width={270} height={215} rx={26} fill={C.dark2} {...L} /><circle cx={0} cy={-120} r={26} fill={C.amber} /><rect x={-10} y={-120} width={20} height={58} fill={C.amber} />
      {a >= 0 && <g transform={`translate(${-330 + entra * 330} -120) rotate(${gira * 90})`} opacity={P01(1.4, 1.15, a)}><circle cx={-125} cy={0} r={42} fill="none" stroke={C.amber} strokeWidth={15} /><rect x={-88} y={-8} width={88} height={16} fill={C.amber} /><rect x={-34} y={0} width={13} height={28} fill={C.amber} /></g>}</g>;
  },
  stairs: ({a}) => <g>{[0, 1, 2].map(i => { const on = a >= i * 0.4; return <rect key={i} x={-170 + i * 110} y={-(i + 1) * 60} width={110} height={(i + 1) * 60} fill={on ? C.amber : C.dark2} {...L} />; })}</g>,
  heart: ({a, s}) => {
    const b = a > 0 && a < 1 ? 1 + Math.abs(Math.sin(a * Math.PI * 2)) * 0.2 : 1, h = 'M0 -30 C-60 -130 -200 -80 -170 30 C-150 110 -50 165 0 215 C50 165 150 110 170 30 C200 -80 60 -130 0 -30 Z';
    return <g transform="translate(0 -220)"><g transform={`scale(${b})`}><path d={h} fill={a >= 0 ? C.red : C.dark2} {...L} /></g>{a > 0 && Array.from({length: 6}).map((_, i) => { const q = P01(0.2 + i * 0.12, 1.3 + i * 0.12, a); if (!q || q >= 1) return null; const x = (random(`${s}-${i}`) - 0.5) * 340; return <path key={i} d={h} fill={C.red} opacity={1 - q} transform={`translate(${x} ${-120 - q * 300}) scale(0.16)`} />; })}</g>;
  },
  trophy: ({a, s}) => {
    const q = volta(a / 0.5);
    return <g><g transform={`translate(0 ${a < 0 ? 0 : (1 - q) * 300})`}><rect x={-90} y={-55} width={180} height={55} fill={C.dark2} {...L} /><rect x={-20} y={-125} width={40} height={75} fill={C.amber} /><path d="M-105 -340 L105 -340 Q100 -180 0 -125 Q-100 -180 -105 -340 Z" fill={C.amber} stroke="#FFFFFF" strokeWidth={5} /><path d="M-105 -310 Q-180 -310 -160 -240 Q-145 -200 -85 -205 M105 -310 Q180 -310 160 -240 Q145 -200 85 -205" fill="none" {...L} /></g><Particulas a={a} seed={s} n={40} conf /></g>;
  },
  phone: ({a}) => {
    const v = a > 0 && a < 1.2 ? Math.sin(a * 95) * 6 : 0, b = volta((a - 0.45) / 0.3);
    return <g><g transform={`translate(${v} 0) rotate(${v / 2} 0 -200)`}><rect x={-88} y={-345} width={176} height={345} rx={28} fill={C.dark2} {...L} /><rect x={-72} y={-310} width={144} height={260} rx={6} fill={a >= 0 ? '#1D3F86' : '#05060A'} /><circle cx={0} cy={-28} r={11} fill="#FFFFFF" /></g>
      {a > 0 && [0, 1, 2].map(i => { const q = ((a + i * 0.3) % 0.9) / 0.9; return <path key={i} d={`M${112 + q * 70} -260 Q${150 + q * 80} -190 ${112 + q * 70} -120`} fill="none" stroke={C.amber} strokeWidth={8} strokeLinecap="round" opacity={(1 - q) * P01(1.8, 1.2, a)} />; })}
      {a >= 0.45 && <g transform={`translate(-30 -440) scale(${b})`}><rect x={-125} y={-68} width={250} height={136} rx={38} fill={C.amber} /><path d="M50 60 L92 118 L6 66 Z" fill={C.amber} />{[-55, 0, 55].map(x => <circle key={x} cx={x} r={15} fill={C.dark} />)}</g>}</g>;
  },
  house: ({a}) => {
    const on = P01(0, 0.4, a), t0 = P01(0.3, 1.2, a);
    return <g><path d="M-210 -180 L-10 -345 L190 -180" fill="none" {...L} /><rect x={-165} y={-185} width={310} height={185} fill={C.dark2} {...L} /><rect x={-120} y={-150} width={85} height={85} fill={C.amber} opacity={0.14 + on * 0.86} stroke="#FFFFFF" strokeWidth={4} /><rect x={25} y={-125} width={75} height={125} fill="#FFFFFF22" stroke="#FFFFFF" strokeWidth={4} />
      <g transform="translate(240 0)"><rect x={-18} y={-300} width={36} height={245} rx={18} fill={C.dark2} {...L} /><circle cy={-45} r={36} fill={C.red} {...L} /><rect x={-9} y={-70 - 200 * t0} width={18} height={40 + 200 * t0} fill={C.red} /></g></g>;
  },
};

// Boneco desenhado por código: ângulos em graus, 0 = apontando para baixo, positivo = para frente.
const ponto = (o: number[], a: number, l: number) => [o[0] + Math.sin(a * Math.PI / 180) * l, o[1] + Math.cos(a * Math.PI / 180) * l];
const Boneco: React.FC<{x: number; y: number; l: Linha; t: number}> = ({x, y, l, t}) => {
  const acao = acaoEm(l, t), phi = x * 2 * Math.PI / 260;
  let coxaE = 0, coxaD = 0, canelaE = 0, canelaD = 0, ombroE = -8, ombroD = 8, cotoveloE = -4, cotoveloD = 4, sobe = 0, cabeca = 0;
  const sopro = Math.sin(t * 2 * Math.PI / 1.6) * 3;
  ombroE -= sopro; ombroD += sopro;
  if (acao === 'andar') {
    coxaD = 28 * Math.sin(phi); coxaE = 28 * Math.sin(phi + Math.PI);
    canelaD = coxaD - Math.max(0, 35 * Math.sin(phi + Math.PI / 2)); canelaE = coxaE - Math.max(0, 35 * Math.sin(phi + Math.PI + Math.PI / 2));
    ombroD = 22 * Math.sin(phi + Math.PI); ombroE = 22 * Math.sin(phi); cotoveloD = ombroD + 14; cotoveloE = ombroE + 14;
    sobe = 6 * Math.abs(Math.sin(phi));
  } else {
    canelaE = coxaE = -4; canelaD = coxaD = 4;
    const ult = l.ats.filter(a => t >= a).pop();
    if (acao === 'apontar') { const q = P01(0, 0.25, t - Math.max(ult ?? 0, l.segs[l.ats.filter(a => t >= a).length]?.fim ?? 0)); ombroD = 8 + q * 92; cotoveloD = ombroD; }
    if (acao === 'surpresa') { ombroD = 132; ombroE = -132; cotoveloD = 150; cotoveloE = -150; cabeca = 8; }
    if (acao === 'comemorar') {
      const c = t - l.ats[l.ats.length - 1], k = P01(0, 0.2, c), bal = Math.sin(t * 7) * 5;
      ombroD = 8 + k * 142 + bal; ombroE = -8 - k * 142 + bal; cotoveloD = ombroD + 8; cotoveloE = ombroE - 8;
      const q = (c % 0.4) / 0.4; sobe = c < 0.8 ? 40 * 4 * q * (1 - q) : 0;
    }
  }
  const cintura = [0, 0], perna = (a1: number, a2: number) => { const j = ponto(cintura, a1, 65); return [j, ponto(j, a2, 62)]; };
  const [jE, pE] = perna(coxaE, canelaE), [jD, pD] = perna(coxaD, canelaD);
  const altura = Math.max(pE[1], pD[1]), ombro = [0, -110], respira = 1 + Math.sin(t * 2 * Math.PI / 1.6) * 0.015;
  const braco = (a1: number, a2: number) => { const j = ponto(ombro, a1, 55); return [j, ponto(j, a2, 50)]; };
  const [cE, mE] = braco(ombroE, cotoveloE), [cD, mD] = braco(ombroD, cotoveloD);
  const pis = random(`pisca-${Math.floor(t / 3)}`) * 2.6, piscando = (t % 3) > pis && (t % 3) < pis + 0.12;
  const linha = (pts: number[][], w: number) => <polyline points={pts.map(q => q.join(',')).join(' ')} fill="none" stroke="#FFFFFF" strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />;
  return <g transform={`translate(${x} ${PISO + y})`} opacity={P01(-0.1, 0.1, t + 0.1)}>
    <ellipse cx={0} cy={2} rx={72 * (1 - sobe / 110)} ry={15 * (1 - sobe / 110)} fill="#000000" opacity={0.42} />
    <g transform={`scale(1.18) translate(0 ${-altura - sobe})`}>
      {linha([cintura, jE, pE], 11)}{linha([ombro, cE, mE], 10)}
      <g transform={`scale(1 ${respira})`}><line x1={0} y1={0} x2={0} y2={-110} stroke="#FFFFFF" strokeWidth={12} strokeLinecap="round" /></g>
      {linha([cintura, jD, pD], 11)}{linha([ombro, cD, mD], 10)}
      <path d="M-20 -116 L20 -116 L6 -84 Z" fill={C.amber} />
      <g transform={`translate(0 ${-148 - cabeca})`}><circle r={34} fill="#FFFFFF" stroke={C.dark} strokeWidth={4} />{!piscando && <><circle cx={5} cy={-5} r={4.5} fill={C.dark} /><circle cx={21} cy={-5} r={4.5} fill={C.dark} /></>}</g>
    </g>
  </g>;
};

const Cartao: React.FC<{cx: number; n: number; texto: string; a: number; visto: boolean}> = ({cx, n, texto, a, visto}) => {
  if (a < 0) return null;
  const q = volta(a / 0.3), k = 0.6 + 0.4 * q, s = visto ? 0.7 : k, up = texto.toUpperCase(), tam = up.length > 26 ? 42 : 52;
  return <foreignObject x={cx - 430} y={TETO + 28} width={860} height={230}>
    <div style={{display: 'flex', justifyContent: 'center', transform: `scale(${s}) rotate(${visto ? 0 : (1 - q) * -3}deg)`, transformOrigin: '50% 0%'}}>
      <div style={{position: 'relative', maxWidth: 760, background: visto ? '#FFFFFF' : C.amber, color: '#0C0C10', fontFamily: T.fonte, fontWeight: 900, fontSize: tam, lineHeight: 1.08, padding: '24px 40px 24px 74px', borderRadius: 28, textAlign: 'center', boxShadow: '0 16px 30px -12px #000C'}}>
        <div style={{position: 'absolute', left: 16, top: '50%', width: 48, height: 48, marginTop: -24, borderRadius: 24, background: '#0C0C10', color: '#FFFFFF', fontSize: 28, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{n}</div>{up}
      </div>
    </div>
  </foreignObject>;
};

const Cadeado: React.FC<{cx: number; i: number; f: number; fps: number}> = ({cx, i, f, fps}) => {
  const s = 1 + 0.04 + 0.04 * Math.sin(f / fps * 2 * Math.PI / 1.2);
  return <g transform={`translate(${cx} ${TETO + 350}) scale(${s})`}>{i % 2
    ? <text textAnchor="middle" y={62} fontSize={190} fontWeight={900} fontFamily={T.fonte} fill={C.amber}>?</text>
    : <><path d="M-46 -8 L-46 -46 Q-46 -92 0 -92 Q46 -92 46 -46 L46 -8" fill="none" stroke={C.amber} strokeWidth={15} /><rect x={-70} y={-12} width={140} height={106} rx={16} fill={C.amber} /><circle cy={34} r={15} fill={C.dark} /></>}</g>;
};

export const Jornada: React.FC<{p: Params; dur: number; fala?: {words: Palavra[]; inicio: number; idioma?: string}}> = ({p, dur, fala}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const etapas = lerEtapas(p), n = etapas.length, inicio = fala?.inicio ?? 0;
  const segundos = Math.max(1, (dur - inicio) / fps), t = (f - inicio) / fps;
  const ats = tempos(etapas.map(e => e.label), fala?.words ?? [], segundos);
  const l = linhaDoTempo(ats, segundos);
  const titulo = one(p, 'titulo', ''), ao = fala?.idioma === 'pt' ? 'AO VIVO' : 'LIVE';
  const largura = 2 * VARANDA + n * LARG;

  // O boneco sobe a escada no lugar e devolve o deslocamento quando volta a andar.
  let x = posEm(l, t), y = 0;
  ats.forEach((at, i) => {
    if (etapas[i].obj !== 'stairs' || t < at) return;
    const s = l.segs[i + 1], volta01 = s ? P01(s.ini, s.fim, t) : 0, q = P01(0, 1.2, t - at);
    x += q * 438 * (1 - volta01);
    y -= q * 220 * (s ? 1 - P01(s.ini, s.ini + 0.35, t) : 1);
  });
  const camX = cameraEm(l, t, TELA) - TELA / 2;
  const pop = 0.92 + 0.08 * spring({frame: f, fps, config: {damping: 11, stiffness: 180}});
  const zoom = 1 + 0.12 * P01(0, 0.6, t - ats[n - 1]);
  const cx = x - camX, cy = PISO - 240;

  return <div style={{position: 'absolute', top: 590, left: 30, width: TELA, height: ALTURA, background: C.dark, borderRadius: T.raio, overflow: 'hidden', boxShadow: T.sombra, border: `2px solid ${C.line}`, opacity: interpolate(f, [dur - 8, dur], [1, 0], clamp)}}>
    <svg viewBox={`0 0 ${TELA} ${ALTURA}`} width={TELA} height={ALTURA} style={{display: 'block'}}>
      <defs>
        <pattern id="jr-listra" width={46} height={46} patternUnits="userSpaceOnUse"><rect width={18} height={46} fill="#FFFFFF" opacity={0.05} /></pattern>
        <pattern id="jr-ponto" width={52} height={52} patternUnits="userSpaceOnUse"><circle cx={26} cy={26} r={6} fill="#FFFFFF" opacity={0.07} /></pattern>
      </defs>
      <g transform={`translate(${TELA / 2} ${ALTURA / 2}) scale(${pop}) translate(${-TELA / 2} ${-ALTURA / 2})`}>
        <g transform={`translate(${cx} ${cy}) scale(${zoom}) translate(${-cx} ${-cy})`}>
          <g transform={`translate(${-camX} 0)`}>
            <rect x={-200} y={PISO} width={largura + 400} height={46} fill="#FFFFFF" opacity={0.07} />
            <line x1={-200} y1={PISO} x2={largura + 200} y2={PISO} stroke="#FFFFFF" strokeWidth={6} />
            {etapas.map((e, i) => {
              const rx = VARANDA + i * LARG, c = centroComodo(i), a = t - ats[i];
              const ativo = a >= 0 && (i === n - 1 || t < ats[i + 1]), visto = a >= 0 && !ativo, luz = P01(0, 0.35, a), Ob = OBJ[e.obj] ?? OBJ.door;
              const balanco = a < 0 ? Math.sin(f / 11 + i) * 2 : 0, h = PISO - TETO;
              return <g key={i}>
                <path d={`M${rx} ${TETO} L${c} ${TOPO} L${rx + LARG} ${TETO} Z`} fill="#FFFFFF" fillOpacity={0.05} stroke="#FFFFFF" strokeWidth={6} strokeLinejoin="round" />
                <rect x={rx} y={TETO} width={LARG} height={h} fill="#FFFFFF" fillOpacity={0.025} />
                {i % 3 !== 2 && <rect x={rx} y={TETO} width={LARG} height={h} fill={`url(#jr-${i % 3 ? 'ponto' : 'listra'})`} />}
                {luz > 0 && <><path d={`M${c - 34} ${TETO} L${c + 34} ${TETO} L${c + 330} ${PISO} L${c - 330} ${PISO} Z`} fill={C.amber} opacity={luz * 0.15} /><rect x={c - 42} y={TETO} width={84} height={16} rx={8} fill={C.amber} opacity={luz} /></>}
                <g transform={`translate(${c + DX_OBJ} ${PISO + balanco}) scale(1.22)`}><Ob a={a} s={`jr-${i}`} ao={ao} /></g>
                {luz < 1 && <rect x={rx} y={TETO} width={LARG} height={h} fill="#000000" opacity={(1 - luz) * 0.52} />}
                {a < 0 && <Cadeado cx={c} i={i} f={f} fps={fps} />}
              </g>;
            })}
            {etapas.map((_, i) => {
              const rx = VARANDA + i * LARG, a = t - ats[i], ativo = a >= 0 && (i === n - 1 || t < ats[i + 1]), visto = a >= 0 && !ativo;
              return <g key={i}>
                <path d={`M${rx} ${PISO - 350} L${rx} ${TETO} L${rx + LARG} ${TETO} L${rx + LARG} ${PISO - 350}`} fill="none" stroke={ativo ? C.amber : '#FFFFFF'} strokeWidth={ativo ? 8 : 5} />
                {visto && <g transform={`translate(${rx + LARG - 62} ${TETO + 58})`}><circle r={32} fill={C.amber} /><path d="M-15 1 L-4 13 L16 -12" fill="none" stroke={C.dark} strokeWidth={8} strokeLinecap="round" strokeLinejoin="round" /></g>}
              </g>;
            })}
            {etapas.map((e, i) => { const a = t - ats[i]; return <Cartao key={i} cx={centroComodo(i)} n={i + 1} texto={e.label} a={a} visto={a >= 0 && i < n - 1 && t >= ats[i + 1]} />; })}
            <Boneco x={x} y={y} l={l} t={t} />
          </g>
        </g>
      </g>
      <rect width={TELA} height={TOPO - 8} fill={C.dark} opacity={0.9} />
      <g>
        <line x1={TELA / 2 - (n - 1) * 70} y1={62} x2={TELA / 2 + (n - 1) * 70} y2={62} stroke="#FFFFFF" strokeOpacity={0.3} strokeWidth={6} />
        {etapas.map((_, i) => { const a = t - ats[i], on = a >= 0, s = on ? volta(a / 0.25) : 1; return <g key={i} transform={`translate(${TELA / 2 + (i - (n - 1) / 2) * 140} 62) scale(${s})`}><circle r={32} fill={on ? C.amber : C.dark2} stroke={on ? C.amber : '#FFFFFF88'} strokeWidth={5} /><text textAnchor="middle" y={13} fontSize={36} fontWeight={900} fontFamily={T.fonte} fill={on ? '#0C0C10' : '#FFFFFFAA'}>{i + 1}</text></g>; })}
        {titulo && <text x={TELA / 2} y={150} textAnchor="middle" fontSize={Math.min(46, 1500 / Math.max(1, titulo.length))} fontWeight={800} fontFamily={T.fonte} fill="#FFFFFF">{titulo}</text>}
      </g>
    </svg>
  </div>;
};
