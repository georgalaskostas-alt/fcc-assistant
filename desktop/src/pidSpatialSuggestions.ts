/** Spatial hypotheses only. OCR tags are not proven equipment or instrument nodes. */
type Segment = {x1:number;y1:number;x2:number;y2:number};
type Candidate = {tag:string;box:{x:number;y:number;width:number;height:number}};
type Path = {segmentIds:number[]};
export type SpatialSuggestion = {pathIndex:number;candidateIndex:number;tag:string;distance:number};

export function suggestPathTags(paths:Path[], segments:Segment[], candidates:Candidate[],
  maxDistance=0.035):SpatialSuggestion[] {
  const suggestions:SpatialSuggestion[]=[];
  paths.forEach((path,pathIndex)=>{
    candidates.forEach((candidate,candidateIndex)=>{
      const b=candidate.box;
      const cx=b.x+b.width/2, cy=b.y+b.height/2;
      let nearest=Infinity;
      for(const id of path.segmentIds){
        const s=segments[id];if(!s)continue;
        for(const [x,y] of [[s.x1,s.y1],[s.x2,s.y2]]){
          nearest=Math.min(nearest,Math.hypot(x-cx,y-cy));
        }
      }
      if(nearest<=maxDistance) suggestions.push({pathIndex,candidateIndex,tag:candidate.tag,distance:Number(nearest.toFixed(5))});
    });
  });
  return suggestions.sort((a,b)=>a.distance-b.distance);
}
