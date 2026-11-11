// entrou: 2026-11-11
// campos: titulo, etapa (repetir), cor
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: titulo, etapa (repetir), cor
// rodizio: nao
export default function Cena({p,dur,tema}) {
  const f=useCurrentFrame();
  const etapas=many(p,'etapa').slice(0,6);
  const n=Math.max(1,etapas.length);
  const atual=Math.min(n-1,Math.floor(f/Math.max(1,dur)*n));
  const cor=colorOf(one(p,'cor'),tema.blue);
  return <AbsoluteFill style={{background:'transparent',fontFamily:font,color:tema.ink}}>
    <div style={{position:'absolute',top:655,left:90,right:90,textAlign:'center',fontSize:48,fontWeight:800}}>{one(p,'titulo')||'O caminho do cliente'}</div>
    {etapas.map((e,i)=>{
      const x=110+i*(850/Math.max(1,n-1));
      const y=1370-i*95;
      const ativo=i<=atual;
      const brilho=ativo?cor:tema.mute;
      return <React.Fragment key={i}>
        {i>0&&<div style={{position:'absolute',left:x-120,top:y+115,width:125,height:10,background:ativo?cor:tema.line,transform:'rotate(-32deg)',borderRadius:8}}/>}
        <div style={{position:'absolute',left:x-60,top:y,width:150,height:92,borderRadius:20,background:ativo?brilho:tema.card,border:'4px solid '+(ativo?cor:tema.line),boxShadow:ativo?'0 0 35px '+cor:'none',transform:'skewY(-10deg)'}}/>
        <div style={{position:'absolute',left:x-75,top:y+100,width:180,textAlign:'center',fontSize:22,fontWeight:700,color:tema.ink}}>{e.split('|').pop().trim()}</div>
      </React.Fragment>;
    })}
    <div style={{position:'absolute',left:110+atual*(850/Math.max(1,n-1))-10,top:1280-atual*95,fontSize:64,transform:'translateY('+(-12*Math.sin(f/5))+'px)'}}>●</div>
  </AbsoluteFill>;
}
