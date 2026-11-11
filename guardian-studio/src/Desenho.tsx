import React from 'react';
import {interpolate, useCurrentFrame, Easing} from 'remotion';
import {C, clamp} from './theme';

// Desenhos simples que se desenham sozinhos (viewBox 200x200).
export const DESENHOS: Record<string, string[]> = {
  seta: ['M20 150 C 60 60, 120 50, 170 70', 'M140 40 L172 70 L132 96'],
  circulo: ['M100 18 C 180 16, 188 150, 110 182 C 30 196, 6 96, 44 52 C 62 32, 92 22, 124 26'],
  sublinhado: ['M12 90 C 60 70, 130 110, 188 82', 'M28 124 C 80 106, 130 138, 172 116'],
  exclamacao: ['M100 22 L100 128', 'M100 166 L100 172'],
  relogio: ['M100 20 A 80 80 0 1 1 99.9 20', 'M100 58 L100 104 L134 124'],
  casa: ['M24 98 L100 30 L176 98', 'M46 82 L46 172 L154 172 L154 82', 'M86 172 L86 122 L114 122 L114 172'],
  telefone: ['M46 34 L76 26 L92 66 L72 80 C 82 108, 96 122, 122 132 L136 112 L176 128 L168 160 C 96 176, 32 110, 46 34', 'M128 32 C 150 38, 164 52, 170 74', 'M122 60 C 134 64, 142 72, 146 84'],
};

export const Desenho: React.FC<{tipo: string; tam?: number; inicio?: number; fim?: number; cor?: string}> = ({tipo, tam = 420, inicio = 6, fim = 40, cor}) => {
  const f = useCurrentFrame();
  const paths = DESENHOS[tipo] ?? DESENHOS.seta;
  const passo = (fim - inicio) / paths.length;
  return <svg viewBox="0 0 200 200" width={tam} height={tam} style={{overflow: 'visible'}}>
    {paths.map((d, i) => <path key={i} d={d} pathLength={1} fill="none" stroke={cor ?? C.blue} strokeWidth={9} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={1} strokeDashoffset={interpolate(f, [inicio + i * passo, inicio + (i + 1) * passo], [1, 0], {...clamp, easing: Easing.inOut(Easing.cubic)})} />)}
  </svg>;
};
