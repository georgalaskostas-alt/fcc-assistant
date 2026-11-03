import type { TraceSegment } from "./pidPipeTrace";
export type RoutePoint={x:number;y:number};
export type RouteAudit={sampleCount:number;matchedCount:number;coverage:number;matchedSegmentIds:number[];unmatched:RoutePoint[];warning:string};
function dist(p:RoutePoint,s:TraceSegment){
 const dx=s.x2-s.x1,dy=s.y2-s.y1,d=dx*dx+dy*dy;
 const t=d?Math.max(0,Math.min(1,((p.x-s.x1)*dx+(p.y-s.y1)*dy)/d)):0;
 return Math.hypot(p.x-s.x1-t*dx,p.y-s.y1-t*dy);
}
/** Compare an engineer-drawn route with detected visual segments.
 * Does not assert connectivity or assign line numbers to detected segments.
 */
export function auditGuidedRoute(points:RoutePoint[],segments:TraceSegment[],tolerance=0.006):RouteAudit{
 const ids=new Set<number>(),unmatched:RoutePoint[]=[];
 let sampleCount=0,matchedCount=0;
 for(let k=1;k<points.length;k++){
  const a=points[k-1],b=points[k],length=Math.hypot(b.x-a.x,b.y-a.y);
  const steps=Math.max(1,Math.ceil(length/0.004));
  for(let j=0;j<=steps;j++){
   if(k>1 && j===0)continue;
   const t=j/steps,p={x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t};
   sampleCount++;
   let nearest=-1,best=Infinity;
   for(let i=0;i<segments.length;i++){
    const s=segments[i];if(s.region_hint==="title_block_candidate")continue;
    const d=dist(p,s);if(d<best){best=d;nearest=i;}
   }
   if(best<=tolerance){matchedCount++;ids.add(nearest);}
   else if(unmatched.length<60)unmatched.push(p);
  }
 }
 return {sampleCount,matchedCount,coverage:sampleCount?matchedCount/sampleCount:0,
  matchedSegmentIds:[...ids].sort((a,b)=>a-b),unmatched,
  warning:"Coverage is proximity to detected raster geometry only. It does not prove line identity, physical connectivity or equipment endpoints."};
}

/** Independent evidence from the OCR preview itself, not the detected line segments.
 * A local 5x5 dark-pixel search tolerates small raster skew and antialiasing.
 * This is deliberately diagnostic, not automatic pipe connectivity.
 */
export function auditRouteRaster(points:RoutePoint[],raster:ImageData):{
 sampleCount:number;matchedCount:number;coverage:number;warning:string
}{
 const {width,height,data}=raster;
 let sampleCount=0,matchedCount=0;
 for(let k=1;k<points.length;k++){
  const a=points[k-1],b=points[k];
  const steps=Math.max(1,Math.ceil(Math.hypot((b.x-a.x)*width,(b.y-a.y)*height)/8));
  for(let j=0;j<=steps;j++){
   if(k>1&&j===0)continue;
   const t=j/steps,x=Math.round((a.x+(b.x-a.x)*t)*(width-1));
   const y=Math.round((a.y+(b.y-a.y)*t)*(height-1));
   sampleCount++;
   let hit=false;
   for(let dy=-3;dy<=3&&!hit;dy++)for(let dx=-3;dx<=3;dx++){
    const xx=x+dx,yy=y+dy;
    if(xx<0||yy<0||xx>=width||yy>=height)continue;
    const index=(yy*width+xx)*4;
    const gray=0.2126*data[index]+0.7152*data[index+1]+0.0722*data[index+2];
    if(gray<145){hit=true;break;}
   }
   if(hit)matchedCount++;
  }
 }
 return {sampleCount,matchedCount,coverage:sampleCount?matchedCount/sampleCount:0,
 warning:"Dark-pixel proximity only; text, arrows and crossing lines can cause false matches. Not verified piping connectivity."};
}
