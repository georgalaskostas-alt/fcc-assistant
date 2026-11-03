/** Conservative visual trace from an engineer-selected point.
 * A collinear endpoint continuation is only a proposal, never verified piping.
 * Turns and branches require explicit accepted endpoint review.
 */
export type TraceSegment = {x1:number;y1:number;x2:number;y2:number;orientation:string;region_hint?:string};
export type TraceJoin = {segment_a:number;segment_b:number;distance:number};
export type VisualTrace = {segments:number[];seedSegment:number|null;distance:number;warning:string};
const distance=(a:{x:number;y:number},b:{x:number;y:number})=>Math.hypot(a.x-b.x,a.y-b.y);
function pointDistance(p:{x:number;y:number},s:TraceSegment){
 const dx=s.x2-s.x1,dy=s.y2-s.y1,den=dx*dx+dy*dy;
 const t=den?Math.max(0,Math.min(1,((p.x-s.x1)*dx+(p.y-s.y1)*dy)/den)):0;
 return distance(p,{x:s.x1+t*dx,y:s.y1+t*dy});
}
export function traceVisualPipe(segments:TraceSegment[],point:{x:number;y:number},accepted:TraceJoin[],maxSeedDistance=0.012):VisualTrace {
 const eligible=segments.map((s,i)=>({s,i,d:pointDistance(point,s)}))
   .filter(v=>v.s.region_hint!=="title_block_candidate" && (v.s.orientation==="horizontal"||v.s.orientation==="vertical"))
   .sort((a,b)=>a.d-b.d);
 const seed=eligible[0];
 if(!seed || seed.d>maxSeedDistance) return {segments:[],seedSegment:null,distance:seed?.d??Infinity,warning:"No detected segment near selected pipe point. Manual review required."};
 const adjacency=new Map<number,Set<number>>();
 const connect=(a:number,b:number)=>{if(!adjacency.has(a))adjacency.set(a,new Set());adjacency.get(a)!.add(b);if(!adjacency.has(b))adjacency.set(b,new Set());adjacency.get(b)!.add(a);};
 for(const j of accepted) if(segments[j.segment_a] && segments[j.segment_b])connect(j.segment_a,j.segment_b);
 // Strict same-axis, endpoint-to-endpoint visual continuations; no crossings.
 const ends=(s:TraceSegment)=>[{x:s.x1,y:s.y1},{x:s.x2,y:s.y2}];
 for(let a=0;a<segments.length;a++){
  const left=segments[a];if(left.region_hint==="title_block_candidate")continue;
  for(let b=a+1;b<segments.length;b++){
   const right=segments[b];if(right.region_hint==="title_block_candidate"||left.orientation!==right.orientation)continue;
   const aligned=left.orientation==="horizontal"
    ? Math.max(Math.abs(left.y1-left.y2),Math.abs(right.y1-right.y2),Math.abs(left.y1-right.y1))<0.0015
    : Math.max(Math.abs(left.x1-left.x2),Math.abs(right.x1-right.x2),Math.abs(left.x1-right.x1))<0.0015;
   if(aligned && ends(left).some(p=>ends(right).some(q=>distance(p,q)<0.0025)))connect(a,b);
  }
 }
 const visited=new Set<number>(),queue=[seed.i];
 while(queue.length && visited.size<250){const id=queue.shift()!;if(visited.has(id))continue;visited.add(id);for(const next of adjacency.get(id)??[])if(!visited.has(next))queue.push(next);}
 return {segments:[...visited].sort((a,b)=>a-b),seedSegment:seed.i,distance:seed.d,
  warning:"Visual geometry hypothesis only. Crossings, valves, bends and connectivity require engineer review."};
}
