/** Suggest a circle bounding box near an engineer-selected center; never auto-verify. */
export function suggestBubbleBox(image:ImageData,x:number,y:number):{width:number;height:number;score:number}|null{
 const {width:w,height:h,data}=image;
 const cx=Math.round(x*w),cy=Math.round(y*h);
 if(cx<0||cy<0||cx>=w||cy>=h)return null;
 const sample=(px:number,py:number)=>{
  if(px<0||py<0||px>=w||py>=h)return 255;
  const i=(py*w+px)*4;
  return .299*data[i]+.587*data[i+1]+.114*data[i+2];
 };
 const maxR=Math.min(Math.round(Math.min(w,h)*.065),100);
 const minR=Math.max(7,Math.round(Math.min(w,h)*.006));
 let best:{r:number;score:number}|null=null;
 for(let r=minR;r<=maxR;r+=2){
  let hits=0,inside=0,outside=0;
  const sectors=[0,0,0,0];
  for(let k=0;k<48;k++){
   const a=k*Math.PI/24,c=Math.cos(a),s=Math.sin(a);
   let found=false;
   for(let d=-2;d<=2;d++)if(sample(Math.round(cx+(r+d)*c),Math.round(cy+(r+d)*s))<145)found=true;
   if(found){hits++;sectors[Math.floor(k/12)]++;}
   if(sample(Math.round(cx+r*.7*c),Math.round(cy+r*.7*s))<145)inside++;
   if(sample(Math.round(cx+r*1.22*c),Math.round(cy+r*1.22*s))<145)outside++;
  }
  if(hits<39||sectors.some(v=>v<8)||outside>31)continue;
  const score=hits/48-.12*(outside/48)-.06*(inside/48);
  if(!best||score>best.score)best={r,score};
 }
 if(!best)return null;
 const pad=3;
 return {width:Math.min(1,2*(best.r+pad)/w),height:Math.min(1,2*(best.r+pad)/h),score:best.score};
}
