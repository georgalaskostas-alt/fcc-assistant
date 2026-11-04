export type Point = {x:number;y:number};
export type RasterSegment = {x1:number;y1:number;x2:number;y2:number;orientation:string;region_hint?:string};
export type BranchProposal = {id:string;x:number;y:number;routeLeg:number;segmentId:number;kind:"possible_branch_or_crossing";status:"requires_engineer_review"};
/** Geometric crossings only: neither junctions nor pipe identity are inferred. */
export function proposeBranchCrossings(route:Point[], segments:RasterSegment[], limit=60):BranchProposal[]{
  const proposals:BranchProposal[]=[];
  if(route.length<2)return proposals;
  for(let leg=0;leg<route.length-1;leg++){
    const a=route[leg],b=route[leg+1],dx=b.x-a.x,dy=b.y-a.y;
    const horizontal=Math.abs(dx)>=Math.abs(dy)*3;
    const vertical=Math.abs(dy)>=Math.abs(dx)*3;
    if(!horizontal&&!vertical)continue;
    for(let i=0;i<segments.length;i++){
      const s=segments[i];if(s.region_hint==="title_block_candidate")continue;
      if(horizontal&&s.orientation!=="vertical")continue;
      if(vertical&&s.orientation!=="horizontal")continue;
      const x=horizontal?(s.x1+s.x2)/2:a.x;
      const y=horizontal?a.y:(s.y1+s.y2)/2;
      const t=horizontal?(x-a.x)/dx:(y-a.y)/dy;
      if(t<0.045||t>0.955)continue;
      const within=horizontal? y>=Math.min(s.y1,s.y2)-0.004&&y<=Math.max(s.y1,s.y2)+0.004
        :x>=Math.min(s.x1,s.x2)-0.004&&x<=Math.max(s.x1,s.x2)+0.004;
      if(!within)continue;
      if(proposals.some(p=>Math.hypot(p.x-x,p.y-y)<0.012))continue;
      proposals.push({id:`leg-${leg}-segment-${i}`,x,y,routeLeg:leg+1,segmentId:i,kind:"possible_branch_or_crossing",status:"requires_engineer_review"});
      if(proposals.length>=limit)return proposals;
    }
  }
  return proposals;
}
