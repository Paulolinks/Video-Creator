// O tema "claro" é o visual original. Um render tem um tema só: Video e Capa chamam setTema() antes de desenhar,
// e todas as cenas (as antigas e as da biblioteca) leem as cores de C.
const BASE = {bg: '#EEF1F6', grid: '#DCE2EC', ink: '#0B0F19', blue: '#2F5BEA', blue2: '#8FA8F5', card: '#FFFFFF', line: '#E3E8F0', mute: '#7B8496', dark: '#0F1626', dark2: '#18213A', orange: '#F26B1D', green: '#18A957', red: '#E5484D', amber: '#F5A524', soft: '#F4F6FA', soft2: '#DDE3EE', solid: '#FFFFFF', onAccent: '#FFFFFF'};
const BASE_T = {fundo: 'grade', flut: 'quadrados', raio: 26, sombra: '0 30px 60px -20px #0B0F1930, 0 2px 0 #0B0F1908', barra: true, pulso: false, fonte: 'Inter, sans-serif', peso: 800, esp: -0.04};
type Pal = typeof BASE; type Vis = typeof BASE_T;

const TEMAS: Record<string, {c: Partial<Pal>; t: Partial<Vis>}> = {
  claro: {c: {}, t: {}},
  noite: {c: {bg: '#070B16', grid: '#1A2440', ink: '#FFFFFF', blue: '#3DD6F5', blue2: '#1E7FA3', card: '#FFFFFF10', line: '#3DD6F544', mute: '#93A4C4', dark: '#0C1426', dark2: '#1C2A48', green: '#2BE38B', orange: '#FF9A3D', red: '#FF5C6C', amber: '#FFC857', soft: '#FFFFFF12', soft2: '#FFFFFF1C', solid: '#121B31', onAccent: '#04121A'}, t: {fundo: 'pontos', flut: 'circulos', sombra: '0 0 50px #3DD6F522', fonte: 'Poppins, sans-serif', esp: -0.03}},
  blueprint: {c: {bg: '#0E3B8C', grid: '#FFFFFF2E', ink: '#FFFFFF', blue: '#FFD84D', blue2: '#7FA6E8', card: '#0E3B8C00', line: '#FFFFFFAA', mute: '#C5D6F5', dark: '#0A2C6B', dark2: '#2D5AAB', green: '#7CF2B0', orange: '#FFB24D', red: '#FF8A8A', amber: '#FFD84D', soft: '#FFFFFF14', soft2: '#FFFFFF26', solid: '#0A2C6B', onAccent: '#0A2C6B'}, t: {fundo: 'linhas', flut: 'cotas', raio: 0, sombra: 'none', barra: false, fonte: 'DejaVuMono, monospace', peso: 700, esp: -0.05}},
  papel: {c: {bg: '#F5EFE3', grid: '#E7DEC9', ink: '#1B1A17', blue: '#E8590C', blue2: '#F0A77C', card: '#FFFFFF', line: '#E5DCC8', mute: '#7D7566', dark: '#2A2620', dark2: '#433C31', green: '#2F8F4E', orange: '#C2410C', red: '#C92A2A', amber: '#C98A0B', soft: '#F8F3E8', soft2: '#E9E0CD', solid: '#FFFFFF'}, t: {fundo: 'ruido', flut: 'nenhum', raio: 6, sombra: '0 18px 30px -18px #3A301F66, 0 1px 0 #3A301F22', barra: false, fonte: 'Poppins, sans-serif', peso: 800, esp: -0.03}},
  terminal: {c: {bg: '#050806', grid: '#0F1D14', ink: '#D9FFE6', blue: '#22E37A', blue2: '#0F7A42', card: '#000000', line: '#22E37A66', mute: '#7FB896', dark: '#020402', dark2: '#123021', green: '#22E37A', orange: '#F2C14E', red: '#FF6B6B', amber: '#F2C14E', soft: '#0E1A12', soft2: '#17291D', solid: '#07100A', onAccent: '#02140A'}, t: {fundo: 'varredura', flut: 'caracteres', raio: 4, sombra: 'none', fonte: 'DejaVuMono, monospace', peso: 700, esp: -0.06}},
  ouro: {c: {bg: '#12121C', grid: '#1E1E2C', ink: '#FFFFFF', blue: '#FFD745', blue2: '#8A7326', card: '#FFFFFF10', line: '#FFD74544', mute: '#A7A7B8', dark: '#0C0C12', dark2: '#1E1E2A', green: '#50DC78', orange: '#FFB347', red: '#FF5C6C', amber: '#FFD745', soft: '#FFFFFF12', soft2: '#FFFFFF1C', solid: '#1A1A26', onAccent: '#12121C'}, t: {fundo: 'pontos', flut: 'circulos', sombra: '0 0 50px #FFD74522', fonte: 'Poppins, sans-serif', esp: -0.03}},
  alerta: {c: {bg: '#120A0A', grid: '#2A1616', ink: '#FFFFFF', blue: '#FF7A1A', blue2: '#8C3B0E', card: '#1E1212', line: '#FF7A1A88', mute: '#C9A9A0', dark: '#180C0C', dark2: '#3A1C1C', green: '#3DDC84', orange: '#FF7A1A', red: '#FF4D4D', amber: '#FFC247', soft: '#FFFFFF10', soft2: '#FFFFFF1E', solid: '#2A1616', onAccent: '#1A0B02'}, t: {fundo: 'gradiente', flut: 'sinais', raio: 14, sombra: '0 0 44px #FF7A1A22', pulso: true, fonte: 'Inter, sans-serif', peso: 900, esp: -0.04}},
};
export const NOMES_TEMAS = Object.keys(TEMAS);

export const C: Pal = {...BASE};
export const T: Vis = {...BASE_T};
export const setTema = (nome?: string) => {
  const tema = TEMAS[nome ?? 'claro'] ?? TEMAS.claro;
  Object.assign(C, BASE, tema.c); Object.assign(T, BASE_T, tema.t);
};
export const useTema = () => C;

export const font = 'Inter, sans-serif';
export const mono = 'DejaVuMono, monospace';
export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export type Params = Record<string, string | string[]>;
export const one = (p: Params, k: string, d = ''): string => { const v = p[k]; return v === undefined ? d : Array.isArray(v) ? v[0] : v; };
export const many = (p: Params, k: string): string[] => { const v = p[k]; return v === undefined ? [] : Array.isArray(v) ? v : [v]; };
export const cells = (s: string) => s.split('|').map(x => x.trim());
export const colorOf = (name: string, d: string) => ({azul: C.blue, blue: C.blue, laranja: C.orange, orange: C.orange, verde: C.green, green: C.green, vermelho: C.red, red: C.red, cinza: C.mute, gray: C.mute, amarelo: C.amber, yellow: C.amber} as Record<string, string>)[(name || '').toLowerCase()] ?? d;
const GOOD = ['yes', 'sim', 'ok', 'online', 'active', 'maybe', 'connected', 'renewed', 'normal', 'recording'];
export const tagColor = (v: string) => GOOD.includes(v.toLowerCase()) ? C.green : C.orange;
export const statusColor = (s: string) => ({ok: C.green, check: C.orange, off: C.mute, alerta: C.red} as Record<string, string>)[(s || '').toLowerCase()] ?? C.blue;
