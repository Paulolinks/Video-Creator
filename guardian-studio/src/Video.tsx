import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig, random, delayRender, continueRender} from 'remotion';
import {C, font, clamp, Params} from './theme';
import {SCENES} from './scenes';

export type Line = {text: string; hl: string[]; scene: string; params: Params; start: number; dur: number; audio: string | null; words: {w: string; t: number}[]};
export type Timeline = {fps: number; total: number; music: {file: string; volume: number} | null; logo?: string | null; lines: Line[]};

const FONTS: [string, string, string][] = [['Inter', 'Inter-Regular.otf', '400'], ['Inter', 'Inter-Medium.otf', '500'], ['Inter', 'Inter-SemiBold.otf', '600'], ['Inter', 'Inter-Bold.otf', '700'], ['Inter', 'Inter-ExtraBold.otf', '800'], ['Inter', 'Inter-Black.otf', '900'], ['DejaVuMono', 'DejaVuSansMono.ttf', '400'], ['DejaVuMono', 'DejaVuSansMono-Bold.ttf', '700']];
const useFonts = () => {
  const [h] = useState(() => delayRender('fonts'));
  useEffect(() => {
    Promise.all(FONTS.map(([fam, file, w]) => new FontFace(fam, `url(${staticFile('fonts/' + file)})`, {weight: w}).load().then(ff => (document.fonts as any).add(ff))))
      .then(() => continueRender(h)).catch(() => continueRender(h));
  }, [h]);
};

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9à-ú$%#]/g, '');

const Grid: React.FC = () => <AbsoluteFill style={{background: C.bg, backgroundImage: `linear-gradient(${C.grid} 2px, transparent 2px), linear-gradient(90deg, ${C.grid} 2px, transparent 2px)`, backgroundSize: '90px 90px'}} />;
const Floaters: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill>{Array.from({length: 14}).map((_, i) => {
    const x = random('fx' + i) * 1080, y0 = random('fy' + i) * 1920, sp = 0.3 + random('fs' + i) * 0.8, s = 14 + random('fz' + i) * 26;
    const y = ((y0 - f * sp) % 1920 + 1920) % 1920;
    return <div key={i} style={{position: 'absolute', left: x, top: y, width: s, height: s, background: i % 3 ? C.blue : C.blue2, opacity: 0.55, borderRadius: 3, transform: `rotate(${f * sp * 0.6}deg)`}} />;
  })}</AbsoluteFill>;
};

const Headline: React.FC<{tl: Timeline}> = ({tl}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const L = tl.lines;
  const line = L.find(l => f >= l.start && f < l.start + l.dur) ?? (f >= L[0].start ? L[L.length - 1] : null);
  if (!line) return null;
  const words = line.words.length ? line.words : line.text.split(' ').map((w, i, a) => ({w, t: (i / a.length) * (line.dur / fps) * 0.85}));
  const hl = new Set(line.hl.flatMap(h => h.split(/\s+/)).map(norm));
  const local = f - line.start;
  const size = words.length > 14 ? 68 : words.length > 11 ? 76 : words.length > 8 ? 86 : 98;
  return <div style={{position: 'absolute', top: 150, left: 60, right: 60, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', columnGap: size * 0.26, fontFamily: font, fontWeight: 800, fontSize: size, lineHeight: 1.04, letterSpacing: -size * 0.04}}>
    {words.map((w, i) => {
      const s = spring({frame: local - w.t * fps + 2, fps, config: {damping: 15, stiffness: 180}});
      return <span key={i} style={{color: hl.has(norm(w.w)) ? C.blue : C.ink, opacity: s, transform: `translateY(${(1 - s) * 30}px) scale(${0.9 + 0.1 * s})`, filter: `blur(${(1 - s) * 8}px)`, display: 'inline-block'}}>{w.w}</span>;
    })}
  </div>;
};

const Blocks: React.FC<{cuts: number[]}> = ({cuts}) => {
  const f = useCurrentFrame();
  const near = cuts.find(c => Math.abs(f - c) <= 9);
  if (near === undefined) return null;
  const t = f - near; const cols = 9, s = 120;
  return <AbsoluteFill style={{top: 600}}>{Array.from({length: cols * 9}).map((_, i) => {
    const r = random(`b${near}-${i}`);
    const inT = -9 + r * 7, outT = 2 + r * 7;
    const k = t < 0 ? interpolate(t, [inT, inT + 3], [0, 1], clamp) : interpolate(t, [outT, outT + 3], [1, 0], clamp);
    const col = r < 0.45 ? C.card : r < 0.8 ? C.blue2 : C.blue;
    return <div key={i} style={{position: 'absolute', left: (i % cols) * s, top: Math.floor(i / cols) * s, width: s - 4, height: s - 4, background: col, transform: `scale(${k})`, borderRadius: 4, boxShadow: '0 2px 6px #0001'}} />;
  })}</AbsoluteFill>;
};

export const Video: React.FC<{timeline: Timeline}> = ({timeline: tl}) => {
  useFonts();
  const f = useCurrentFrame();
  const L = tl.lines;
  return <AbsoluteFill style={{fontFamily: font}}>
    <Grid /><Floaters />
    {tl.music && <Audio src={staticFile(tl.music.file)} loop volume={(fr) => tl.music!.volume * interpolate(fr, [0, 15, tl.total - 30, tl.total], [0, 1, 1, 0], clamp)} />}
    {L.map((l, i) => {
      const S = SCENES[l.scene] ?? SCENES.frase;
      const from = i === 0 ? 0 : l.start;
      const end = L[i + 1] ? L[i + 1].start : tl.total;
      return <Sequence key={i} from={from} durationInFrames={Math.max(1, end - from)}>
        <S p={l.params} dur={end - from} />
        {l.audio && <Sequence from={l.start - from}><Audio src={staticFile(l.audio)} /></Sequence>}
      </Sequence>;
    })}
    <Headline tl={tl} />
    <Blocks cuts={L.slice(1).map(l => l.start)} />
    {tl.logo && <Img src={staticFile(tl.logo)} style={{position: 'absolute', top: 18, left: '50%', transform: 'translateX(-50%)', maxWidth: 460, maxHeight: 126, objectFit: 'contain', filter: 'drop-shadow(0 0 1px #0b1f40) drop-shadow(0 0 2px #0b1f40) drop-shadow(0 1px 3px #0b1f40aa)'}} />}
    <div style={{position: 'absolute', bottom: 0, left: 0, height: 10, width: `${(f / tl.total) * 100}%`, background: C.blue}} />
  </AbsoluteFill>;
};
