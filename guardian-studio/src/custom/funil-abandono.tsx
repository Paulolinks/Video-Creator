// entrou: 2026-11-11
// campos: titulo, motivo, recuperacao
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: titulo, motivo, recuperacao
// rodizio: nao
export default function Cena({p,dur,tema}) {
 const f=useCurrentFrame();
 const t=Math.min(1,f/Math.max(1,dur));
 const x=210+550*t;
 return <AbsoluteFill style={{fontFamily:font,color:tema.ink}}>
  <div style={{position:'absolute',top:680,left:80,right:80,textAlign:'center',fontSize:50,fontWeight:800}}>{one(p,'titulo')||'Abandono do funil'}</div>
  <div style={{position:'absolute',top:970,left:140,width:800,height:160,borderRadius:32,background:tema.card,border:'5px solid '+tema.red,textAlign:'center',paddingTop:38,fontSize:34}}>{one(p,'motivo')}</div>
  <div style={{position:'absolute',top:1200,left:150,width:780,height:12,borderRadius:8,background:tema.line}}/>
  <div style={{position:'absolute',top:1120,left:x,fontSize:75,color:tema.red,transform:'rotate('+(-18*t)+'deg)',opacity:1-.6*t}}>●</div>
  <div style={{position:'absolute',top:1380,left:120,width:840,padding:28,borderRadius:20,background:tema.card,border:'3px solid '+tema.green,fontSize:29,textAlign:'center',opacity:Math.max(0,(t-.45)*2)}}>{one(p,'recuperacao')}</div>
 </AbsoluteFill>;
}
