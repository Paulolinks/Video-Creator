// entrou: 2026-11-11
// campos: titulo, pergunta, erro, acerto
// rodizio: nao
import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, T, cells, clamp, colorOf, font, many, mono, one, tagColor} from '../theme';

// campos: titulo, pergunta, erro, acerto
// rodizio: nao
export default function Cena({p,dur,tema}) {
 const f=useCurrentFrame();
 const k=Math.min(1,f/Math.max(1,dur)*2);
 const s=Math.max(0,Math.min(1,(f/dur-.25)*2));
 return <AbsoluteFill style={{fontFamily:font,color:tema.ink}}>
   <div style={{position:'absolute',top:690,left:80,right:80,fontSize:49,fontWeight:800,textAlign:'center'}}>{one(p,'titulo')||'Uma decisao'}</div>
   <div style={{position:'absolute',top:830,left:160,width:760,padding:32,borderRadius:28,background:tema.card,border:'4px solid '+tema.blue,textAlign:'center',fontSize:36,transform:'scale('+(.8+.2*k)+')'}}>{one(p,'pergunta')}</div>
   <div style={{position:'absolute',top:1010,left:523,width:8,height:130,background:tema.line}}/>
   <div style={{position:'absolute',top:1125,left:275,width:530,height:8,background:tema.line,transform:'scaleX('+s+')'}}/>
   {[{x:80,c:tema.red,t:'✕',v:one(p,'erro')},{x:565,c:tema.green,t:'✓',v:one(p,'acerto')}].map((a,i)=><div key={i} style={{position:'absolute',top:1210,left:a.x,width:435,minHeight:170,padding:25,borderRadius:24,background:tema.card,border:'5px solid '+a.c,opacity:s,transform:'translateY('+((1-s)*60)+'px)',textAlign:'center',fontSize:29,fontWeight:700}}><span style={{fontSize:52,color:a.c}}>{a.t}</span><div>{a.v}</div></div>)}
 </AbsoluteFill>;
}
