/** Experimental, conservative local raster-following preview.
 * The seed identifies a visual stroke only. Never infer connectivity or flow.
 */
export type PipePoint={x:number;y:number};
export type AutoPipePreview={paths:PipePoint[][];stopReasons:string[];sampleCount:number};
export function traceRasterFromSeed(image:ImageData,seed:PipePoint):AutoPipePreview{
 const {width:w,height:h,data}=image;
 if(w<8||h<8||!Number.isFinite(seed.x)||!Number.isFinite(seed.y)||seed.x<0||seed.x>1||seed.y<0||seed.y>1)
  return {paths:[],stopReasons:["Invalid image or seed coordinates"],sampleCount:0};
 const luminance=(x:number,y:number)=>{
  const k=(y*w+x)*4;
  return data[k]*.299+data[k+1]*.587+data[k+2]*.114;
 };
 const sx=Math.round(seed.x*w),sy=Math.round(seed.y*h);
 // Local background estimate compensates for yellowed/unevenly lit scans.
 const background:number[]=[];
 for(let dy=-14;dy<=14;dy+=4)for(let dx=-14;dx<=14;dx+=4){
  const x=sx+dx,y=sy+dy;
  if(x>=2&&y>=2&&x<w-2&&y<h-2)background.push(luminance(x,y));
 }
 background.sort((a,b)=>a-b);
 const paper=background.length?background[Math.floor(background.length*.8)]:220;
 const threshold=Math.min(190,Math.max(115,paper-48));
 const dark=(x:number,y:number)=>{
  x=Math.round(x);y=Math.round(y);
  return x>=2&&y>=2&&x<w-2&&y<h-2&&luminance(x,y)<threshold;
 };
 // Snap only within four source pixels. Require a short, predominantly
 // horizontal or vertical stroke; isolated dark lettering is not sufficient.
 const candidates:{x:number;y:number;distance:number;axis:number}[]=[];
 for(let dy=-4;dy<=4;dy++)for(let dx=-4;dx<=4;dx++){
  const x=sx+dx,y=sy+dy;
  if(!dark(x,y))continue;
  const horizontal=Array.from({length:11},(_,i)=>dark(x+i-5,y)).filter(Boolean).length;
  const vertical=Array.from({length:11},(_,i)=>dark(x,y+i-5)).filter(Boolean).length;
  const axis=Math.max(horizontal,vertical);
  if(axis>=8)candidates.push({x,y,distance:dx*dx+dy*dy,axis});
 }
 candidates.sort((a,b)=>a.distance-b.distance||b.axis-a.axis);
 if(!candidates.length)return {paths:[],stopReasons:["No coherent dark stroke within 4 source pixels of seed; check image alignment or select a clear straight pipe."],sampleCount:0};
 const start=candidates[0];
 const directions:[[number,number],[number,number],[number,number],[number,number]]=[[1,0],[-1,0],[0,1],[0,-1]];
 const paths:PipePoint[][]=[],stopReasons:string[]=[];
 const sustained=(x:number,y:number,dx:number,dy:number)=>{
  let hits=0;
  for(let k=1;k<=9;k++)if(dark(x+dx*k,y+dy*k)||dark(x+dx*k+dy,y+dy*k+dx)||dark(x+dx*k-dy,y+dy*k-dx))hits++;
  return hits>=8;
 };
 // Probe the extent of perpendicular ink; evidence only, never connectivity.
 const branchExtent=(x:number,y:number,dx:number,dy:number)=>{
  let consecutiveMisses=0,lastHit=0;
  for(let k=1;k<=32;k++){
   const px=x+dx*k,py=y+dy*k;
   const hit=dark(px,py)||dark(px+dy,py+dx)||dark(px-dy,py-dx);
   if(hit){lastHit=k;consecutiveMisses=0;}
   else if(++consecutiveMisses>=3)break;
  }
  return lastHit;
 };
 const elbow=(x:number,y:number,dx:number,dy:number)=>{
  // Search a small neighborhood ahead, as scanned corners rarely align exactly.
  // Do not turn while the incoming stroke still has a clear continuation.
  if(sustained(x,y,dx,dy))return null;
  const proposals:{x:number;y:number;dx:number;dy:number;score:number}[]=[];
  for(let ahead=0;ahead<=6;ahead++)for(let lateral=-3;lateral<=3;lateral++){
   const cx=x+dx*ahead+dy*lateral,cy=y+dy*ahead+dx*lateral;
   if(!dark(cx,cy))continue;
   const turns:[[number,number],[number,number]]=[[dy,dx],[-dy,-dx]];
   const supported=turns.filter(([tx,ty])=>sustained(cx,cy,tx,ty));
   if(supported.length!==1)continue;
   const [tx,ty]=supported[0];
   // Reject crosses/T-junctions: the opposite perpendicular arm must not continue.
   if(sustained(cx,cy,-tx,-ty))continue;
   proposals.push({x:cx,y:cy,dx:tx,dy:ty,score:ahead+Math.abs(lateral)*2});
  }
  proposals.sort((a,b)=>a.score-b.score);
  if(!proposals.length)return null;
  // Multiple distinct turn directions are ambiguous.
  if(proposals.some(p=>p.dx!==proposals[0].dx||p.dy!==proposals[0].dy))return null;
  return proposals[0];
 };
 for(const [dx,dy] of directions){
  // Direction must already be supported by the local raster evidence.
  if(!dark(start.x+dx*3,start.y+dy*3))continue;
  let x=start.x,y=start.y,steps=0,headingX=dx,headingY=dy,turns=0;
  let cornerX=-9999,cornerY=-9999,entryX=0,entryY=0;
  const points:PipePoint[]=[{x:x/w,y:y/h}];
  let reason="Reached maximum safe preview distance";
  const diagnostics=(label:string)=>{const left=sustained(x,y,headingY,headingX),right=sustained(x,y,-headingY,-headingX),forward=sustained(x,y,headingX,headingY);const extentA=branchExtent(x,y,headingY,headingX),extentB=branchExtent(x,y,-headingY,-headingX);const kind=forward&&left&&right?"possible-crossing-or-four-way-junction":
 forward&&(left||right)?"possible-tee-or-annotation":
 !forward&&(left!==right)?"possible-elbow":
 !forward&&left&&right?"possible-three-way-endpoint":"unclassified";
 const span=branchExtent(x,y,-headingX,-headingY);
 const evidence=forward&&(left||right)?"main-line-continuity-with-perpendicular-ink":
 !forward&&(left!==right)?"single-perpendicular-continuation":"insufficient-geometry";return `${label} at (${x},${y}) heading (${headingX},${headingY}); raster forward=${forward}, perpendicularA=${left}, perpendicularB=${right}, sideExtentA=${extentA}px, sideExtentB=${extentB}px, classification=${kind}, evidence=${evidence}, reverseExtent=${span}px, turns=${turns}, threshold=${threshold.toFixed(0)}`;};
  for(;steps<Math.min(420,Math.max(w,h));steps++){
   const nx=x+headingX*2,ny=y+headingY*2;
   const options:{x:number;y:number;offset:number}[]=[];
   for(let offset=-2;offset<=2;offset++){
    const cx=nx+(headingY!==0?offset:0),cy=ny+(headingX!==0?offset:0);
    if(dark(cx,cy))options.push({x:cx,y:cy,offset});
   }
   if(!options.length){
    const turn=turns===0&&steps>=8?elbow(x,y,headingX,headingY):null;
    if(turn){
     // Only count a turn after actually advancing onto its new leg.
     const tx=turn.x+turn.dx*2,ty=turn.y+turn.dy*2;
     if(dark(tx,ty)){
      cornerX=turn.x;cornerY=turn.y;entryX=headingX;entryY=headingY;
      x=tx;y=ty;headingX=turn.dx;headingY=turn.dy;turns++;
      points.push({x:x/w,y:y/h});continue;
     }
    }
    reason=diagnostics("Raster interruption / elbow rejected");break;
   }
   const chosen=options.sort((a,b)=>Math.abs(a.offset)-Math.abs(b.offset))[0];
   const sideInk=dark(chosen.x+headingY*5,chosen.y+headingX*5)||dark(chosen.x-headingY*5,chosen.y-headingX*5);
   if(sideInk){
    // A single side pixel is not a junction. Require sustained perpendicular
    // evidence, and distinguish a true T/cross from a short arrow or scan mark.
    const sideA=sustained(chosen.x,chosen.y,headingY,headingX);
    const sideB=sustained(chosen.x,chosen.y,-headingY,-headingX);
    const forward=sustained(chosen.x,chosen.y,headingX,headingY);
    // After turning, the previous leg lies OPPOSITE the arrival heading.
    // Ignore only that known leg close to the elbow; retain other junction checks.
    const nearKnownCorner=turns===1&&Math.hypot(chosen.x-cornerX,chosen.y-cornerY)<=12;
    const incomingOnA=-entryX===headingY&&-entryY===headingX;
    const incomingOnB=-entryX===-headingY&&-entryY===-headingX;
    const novelA=sideA&&!(nearKnownCorner&&incomingOnA);
    const novelB=sideB&&!(nearKnownCorner&&incomingOnB);
    if(novelA||novelB){
     // At an ambiguous branch, stop rather than silently choosing a pipe.
     if(forward||(novelA&&novelB)){
      x=chosen.x;y=chosen.y;
      reason=diagnostics("Sustained perpendicular branch / junction: manual review required");break;
     }
     const turn=turns===0?elbow(x,y,headingX,headingY):null;
     if(turn){
      const tx=turn.x+turn.dx*2,ty=turn.y+turn.dy*2;
      if(dark(tx,ty)){cornerX=turn.x;cornerY=turn.y;entryX=headingX;entryY=headingY;
      x=tx;y=ty;headingX=turn.dx;headingY=turn.dy;turns++;points.push({x:x/w,y:y/h});continue;}
     }
     x=chosen.x;y=chosen.y;
     reason=diagnostics("Perpendicular ink but no unique safe elbow");break;
    }
    // Short side marks do not interrupt a supported forward stroke.
   }
   x=chosen.x;y=chosen.y;
   if(steps%4===0)points.push({x:x/w,y:y/h});
  }
  if(points.length>=4){
   paths.push(points);
   stopReasons.push((turns?'One provisional 90-degree turn advanced onto perpendicular ink; ':'')+reason);
  }
 }
 if(!paths.length)stopReasons.push("Seed snapped to coherent raster ink, but no safe straight continuation was found");
 else stopReasons.unshift(start.distance>0?"Seed snapped to nearby coherent stroke (preview only)":"Seed confirmed on coherent stroke (preview only)");
 return {paths,stopReasons,sampleCount:paths.reduce((sum,p)=>sum+p.length,0)};
}
