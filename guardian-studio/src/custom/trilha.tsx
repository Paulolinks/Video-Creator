// entrou: 2026-11-11
// campos: titulo, casa, total, trilha, objeto, etapa, erro, acerto, virada, visao, final
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: titulo, casa, total, trilha, objeto, etapa, erro, acerto, virada, visao, final
// rodizio: nao
export default function Cena({p, dur, tema}) {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const T = (v, d) => { const x = parseFloat(v); return isNaN(x) ? d : x; };
  const up = (s) => String(s || '').toUpperCase();
  const casa = Math.max(1, Math.round(T(one(p, 'casa'), 1)));
  const lista = String(one(p, 'trilha') || '').split('|').map(s => s.trim().toUpperCase()).filter(Boolean);
  const total = Math.max(casa, Math.round(T(one(p, 'total'), lista.length || casa)));
  const objeto = up(one(p, 'objeto') || lista[casa - 1] || 'CASA');
  const objs = Array.from({length: total}, (_, i) => i === casa - 1 ? objeto : (lista[i] || ''));
  const etapa = one(p, 'etapa') || '';
  const erro = one(p, 'erro') || '';
  const acerto = one(p, 'acerto') || '';
  const titulo = one(p, 'titulo') || '';
  const geral = /geral/i.test(one(p, 'visao') || '');
  const fim = /^(sim|yes|s)$/i.test(String(one(p, 'final') || '').trim());
  const virada = Math.min(0.85, Math.max(0.15, T(one(p, 'virada'), erro ? 0.5 : 0.12)));
  const OURO = tema.amber, VERDE = tema.green, VERM = tema.red, INK = tema.ink, CARD = tema.card, LINHA = tema.line, MUTE = tema.mute;
  const ff = font;
  const sp = (from, damping = 14) => spring({frame: f - from, fps, config: {damping, mass: 0.7}});
  const L = (a, b, c, d, e) => interpolate(f, [a, b], [c, d], {...clamp, easing: e || Easing.inOut(Easing.cubic)});

  // ---------------------------------------------------------------- tempos (em quadros)
  const tViagem = casa > 1 && !geral && !fim ? 18 : 0;
  const tPuf = tViagem ? tViagem - 4 : 4;
  const tErro = erro ? Math.round(dur * 0.14) : -1;
  const tVirada = Math.round(dur * virada);
  const tEtapa = Math.round(tVirada + (dur - tVirada) * 0.45);

  // ---------------------------------------------------------------- câmera
  const cur = casa - 1;
  let cam = cur;
  if (tViagem) cam = L(0, tViagem, cur - 1, cur, Easing.inOut(Easing.cubic));
  const mapa = geral || fim;
  const cols = total <= 4 ? 2 : total <= 9 ? 3 : 4, rows = Math.ceil(total / cols);
  const cw = 980 / cols, ch = Math.min(300, 600 / rows), ms = Math.min(cw / 470, ch / 440);
  const M = (i) => { const r = Math.floor(i / cols), c = i % cols, cc = r % 2 ? cols - 1 - c : c;
    return {x: 50 + cw * cc + cw / 2, y: 860 + r * ch + ch * 0.62, s: ms}; };
  const P = (d) => {
    if (d <= 0) return {x: 540 + 640 * d, y: 1180 - 30 * d, s: 1};
    const s = Math.pow(0.6, d);
    return {x: 540 + 300 * Math.sin(d * 1.15) * Math.pow(s, 0.35), y: 1180 - 330 * (1 - s), s};
  };

  // ---------------------------------------------------------------- ícones (caixa 100x100)
  const icone = (o, c, k = 0) => {
    const st = {fill: 'none', stroke: c, strokeWidth: 7, strokeLinecap: 'round', strokeLinejoin: 'round'};
    const a = {fill: OURO, stroke: 'none'};
    switch (o) {
      case 'PORTA': return <g><rect x="28" y="10" width="44" height="82" rx="4" {...st}/><circle cx="62" cy="54" r="5" {...a}/></g>;
      case 'PRESENTE': return <g><rect x="16" y="44" width="68" height="48" rx="4" {...st}/><rect x="10" y={30 - 14 * k} width="80" height="16" rx="3" {...st}/><line x1="50" y1="30" x2="50" y2="92" stroke={OURO} strokeWidth="8"/><path d={`M50 ${28 - 14 * k} C40 ${10 - 14 * k} 26 ${18 - 14 * k} 50 ${28 - 14 * k} C74 ${18 - 14 * k} 60 ${10 - 14 * k} 50 ${28 - 14 * k}`} {...st} stroke={OURO}/></g>;
      case 'ENVELOPE': return <g><rect x="10" y="24" width="80" height="54" rx="5" {...st}/><path d="M12 28 L50 56 L88 28" {...st}/></g>;
      case 'TELA': return <g><rect x="8" y="14" width="84" height="58" rx="6" {...st}/><path d="M42 30 L62 43 L42 56 Z" {...a}/><line x1="34" y1="90" x2="66" y2="90" {...st}/><line x1="50" y1="72" x2="50" y2="90" {...st}/></g>;
      case 'PALCO': return <g><rect x="38" y="8" width="24" height="44" rx="12" {...st}/><path d="M28 40 C28 66 72 66 72 40" {...st}/><line x1="50" y1="62" x2="50" y2="92" {...st}/><circle cx="82" cy="18" r="7" fill={VERM}/></g>;
      case 'CALENDARIO': return <g><rect x="12" y="18" width="76" height="72" rx="6" {...st}/><line x1="12" y1="38" x2="88" y2="38" {...st}/><line x1="32" y1="8" x2="32" y2="26" {...st}/><line x1="68" y1="8" x2="68" y2="26" {...st}/><circle cx="62" cy="64" r="12" fill="none" stroke={OURO} strokeWidth="6"/></g>;
      case 'RELOGIO': return <g><circle cx="50" cy="52" r="40" {...st}/><line x1="50" y1="52" x2="50" y2="26" {...st}/><line x1="50" y1="52" x2={50 + 22 * Math.cos(k * 6)} y2={52 + 22 * Math.sin(k * 6)} stroke={OURO} strokeWidth="7" strokeLinecap="round"/></g>;
      case 'CARRINHO': return <g><path d="M6 18 L20 18 L30 64 L80 64 L90 32 L24 32" {...st}/><circle cx="36" cy="82" r="7" {...st}/><circle cx="74" cy="82" r="7" {...st}/><rect x="40" y={36 - 30 * (1 - k)} width="20" height="18" rx="3" {...a} opacity={k}/></g>;
      case 'CHAVE': return <g><circle cx="30" cy="50" r="20" {...st}/><line x1="50" y1="50" x2="92" y2="50" {...st}/><line x1="80" y1="50" x2="80" y2="66" {...st}/><line x1="68" y1="50" x2="68" y2="62" {...st}/><circle cx="30" cy="50" r="6" {...a}/></g>;
      case 'ESCADA': return <g><path d="M8 90 L8 72 L30 72 L30 52 L52 52 L52 32 L74 32 L74 12 L94 12" {...st}/><path d="M74 12 L94 12" stroke={OURO} strokeWidth="9" strokeLinecap="round"/></g>;
      case 'CORACAO': return <g><path d="M50 88 C10 60 6 30 26 18 C40 10 50 24 50 30 C50 24 60 10 74 18 C94 30 90 60 50 88 Z" {...st} fill={OURO} fillOpacity={0.25 + 0.5 * k}/></g>;
      case 'TROFEU': return <g><path d="M28 10 L72 10 L72 36 C72 56 28 56 28 36 Z" {...st} fill={OURO} fillOpacity="0.35"/><path d="M28 18 C10 18 12 42 30 44 M72 18 C90 18 88 42 70 44" {...st}/><line x1="50" y1="56" x2="50" y2="76" {...st}/><rect x="30" y="76" width="40" height="14" rx="3" {...st}/></g>;
      case 'TELEFONE': return <g><rect x="28" y="6" width="44" height="88" rx="9" {...st}/><line x1="44" y1="80" x2="56" y2="80" {...st}/><path d="M78 30 C88 40 88 56 78 66" {...st} stroke={OURO}/></g>;
      case 'MEGAFONE': return <g><path d="M14 40 L14 62 L30 62 L74 86 L74 16 L30 40 Z" {...st}/><path d="M84 36 C92 44 92 58 84 66" {...st} stroke={OURO}/><line x1="24" y1="62" x2="30" y2="84" {...st}/></g>;
      case 'PAGINA': return <g><path d="M20 8 L64 8 L82 26 L82 92 L20 92 Z" {...st}/><line x1="32" y1="40" x2="70" y2="40" {...st}/><line x1="32" y1="56" x2="70" y2="56" {...st}/><rect x="32" y="68" width="38" height="14" rx="4" {...a}/></g>;
      case 'ESTRELA': return <g>{[0, 1, 2].map(i => <path key={i} transform={`translate(${6 + i * 30} ${i === 1 ? 20 : 38}) scale(0.32)`} d="M50 4 L62 38 L98 38 L69 59 L80 94 L50 73 L20 94 L31 59 L2 38 L38 38 Z" fill={i < 1 + 2 * k ? OURO : 'none'} stroke={OURO} strokeWidth="14" strokeLinejoin="round"/>)}<line x1="22" y1="84" x2="78" y2="84" {...st}/></g>;
      case 'MAIS': return <g><circle cx="50" cy="50" r="38" {...st}/><line x1="50" y1="30" x2="50" y2="70" stroke={OURO} strokeWidth="9" strokeLinecap="round"/><line x1="30" y1="50" x2="70" y2="50" stroke={OURO} strokeWidth="9" strokeLinecap="round"/></g>;
      case 'CAIXA': return <g><path d="M14 30 L50 14 L86 30 L86 74 L50 90 L14 74 Z" {...st}/><path d="M14 30 L50 46 L86 30 M50 46 L50 90" {...st}/><path d="M32 22 L68 38" stroke={OURO} strokeWidth="7"/></g>;
      default: return <g><path d="M14 48 L50 16 L86 48 L86 90 L14 90 Z" {...st}/><rect x="40" y="62" width="20" height="28" {...a}/></g>;
    }
  };

  // ---------------------------------------------------------------- bonequinho
  const boneco = (x, y, s, ang, cor, extra = {}) => {
    const sw = Math.sin(ang) * 0.5, bob = Math.abs(Math.sin(ang)) * 4;
    const leg = (dir) => { const a = sw * dir; return `M0 -60 L${Math.sin(a) * 26} ${-60 + Math.cos(a) * 26} L${Math.sin(a * 1.4) * 44} ${-60 + Math.cos(a) * 26 + 32}`; };
    const arm = (dir) => extra.braco && dir === extra.braco ? `M0 -112 L${dir * 34} -136 L${dir * 62} -150` : `M0 -112 L${-Math.sin(sw * dir) * 26} -86 L${-Math.sin(sw * dir) * 34} -64`;
    return <g transform={`translate(${x} ${y - bob * s}) scale(${s * (extra.vira ? -1 : 1)} ${s})`} opacity={extra.op == null ? 1 : extra.op}>
      <ellipse cx="0" cy="2" rx="26" ry="6" fill="#000" opacity="0.18"/>
      <g fill="none" stroke={cor} strokeWidth="9" strokeLinecap="round" strokeLinejoin="round">
        <path d={leg(1)}/><path d={leg(-1)}/><line x1="0" y1="-60" x2="0" y2="-120"/><path d={arm(1)}/><path d={arm(-1)}/>
      </g>
      <circle cx="0" cy="-146" r="24" fill={CARD} stroke={cor} strokeWidth="8"/>
      {extra.gravata ? <path d="M0 -118 L-7 -102 L0 -88 L7 -102 Z" fill={OURO}/> : null}
      {extra.balao ? <g transform="translate(26 -200)"><circle cx="0" cy="0" r="22" fill={CARD} stroke={extra.balaoCor || INK} strokeWidth="4"/><text x="0" y="11" textAnchor="middle" fontFamily={ff} fontWeight="800" fontSize="32" fill={extra.balaoCor || INK}>{extra.balao}</text></g> : null}
    </g>;
  };

  // ---------------------------------------------------------------- casinha
  const casinha = (i, pos, estado, kPop) => {
    const w = 360, h = 250, s = pos.s * (estado === 'atual' ? 1 + 0.06 * kPop : 1);
    const cor = estado === 'feita' ? VERDE : estado === 'atual' ? OURO : LINHA;
    const op = mapa ? (estado === 'futura' ? 0.55 : 1) : estado === 'futura' ? 0.22 + 0.45 * pos.s : estado === 'feita' && !fim ? 0.75 : 1;
    const luz = estado === 'atual' ? L(tVirada, tVirada + 12, 0, 1) : estado === 'feita' ? 1 : 0;
    return <g key={i} transform={`translate(${pos.x} ${pos.y}) scale(${s})`} opacity={op}>
      <path d={`M${-w / 2 - 24} ${-h / 2} L0 ${-h / 2 - 140} L${w / 2 + 24} ${-h / 2} Z`} fill={CARD} stroke={cor} strokeWidth="10" strokeLinejoin="round"/>
      <rect x={-w / 2} y={-h / 2} width={w} height={h} rx="14" fill={CARD} stroke={cor} strokeWidth="10"/>
      {luz > 0 ? <rect x={-w / 2 + 10} y={-h / 2 + 10} width={w - 20} height={h - 20} rx="8" fill={OURO} opacity={0.18 * luz}/> : null}
      <g transform={`translate(${-60} ${-h / 2 + 30}) scale(1.2)`} opacity={estado === 'futura' ? 0.5 : 1}>{icone(objs[i], estado === 'futura' ? MUTE : INK, estado === 'atual' ? luz : 1)}</g>
      <circle cx={-w / 2 + 6} cy={-h / 2 - 8} r="30" fill={estado === 'futura' ? CARD : cor} stroke={cor} strokeWidth="6"/>
      <text x={-w / 2 + 6} y={-h / 2 + 4} textAnchor="middle" fontFamily={ff} fontWeight="800" fontSize="34" fill={estado === 'futura' ? MUTE : tema.bg}>{i + 1}</text>
      {estado === 'futura' && !(geral && false) ? <text x="0" y={-h / 2 - 40} textAnchor="middle" fontFamily={ff} fontWeight="800" fontSize="64" fill={OURO} opacity={0.75}>?</text> : null}
      {estado === 'feita' ? <g transform={`translate(${w / 2 - 6} ${-h / 2 - 8})`}><circle r="30" fill={VERDE}/><path d="M-13 0 L-3 11 L15 -11" fill="none" stroke="#fff" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round"/></g> : null}
    </g>;
  };

  // ---------------------------------------------------------------- estrada
  const pts = (arr) => arr.map((q, k) => `${k ? 'L' : 'M'}${q.x.toFixed(1)} ${(q.y + 150 * q.s).toFixed(1)}`).join(' ');
  const estrada = [];
  for (let d = -2.2; d <= total - 1 - cam + 0.01; d += 0.08) estrada.push(d);
  const nFeitas = fim ? interpolate(f, [20, 20 + total * 5], [0, total - 1], clamp) : 0;
  const mapaPts = Array.from({length: total}, (_, i) => M(i));
  const mapaFeito = [];
  if (fim) { const n = Math.floor(nFeitas), fr = nFeitas - n; for (let i = 0; i <= n; i++) mapaFeito.push(mapaPts[i]);
    if (n < total - 1) mapaFeito.push({x: mapaPts[n].x + (mapaPts[n + 1].x - mapaPts[n].x) * fr, y: mapaPts[n].y + (mapaPts[n + 1].y - mapaPts[n].y) * fr, s: ms}); }
  const caminho0 = estrada.map((d, k) => { const q = P(d); return `${k ? 'L' : 'M'}${q.x.toFixed(1)} ${(q.y + 150 * q.s).toFixed(1)}`; }).join(' ');
  const caminho = mapa ? pts(mapaPts) : caminho0;
  const feitoAte = geral ? -99 : fim ? total - 1 - cam : (cur - cam) - (1 - L(0, Math.max(tViagem, 1), 0, 1));
  const caminhoFeito = mapa ? (fim ? pts(mapaFeito) : '') : estrada.filter(d => d <= feitoAte).map((d, k) => { const q = P(d); return `${k ? 'L' : 'M'}${q.x.toFixed(1)} ${(q.y + 150 * q.s).toFixed(1)}`; }).join(' ');

  // ordem: longe -> perto
  const ordem = Array.from({length: total}, (_, i) => i).sort((a, b) => (b - cam) - (a - cam));
  const estadoDe = (i) => fim ? (f >= 20 + i * 5 ? 'feita' : 'futura') : geral ? 'futura' : i < cur ? 'feita' : i === cur ? 'atual' : 'futura';
  const kPop = sp(tPuf, 9);

  // ---------------------------------------------------------------- puf
  const puf = () => {
    const k = interpolate(f, [tPuf, tPuf + 16], [0, 1], clamp);
    if (k <= 0 || k >= 1 || geral) return null;
    const q = P(cur - cam);
    return <g opacity={1 - k}>{Array.from({length: 9}, (_, j) => {
      const a = (j / 9) * Math.PI * 2 + random('puf' + j) * 0.5;
      const r = 150 + 170 * Easing.out(Easing.cubic)(k);
      return <circle key={j} cx={q.x + Math.cos(a) * r} cy={q.y + Math.sin(a) * r * 0.6} r={34 * (1 - k * 0.5) + random('pr' + j) * 16} fill={INK} opacity={0.25}/>;
    })}</g>;
  };

  // ---------------------------------------------------------------- personagens da casa atual
  const chao = 1330;
  const pessoas = () => {
    if (geral || fim) return null;
    const out = [];
    const cores = [tema.blue, tema.orange, INK];
    for (let j = 0; j < 3; j++) {
      let x, op = 1, vira = false, balao = null, balaoCor = INK, ang = f * 0.45 + j;
      const alvo = 250 + j * 70;
      if (erro && f < tVirada) {
        const chega = L(tErro - 14 + j * 4, tErro + 10 + j * 4, -120 - j * 90, alvo, Easing.out(Easing.quad));
        const sai = L(tErro + 26 + j * 5, tVirada - 2, 0, 1, Easing.in(Easing.quad));
        x = chega - sai * (alvo + 220);
        vira = sai > 0.02;
        if (f > tErro + 12 && sai < 0.6) { balao = '?'; balaoCor = VERM; }
        if (Math.abs(x - alvo) < 2 && sai === 0) ang = 0;
      } else {
        const t0 = tVirada + 6 + j * 7;
        const ini = -140 - j * 90;
        x = L(t0, t0 + 22, ini, 540, Easing.inOut(Easing.quad));
        op = L(t0 + 18, t0 + 26, 1, 0);
        if (f > t0 + 26) continue;
        if (f < t0) ang = 0;
      }
      out.push(boneco(x, chao, 0.85, ang, cores[j], {vira, balao, balaoCor, op}));
    }
    const kA = casa > 1 ? 1 : sp(4, 12);
    out.push(boneco(930 + (1 - kA) * 200, chao, 1.0, 0, INK, {gravata: true, vira: true, braco: f > tVirada ? 1 : (erro && f > tErro ? 1 : 0)}));
    return out;
  };

  // ---------------------------------------------------------------- cartões erro / acerto / etapa
  const cartao = (txt, cor, simbolo, k, sai) => {
    if (!txt || k <= 0.001) return null;
    const x = 540 - sai * 1400;
    return <g transform={`translate(${x} 1455) scale(${0.6 + 0.4 * k})`} opacity={Math.min(1, k * 1.5)}>
      <rect x="-470" y="-62" width="940" height="124" rx="26" fill={CARD} stroke={cor} strokeWidth="7"/>
      <circle cx="-400" cy="0" r="38" fill={cor}/>
      {simbolo === 'x' ? <path d="M-414 -14 L-386 14 M-386 -14 L-414 14" stroke="#fff" strokeWidth="9" strokeLinecap="round"/> : <path d="M-416 0 L-404 13 L-382 -13" fill="none" stroke="#fff" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round"/>}
      <text x="-340" y="16" fontFamily={ff} fontWeight="800" fontSize={Math.min(46, 1450 / Math.max(1, txt.length))} fill={INK}>{txt}</text>
    </g>;
  };
  const kErro = erro && !geral && !fim ? sp(tErro + 10, 11) : 0;
  const saiErro = interpolate(f, [tVirada - 4, tVirada + 8], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  const kAcerto = !geral && !fim ? sp(tVirada + 2, 11) : 0;
  const kEtapa = !geral && !fim && etapa ? sp(tEtapa, 10) : 0;

  // ---------------------------------------------------------------- confete (final)
  const confete = () => {
    if (!fim) return null;
    return Array.from({length: 46}, (_, j) => {
      const t0 = 24 + total * 5 + random('c' + j) * 25;
      const k = (f - t0) / fps;
      if (k < 0) return null;
      const x = 540 + (random('x' + j) - 0.5) * 1000 + Math.sin(k * 3 + j) * 30;
      const y = 600 + k * (380 + random('v' + j) * 260);
      if (y > 1600) return null;
      const cs = [OURO, VERDE, tema.blue, tema.orange, VERM];
      return <rect key={j} x={x} y={y} width="16" height="26" rx="3" fill={cs[j % 5]} transform={`rotate(${k * 300 + j * 40} ${x + 8} ${y + 13})`}/>;
    });
  };

  // ---------------------------------------------------------------- cabeçalho (progresso)
  const feitas = fim ? total : geral ? 0 : cur;
  const cab = <g>
    <text x="540" y="700" textAnchor="middle" fontFamily={ff} fontWeight="800" fontSize="34" letterSpacing="4" fill={MUTE}>{geral ? up(titulo) : fim ? 'COMPLETO' : `CASA ${casa} DE ${total}`}</text>
    {Array.from({length: total}, (_, i) => {
      const gap = Math.min(64, 860 / total), x = 540 - ((total - 1) * gap) / 2 + i * gap;
      const on = i < feitas || (!geral && !fim && i === cur);
      const atual = !geral && !fim && i === cur;
      return <circle key={i} cx={x} cy="745" r={atual ? 13 + 3 * Math.sin(f * 0.25) : 10} fill={i < feitas ? VERDE : atual ? OURO : 'none'} stroke={on ? 'none' : LINHA} strokeWidth="4"/>;
    })}
  </g>;

  const tituloGeral = geral ? <g transform={`translate(540 1590) scale(${0.7 + 0.3 * sp(6, 10)})`}>
    <rect x="-460" y="-70" width="920" height="140" rx="30" fill={OURO}/>
    <text x="0" y="20" textAnchor="middle" fontFamily={ff} fontWeight="800" fontSize={Math.min(62, 1250 / Math.max(1, titulo.length))} fill={tema.bg}>{up(titulo)}</text>
  </g> : null;
  const final = fim ? <g transform={`translate(540 1590) scale(${0.6 + 0.4 * sp(24 + total * 5, 9)})`}>
    <rect x="-460" y="-74" width="920" height="148" rx="30" fill={VERDE}/>
    <text x="0" y="22" textAnchor="middle" fontFamily={ff} fontWeight="800" fontSize={Math.min(62, 1250 / Math.max(1, (etapa || titulo || 'Funil completo').length))} fill="#fff">{up(etapa || titulo || 'Funil completo')}</text>
  </g> : null;

  return <AbsoluteFill>
    <svg width="1080" height="1920" viewBox="0 0 1080 1920" style={{position: 'absolute', top: 0, left: 0}}>
      {cab}
      <path d={caminho} fill="none" stroke={LINHA} strokeWidth="26" strokeLinecap="round" strokeLinejoin="round" opacity="0.45" strokeDasharray="2 34"/>
      {caminhoFeito ? <path d={caminhoFeito} fill="none" stroke={OURO} strokeWidth="14" strokeLinecap="round" strokeLinejoin="round"/> : null}
      {ordem.map(i => { const q = mapa ? {...M(i), s: ms * (geral ? sp(4 + i * 4, 10) : 1)} : P(i - cam); if (q.x < -400 || q.x > 1480) return null; return casinha(i, q, estadoDe(i), i === cur ? kPop : 0); })}
      {puf()}
      {pessoas()}
      {cartao(erro, VERM, 'x', kErro, saiErro)}
      {cartao(acerto, VERDE, 'v', kAcerto, 0)}
      {kEtapa > 0.001 ? <g transform={`translate(540 1600) scale(${0.5 + 0.5 * kEtapa})`} opacity={Math.min(1, kEtapa * 1.4)}>
        <rect x="-420" y="-58" width="840" height="116" rx="58" fill={OURO}/>
        <text x="0" y="18" textAnchor="middle" fontFamily={ff} fontWeight="800" fontSize={Math.min(56, 1150 / Math.max(1, etapa.length))} fill={tema.bg}>{up(etapa)}</text>
      </g> : null}
      {tituloGeral}
      {confete()}
      {final}
    </svg>
  </AbsoluteFill>;
}
