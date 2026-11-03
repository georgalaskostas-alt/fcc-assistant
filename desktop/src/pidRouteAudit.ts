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
