import { useState } from "react";
import { SYMBOL_CLASSES, validateSymbolDataset, type TrainingAnnotation } from "./pidDatasetQuality";
import { zipBinaryFiles } from "./pidDatasetBinaryZip";

type DatasetRow={image:File;label:File|null;count:number;errors:string[];warnings:string[]};
const stem=(name:string)=>name.replace(/\.[^.]+$/,"").toLowerCase();
const imageExt=/\.(png|jpe?g|webp)$/i;
function matchLabel(image:File,labels:File[]):File|null{
 const base=stem(image.name);
 return labels.find(label=>stem(label.name)===base)??null;
}
async function inspect(images:File[],labels:File[]):Promise<DatasetRow[]>{
 const rows:DatasetRow[]=[];
 for(const image of images){
  const label=matchLabel(image,labels),errors:string[]=[],warnings:string[]=[];
  let count=0;
  if(!label){errors.push("No matching YOLO .txt file (same filename stem)");}
  else {
   const lines=(await label.text()).split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
   const annotations:TrainingAnnotation[]=[];
   for(let index=0;index<lines.length;index++){
    const tokens=lines[index].split(/\s+/),values=tokens.map(Number);
    if(tokens.length!==5||values.some(v=>!Number.isFinite(v))||!Number.isInteger(values[0])||values[0]<0||values[0]>=SYMBOL_CLASSES.length){
     errors.push(`Line ${index+1}: expected class x_center y_center width height`);continue;
    }
    const [cls,cx,cy,w,h]=values;
    annotations.push({id:`${index+1}`,category:SYMBOL_CLASSES[cls],tag:"",reviewed:true,bbox:{x:cx-w/2,y:cy-h/2,width:w,height:h}});
   }
   count=annotations.length;
   const issues=validateSymbolDataset(annotations);
   errors.push(...issues.filter(i=>i.severity==="error").map(i=>`${i.annotationIds.join(",")}: ${i.message}`));
   warnings.push(...issues.filter(i=>i.severity==="warning"&&i.code!=="missing_tag").map(i=>`${i.annotationIds.join(",")}: ${i.message}`));
  }
  rows.push({image,label,count,errors,warnings});
 }
 return rows;
}
export function PidTrainingDatasetManager(){
 const [images,setImages]=useState<File[]>([]);
 const [labels,setLabels]=useState<File[]>([]);
 const [rows,setRows]=useState<DatasetRow[]>([]);
 const [status,setStatus]=useState("");
 const [packaging,setPackaging]=useState(false);
 const onInspect=async()=>{
  const next=await inspect(images,labels);setRows(next);
  const unmatched=labels.filter(label=>!images.some(image=>matchLabel(image,[label])));
  setStatus(`${next.length} images · ${next.filter(r=>r.errors.length===0).length} valid pairs · ${unmatched.length} unmatched label files. Original images are not modified.`);
 };
 const exportTrainingPackage=async()=>{
  if(packaging)return;
  if(!rows.length||rows.some(r=>r.errors.length)||rows.some(r=>!r.label)){
   setStatus("Validate all image–label pairs before packaging.");return;
  }
  if(rows.length<2){
   setStatus("At least two independent source drawings are required for a train/validation package. Add another labeled P&ID; one image cannot support a meaningful validation split.");return;
  }
  setPackaging(true);
  try{
   // Deterministic split by source drawing; never split crops from the same drawing.
   const sorted=[...rows].sort((a,b)=>a.image.name.localeCompare(b.image.name));
   const valCount=Math.max(1,Math.round(sorted.length*.2));
   const entries:Array<{name:string;data:Uint8Array}>=[];
   const encode=(value:string)=>new TextEncoder().encode(value);
   const manifest:Array<{image:string;label:string;split:"train"|"val";annotations:number}>=[];
   for(let index=0;index<sorted.length;index++){
    const row=sorted[index],split=index>=sorted.length-valCount?"val":"train";
    const imageName=row.image.name,labelName=`${stem(imageName)}.txt`;
    if(!row.label)throw new Error("Missing labels");
    entries.push({name:`images/${split}/${imageName}`,data:new Uint8Array(await row.image.arrayBuffer())});
    entries.push({name:`labels/${split}/${labelName}`,data:new Uint8Array(await row.label.arrayBuffer())});
    manifest.push({image:imageName,label:labelName,split,annotations:row.count});
   }
   const yaml=`path: .\ntrain: images/train\nval: images/val\nnc: ${SYMBOL_CLASSES.length}\nnames:\n${SYMBOL_CLASSES.map((name,i)=>`  ${i}: ${name}`).join("\n")}\n`;
   entries.push({name:"data.yaml",data:encode(yaml)});
   entries.push({name:"manifest.json",data:encode(JSON.stringify({schema_version:2,format:"fcc_pid_yolo_package",split_strategy:"deterministic_by_source_image",validation_images:valCount,classes:SYMBOL_CLASSES,images:manifest},null,2))});
   const zip=zipBinaryFiles(entries),url=URL.createObjectURL(zip),a=document.createElement("a");
   a.href=url;a.download="fcc-pid-yolo-dataset.zip";a.click();
   window.setTimeout(()=>URL.revokeObjectURL(url),10000);
   setStatus(`Training ZIP created: ${sorted.length-valCount} train images, ${valCount} validation images, ${manifest.reduce((n,row)=>n+row.annotations,0)} labels. Keep related pages from the same original drawing in one split.`);
  }catch(error){setStatus(`Dataset packaging failed: ${error instanceof Error?error.message:String(error)}`);}
  finally{setPackaging(false);}
 };
 const exportManifest=()=>{
  if(!rows.length||rows.some(r=>r.errors.length)){setStatus("Resolve dataset errors before exporting a manifest.");return;}
  const payload={schema_version:1,format:"fcc_pid_dataset_manifest",classes:SYMBOL_CLASSES,images:rows.map(r=>({image:r.image.name,label:r.label?.name,annotations:r.count,bytes:r.image.size})),note:"Manifest only. Keep original image and label files together. Split train/validation by source drawing, not individual crops."};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download="pid-dataset-manifest.json";a.click();window.setTimeout(()=>URL.revokeObjectURL(url),1500);
 };
 return <section className="pid-graph-panel pid-dataset-manager">
  <div className="pid-table-head"><h3>Training Dataset Manager · local validation</h3><button type="button" className="secondary-button" onClick={exportTrainingPackage} disabled={packaging||rows.length<2||rows.some(r=>r.errors.length>0)}>{packaging?"Packaging…":"Export YOLO training ZIP"}</button><button type="button" className="secondary-button" onClick={exportManifest} disabled={!rows.length||rows.some(r=>r.errors.length>0)}>Export dataset manifest JSON</button></div>
  <p>Choose original P&ID images and matching YOLO label files. Filenames must match, for example <code>drawing01.jpg</code> + <code>drawing01.txt</code>. The existing <code>pid-page-1.txt</code> must be renamed to match its source image before pairing.</p>
  <div className="pid-dataset-inputs">
   <label>Original P&ID images<input type="file" accept=".png,.jpg,.jpeg,.webp" multiple onChange={e=>{setImages(Array.from(e.target.files??[]).filter(f=>imageExt.test(f.name)));setRows([]);}}/></label>
   <label>YOLO label files<input type="file" accept=".txt" multiple onChange={e=>{setLabels(Array.from(e.target.files??[]).filter(f=>f.name.toLowerCase().endsWith(".txt")&&!f.name.toLowerCase().includes("classes")));setRows([]);}}/></label>
   <button type="button" onClick={onInspect} disabled={!images.length}>Validate image–label pairs</button>
  </div>
  <p role="status">{status}</p>
  {rows.length>0&&<div className="pid-dataset-results">{rows.map((r,i)=><div key={i} className="pid-dataset-result"><strong>{r.image.name}</strong> · {r.label?.name??"No label"} · {r.count} annotations · {r.errors.length} errors · {r.warnings.length} warnings
   {r.errors.map((message,j)=><p key={j} className="pid-dataset-error">{message}</p>)}
   {r.warnings.map((message,j)=><p key={j}>{message}</p>)}
  </div>)}</div>}
  <small>This manager validates YOLO structure and packages original images with labels. It does not visually verify annotations or train AI. Validation splitting is by image filename; manually keep pages from the same source drawing in the same split.</small>
 </section>;
}
