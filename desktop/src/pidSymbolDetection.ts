export type SymbolProposal={x:number;y:number;radius:number;kind:"instrument";score:number};
/**
 * Instrument bubble proposal v2. Uses edge ring continuity, interior texture,
 * and exclusion of dotted-line patterns. Geometry alone never verifies a symbol.
 */
export function detectInstrumentCircles(image:ImageData,maxResults=80):SymbolProposal[]{
 const {width:w,height:h,data}=image;
 if(w<100||h<100)return [];
 const scale=Math.min(1,1200/Math.max(w,h));
 const sw=Math.max(1,Math.round(w*scale)),sh=Math.max(1,Math.round(h*scale));
 const gray=new Uint8Array(sw*sh);
 for(let y=0;y<sh;y++)for(let x=0;x<sw;x++){
  const ox=Math.min(w-1,Math.floor(x/scale)),oy=Math.min(h-1,Math.floor(y/scale)),i=(oy*w+ox)*4;
  gray[y*sw+x]=Math.round(data[i]*0.299+data[i+1]*0.587+data[i+2]*0.114);
 }
 // Local threshold helps with nonuniform illumination in photographed drawings.
 const dark=new Uint8Array(sw*sh);
 for(let y=0;y<sh;y++)for(let x=0;x<sw;x++){
  let sum=0,n=0;
  for(let dy=-7;dy<=7;dy+=3)for(let dx=-7;dx<=7;dx+=3){
   const xx=x+dx,yy=y+dy;if(xx>=0&&xx<sw&&yy>=0&&yy<sh){sum+=gray[yy*sw+xx];n++;}
  }
  dark[y*sw+x]=gray[y*sw+x]<Math.min(175,sum/n-17)?1:0;
 }
 const at=(x:number,y:number)=>x>=0&&y>=0&&x<sw&&y<sh?dark[y*sw+x]:0;
 const angles=Array.from({length:48},(_,i)=>i*Math.PI/24);
 const proposals:SymbolProposal[]=[];
 const radii=[9,12,15,19,24,30].filter(radius=>radius<Math.min(sw,sh)/14);
 for(const radius of radii){
  const step=Math.max(3,Math.round(radius/4));
  for(let y=radius+4;y<sh-radius-4;y+=step)for(let x=radius+4;x<sw-radius-4;x+=step){
   const ring:number[]=[];
   let inner=0,outer=0;
   for(let k=0;k<48;k++){
    const a=angles[k],cx=Math.cos(a),cy=Math.sin(a);
    const hit=[-2,-1,0,1,2].some(d=>at(Math.round(x+(radius+d)*cx),Math.round(y+(radius+d)*cy))===1);
    ring.push(hit?1:0);
    inner+=at(Math.round(x+radius*.62*cx),Math.round(y+radius*.62*cy));
    outer+=at(Math.round(x+radius*1.28*cx),Math.round(y+radius*1.28*cy));
   }
   const hits=ring.reduce((a,b)=>a+b,0);
   if(hits<38)continue;
   if([0,12,24,36].some(start=>ring.slice(start,start+12).reduce((a,b)=>a+b,0)<8))continue;
   // Long missing arcs and mostly blank interiors indicate fragments/line dots.
   let longestGap=0,gap=0;
   for(let k=0;k<96;k++){gap=ring[k%48]===0?gap+1:0;longestGap=Math.max(longestGap,gap);}
   if(longestGap>6||inner<2||inner>30||outer>29)continue;
   // Reject dense or empty centers; actual bubbles typically contain lettering.
   let center=0;
   for(let dy=-Math.floor(radius*.35);dy<=radius*.35;dy+=2)
    for(let dx=-Math.floor(radius*.35);dx<=radius*.35;dx+=2)center+=at(x+dx,y+dy);
   if(center<2)continue;
   const score=(hits/48)*.7+(1-Math.abs(inner-12)/48)*.2+(1-outer/48)*.1;
   proposals.push({x:x/sw,y:y/sh,radius:radius/sw,kind:"instrument",score:Math.min(1,score)});
  }
 }
 proposals.sort((a,b)=>b.score-a.score);
 const kept:SymbolProposal[]=[];
 for(const p of proposals){
  if(kept.some(k=>Math.hypot((p.x-k.x)*sw,(p.y-k.y)*sh)<Math.max(p.radius,k.radius)*sw*1.4))continue;
  kept.push(p);if(kept.length>=maxResults)break;
 }
 return kept;
}
