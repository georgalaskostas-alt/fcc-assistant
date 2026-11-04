/** Experimental local raster-following preview.
 * A user-selected seed anchors the pipe identity; no OCR proximity assignment,
 * physical connectivity or flow direction is inferred.
 */
export type PipePoint={x:number;y:number};
export type AutoPipePreview={paths:PipePoint[][];stopReasons:string[];sampleCount:number};
export function traceRasterFromSeed(image:ImageData,seed:PipePoint):AutoPipePreview{
 const {width:w,height:h,data}=image;
 const dark=(x:number,y:number)=>{x=Math.round(x);y=Math.round(y);if(x<2||y<2||x>=w-2||y>=h-2)return false;const k=(y*w+x)*4;return data[k]*.299+data[k+1]*.587+data[k+2]*.114<145;};
 const sx=Math.round(seed.x*w),sy=Math.round(seed.y*h);
 if(!dark(sx,sy))return {paths:[],stopReasons:["Selected seed is not on dark raster ink. Choose the pipe centerline."],sampleCount:0};
 const directions:[[number,number],[number,number],[number,number],[number,number]]=[[1,0],[-1,0],[0,1],[0,-1]];
 const paths:PipePoint[][]=[],stopReasons:string[]=[];
 for(const [dx,dy] of directions){
  let x=sx,y=sy,steps=0;const points:PipePoint[]=[seed];
  let reason="Reached maximum safe preview distance";
  // Follow only a straight, narrow stroke. No guessing at elbows, crossings or text.
  for(;steps<Math.min(420,Math.max(w,h));steps++){
   const nx=x+dx*2,ny=y+dy*2;
   const candidates=[] as {x:number;y:number;offset:number}[];
   for(let offset=-2;offset<=2;offset++){
    const cx=nx+(dy!==0?offset:0),cy=ny+(dx!==0?offset:0);
    if(dark(cx,cy))candidates.push({x:cx,y:cy,offset});
   }
   if(!candidates.length){reason="Raster stroke ended or interrupted";break;}
   const chosen=candidates.sort((a,b)=>Math.abs(a.offset)-Math.abs(b.offset))[0];
   const sideA=dark(chosen.x+dy*5,chosen.y+dx*5);
   const sideB=dark(chosen.x-dy*5,chosen.y-dx*5);
   if(sideA||sideB){reason="Nearby parallel ink / symbol / possible junction: manual review required";break;}
   x=chosen.x;y=chosen.y;
   if(steps%4===0)points.push({x:x/w,y:y/h});
  }
  if(points.length>=4){paths.push(points);stopReasons.push(reason);}
 }
 return {paths,stopReasons,sampleCount:paths.reduce((sum,p)=>sum+p.length,0)};
}
