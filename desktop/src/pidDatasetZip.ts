/** Minimal ZIP writer (STORE/no compression) for small UTF-8 text datasets. */
export function zipTextFiles(files:Array<{name:string;content:string}>):Blob{
 const encoder=new TextEncoder(),chunks:Uint8Array[]=[],central:Uint8Array[]=[];
 let offset=0;
 const crcTable=new Uint32Array(256);
 for(let n=0;n<256;n++){let c=n;for(let j=0;j<8;j++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;crcTable[n]=c>>>0;}
 const crc32=(bytes:Uint8Array)=>{let c=0xffffffff;for(const b of bytes)c=crcTable[(c^b)&255]^(c>>>8);return(c^0xffffffff)>>>0;};
 const write16=(v:DataView,p:number,n:number)=>v.setUint16(p,n,true);
 const write32=(v:DataView,p:number,n:number)=>v.setUint32(p,n>>>0,true);
 for(const file of files){
  const name=encoder.encode(file.name),data=encoder.encode(file.content),crc=crc32(data);
  if(name.length>65535||data.length>0xffffffff)throw new Error("ZIP entry too large");
  const local=new Uint8Array(30+name.length),lv=new DataView(local.buffer);
  write32(lv,0,0x04034b50);write16(lv,4,20);write16(lv,6,0x0800);write16(lv,8,0);
  write32(lv,14,crc);write32(lv,18,data.length);write32(lv,22,data.length);write16(lv,26,name.length);
  local.set(name,30);chunks.push(local,data);
  const dir=new Uint8Array(46+name.length),dv=new DataView(dir.buffer);
  write32(dv,0,0x02014b50);write16(dv,4,20);write16(dv,6,20);write16(dv,8,0x0800);
  write32(dv,16,crc);write32(dv,20,data.length);write32(dv,24,data.length);write16(dv,28,name.length);
  write32(dv,42,offset);dir.set(name,46);central.push(dir);
  offset+=local.length+data.length;
 }
 const centralSize=central.reduce((sum,part)=>sum+part.length,0);
 const end=new Uint8Array(22),view=new DataView(end.buffer);
 write32(view,0,0x06054b50);write16(view,8,files.length);write16(view,10,files.length);
 write32(view,12,centralSize);write32(view,16,offset);
 return new Blob([...chunks,...central,end].map(part=>new Uint8Array(part).buffer),{type:"application/zip"});
}
