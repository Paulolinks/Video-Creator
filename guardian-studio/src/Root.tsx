import React from 'react';
import {Composition} from 'remotion';
import {Video, Timeline} from './Video';

const exemplo: Timeline = {
  fps: 30, total: 150, music: null,
  lines: [{text: 'Preview: run gerar-video.bat to render a script.', hl: ['gerar-video.bat'], scene: 'frase', params: {}, start: 0, dur: 150, audio: null, words: []}],
};

export const Root: React.FC = () => (
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
);
