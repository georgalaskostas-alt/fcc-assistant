import { useEffect, useState } from "react";
import { SYMBOL_CLASSES } from "./pidDatasetQuality";

type Box = {cls:number;cx:number;cy:number;w:number;h:number};
type Props = {image:File;label:File;onClose:()=>void};
const clamp=(v:number)=>Math.min(1,Math.max(0,v));
export function PidVisualDatasetInspector({image,label,onClose}:Props){
 const [url,setUrl]=useState("");
 const [boxes,setBoxes]=useState<Box[]>([]);
 const [selected,setSelected]=useState(0);
 const [error,setError]=useState("");
 const [reviewed,setReviewed]=useState(false);
 useEffect(()=>{
  const objectUrl=URL.createObjectURL(image);setUrl(objectUrl);setReviewed(false);setSelected(0);
  label.text().then(content=>{
   const parsed=content.split(/\r?\n/).map(line=>line.trim()).filter(Boolean).map(line=>{
    const [cls,cx,cy,w,h]=line.split(/\s+/).map(Number);
    return {cls,cx,cy,w,h};
   });
   setBoxes(parsed);setError("");
  }).catch(e=>setError(String(e)));
  return ()=>URL.revokeObjectURL(objectUrl);
 },[image,label]);
 const update=(key:keyof Box,value:number)=>{
  if(!Number.isFinite(value))return;
  setBoxes(previous=>previous.map((b,i)=>i===selected?{...b,[key]:key==="cls"?value:clamp(value)}:b));
  setReviewed(false);
 };
 const exportLabels=()=>{
  if(!reviewed){setError("Confirm visual review before exporting corrected labels.");return;}
  if(boxes.some(b=>!Number.isInteger(b.cls)||b.cls<0||b.cls>=SYMBOL_CLASSES.length||b.w<=0||b.h<=0||b.cx-b.w/2<0||b.cy-b.h/2<0||b.cx+b.w/2>1||b.cy+b.h/2>1)){
   setError("One or more boxes have invalid dimensions or extend outside the image.");return;
  }
  const text=boxes.map(b=>[b.cls,b.cx,b.cy,b.w,b.h].map((n,i)=>i===0?String(n):n.toFixed(6)).join(" ")).join("\n")+"\n";
  const blob=new Blob([text],{type:"text/plain"}),href=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=href;a.download=image.name.replace(/\.[^.]+$/,"")+".txt";a.click();
  window.setTimeout(()=>URL.revokeObjectURL(href),10000);setError("Corrected labels downloaded. Re-select the new .txt in Dataset Manager and validate again.");
 };
 return <div className="pid-visual-inspector">
  <div className="pid-table-head"><h3>Visual Dataset Quality Inspector · {image.name}</h3><button type="button" className="secondary-button" onClick={onClose}>Close inspector</button></div>
  <p>Review every bounding box against the actual symbol. Click a box to edit its coordinates. This tool cannot automatically identify missing symbols.</p>
  <div className="pid-inspector-image">
   {url&&<img src={url} alt={image.name} draggable={false}/>}
   {boxes.map((b,i)=><button key={i} type="button" className={selected===i?"pid-inspector-box selected":"pid-inspector-box"}
    style={{left:`${(b.cx-b.w/2)*100}%`,top:`${(b.cy-b.h/2)*100}%`,width:`${b.w*100}%`,height:`${b.h*100}%`}}
    onClick={()=>setSelected(i)} title={`Annotation ${i+1}: ${SYMBOL_CLASSES[b.cls]??"unknown"}`} aria-label={`Select annotation ${i+1}`}/>
   )}
  </div>
  <p>{boxes.length} labeled symbols · {selected+1} selected. Unlabeled instruments in the image still require annotation before model training.</p>
  {boxes[selected]&&<div className="pid-inspector-fields">
   <label>Class<select value={boxes[selected].cls} onChange={e=>update("cls",Number(e.target.value))}>{SYMBOL_CLASSES.map((name,i)=><option value={i} key={name}>{name}</option>)}</select></label>
   {(["cx","cy","w","h"] as const).map(key=><label key={key}>{key}<input type="number" min="0" max="1" step="0.001" value={boxes[selected][key]} onChange={e=>update(key,Number(e.target.value))}/></label>)}
   <button type="button" className="secondary-button" onClick={()=>{setBoxes(previous=>previous.filter((_,i)=>i!==selected));setSelected(0);setReviewed(false);}}>Delete selected box</button>
  </div>}
  <label className="pid-inspector-reviewed"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/> I checked all boxes and checked for missing symbols</label>
  <button type="button" onClick={exportLabels} disabled={!reviewed}>Export reviewed YOLO labels</button>
  {error&&<p role="status">{error}</p>}
 </div>;
}
