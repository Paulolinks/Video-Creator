import React from 'react';
import {Composition, Still} from 'remotion';
import {CenaSolta, TesteCena, Video, Timeline} from './Video';
import {Capa} from './Capa';

const exemplo: Timeline = {
  fps: 30, total: 150, music: null,
  lines: [{text: 'Preview: run gerar-video.bat to render a script.', hl: ['gerar-video.bat'], scene: 'frase', params: {}, start: 0, dur: 150, audio: null, words: []}],
};

export const Root: React.FC = () => (<>
  <Composition
    id="Video"
    component={Video}
    fps={30}
    width={1080}
    height={1920}
    durationInFrames={150}
    defaultProps={{timeline: exemplo}}
    calculateMetadata={({props}) => ({durationInFrames: props.timeline.total})}
  />
  <Still id="Capa" component={Capa} width={1080} height={1920} defaultProps={{capa: {titulo: 'Preview', destaque: [], estilo: 'gigante'}, tema: 'claro'}} />
  <Composition id="CenaSolta" component={CenaSolta} fps={30} width={1080} height={1920} durationInFrames={90} defaultProps={{cena: 'frase', params: {}, words: [], inicio: 0, total: 90, tema: 'ouro', texto: 'baixo', idioma: 'pt'}} calculateMetadata={({props}) => ({durationInFrames: props.total})} />
  <Composition id="TesteCena" component={TesteCena} fps={30} width={1080} height={1920} durationInFrames={90} defaultProps={{cena: 'frase', p: {}}} />
</>);
