export const SYMBOL_CLASSES=["instrument","valve","equipment","connector"] as const;
export type SymbolClass=typeof SYMBOL_CLASSES[number];
export type TrainingAnnotation={id:string;category:string;tag:string;bbox:{x:number;y:number;width:number;height:number};reviewed:boolean};
export type ValidationIssue={severity:"error"|"warning";code:string;annotationIds:string[];message:string};
const finite=(n:number)=>typeof n==="number"&&Number.isFinite(n);
export function validateSymbolDataset(items:TrainingAnnotation[]):ValidationIssue[]{
 const issues:ValidationIssue[]=[];
 for(const a of items){
  const b=a.bbox;
  if(!SYMBOL_CLASSES.includes(a.category as SymbolClass))issues.push({severity:"error",code:"unknown_class",annotationIds:[a.id],message:"Unsupported symbol class"});
  if(!a.reviewed)issues.push({severity:"error",code:"unreviewed",annotationIds:[a.id],message:"Annotation not reviewed"});
  if(![b.x,b.y,b.width,b.height].every(finite)||b.width<=0||b.height<=0||b.x<0||b.y<0||b.x+b.width>1.000001||b.y+b.height>1.000001)
   issues.push({severity:"error",code:"invalid_bbox",annotationIds:[a.id],message:"Bounding box outside normalized image or has invalid dimensions"});
  if(!a.tag.trim())issues.push({severity:"warning",code:"missing_tag",annotationIds:[a.id],message:"Tag is empty (permitted for object detection)"});
  if(a.tag.trim()&&!/^[A-Z0-9][A-Z0-9\s/_-]{0,39}$/i.test(a.tag.trim()))issues.push({severity:"warning",code:"tag_format",annotationIds:[a.id],message:"Tag contains unusual characters; check plant naming convention"});
  if(b.width<.003||b.height<.003)issues.push({severity:"warning",code:"tiny_bbox",annotationIds:[a.id],message:"Very small bounding box; inspect visually"});
 }
 for(let i=0;i<items.length;i++)for(let j=i+1;j<items.length;j++){
  const a=items[i],b=items[j],u=a.bbox,v=b.bbox;
  if(![u.x,u.y,u.width,u.height,v.x,v.y,v.width,v.height].every(finite)||u.width<=0||u.height<=0||v.width<=0||v.height<=0)continue;
  const intersection=Math.max(0,Math.min(u.x+u.width,v.x+v.width)-Math.max(u.x,v.x))*Math.max(0,Math.min(u.y+u.height,v.y+v.height)-Math.max(u.y,v.y));
  const union=u.width*u.height+v.width*v.height-intersection;
  if(union>0&&intersection/union>.65)issues.push({severity:"warning",code:"overlap",annotationIds:[a.id,b.id],message:"Overlapping boxes (IoU > 0.65); check duplicates"});
  if(a.tag.trim()&&a.tag.trim().toUpperCase()===b.tag.trim().toUpperCase())issues.push({severity:"warning",code:"duplicate_tag",annotationIds:[a.id,b.id],message:"Repeated tag on same page; verify intentional reuse"});
 }
 return issues;
}
export function toYoloLabels(items:TrainingAnnotation[]):string{
 return items.map(a=>{
  const b=a.bbox,cls=SYMBOL_CLASSES.indexOf(a.category as SymbolClass);
  if(cls<0)throw new Error("Unsupported YOLO class");
  return [cls,(b.x+b.width/2).toFixed(6),(b.y+b.height/2).toFixed(6),b.width.toFixed(6),b.height.toFixed(6)].join(" ");
 }).join("\n")+(items.length?"\n":"");
}
