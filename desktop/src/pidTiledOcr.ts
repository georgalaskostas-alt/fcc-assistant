import type { PidOcrResult } from "./api";

type Box = {x:number;y:number;width:number;height:number};
type Candidate = PidOcrResult["candidates"][number];
const clamp=(v:number)=>Math.max(0,Math.min(1,v));
const iou=(a:Box,b:Box)=>{
  const w=Math.max(0,Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x));
  const h=Math.max(0,Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y));
  const intersection=w*h;
  return intersection/(a.width*a.height+b.width*b.height-intersection||1);
};
const sameDetection=(a:Candidate,b:Candidate)=>{
  const ax=a.box.x+a.box.width/2,ay=a.box.y+a.box.height/2;
  const bx=b.box.x+b.box.width/2,by=b.box.y+b.box.height/2;
  const near=Math.abs(ax-bx)<Math.max(a.box.width,b.box.width)*0.5 && Math.abs(ay-by)<Math.max(a.box.height,b.box.height)*0.5;
  return a.tag.replace(/[^A-Z0-9]/gi,"").toUpperCase()===b.tag.replace(/[^A-Z0-9]/gi,"").toUpperCase() && (iou(a.box,b.box)>0.25||near);
};

/** On-demand, image-only tiled OCR. No connectivity is inferred. */
export async function augmentPidOcrWithTiles(
  original:File, base:PidOcrResult,
  recognize:(file:File)=>Promise<PidOcrResult>,
):Promise<{result:PidOcrResult;tiles:number;added:number;failures:number}>{
  if(!/^image\/(png|jpeg)$/i.test(original.type) && !/\.(png|jpe?g)$/i.test(original.name)) throw new Error("Tiled OCR currently supports PNG and JPG drawings only.");
  const bitmap=await createImageBitmap(original);
  try{
    const candidates=[...base.candidates];
    let tiles=0,failures=0;
    // 2x2 with 12% overlap, clipped to source image boundaries.
    for(let row=0;row<2;row++)for(let col=0;col<2;col++){
      const x=col===0?0:0.44,y=row===0?0:0.44;
      const w=0.56,h=0.56;
      const canvas=document.createElement("canvas");
      canvas.width=Math.round(bitmap.width*w);canvas.height=Math.round(bitmap.height*h);
      const context=canvas.getContext("2d");
      if(!context){failures++;continue;}
      context.drawImage(bitmap,Math.round(bitmap.width*x),Math.round(bitmap.height*y),canvas.width,canvas.height,0,0,canvas.width,canvas.height);
      const blob=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve,"image/png"));
      if(!blob){failures++;continue;}
      try{
        const response=await recognize(new File([blob],`tile-${row}-${col}.png`,{type:"image/png"}));
        tiles++;
        for(const candidate of response.candidates){
          const mapped={...candidate,box:{
            x:clamp(x+candidate.box.x*w),y:clamp(y+candidate.box.y*h),
            width:Math.min(candidate.box.width*w,1-clamp(x+candidate.box.x*w)),
            height:Math.min(candidate.box.height*h,1-clamp(y+candidate.box.y*h)),
          }};
          const duplicate=candidates.findIndex(existing=>sameDetection(existing,mapped));
          if(duplicate<0)candidates.push(mapped);
          else if(mapped.confidence>candidates[duplicate].confidence)candidates[duplicate]=mapped;
        }
      }catch{failures++;}
    }
    return {result:{...base,candidates,warning:[base.warning,"Tiled OCR supplements text candidates only; instrument symbols and connections require separate verification."].filter(Boolean).join(" ")},tiles,added:candidates.length-base.candidates.length,failures};
  }finally{bitmap.close();}
}
