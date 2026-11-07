export type SymbolProposal={x:number;y:number;radius:number;kind:"instrument";score:number};
/** Experimental dark circular-outline finder. Proposals are never verified automatically. */
export function detectInstrumentCircles(image:ImageData,maxResults=80):SymbolProposal[]{
 const {width:w,height:h,data}=image;
 if(w<100||h<100)return [];
 const scale=Math.min(1,1100/Math.max(w,h));
 const sw=Math.max(1,Math.round(w*scale)),sh=Math.max(1,Math.round(h*scale));
 const dark=new Uint8Array(sw*sh);
 for(let y=0;y<sh;y++)for(let x=0;x<sw;x++){
  const ox=Math.min(w-1,Math.floor(x/scale)),oy=Math.min(h-1,Math.floor(y/scale)),i=(oy*w+ox)*4;
  dark[y*sw+x]=(data[i]*0.299+data[i+1]*0.587+data[i+2]*0.114)<125?1:0;
 }
 const proposals:SymbolProposal[]=[];
 const angles=Array.from({length:24},(_,i)=>i*Math.PI/12);
 const radii=[7,10,13,17,22,28].filter(r=>r<Math.min(sw,sh)/12);
 for(const radius of radii){
  const offsets=angles.map(a=>[Math.round(Math.cos(a)*radius),Math.round(Math.sin(a)*radius)]);
  const step=Math.max(3,Math.round(radius/3));
  for(let y=radius+2;y<sh-radius-2;y+=step)for(let x=radius+2;x<sw-radius-2;x+=step){
   let hits=0,quadrants=[0,0,0,0];
   for(let k=0;k<offsets.length;k++){
    const [dx,dy]=offsets[k];let found=false;
    for(let d=-1;d<=1&&!found;d++)if(dark[(y+dy+d)*sw+x+dx]===1)found=true;
    if(found){hits++;quadrants[Math.floor(k/6)]++;}
   }
   const score=hits/24;
   if(score<0.79||quadrants.some(v=>v<3))continue;
   // Avoid line crossings and filled blobs: center should be predominantly light.
   let centerDark=0;
   for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++)centerDark+=dark[(y+dy)*sw+x+dx];
   if(centerDark>14)continue;
   proposals.push({x:x/sw,y:y/sh,radius:radius/sw,kind:"instrument",score});
  }
 }
 proposals.sort((a,b)=>b.score-a.score);
 const kept:SymbolProposal[]=[];
 for(const p of proposals){
  if(kept.some(k=>Math.hypot((p.x-k.x)*sw,(p.y-k.y)*sh)<Math.max(p.radius,k.radius)*sw*0.9))continue;
  kept.push(p);if(kept.length>=maxResults)break;
 }
 return kept;
}
