export type Point = {x:number;y:number};
export type RasterSegment = {x1:number;y1:number;x2:number;y2:number;orientation:string;region_hint?:string};
export type BranchProposal = {id:string;x:number;y:number;routeLeg:number;segmentId:number;kind:"possible_branch_or_crossing";status:"requires_engineer_review"};
/** Intersections are hypotheses, never proof of connected piping. Coordinates are normalized. */
export function proposeBranchCrossings(route:Point[],segments:RasterSegment[],limit=60):BranchProposal[]{
 const results:BranchProposal[]=[];
 if(route.length<2)return results;
 const cross=(a:Point,b:Point)=>a.x*b.y-a.y*b.x;
 for(let leg=0;leg<route.length-1;leg++){
  const a=route[leg],b=route[leg+1],r={x:b.x-a.x,y:b.y-a.y};
  const routeLength=Math.hypot(r.x,r.y);
  if(routeLength<0.015)continue;
  const horizontal=Math.abs(r.x)>=Math.abs(r.y)*3;
  const vertical=Math.abs(r.y)>=Math.abs(r.x)*3;
  if(!horizontal&&!vertical)continue;
  for(let i=0;i<segments.length;i++){
   const s=segments[i];
   if(s.region_hint==="title_block_candidate" || (horizontal&&s.orientation!=="vertical") || (vertical&&s.orientation!=="horizontal"))continue;
   const c={x:s.x1,y:s.y1},d={x:s.x2,y:s.y2},v={x:d.x-c.x,y:d.y-c.y};
   const denom=cross(r,v);
   if(Math.abs(denom)<1e-9)continue;
   const delta={x:c.x-a.x,y:c.y-a.y};
   const t=cross(delta,v)/denom;
   const u=cross(delta,r)/denom;
   // Accept small endpoint/scan tolerances; never extrapolate beyond a full stroke.
   const extension=Math.min(0.015,0.006/routeLength);
   if(t<0.035||t>0.965||u < -extension||u > 1+extension)continue;
   const x=a.x+t*r.x,y=a.y+t*r.y;
   if(results.some(p=>Math.hypot(p.x-x,p.y-y)<0.012))continue;
   results.push({id:`leg-${leg}-segment-${i}`,x,y,routeLeg:leg+1,segmentId:i,kind:"possible_branch_or_crossing",status:"requires_engineer_review"});
   if(results.length>=limit)return results;
  }
 }
 return results;
}
