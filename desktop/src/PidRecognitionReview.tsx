import { useEffect, useState } from "react";
import { SYMBOL_CLASSES } from "./pidDatasetQuality";

type Item={id:string;cls:number;cx:number;cy:number;w:number;h:number;tag:string;status:"pending"|"approved"|"rejected"};
type Stored={version:1;imageName:string;imageSize:number;imageModified:number;items:Item[];approvedAt:string};
const databaseName="fcc-pid-engineer-memory";
const storeName="approved-drawings";
function openDb():Promise<IDBDatabase>{
 return new Promise((resolve,reject)=>{
  const request=indexedDB.open(databaseName,1);
  request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains(storeName))request.result.createObjectStore(storeName);};
  request.onsuccess=()=>resolve(request.result);
  request.onerror=()=>reject(request.error);
 });
}
async function saveDrawing(key:string,data:Stored,image:File){
 const db=await openDb();
 try{await new Promise<void>((resolve,reject)=>{
  const tx=db.transaction(storeName,"readwrite");
  tx.objectStore(storeName).put({data,image},key);
  tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
 });}finally{db.close();}
}
async function loadDrawing(key:string):Promise<Stored|null>{
 const db=await openDb();
 try{return await new Promise((resolve,reject)=>{
  const tx=db.transaction(storeName,"readonly"),request=tx.objectStore(storeName).get(key);
  request.onsuccess=()=>resolve((request.result?.data as Stored|undefined)??null);
  request.onerror=()=>reject(request.error);
 });}finally{db.close();}
}
const drawingKey=(image:File)=>[image.name,image.size,image.lastModified].join(":");
const normalizeTag=(value:string)=>{
 const confusables:Record<string,string>={
  "Α":"A","Β":"B","Ε":"E","Ζ":"Z","Η":"H","Ι":"I","Κ":"K","Μ":"M","Ν":"N","Ο":"O","Ρ":"P","Τ":"T","Υ":"Y","Χ":"X",
  "а":"A","в":"B","е":"E","к":"K","м":"M","н":"H","о":"O","р":"P","с":"C","т":"T","у":"Y","х":"X",
  "А":"A","В":"B","Е":"E","К":"K","М":"M","Н":"H","О":"O","Р":"P","С":"C","Т":"T","У":"Y","Х":"X"
 };
 return value.normalize("NFKC").toUpperCase().replace(/[\u200B-\u200D\u2060\uFEFF]/g,"")
  .split("").map(char=>confusables[char]??char).join("")
  .trim().replace(/[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]/g,"-")
  .replace(/\s*-\s*/g,"-").replace(/\s+/g,"-");
};
const tagCodepoints=(value:string)=>Array.from(value).map(c=>c.codePointAt(0)?.toString(16).toUpperCase()).join(" ");
export function PidRecognitionReview({image,label}: {image:File;label:File}){
 const [items,setItems]=useState<Item[]>([]);
 const [message,setMessage]=useState("");
 const [url,setUrl]=useState("");
 const [saved,setSaved]=useState(false);
 useEffect(()=>{
  let active=true;const objectUrl=URL.createObjectURL(image);setUrl(objectUrl);setSaved(false);
  Promise.all([label.text(),loadDrawing(drawingKey(image))]).then(([raw,stored])=>{
   if(!active)return;
   const parsed=raw.split(/\r?\n/).map(s=>s.trim()).filter(Boolean).map((line,i)=>{
    const [cls,cx,cy,w,h]=line.split(/\s+/).map(Number);
    return {id:String(i),cls,cx,cy,w,h,tag:"",status:"pending" as const};
   });
   if(stored&&stored.items.length===parsed.length&&stored.items.every((item,i)=>item.cls===parsed[i].cls&&["cx","cy","w","h"].every(k=>Math.abs(Number(item[k as keyof Item])-Number(parsed[i][k as keyof Item]))<0.000002))){
    setItems(stored.items);setSaved(true);setMessage("Restored previously approved drawing from local engineer memory.");
   }else{setItems(parsed);setMessage(stored?"Labels changed since approval. Review again before saving.":"Imported YOLO boxes as unverified candidates. Add tags and approve individually.");}
  }).catch(e=>setMessage("Unable to read local review: "+String(e)));
  return ()=>{active=false;URL.revokeObjectURL(objectUrl);};
 },[image,label]);
 const patch=(index:number,changes:Partial<Item>)=>{setItems(old=>old.map((item,i)=>i===index?{...item,...changes,status:changes.status??"pending"}:item));setSaved(false);setMessage("");};
 const approve=async()=>{
  const normalizedItems=items.map(item=>({...item,tag:normalizeTag(item.tag)}));
  const approved=normalizedItems.filter(item=>item.status==="approved");
  if(!approved.length||items.some(item=>item.status==="pending")){setMessage("Review every candidate and approve at least one before saving.");return;}
  const invalid=approved.filter(item=>!/^([A-Z]{1,8})-?\d+[A-Z0-9/-]*$/i.test(item.tag));
  if(invalid.length){setMessage(`Invalid tag(s): ${invalid.map(item=>`${JSON.stringify(item.tag)} [Unicode: ${tagCodepoints(item.tag)}]`).join(", ")}. Use e.g. TI-544.`);return;}
  try{
   await saveDrawing(drawingKey(image),{version:1,imageName:image.name,imageSize:image.size,imageModified:image.lastModified,items:normalizedItems,approvedAt:new Date().toISOString()},image);
   setItems(normalizedItems);
   setSaved(true);setMessage("Engineer-approved drawing, original image, tags and rejected proposals saved locally in IndexedDB. No model training has occurred.");
  }catch(e){setMessage("Save failed: "+String(e));}
 };
 return <section className="pid-recognition-workspace">
  <h3>Recognition & Learning Workspace · {image.name}</h3>
  <p>Existing YOLO labels are imported as candidates, not AI detections. Enter instrument tags and explicitly approve or reject every proposal. Only approval writes to local memory.</p>
  <div className="pid-inspector-image">
   {url&&<img src={url} alt={image.name}/>}
   {items.filter(item=>item.status!=="rejected").map(item=><div key={item.id} className={item.status==="approved"?"pid-learning-box approved":"pid-learning-box"} style={{left:`${(item.cx-item.w/2)*100}%`,top:`${(item.cy-item.h/2)*100}%`,width:`${item.w*100}%`,height:`${item.h*100}%`}} title={item.tag||"Unverified instrument"}/>)}
  </div>
  <div className="pid-learning-list">{items.map((item,i)=><div key={item.id} className="pid-learning-row">
   <strong>#{i+1} {SYMBOL_CLASSES[item.cls]}</strong>
   <input aria-label={`Instrument tag ${i+1}`} placeholder="e.g. TI-544" value={item.tag} onChange={e=>patch(i,{tag:e.target.value.toUpperCase()})}/>
   <select aria-label={`Review status ${i+1}`} value={item.status} onChange={e=>patch(i,{status:e.target.value as Item["status"]})}>
    <option value="pending">Pending review</option><option value="approved">Approved</option><option value="rejected">Rejected</option>
   </select>
  </div>)}</div>
  <p>{items.filter(i=>i.status==="approved").length} approved · {items.filter(i=>i.status==="pending").length} pending · {items.filter(i=>i.status==="rejected").length} rejected</p>
  <button type="button" onClick={approve} disabled={saved||!items.length}>Save engineer-approved P&ID to local memory</button>
  <p role="status">{message}</p>
  <small>Local IndexedDB storage is device/browser-profile specific. Clearing application data can erase it; export a backup before relying on it for operational records. This is not yet automatic OCR or model learning.</small>
 </section>;
}
