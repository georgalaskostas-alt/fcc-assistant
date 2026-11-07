import { proposeBranchCrossings, proposeRasterBranches } from "./pidBranchProposals";
import { auditGuidedRoute, auditRouteRaster, auditRasterLegAlignment } from "./pidRouteAudit";
import { proposeCenterlineLegs } from "./pidCenterline";
import { useEffect, useRef, useState } from "react";
import { FileSearch, ShieldCheck, Upload } from "lucide-react";
import { api, PidInspectionResult, PidOcrResult } from "./api";
import "./PidIntelligenceView.css";
import { reconstructVisualPaths } from "./pidVisualPaths";
import { augmentPidOcrWithTiles } from "./pidTiledOcr";
import { assessPidCandidate } from "./pidCandidateAssessment";
import { matchPidKnowledge, pidKnowledgeReferences } from "./pidEngineeringKnowledge";
import { detectInstrumentCircles, type SymbolProposal } from "./pidSymbolDetection";
import { suggestPathTags } from "./pidSpatialSuggestions";
import { traceVisualPipe } from "./pidPipeTrace";
import { traceRasterFromSeed } from "./pidRasterAutoTrace";

export function PidIntelligenceView() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PidInspectionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [ocr, setOcr] = useState<PidOcrResult | null>(null);
  const [raster, setRaster] = useState<ImageData | null>(null);
  useEffect(()=>{
    setRaster(null);
    setSymbolProposals([]);
    if(!ocr?.preview_png_base64)return;
    let cancelled=false;
    const image=new Image();
    image.onload=()=>{
      if(cancelled)return;
      const canvas=document.createElement("canvas");
      canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
      const ctx=canvas.getContext("2d",{willReadFrequently:true});
      if(!ctx)return;
      ctx.drawImage(image,0,0);
      setRaster(ctx.getImageData(0,0,canvas.width,canvas.height));
    };
    image.src="data:image/png;base64,"+ocr.preview_png_base64;
    return ()=>{cancelled=true;image.onload=null;};
  },[ocr?.preview_png_base64]);

  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);
  const [selectedLineLabel, setSelectedLineLabel] = useState<number | null>(null);
  const [showAllLineBoxes, setShowAllLineBoxes] = useState(false);
  const [showEquipmentBoxes, setShowEquipmentBoxes] = useState(false);
  const drawingRef = useRef<HTMLDivElement | null>(null);
  const [drawingZoom, setDrawingZoom] = useState(1);
  const drawingZoomRef = useRef(1);
  const focusTimerRef = useRef<number | null>(null);
  const lineReviewRef = useRef<HTMLDivElement | null>(null);
  const [lineReviews, setLineReviews] = useState<Record<number, "correct" | "rejected">>({});
  const [lineCorrections, setLineCorrections] = useState<Record<number, string>>({});
  const [lineDraft, setLineDraft] = useState("");
  const [pipePickMode, setPipePickMode] = useState(false);
  const [pipeAnchors, setPipeAnchors] = useState<Record<number,{x:number;y:number}>>({});
  const [traceLine, setTraceLine] = useState<number | null>(null);
  const [routeMode, setRouteMode] = useState(false);
  const [routeWarning, setRouteWarning] = useState("");
  const [autoTracePreview, setAutoTracePreview] = useState<{line:number;paths:Array<Array<{x:number;y:number}>>;stopReasons:string[];shadowPaths:Array<Array<{x:number;y:number}>>;shadowReviews:Record<number,"approved"|"rejected">}|null>(null);
  // Endpoint annotations are explicit engineer reviews, never inferred topology.
  const [endpointReviews,setEndpointReviews] = useState<Record<string,{equipment:string;nozzle:string;side:"left"|"right"|"top"|"bottom"|"";point?:{x:number;y:number};status:"confirmed"|"rejected"}>>({});
  const [targetTraceProposals,setTargetTraceProposals] = useState<Record<string,{points:Array<{x:number;y:number}>;support:number;status:"proposed"|"approved"|"rejected"}>>({});
  const [endpointPick,setEndpointPick] = useState<{key:string;index:number}|null>(null);
  const [routePoints, setRoutePoints] = useState<Record<number,Array<{x:number;y:number}>>>({});
  const [dragRoutePoint, setDragRoutePoint] = useState<number | null>(null);
  const suppressRouteClick = useRef(false);
  const [showCenterlineCandidates, setShowCenterlineCandidates] = useState(false);
  const [selectedCenterlineLeg, setSelectedCenterlineLeg] = useState<number | null>(null);
  const [centerlineReviews, setCenterlineReviews] = useState<Record<number, Record<number, "accepted" | "rejected">>>({});
  const [manualGeometryReviews, setManualGeometryReviews] = useState<Record<number, Record<number, "verified" | "rejected">>>({});
  useEffect(()=>{if(traceLine!==null)setManualGeometryReviews(previous=>({...previous,[traceLine]:{}}));},[routePoints,traceLine]);


  const [inspectedBranch, setInspectedBranch] = useState<{id:string;index:number;x:number;y:number;line:number}|null>(null);
  const [branchDecisions, setBranchDecisions] = useState<Record<number, Record<string,"branch"|"crossing"|"reject">>>({});
  const [connectivityRecords, setConnectivityRecords] = useState<Record<number, {fromEquipment:string;toEquipment:string;valves:string;instruments:string;junctions:string;crossings:"unreviewed"|"reviewed";endpointReview:"unreviewed"|"reviewed";status:"draft"|"engineer_reviewed"}>>({});
  const connectivityFor = (index:number) => connectivityRecords[index] ?? {fromEquipment:"",toEquipment:"",valves:"",instruments:"",junctions:"",crossings:"unreviewed" as const,endpointReview:"unreviewed" as const,status:"draft" as const};
  const updateConnectivity = (index:number, patch:Partial<ReturnType<typeof connectivityFor>>) => setConnectivityRecords(previous=>({...previous,[index]:{...connectivityFor(index),...patch,status:"draft"}}));
  function exportConnectivityReview() {
    if(!ocr)return;
    const records=(ocr.line_labels??[]).flatMap((label,index)=>{
      const record=connectivityRecords[index];
      if(!record)return [];
      return [{line_number:lineCorrections[index]??label.tag,source_ocr_text:label.tag,route_waypoints:routePoints[index]??[],
        manual_leg_reviews:manualGeometryReviews[index]??{},branch_candidate_decisions:branchDecisions[index]??{},...record}];
    });
    const payload={schema_version:1,kind:"engineer_assisted_pid_connectivity",drawing:file?.name??null,page:ocr.page,records,
      warning:"Manual engineering assertions only. Not independently verified against as-built drawings or plant equipment."};
    const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`pid-connectivity-page-${ocr.page}.json`;a.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }

  const [reviews, setReviews] = useState<Record<number, "correct" | "incorrect">>({});
  const [corrections, setCorrections] = useState<Record<number, string>>({});
  const [candidateKinds, setCandidateKinds] = useState<Record<number, "equipment" | "instrument" | "line" | "valve" | "note" | "other">>({});
  const [symbolReviews,setSymbolReviews] = useState<Record<number,boolean>>({});
  const [reviewStorageMessage, setReviewStorageMessage] = useState("");
  const [candidateTierFilter,setCandidateTierFilter]=useState<"all"|"plausible"|"uncertain">("all");
  const [tiledOcrBusy,setTiledOcrBusy]=useState(false);
  const [tiledOcrMessage,setTiledOcrMessage]=useState("");
  const reviewStorageKey = file && ocr ? `fcc-pid-reviews-v1:${file.name}:${file.size}:${file.lastModified}:page-${ocr.page}:${ocr.candidates.map(item=>`${item.tag}@${item.box.x.toFixed(4)},${item.box.y.toFixed(4)}`).join("|")}` : null;
  useEffect(() => {
    if (!reviewStorageKey) return;
    try {
      localStorage.setItem(reviewStorageKey, JSON.stringify({schema_version:1,reviews,corrections,candidateKinds,symbolReviews}));
      setReviewStorageMessage("Reviews saved locally for this drawing and page.");
    } catch {
      setReviewStorageMessage("Local review storage unavailable. Export the graph JSON as a backup.");
    }
  }, [reviewStorageKey, reviews, corrections, candidateKinds, symbolReviews]);
  type ManualEdge = {id:string;source:string;target:string;kind:"process"|"signal"|"mechanical";review_method:"manual_engineer_review";verified:true};
  const [manualEdges,setManualEdges] = useState<ManualEdge[]>([]);
  const [edgeSource,setEdgeSource] = useState("");
  const [edgeTarget,setEdgeTarget] = useState("");
  const [edgeKind,setEdgeKind] = useState<ManualEdge["kind"]>("process");
  const [edgeMessage,setEdgeMessage] = useState("");
  const edgeStorageKey = reviewStorageKey ? reviewStorageKey.replace("fcc-pid-reviews-v1:","fcc-pid-edges-v1:") : null;
  useEffect(()=>{
    if(!edgeStorageKey)return;
    try{
      const raw=localStorage.getItem(edgeStorageKey);
      const data:unknown=raw?JSON.parse(raw):[];
      const validIds=new Set((ocr?.candidates??[]).map((_,index)=>`p${ocr!.page}-ocr-${index}`));
      setManualEdges(Array.isArray(data)?data.filter((edge):edge is ManualEdge=>Boolean(edge&&typeof edge==="object"&&typeof edge.id==="string"&&validIds.has(edge.source)&&validIds.has(edge.target)&&edge.source!==edge.target&&(edge.kind==="process"||edge.kind==="signal"||edge.kind==="mechanical")&&edge.verified===true&&edge.review_method==="manual_engineer_review")):[]);
    }catch{setManualEdges([]);setEdgeMessage("Saved connections could not be restored.");}
  },[edgeStorageKey]);
  function saveManualEdges(next:ManualEdge[]){
    if(!edgeStorageKey)return;
    try{localStorage.setItem(edgeStorageKey,JSON.stringify(next));setManualEdges(next);setEdgeMessage("Verified connections saved locally.");}
    catch{setEdgeMessage("Storage failed. Connections were not saved.");}
  }
  const [draftTag, setDraftTag] = useState("");
  const [showGeometry, setShowGeometry] = useState(false);
  const [includeTitleBlock, setIncludeTitleBlock] = useState(false);
  const [selectedTopology, setSelectedTopology] = useState<number | null>(null);
  const [selectedVisualPath, setSelectedVisualPath] = useState<number | null>(null);
  const [pathEquipment, setPathEquipment] = useState<Record<string, string>>({});
  const [lineNumberPattern, setLineNumberPattern] = useState("");
  const [standardName, setStandardName] = useState("FCC line numbering");
  const [standardExample, setStandardExample] = useState('10"-0-425112-B');
  const [savedStandards, setSavedStandards] = useState<Array<{name:string;pattern:string;example:string}>>(() => {
    try {
      const value: unknown = JSON.parse(localStorage.getItem("fcc-pid-line-standards-v1") ?? "[]");
      return Array.isArray(value) ? value.filter((item): item is {name:string;pattern:string;example:string} =>
        typeof item?.name === "string" && typeof item?.pattern === "string" && typeof item?.example === "string").slice(0,30) : [];
    } catch { return []; }
  });
  const [standardMessage, setStandardMessage] = useState("");

  const [pathLineNumbers, setPathLineNumbers] = useState<Record<string, string>>({});
  const [symbolMode, setSymbolMode] = useState<"off" | "equipment" | "valve" | "instrument" | "connector">("off");
  const [symbolProposals,setSymbolProposals]=useState<SymbolProposal[]>([]);
  const [symbolDetectionMessage,setSymbolDetectionMessage]=useState("");
  const [symbolAnnotations, setSymbolAnnotations] = useState<Array<{x:number;y:number;kind:"equipment" | "valve" | "instrument" | "connector";tag:string;width?:number;height?:number;reviewed?:boolean}>>([]);
  const [datasetMessage,setDatasetMessage]=useState("");
  const datasetStorageKey=file&&ocr?`fcc-pid-symbol-dataset-v1:${file.name}:${file.size}:${file.lastModified}:page-${ocr.page}`:null;
  useEffect(()=>{
    if(!datasetStorageKey)return;
    try{
      const parsed:unknown=JSON.parse(localStorage.getItem(datasetStorageKey)??"[]");
      if(!Array.isArray(parsed))return;
      const valid=parsed.filter(item=>item&&typeof item==="object"&&Number.isFinite(item.x)&&Number.isFinite(item.y)&&item.x>=0&&item.x<=1&&item.y>=0&&item.y<=1&&["equipment","valve","instrument","connector"].includes(item.kind)&&typeof item.tag==="string"&&item.tag.length<=40&&(!item.width||(Number.isFinite(item.width)&&item.width>0&&item.width<=1))&&(!item.height||(Number.isFinite(item.height)&&item.height>0&&item.height<=1)));
      setSymbolAnnotations(valid.map(item=>({x:item.x,y:item.y,kind:item.kind,tag:item.tag,width:item.width??0.04,height:item.height??0.04,reviewed:item.reviewed===true})));
      setDatasetMessage(`Restored ${valid.length} symbol annotations.`);
    }catch{setDatasetMessage("Could not restore saved symbol annotations.");}
  },[datasetStorageKey]);
  useEffect(()=>{
    if(!datasetStorageKey)return;
    try{localStorage.setItem(datasetStorageKey,JSON.stringify(symbolAnnotations));}
    catch{setDatasetMessage("Local symbol storage unavailable; export your dataset.");}
  },[datasetStorageKey,symbolAnnotations]);
  const [topologyReviews, setTopologyReviews] = useState<Record<number, "accepted" | "rejected">>({});
  const [ocrBusy, setOcrBusy] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  useEffect(() => {
    if (!file) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function focusDrawing(x=0.5,y=0.5) {
    const viewport=drawingRef.current;
    if (!viewport) return;
    viewport.scrollIntoView({behavior:"smooth",block:"center"});
    if (focusTimerRef.current !== null) window.clearTimeout(focusTimerRef.current);
    focusTimerRef.current=window.setTimeout(() => {
      const canvas=viewport.querySelector(".pid-image-canvas") as HTMLElement | null;
      if (!canvas) return;
      viewport.scrollTo({
        left:Math.max(0,x*canvas.offsetWidth-viewport.clientWidth/2),
        top:Math.max(0,y*canvas.offsetHeight-viewport.clientHeight/2),
        behavior:"smooth"
      });
    },160);
  }
  function applyDrawingZoom(next:number, x=0.5,y=0.5, screenX=0.5,screenY=0.5) {
    const viewport=drawingRef.current;
    const zoom=Math.max(0.75,Math.min(6,Math.round(next*100)/100));
    drawingZoomRef.current=zoom;
    setDrawingZoom(zoom);
    window.requestAnimationFrame(()=>{
      if (!viewport) return;
      const canvas=viewport.querySelector(".pid-image-canvas") as HTMLElement | null;
      if (!canvas) return;
      viewport.scrollLeft=Math.max(0,x*canvas.offsetWidth-screenX*viewport.clientWidth);
      viewport.scrollTop=Math.max(0,y*canvas.offsetHeight-screenY*viewport.clientHeight);
    });
  }
  function changeDrawingZoom(next:number) {
    const viewport=drawingRef.current;
    const canvas=viewport?.querySelector(".pid-image-canvas") as HTMLElement | null;
    const x=viewport && canvas ? (viewport.scrollLeft+viewport.clientWidth/2)/canvas.offsetWidth : 0.5;
    const y=viewport && canvas ? (viewport.scrollTop+viewport.clientHeight/2)/canvas.offsetHeight : 0.5;
    applyDrawingZoom(next,x,y);
  }
  useEffect(()=>{
    const viewport=drawingRef.current;
    if (!viewport || !ocr?.preview_png_base64) return;
    const onWheel=(event:WheelEvent)=>{
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const canvas=viewport.querySelector(".pid-image-canvas") as HTMLElement | null;
      if (!canvas) return;
      const rect=canvas.getBoundingClientRect();
      const vp=viewport.getBoundingClientRect();
      const x=Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width));
      const y=Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height));
      const screenX=Math.max(0,Math.min(1,(event.clientX-vp.left)/vp.width));
      const screenY=Math.max(0,Math.min(1,(event.clientY-vp.top)/vp.height));
      applyDrawingZoom(drawingZoomRef.current*Math.exp(-event.deltaY*0.008),x,y,screenX,screenY);
    };
    viewport.addEventListener("wheel",onWheel,{passive:false});
    return ()=>viewport.removeEventListener("wheel",onWheel);
  },[ocr]);
  useEffect(()=>()=>{if(focusTimerRef.current!==null)window.clearTimeout(focusTimerRef.current);},[]);
  function inspectLine(index: number) {
    const label = ocr?.line_labels?.[index];
    if (!label) return;
    setSelectedLineLabel(index);
    setLineDraft(lineCorrections[index] ?? label.tag);
    focusDrawing(label.box.x+label.box.width/2,label.box.y+label.box.height/2);
  }
  async function runOcr() {
    if (!file || ocrBusy) return;
    setOcrBusy(true); setOcrError(null); setOcr(null); setSelectedLineLabel(null); setLineReviews({}); setLineCorrections({}); setPipeAnchors({}); setPipePickMode(false); setTraceLine(null); setPipeAnchors({}); setPipePickMode(false); setSelectedCandidate(null); setReviews({}); setCorrections({}); setCandidateKinds({}); setSymbolReviews({}); setTopologyReviews({}); setSelectedTopology(null); setPathEquipment({}); setPathLineNumbers({}); setSymbolMode("off"); setSelectedVisualPath(null);
    try {
      const nextOcr = await api.ocrPidPage(file, page);
      const key = `fcc-pid-reviews-v1:${file.name}:${file.size}:${file.lastModified}:page-${nextOcr.page}:${nextOcr.candidates.map(item=>`${item.tag}@${item.box.x.toFixed(4)},${item.box.y.toFixed(4)}`).join("|")}`;
      try {
        const saved = localStorage.getItem(key);
        if (saved) {
          const parsed: unknown = JSON.parse(saved);
          if (parsed && typeof parsed === "object" && "schema_version" in parsed && parsed.schema_version === 1) {
            const data = parsed as {reviews?:Record<string,unknown>;corrections?:Record<string,unknown>;candidateKinds?:Record<string,unknown>;symbolReviews?:Record<string,unknown>};
            const validIndex = (index:string) => /^\d+$/.test(index) && Number(index)<nextOcr.candidates.length;
            const restoredReviews:Record<number,"correct"|"incorrect"> = {};
            const restoredCorrections:Record<number,string> = {};
            const restoredKinds:Record<number,"equipment"|"instrument"|"line"|"valve"|"note"|"other"> = {};
            for(const [index,value] of Object.entries(data.reviews ?? {})) if(validIndex(index) && (value==="correct"||value==="incorrect")) restoredReviews[Number(index)]=value;
            for(const [index,value] of Object.entries(data.corrections ?? {})) if(validIndex(index) && typeof value==="string" && /^[A-Z0-9][A-Z0-9 _/-]{0,39}$/.test(value)) restoredCorrections[Number(index)]=value;
            for(const [index,value] of Object.entries(data.candidateKinds ?? {})) if(validIndex(index) && (value==="equipment"||value==="instrument"||value==="line"||value==="valve"||value==="note"||value==="other")) restoredKinds[Number(index)]=value;
            const restoredSymbols:Record<number,boolean>={};
            for(const [index,value] of Object.entries(data.symbolReviews??{}))if(validIndex(index)&&value===true)restoredSymbols[Number(index)]=true;
            setReviews(restoredReviews);setCorrections(restoredCorrections);setCandidateKinds(restoredKinds);setSymbolReviews(restoredSymbols);
            setReviewStorageMessage("Previous reviews restored for this drawing and page.");
          }
        } else setReviewStorageMessage("New review session. Changes will be saved locally.");
      } catch { setReviewStorageMessage("Could not restore local reviews; starting a fresh review."); }
      setOcr(nextOcr);
    }
    catch (err) { setOcrError(err instanceof Error ? err.message : "OCR failed"); }
    finally { setOcrBusy(false); }
  }


  async function runTiledOcr(){
    if(!file||!ocr||tiledOcrBusy)return;
    setTiledOcrBusy(true);setTiledOcrMessage("Analyzing four overlapping image tiles...");
    try{
      const {result:enhanced,tiles,added,failures}=await augmentPidOcrWithTiles(file,ocr,tile=>api.ocrPidPage(tile,1));
      // Keep current manual decisions when the candidate inventory grows.
      const nextKey=`fcc-pid-reviews-v1:${file.name}:${file.size}:${file.lastModified}:page-${enhanced.page}:${enhanced.candidates.map(item=>`${item.tag}@${item.box.x.toFixed(4)},${item.box.y.toFixed(4)}`).join("|")}`;
      try{
        localStorage.setItem(nextKey,JSON.stringify({schema_version:1,reviews,corrections,candidateKinds}));
        if(edgeStorageKey){
          const previousEdges=localStorage.getItem(edgeStorageKey);
          if(previousEdges)localStorage.setItem(nextKey.replace("fcc-pid-reviews-v1:","fcc-pid-edges-v1:"),previousEdges);
        }
      }catch{setTiledOcrMessage("Review migration could not be saved; export your graph as backup.");}
      setOcr(enhanced);
      setTiledOcrMessage(`Tiled OCR: ${tiles}/4 tiles completed, ${added} additional candidates, ${failures} failed. Review all new detections manually.`);
    }catch(error){setTiledOcrMessage(error instanceof Error?error.message:"Tiled OCR failed.");}
    finally{setTiledOcrBusy(false);}
  }

  async function inspect() {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.inspectPidPdf(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Drawing inspection failed");
    } finally {
      setBusy(false);
    }
  }

  const tags = (result?.candidate_tags ?? []).filter((entry) =>
    entry.tag.toLowerCase().includes(filter.trim().toLowerCase()),
  );
  const textPages = result?.pages.filter((entry) => entry.text_available).length ?? 0;
  const isPhoto = Boolean(file && /\\.(png|jpe?g)$/i.test(file.name));
  const candidateTotal = (result?.candidate_tags.length ?? 0) + (ocr?.candidates.length ?? 0);
  const candidateAssessments=(ocr?.candidates??[]).map(assessPidCandidate);
  const knowledgeMatches=(ocr?.candidates??[]).map((item,index)=>matchPidKnowledge(corrections[index]??item.tag));
  const candidateCounts={plausible:candidateAssessments.filter(item=>item.tier==="plausible").length,uncertain:candidateAssessments.filter(item=>item.tier==="uncertain").length};
  const reviewedCount=Object.values(reviews).filter(value=>value==="correct"||value==="incorrect").length;
  const correctCount=Object.values(reviews).filter(value=>value==="correct").length;
  const rejectedCount=Object.values(reviews).filter(value=>value==="incorrect").length;
  const reviewedPrecision=reviewedCount>0?100*correctCount/reviewedCount:null;
  const graphNodes = (ocr?.candidates ?? []).flatMap((item, originalIndex) => {
    if (reviews[originalIndex] === "incorrect") return [];
    const category = candidateKinds[originalIndex] ?? "unknown";
    const reviewedLabel = corrections[originalIndex] ?? item.tag;
    const textVerified = reviews[originalIndex] === "correct";
    const symbolVerified = textVerified && symbolReviews[originalIndex]===true && category !== "unknown";
    const verified = textVerified && category !== "unknown";
    return [{
      id: `p${ocr!.page}-ocr-${originalIndex}`,
      kind: category,
      tag: reviewedLabel,
      original_tag: item.tag,
      page: ocr!.page,
      box: [item.box.x, item.box.y, item.box.width, item.box.height],
      verified,
      text_verified: textVerified,
      symbol_verified: symbolVerified,
      connectivity_verified: false,
      review_status: reviews[originalIndex] ?? "unreviewed",
      review_method: verified ? "manual_engineer_review" : null,
      source: "ocr" as const,
      confidence: item.confidence,
    }];
  });
  const visualPaths = reconstructVisualPaths(ocr?.topology?.proposals ?? [], topologyReviews);
  function saveLineStandard() {
    const name = standardName.trim();
    if (!name || name.length > 80 || !compiledLinePattern || !compiledLinePattern.test(standardExample.trim())) {
      setStandardMessage("Provide a name, valid pattern and a matching example."); return;
    }
    const next = [...savedStandards.filter(item => item.name !== name), {
      name, pattern: lineNumberPattern, example: standardExample.trim(),
    }].slice(-30);
    try { localStorage.setItem("fcc-pid-line-standards-v1", JSON.stringify(next)); }
    catch { setStandardMessage("Could not save locally."); return; }
    setSavedStandards(next); setStandardMessage("Saved locally on this device.");
  }
  function deleteLineStandard(name:string) {
    const next = savedStandards.filter(item => item.name !== name);
    try { localStorage.setItem("fcc-pid-line-standards-v1", JSON.stringify(next)); }
    catch { setStandardMessage("Could not update local storage."); return; }
    setSavedStandards(next); setStandardMessage("Profile deleted.");
  }
  const compiledLinePattern = (() => {
    if (!lineNumberPattern.trim() || lineNumberPattern.length > 160) return null;
    try { return new RegExp(lineNumberPattern, "i"); } catch { return null; }
  })();
  const lineNumberCandidates = (ocr?.line_labels ?? []).map((item, index) => ({
    index, tag: item.tag,
  })).filter(item => compiledLinePattern?.test(item.tag));
  const pipeTrace = traceLine !== null && pipeAnchors[traceLine] && ocr?.geometry
    ? traceVisualPipe(ocr.geometry.segments,pipeAnchors[traceLine],
      (ocr.topology?.proposals ?? []).filter((_,index)=>topologyReviews[index]==="accepted"))
    : null;
  const guidedAudit = traceLine !== null && ocr?.geometry && (routePoints[traceLine]?.length ?? 0)>1
    ? auditGuidedRoute(routePoints[traceLine],ocr.geometry.segments)
    : null;
  const rasterAudit = traceLine !== null && raster && (routePoints[traceLine]?.length ?? 0)>1
    ? auditRouteRaster(routePoints[traceLine],raster)
    : null;
  const centerlineLegs = traceLine !== null && raster && (routePoints[traceLine]?.length ?? 0)>1
    ? proposeCenterlineLegs(routePoints[traceLine], raster) : [];
  const activeLegReviews = traceLine === null ? {} : (centerlineReviews[traceLine] ?? {});
  const legAlignment = traceLine !== null && raster && (routePoints[traceLine]?.length ?? 0)>1
    ? auditRasterLegAlignment(routePoints[traceLine],raster)
    : null;
  const relaxedGuidedAudit = traceLine !== null && ocr?.geometry && (routePoints[traceLine]?.length ?? 0)>1
    ? auditGuidedRoute(routePoints[traceLine],ocr.geometry.segments,0.010)
    : null;
  const spatialSuggestions = suggestPathTags(visualPaths, ocr?.geometry?.segments ?? [], ocr?.line_labels ?? [])
    .filter(item => lineNumberCandidates.some(candidate => candidate.index === item.candidateIndex));
  const selectedPathKey = selectedVisualPath !== null && visualPaths[selectedVisualPath] ? visualPaths[selectedVisualPath].segmentIds.join(",") : null;
  const verifiedNodeIds=new Set(graphNodes.filter(node=>node.verified && node.kind!=="note" && node.kind!=="other").map(node=>node.id));
  const verifiedEdges=manualEdges.filter(edge=>verifiedNodeIds.has(edge.source)&&verifiedNodeIds.has(edge.target));
  const graphDraft = { schema_version: 1, read_only: true, nodes: graphNodes, edges: verifiedEdges,
    warning: "Only explicitly engineer-reviewed connections are exported. OCR and proximity do not prove topology." };
  function exportTopologyReview() {
    if (!ocr?.topology) return;
    const decisions = ocr.topology.proposals.flatMap((proposal, index) =>
      topologyReviews[index] ? [{...proposal, review: topologyReviews[index], proposal_index: index}] : []);
    const payload = {schema_version: 1, page: ocr.page, decisions,
      warning: "Human review of endpoint proximity only; not certified piping or signal connectivity."};
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url;
    link.download = `pid-topology-review-page-${ocr.page}.json`; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exportVerifiedLineLabels() {
    if (!ocr) return;
    const labels=(ocr.line_labels ?? []).map((item,index) => ({
      original_text:item.tag, reviewed_text:lineCorrections[index] ?? item.tag,
      confidence:item.confidence, box:item.box, review_status:lineReviews[index] ?? "unverified",
      source:"local_ocr", connectivity_status:"not_verified", manual_pipe_point:pipeAnchors[index] ?? null, manual_route_waypoints:routePoints[index] ?? [], association_status:pipeAnchors[index] ? "engineer_selected_point_unverified_continuity" : "not_associated",
    }));
    const payload={schema_version:1, drawing:file?.name ?? null, page:ocr.page,
      standard_name:standardName, standard_pattern:lineNumberPattern, labels,
      warning:"Engineer review of text only. No piping or instrument connectivity verified."};
    const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob);const link=document.createElement("a");
    link.href=url;link.download=`pid-reviewed-line-labels-page-${ocr.page}.json`;link.click();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function exportLineNumberAnnotations() {
    if (!ocr) return;
    const annotations = visualPaths.flatMap(path => {
      const key = path.segmentIds.join(",");
      const lineNumber = pathLineNumbers[key]?.trim();
      return lineNumber ? [{line_number: lineNumber, segment_ids: path.segmentIds,
        status: "manual_unverified_line_association"}] : [];
    });
    const payload = {schema_version: 1, page: ocr.page, line_number_pattern: lineNumberPattern,
      annotations, warning: "Line-number labels and path associations are unverified. No inferred equipment connection."};
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = `pid-line-annotations-page-${ocr.page}.json`;
    link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exportConnectivityAnnotations() {
    if (!ocr) return;
    const annotations = visualPaths.flatMap(path => {
      const key = path.segmentIds.join(",");
      const equipmentTag = pathEquipment[key]?.trim();
      return equipmentTag ? [{equipment_tag: equipmentTag, segment_ids: path.segmentIds,
        proposal_ids: path.proposalIds, status: "manual_unverified_association"}] : [];
    });
    const payload = {schema_version: 1, page: ocr.page, annotations,
      warning: "Manual visual-path associations only. No verified engineering connectivity or flow direction."};
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `pid-connectivity-annotations-page-${ocr.page}.json`;
    link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exportTrainingDataset(){
    if(!ocr||!file)return;
    const annotations=symbolAnnotations.filter(item=>item.reviewed===true).map((item,index)=>({
      id:`p${ocr.page}-training-${index}`,category:item.kind,tag:item.tag,
      bbox:{x:Math.max(0,item.x-(item.width??0.04)/2),y:Math.max(0,item.y-(item.height??0.04)/2),
        width:Math.min(item.width??0.04,1-Math.max(0,item.x-(item.width??0.04)/2)),
        height:Math.min(item.height??0.04,1-Math.max(0,item.y-(item.height??0.04)/2))},
      source:"engineer_manual",reviewed:true,
    }));
    const payload={schema_version:1,format:"fcc_symbol_detection_dataset",image:{name:file.name,size:file.size,last_modified:file.lastModified,page:ocr.page},coordinate_system:"normalized_xywh",annotations,excluded_unreviewed:symbolAnnotations.length-annotations.length,warning:"Labels are engineer-reviewed annotations; training image must be provided separately. No topology inferred."};
    const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob),link=document.createElement("a");
    link.href=url;link.download=`pid-training-dataset-page-${ocr.page}.json`;link.click();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);
    setDatasetMessage(`Exported ${annotations.length} reviewed labels; ${payload.excluded_unreviewed} unreviewed excluded.`);
  }
  function exportSymbolAnnotations() {
    if (!ocr) return;
    const payload = {schema_version: 1, page: ocr.page, symbols: symbolAnnotations.map((symbol, index) => ({
      id: `p${ocr.page}-manual-symbol-${index}`, ...symbol, source: "engineer_manual",
      status: "unverified_symbol_annotation",
    })), warning: "Manual visual annotations, not machine-recognized symbols or proven connectivity."};
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type:"application/json"});
    const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href=url; link.download=`pid-symbol-annotations-page-${ocr.page}.json`; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exportGraphDraft() {
    if (!ocr) return;
    const blob = new Blob([JSON.stringify(graphDraft, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `pid-graph-page-${ocr.page}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }


  return (
    <section className={`pid-workspace ${ocr?.preview_png_base64 ? "pid-workspace-active" : ""}`}>
      <div className="pid-intro">
        <div><span className="eyebrow">P&ID INTELLIGENCE · PHASE 1</span>
          <h2>P&ID drawing inspection</h2>
          {!ocr?.preview_png_base64 && <p>Read-only discovery of candidate tags from PDFs and photos. OCR results require verification; no diagram topology is inferred.</p>}
        </div>
        <span className="pid-readonly"><ShieldCheck size={16}/> Read-only</span>
      </div>

      <div className="pid-upload-panel">
        <FileSearch size={27}/>
        <div><strong>{file ? "Drawing source" : "Choose a P&ID PDF or photo"}</strong>{!ocr?.preview_png_base64&&<p>Local processing · PDF, PNG or JPEG up to 20 MB. Use only documents authorized for this environment.</p>}</div>
        <label className="pid-file-picker"><Upload size={16}/> Select file
          <input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setResult(null);
            setOcr(null); setSelectedLineLabel(null); setLineReviews({}); setLineCorrections({});
            setReviews({}); setTopologyReviews({}); setSelectedTopology(null);
            setOcrError(null);
            setPage(1);
            setError(null);
          }}/>
        </label>
      </div>
      {file && <div className="pid-selection"><span title={file.name}>{file.name} · {(file.size / 1048576).toFixed(2)} MB</span>
        <button type="button" className="primary-button" onClick={() => void inspect()} disabled={busy || file.size > 20 * 1048576}>
          {busy ? "Inspecting…" : "Inspect drawing"}
        </button>
      </div>}
      {error && <div role="alert" className="error-banner">{error}</div>}

      {previewUrl && <section className="pid-preview-panel">
        {!ocr?.preview_png_base64&&<div className="pid-table-head"><div><span className="pid-section-kicker">DRAWING WORKSPACE</span><h3>Prepare drawing</h3></div><span className="pid-muted">Local processing · original file unchanged</span></div>}
        {!ocr?.preview_png_base64 && <details className="pid-original-preview"><summary>View original file (optional)</summary>
          {file?.type.startsWith("image/") ? <img src={previewUrl} alt="Original P&ID drawing" className="pid-photo-preview"/> : <iframe title="Original P&ID PDF preview" src={previewUrl} className="pid-pdf-frame"/>}
        </details>}
        <div className="pid-ocr-controls">
          <label>OCR page <input type="number" min={1} max={result?.pages.length ?? 100} value={page}
            onChange={(event) => { setPage(Number(event.target.value)); setOcr(null); }}/></label>
          <button type="button" className="secondary-button" disabled={!result || ocrBusy || page < 1 || page > result.pages.length}
            onClick={() => void runOcr()}>{ocrBusy ? "Running local OCR…" : "Run local OCR on page"}</button>
          {ocr&&<button type="button" className="secondary-button" disabled={ocrBusy||tiledOcrBusy||!file||!/\.(png|jpe?g)$/i.test(file.name)} onClick={()=>void runTiledOcr()}>{tiledOcrBusy?"Scanning tiles…":"Enhance OCR · 4 image tiles"}</button>}
          {tiledOcrMessage&&<small role="status">{tiledOcrMessage}</small>}
          {!ocr?.preview_png_base64&&<small>Next step: run OCR to enable the interactive engineering canvas. Local Tesseract · no cloud processing.</small>}
        </div>
        {ocrError && <div role="alert" className="error-banner">{ocrError}</div>}
        {ocr?.preview_png_base64 && <div className="pid-annotated">
          <div className="pid-table-head pid-drawing-heading"><div><span className="pid-section-kicker">ENGINEERING CANVAS</span><h3>Drawing workspace <span className="pid-page-chip">Page {ocr.page}</span></h3></div><span className="pid-muted">Visual inspection · no automatic topology</span></div>
          <div className="pid-canvas-commandbar" role="toolbar" aria-label="Drawing navigation and layers">
            <div className="pid-canvas-commandgroup">
              <span className="pid-canvas-command-label">NAVIGATE</span>
              <button type="button" aria-label="Zoom out" title="Zoom out" onClick={()=>changeDrawingZoom(drawingZoom-0.25)} disabled={drawingZoom<=0.75}>−</button>
              <strong aria-label="Zoom level">{Math.round(drawingZoom*100)}%</strong>
              <button type="button" aria-label="Zoom in" title="Zoom in" onClick={()=>changeDrawingZoom(drawingZoom+0.25)} disabled={drawingZoom>=6}>+</button>
              <button type="button" onClick={()=>changeDrawingZoom(1)}>Fit</button>
            </div>
            <div className="pid-canvas-commandgroup">
              <span className="pid-canvas-command-label">LAYERS</span>
              <label className="pid-layer-toggle"><input type="checkbox" checked={showAllLineBoxes} onChange={event=>setShowAllLineBoxes(event.target.checked)}/> Lines</label>
              <label className="pid-layer-toggle"><input type="checkbox" checked={showEquipmentBoxes} onChange={event=>setShowEquipmentBoxes(event.target.checked)}/> Equipment</label>
            </div>
            {(pipePickMode||routeMode||endpointPick!==null)&&<span className="pid-canvas-active-mode" role="status">{endpointPick?"Select equipment junction":pipePickMode?"Select pipe on drawing":"Select successive route points"}</span>}
          </div>
          <div className="pid-canvas-inspector-layout"><div className="pid-canvas-primary">
          <div className={`pid-annotated-image ${(pipePickMode || routeMode || endpointPick!==null) ? "pid-pipe-picking" : ""}`} ref={drawingRef} onClick={event => {
            if (endpointPick) {
              if ((event.target as HTMLElement).closest("button, input, select, label")) return;
              const bounds=event.currentTarget.querySelector(".pid-image-canvas")?.getBoundingClientRect();
              if (!bounds?.width||!bounds.height)return;
              const x=Math.max(0,Math.min(1,(event.clientX-bounds.left)/bounds.width));
              const y=Math.max(0,Math.min(1,(event.clientY-bounds.top)/bounds.height));
              setEndpointReviews(prev=>({...prev,[endpointPick.key]:{equipment:prev[endpointPick.key]?.equipment??"",nozzle:prev[endpointPick.key]?.nozzle??"",side:"",point:{x,y},status:"rejected"}}));
              setEndpointPick(null);
              return;
            }
            if (suppressRouteClick.current) { suppressRouteClick.current=false; return; }
             if ((pipePickMode || routeMode) && selectedLineLabel !== null) {
              if ((event.target as HTMLElement).closest("button")) return;
              const canvas=event.currentTarget.querySelector(".pid-image-canvas");
              const bounds=canvas?.getBoundingClientRect();
              if (!bounds?.width || !bounds.height) return;
              const x=Math.max(0,Math.min(1,(event.clientX-bounds.left)/bounds.width));
              const y=Math.max(0,Math.min(1,(event.clientY-bounds.top)/bounds.height));
              if (routeMode) {
                const existing = routePoints[selectedLineLabel] ?? [];
                const last = existing[existing.length-1];
                if (last) {
                  const dx=Math.abs(last.x-x),dy=Math.abs(last.y-y);
                  const nearHorizontal=dy<=Math.max(0.012,dx*0.045);
                  const nearVertical=dx<=Math.max(0.012,dy*0.045);
                  if (!nearHorizontal && !nearVertical) {
                    setRouteWarning("Diagonal route blocked. Select the actual elbow/corner first; a pipe crossing is not a connection.");
                    return;
                  }
                }
                setRoutePoints(previous=>({...previous,[selectedLineLabel]:[...(previous[selectedLineLabel]??[]),{x,y}]}));
                setRouteWarning("");
              }
              else {setPipeAnchors(previous=>({...previous,[selectedLineLabel]:{x,y}}));setPipePickMode(false);}
              return;
            }
            if (symbolMode === "off") return;
            if (event.target !== event.currentTarget && (event.target as HTMLElement).closest("button")) return;
            const bounds = (event.currentTarget.querySelector(".pid-image-canvas") ?? event.currentTarget).getBoundingClientRect();
            if (!bounds.width || !bounds.height) return;
            const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
            const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
            setSymbolAnnotations(previous => [...previous, {x, y, kind: symbolMode, tag:""}]);
          }}>

            <div className="pid-image-canvas" style={{width:`${drawingZoom*100}%`}}>
            <img alt={`Rendered P&ID page ${ocr.page} for visual OCR verification`} src={`data:image/png;base64,${ocr.preview_png_base64}`}/>
            {Object.entries(targetTraceProposals).filter(([,proposal])=>proposal.status!=="rejected").map(([key,proposal])=><svg key={`target-${key}`} className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" style={{pointerEvents:"none"}}>
              <polyline points={proposal.points.map(p=>`${p.x*1000},${p.y*1000}`).join(" ")} stroke={proposal.status==="approved"?"#16a34a":"#a855f7"} strokeWidth="4" strokeDasharray="8 5" fill="none"/>
            </svg>)}
            {Object.entries(endpointReviews).filter(([,review])=>review.point).map(([key,review])=><svg key={key} className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" style={{pointerEvents:"none"}}>
              <circle cx={review.point!.x*1000} cy={review.point!.y*1000} r="7" fill={review.status==="confirmed"?"#16a34a":"#f59e0b"} stroke="white" strokeWidth="2"/>
            </svg>)}
            {inspectedBranch && inspectedBranch.line===selectedLineLabel && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label={`Selected branch candidate ${inspectedBranch.index}`} style={{pointerEvents:"none",overflow:"visible"}}>
              <circle cx={inspectedBranch.x*1000} cy={inspectedBranch.y*1000} r="22" fill="#facc15" fillOpacity="0.28" stroke="#facc15" strokeWidth="5" vectorEffect="non-scaling-stroke"/>
              <circle cx={inspectedBranch.x*1000} cy={inspectedBranch.y*1000} r="5" fill="#ef4444" stroke="#ffffff" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
              <line x1={inspectedBranch.x*1000-35} y1={inspectedBranch.y*1000} x2={inspectedBranch.x*1000+35} y2={inspectedBranch.y*1000} stroke="#facc15" strokeWidth="2.5" vectorEffect="non-scaling-stroke"/>
              <line x1={inspectedBranch.x*1000} y1={inspectedBranch.y*1000-35} x2={inspectedBranch.x*1000} y2={inspectedBranch.y*1000+35} stroke="#facc15" strokeWidth="2.5" vectorEffect="non-scaling-stroke"/>
              <text x={Math.min(940,inspectedBranch.x*1000+26)} y={Math.max(40,inspectedBranch.y*1000-28)} fontSize="24" fontWeight="bold" fill="#facc15" stroke="#102638" strokeWidth="4" paintOrder="stroke">#{inspectedBranch.index}</text>
            </svg>}
            {showGeometry && ocr.geometry && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Unverified visual line segments">
              {ocr.geometry.segments.filter(segment => includeTitleBlock || segment.region_hint !== "title_block_candidate").map((segment, index) => <line key={index}
                x1={segment.x1 * 1000} y1={segment.y1 * 1000}
                x2={segment.x2 * 1000} y2={segment.y2 * 1000}
                stroke="#00b8ff" strokeWidth="1.5" vectorEffect="non-scaling-stroke" opacity="0.8" />)}
            </svg>}
            {autoTracePreview && autoTracePreview.line===selectedLineLabel && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Experimental raster auto trace preview" style={{pointerEvents:"none"}}>
              {autoTracePreview.paths.map((path,index)=><polyline key={index} points={path.map(p=>`${p.x*1000},${p.y*1000}`).join(" ")} stroke="#f59e0b" strokeWidth="4" strokeDasharray="8 5" fill="none" vectorEffect="non-scaling-stroke"/>)}
              {autoTracePreview.shadowPaths.map((path,index)=>autoTracePreview.shadowReviews[index]!=="rejected"&&<polyline key={`shadow-${index}`} points={path.map(p=>`${p.x*1000},${p.y*1000}`).join(" ")} stroke={autoTracePreview.shadowReviews[index]==="approved"?"#22c55e":"#38bdf8"} strokeWidth="3" strokeDasharray="3 6" fill="none" opacity="0.9" vectorEffect="non-scaling-stroke"/>)}
            </svg>}
            {traceLine !== null && pipeAnchors[traceLine] && (routePoints[traceLine]?.length ?? 0)>0 && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Engineer-guided pipe route">
              <polyline points={(routePoints[traceLine]??[]).map(p=>String(p.x*1000)+","+String(p.y*1000)).join(" ")} stroke="#22c55e" strokeWidth="5" fill="none" vectorEffect="non-scaling-stroke" strokeLinejoin="round"/>
              {(routePoints[traceLine]??[]).map((p,i)=><circle key={i} cx={p.x*1000} cy={p.y*1000} r="8" fill={dragRoutePoint===i ? "#facc15" : "#22c55e"} stroke="#065f46" strokeWidth="1.5" style={{pointerEvents:"all",cursor:"grab",touchAction:"none"}} onPointerDown={event=>{event.stopPropagation();suppressRouteClick.current=true;setDragRoutePoint(i);event.currentTarget.setPointerCapture(event.pointerId);}} onPointerMove={event=>{if(dragRoutePoint!==i)return;const bounds=drawingRef.current?.querySelector(".pid-image-canvas")?.getBoundingClientRect();if(!bounds?.width||!bounds.height)return;const x=Math.max(0,Math.min(1,(event.clientX-bounds.left)/bounds.width));const y=Math.max(0,Math.min(1,(event.clientY-bounds.top)/bounds.height));setRoutePoints(previous=>({...previous,[traceLine]:(previous[traceLine]??[]).map((point,j)=>j===i?{x,y}:point)}));}} onPointerUp={event=>{event.stopPropagation();setDragRoutePoint(null);if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);}} onPointerCancel={()=>setDragRoutePoint(null)}/>)}
            </svg>}
            {showCenterlineCandidates && centerlineLegs.length>0 && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Proposed centerline offsets, not accepted">
              {centerlineLegs.filter(leg=>leg.eligible && activeLegReviews[leg.index] !== "rejected").map(leg=><line key={leg.index} x1={leg.start.x*1000} y1={leg.start.y*1000} x2={leg.end.x*1000} y2={leg.end.y*1000} stroke={activeLegReviews[leg.index] === "accepted" ? "#38bdf8" : "#a78bfa"} strokeWidth={selectedCenterlineLeg === leg.index ? "5" : "3"} strokeDasharray="7 5" vectorEffect="non-scaling-stroke"/>)}
            </svg>}
            {guidedAudit && traceLine !== null && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Unmatched guided-route samples">
              {guidedAudit.unmatched.map((p,i)=><circle key={i} cx={p.x*1000} cy={p.y*1000} r="2.5" fill="#f97316" opacity="0.95"/>)}
            </svg>}
            {pipeTrace && ocr.geometry && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Provisional visual pipe trace">
              {pipeTrace.segments.map(id=>{const segment=ocr.geometry!.segments[id];return segment ? <line key={id}
                x1={segment.x1*1000} y1={segment.y1*1000} x2={segment.x2*1000} y2={segment.y2*1000}
                stroke="#e11d48" strokeWidth="5" vectorEffect="non-scaling-stroke" opacity=".85"/> : null;})}
            </svg>}
            {selectedTopology !== null && ocr.topology && ocr.geometry && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Selected endpoint proposal">
              {[ocr.topology.proposals[selectedTopology]?.segment_a, ocr.topology.proposals[selectedTopology]?.segment_b].filter((id): id is number => id !== undefined).map((id, index) => {
                const segment = ocr.geometry!.segments[id];
                return segment ? <line key={id} x1={segment.x1*1000} y1={segment.y1*1000} x2={segment.x2*1000} y2={segment.y2*1000}
                  stroke={index === 0 ? "#ff9d00" : "#ff2d88"} strokeWidth="4" vectorEffect="non-scaling-stroke"/> : null;
              })}
            </svg>}
            {selectedVisualPath !== null && ocr.geometry && visualPaths[selectedVisualPath] && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Selected visual path">
              {visualPaths[selectedVisualPath].segmentIds.map(id => {
                const segment = ocr.geometry!.segments[id];
                return segment ? <line key={id} x1={segment.x1*1000} y1={segment.y1*1000} x2={segment.x2*1000} y2={segment.y2*1000} stroke="#00d9a6" strokeWidth="5" vectorEffect="non-scaling-stroke"/> : null;
              })}
            </svg>}
            {(ocr.line_labels ?? []).map((item,index) => {
              if (!showAllLineBoxes && selectedLineLabel !== index) return null;
              const active = selectedLineLabel === index;
              return <button key={`line-${index}`} type="button"
                title={`Line OCR: ${item.tag} · ${item.confidence.toFixed(0)}% · ${lineReviews[index] ?? "unverified"}`}
                aria-label={`Review line number ${item.tag}`}
                onClick={() => inspectLine(index)}
                className={`pid-line-box ${active ? "pid-line-box-active" : ""}`}
                style={{left:`${item.box.x*100}%`,top:`${item.box.y*100}%`,
                  width:`${Math.max(item.box.width*100,0.7)}%`,height:`${Math.max(item.box.height*100,0.7)}%`}} />;
            })}
            {Object.entries(pipeAnchors).map(([index,point]) => <span key={index} className="pid-pipe-anchor"
              style={{left:`${point.x*100}%`,top:`${point.y*100}%`}}
              title={`Engineer-selected pipe location for line OCR #${Number(index)+1}`}>+</span>)}
            {symbolProposals.map((proposal,index)=><button type="button" key={index} className="pid-symbol-proposal" style={{left:`${proposal.x*100}%`,top:`${proposal.y*100}%`}} title={`Unverified circular symbol proposal · ${Math.round(proposal.score*100)}% geometry score`} aria-label={`Review proposed instrument bubble ${index+1}`} onClick={()=>{setSymbolAnnotations(previous=>[...previous,{x:proposal.x,y:proposal.y,kind:"instrument",tag:""}]);setSymbolProposals(previous=>previous.filter((_,i)=>i!==index));}}>?</button>)}
            {symbolAnnotations.map((symbol, index) => <span key={index} className="pid-manual-symbol" style={{left:`${symbol.x*100}%`,top:`${symbol.y*100}%`}} title={`Manual ${symbol.kind}: ${symbol.tag || "unlabeled"}`}>{symbol.kind === "valve" ? "V" : symbol.kind === "instrument" ? "I" : symbol.kind === "connector" ? "C" : "E"}</span>)}
            {showEquipmentBoxes && ocr.candidates.map((item,index) => <button key={index} type="button"
              title={`${item.tag} · OCR ${item.confidence.toFixed(0)}% · not verified`}
              aria-label={`Inspect candidate ${item.tag}`}
              onClick={() => {setSelectedCandidate(index); setDraftTag(corrections[index] ?? item.tag);}}
              className={`pid-ocr-box ${selectedCandidate === index ? "pid-ocr-box-active" : ""}`}
              style={{left:`${item.box.x*100}%`,top:`${item.box.y*100}%`,width:`${Math.max(item.box.width*100,0.5)}%`,height:`${Math.max(item.box.height*100,0.5)}%`}} />)}
            </div>
          </div>
          </div>
          <aside className="pid-context-inspector" aria-label="P&ID object inspector">
            <div className="pid-inspector-heading"><span className="pid-section-kicker">OBJECT INSPECTOR</span><h3>Engineering review</h3><small>Manual verification · read-only drawing</small></div>
            <div className="pid-inspector-block">
              <span className="pid-inspector-label">Current selection</span>
              {selectedCandidate !== null && ocr.candidates[selectedCandidate] ? <>
                <strong>{corrections[selectedCandidate] || ocr.candidates[selectedCandidate].tag}</strong>
                <small>OCR candidate · {ocr.candidates[selectedCandidate].confidence.toFixed(0)}% confidence</small>
                <small>Candidate triage: {candidateAssessments[selectedCandidate]?.tier} · {candidateAssessments[selectedCandidate]?.reasons.join("; ")}</small>
                <span className="pid-inspector-label">Engineering knowledge hints</span>
                {knowledgeMatches[selectedCandidate]?.length ? knowledgeMatches[selectedCandidate].map(match=><small key={match.id}><strong>{match.label}</strong> · {match.reason} Source: {match.reference}. Pattern match only; not verified.</small>) : <small>No engineering pattern match. Check the drawing legend and original image.</small>}
                <span className="pid-inspector-state">{reviews[selectedCandidate] ?? "Unverified OCR"}</span>
                <label className="pid-inspector-label" htmlFor="pid-inspector-kind">Object category</label>
                <select id="pid-inspector-kind" value={candidateKinds[selectedCandidate] ?? ""} onChange={event=>{
                  const kind=event.target.value as "equipment"|"instrument"|"line"|"valve"|"note"|"other"|"";
                  setCandidateKinds(previous=>{const next={...previous};if(kind)next[selectedCandidate]=kind;else delete next[selectedCandidate];return next;});
                  setReviews(previous=>{const next={...previous};delete next[selectedCandidate];return next;});
                  setSymbolReviews(previous=>{const next={...previous};delete next[selectedCandidate];return next;});
                }}>
                  <option value="">Select category...</option>
                  <option value="equipment">Equipment</option><option value="instrument">Instrument</option><option value="line">Line number</option><option value="valve">Valve</option><option value="note">Drawing note</option><option value="other">Other / unknown</option>
                </select>
                <label className="pid-inspector-label" htmlFor="pid-inspector-tag">Reviewed label</label>
                <input id="pid-inspector-tag" aria-label="Reviewed OCR label" maxLength={40} value={draftTag} onChange={event=>setDraftTag(event.target.value.toUpperCase())}/>
                <button type="button" disabled={!/^[A-Z0-9][A-Z0-9 _/-]{0,39}$/.test(draftTag.trim())} onClick={()=>{
                  setCorrections(previous=>({...previous,[selectedCandidate]:draftTag.trim()}));
                  setSymbolReviews(previous=>({...previous,[selectedCandidate]:false}));
                  setReviews(previous=>{const next={...previous};delete next[selectedCandidate];return next;});
                }}>Save reviewed label</button>
                <div className="pid-inspector-review-actions">
                  <button type="button" disabled={!candidateKinds[selectedCandidate] || !/^[A-Z0-9][A-Z0-9 _/-]{0,39}$/.test((corrections[selectedCandidate]??ocr.candidates[selectedCandidate].tag).trim()) || draftTag.trim() !== (corrections[selectedCandidate]??ocr.candidates[selectedCandidate].tag).trim()} onClick={()=>setReviews(previous=>({...previous,[selectedCandidate]:"correct"}))}>Confirm label</button>
                  <button type="button" onClick={()=>{setReviews(previous=>({...previous,[selectedCandidate]:"incorrect"}));setSymbolReviews(previous=>({...previous,[selectedCandidate]:false}));}}>Reject</button>
                </div>
                <label className="pid-inspector-symbol-review"><input type="checkbox" checked={symbolReviews[selectedCandidate]===true} disabled={reviews[selectedCandidate]!=="correct"||!candidateKinds[selectedCandidate]} onChange={event=>setSymbolReviews(previous=>({...previous,[selectedCandidate]:event.target.checked}))}/> Symbol verified against the original drawing and plant legend</label>
                <small>Text verified: {reviews[selectedCandidate]==="correct"?"Yes":"No"} · Symbol verified: {reviews[selectedCandidate]==="correct"&&symbolReviews[selectedCandidate]?"Yes":"No"} · Connectivity verified: No (requires independent edge review).</small>
                <small>Category and label are reviewed independently. Confirmation applies only to the OCR label, not piping connectivity.</small>
              </> : selectedVisualPath !== null && visualPaths[selectedVisualPath] ? <>
                <strong>Visual path {selectedVisualPath + 1}</strong>
                <small>{visualPaths[selectedVisualPath].segmentIds.length} raster segments</small>
                <span className="pid-inspector-state">Connectivity unverified</span>
              </> : <><strong>No object selected</strong><small>Choose an OCR box or a visual path to inspect its evidence.</small></>}
            </div>
            <div className="pid-inspector-block"><span className="pid-inspector-label">Drawing evidence</span>
              <small>{ocr.candidates.length} OCR candidates · {ocr.geometry?.segments.length ?? 0} raster segments</small>
              <small>Geometry and OCR alone do not prove a piping connection.</small>
              <small role="status">{reviewStorageMessage}</small>
            </div>
            <div className="pid-inspector-block">
              <span className="pid-inspector-label">Quick selection</span>
              <button type="button" onClick={()=>setShowEquipmentBoxes(previous=>!previous)}>{showEquipmentBoxes?"Hide":"Show"} equipment boxes</button>
              <button type="button" onClick={()=>setShowAllLineBoxes(previous=>!previous)}>{showAllLineBoxes?"Hide":"Show"} line boxes</button>
              {selectedCandidate!==null&&<button type="button" onClick={()=>{setSelectedCandidate(null);setDraftTag("");}}>Clear OCR selection</button>}
            </div>
            <p className="pid-inspector-footnote">Advanced engineering tools below contain tracing, topology proposals and export controls. No connection is verified automatically.</p>
          </aside></div>
          {selectedCandidate !== null && ocr.candidates[selectedCandidate] && <div className="pid-ocr-selection">
            Candidate: <strong>{ocr.candidates[selectedCandidate].tag}</strong> · OCR confidence {ocr.candidates[selectedCandidate].confidence.toFixed(0)}% · Requires engineer verification
          </div>}
        </div>}
        {ocr && selectedLineLabel !== null && ocr.line_labels?.[selectedLineLabel] && <div className="pid-review-panel" ref={lineReviewRef}>
          <strong>Line number visual verification · {ocr.line_labels[selectedLineLabel].tag}</strong>
          <small>OCR confidence {ocr.line_labels[selectedLineLabel].confidence.toFixed(0)}%. Format matching alone does not verify the text or piping connection.</small>
          <label>Corrected line number
            <input aria-label="Corrected line number" maxLength={80} value={lineDraft}
              onChange={event => setLineDraft(event.target.value.toUpperCase())}/>
          </label>
          <small>{!lineDraft.trim() ? "Enter a line number to enable confirmation." : compiledLinePattern && !compiledLinePattern.test(lineDraft.trim()) ? "Line number does not match the active site standard. Correct the text or update the standard." : !compiledLinePattern ? "No active line-number standard: manual text verification is available." : "Line number matches the active standard; confirm it after visually checking the drawing."}</small>
          <div className="pid-review-actions">
            <button type="button" disabled={!lineDraft.trim() || Boolean(compiledLinePattern && !compiledLinePattern.test(lineDraft.trim()))} onClick={() => {
              const value=lineDraft.trim();
              setLineCorrections(previous => ({...previous,[selectedLineLabel]:value}));
              setLineReviews(previous => ({...previous,[selectedLineLabel]:"correct"}));
            }}>Confirm / save correction</button>
            <button type="button" onClick={() => setLineReviews(previous => ({...previous,[selectedLineLabel]:"rejected"}))}>Reject</button>
            <button type="button" onClick={() => {
              setLineReviews(previous => {const next={...previous};delete next[selectedLineLabel];return next;});
              setLineCorrections(previous => {const next={...previous};delete next[selectedLineLabel];return next;});
            }}>Clear review</button>
          </div>
          {lineReviews[selectedLineLabel] !== "correct" && <small>To select a pipe, first press Confirm / save correction above. Current status: {lineReviews[selectedLineLabel] ?? "unverified"}.</small>}
          <div className="pid-review-actions">
            <button type="button" title={lineReviews[selectedLineLabel] !== "correct" ? "Confirm the line number first" : "Select a point on the actual pipe"} disabled={lineReviews[selectedLineLabel] !== "correct"} onClick={() => {
              setPipePickMode(true);
              const label=ocr.line_labels?.[selectedLineLabel];
              focusDrawing(label ? label.box.x+label.box.width/2 : 0.5,label ? label.box.y+label.box.height/2 : 0.5);
            }}>Select pipe location on drawing</button>
            <button type="button" disabled={!pipeAnchors[selectedLineLabel]} onClick={() => {
              setPipeAnchors(previous=>{const next={...previous};delete next[selectedLineLabel];return next;});
              setPipePickMode(false);
            }}>Clear pipe location</button>
          </div>
          <div className="pid-review-note">
            <strong>Experimental automatic raster trace · preview only</strong>
            <p>First select a seed point on the actual pipe. This attempts to follow nearby straight dark strokes without manual route clicks. It stops at uncertainty and does not assign connectivity or flow direction.</p>
            <button type="button" disabled={!raster || !pipeAnchors[selectedLineLabel]} onClick={()=>{const seed=pipeAnchors[selectedLineLabel];if(!seed||!raster)return;const result=traceRasterFromSeed(raster,seed);setAutoTracePreview({line:selectedLineLabel,paths:result.paths,stopReasons:result.stopReasons,shadowPaths:result.shadowPaths??[],shadowReviews:{}});setTraceLine(selectedLineLabel);setRouteMode(false);focusDrawing(seed.x,seed.y);}}>Preview automatic raster trace</button>
            <button type="button" disabled={!autoTracePreview} onClick={()=>setAutoTracePreview(null)}>Clear automatic preview</button>
            {autoTracePreview?.line===selectedLineLabel&&<details className="pid-technical-details"><summary>Trace diagnostics · {autoTracePreview.paths.length} provisional strokes</summary><p>{autoTracePreview.stopReasons.join("; ")||"No confident strokes found; reposition the seed on a clear straight section."} Orange dashed strokes are not a verified pipe route.</p></details>}
            {autoTracePreview?.line===selectedLineLabel&&autoTracePreview.shadowPaths.length>0&&<div className="pid-trace-review">
              <h3>Review traced segments <span className="pid-review-count">{autoTracePreview.shadowPaths.filter((_,i)=>autoTracePreview.shadowReviews[i]==="approved").length}/{autoTracePreview.shadowPaths.length} reviewed</span></h3>
              <p>Blue dotted paths are raster-only hypotheses. Approve records a visual review, not equipment connectivity or flow direction.</p>
              {autoTracePreview.shadowPaths.map((path,index)=><div className={`pid-candidate-card pid-candidate-${autoTracePreview.shadowReviews[index]??"pending"}`} key={index}>
                <span className="pid-candidate-label"><strong>Segment {index+1}</strong><small>{path.length} sampled points · {autoTracePreview.shadowReviews[index]==="approved"?"Visually approved":autoTracePreview.shadowReviews[index]==="rejected"?"Rejected":"Awaiting review"}</small></span>
                {autoTracePreview.shadowReviews[index]!=="approved"&&<button type="button" className="pid-action-primary" onClick={()=>setAutoTracePreview(previous=>previous?{...previous,shadowReviews:{...previous.shadowReviews,[index]:"approved"}}:previous)}>Approve segment</button>}
                {autoTracePreview.shadowReviews[index]!=="rejected"&&<button type="button" onClick={()=>setAutoTracePreview(previous=>previous?{...previous,shadowReviews:{...previous.shadowReviews,[index]:"rejected"}}:previous)}>{autoTracePreview.shadowReviews[index]==="approved"?"Revoke approval":"Reject"}</button>}
                {autoTracePreview.shadowReviews[index]==="rejected"&&<button type="button" onClick={()=>setAutoTracePreview(previous=>previous?{...previous,shadowReviews:{...previous.shadowReviews,[index]:"pending"}}:previous)}>Review again</button>}
              </div>)}
              <div className="pid-endpoint-section">
                <h4>Equipment endpoint review · manual verification</h4>
                <p>Candidate endpoints are visual observations only. Enter the equipment tag and select the exact junction on the drawing. Nozzle ID is optional when absent from the drawing. This is a manual visual review, not verified topology.</p>
                {autoTracePreview.shadowPaths.map((candidate,index)=>{
                  if(autoTracePreview.shadowReviews[index]!=="approved"||candidate.length<2)return null;
                  const tip=candidate[candidate.length-1];
                  const key=`${ocr?.page??0}:${autoTracePreview.line}:${Math.round(tip.x*10000)}:${Math.round(tip.y*10000)}`;
                  const review=endpointReviews[key];
                  // Pixel-space distance to the *selected* candidate, not to unrelated strokes.
                  const point=review?.point;
                  const distanceToSegment=(p:{x:number;y:number},a:{x:number;y:number},b:{x:number;y:number})=>{
                    const width=raster?.width??1000,height=raster?.height??1000;
                    const vx=(b.x-a.x)*width,vy=(b.y-a.y)*height;
                    const wx=(p.x-a.x)*width,wy=(p.y-a.y)*height;
                    const t=Math.max(0,Math.min(1,(wx*vx+wy*vy)/(vx*vx+vy*vy||1)));
                    return Math.hypot(wx-t*vx,wy-t*vy);
                  };
                  const gapPx=point?Math.min(...candidate.slice(1).map((p,i)=>distanceToSegment(point,candidate[i],p))):null;
                  const tipGapPx=point&&raster?Math.hypot((point.x-tip.x)*raster.width,(point.y-tip.y)*raster.height):null;
                  return <div className="pid-endpoint-card" key={key}>
                    <label>Candidate {index+1} endpoint ({Math.round(tip.x*1000)}, {Math.round(tip.y*1000)})
                      <input aria-label={`Equipment tag for candidate ${index+1}`} placeholder="Equipment tag (e.g. M-4252)" value={review?.equipment??""}
                        onChange={event=>setEndpointReviews(prev=>({...prev,[key]:{equipment:event.target.value,nozzle:prev[key]?.nozzle??"",side:"",point:prev[key]?.point,status:"rejected"}}))}/>
                    </label>
                    <label>Nozzle / connection reference (optional)
                      <input aria-label={`Nozzle reference for candidate ${index+1}`} placeholder="Nozzle ID from drawing" value={review?.nozzle??""}
                        onChange={event=>setEndpointReviews(prev=>({...prev,[key]:{equipment:prev[key]?.equipment??"",nozzle:event.target.value,side:"",point:prev[key]?.point,status:"rejected"}}))}/>
                    </label>
                    <button type="button" onClick={()=>{setEndpointPick({key,index});setPipePickMode(false);setRouteMode(false);}}>Select connection point on drawing</button>
                    {endpointPick?.key===key&&<span>Click the junction on the P&amp;ID (zoom first if needed).</span>}
                    {review?.point&&<span>Selected point: ({Math.round(review.point.x*1000)}, {Math.round(review.point.y*1000)})</span>}
                    {gapPx!==null&&<div role="status">
                      <strong>Endpoint geometry audit (preview only):</strong> closest distance to Candidate {index+1}: {gapPx.toFixed(1)} px; distance to candidate tip: {tipGapPx===null?"unknown":tipGapPx.toFixed(1)+" px"}.
                      {gapPx<=8?" Visual proximity detected; this does not prove a physical connection.":" Gap detected: candidate does not reach the inspected junction. Extend or correct the trace before verifying connectivity."}
                    </div>}
                    {review?.point&&gapPx!==null&&gapPx>8&&<button type="button" disabled={!raster} onClick={()=>{
                      if(!raster||!review.point)return;
                      // Conservative first pass: straight horizontal/vertical segment with ink evidence.
                      // A diagonal or unsupported gap is never silently bridged.
                      const start=tip,end=review.point;
                      const dx=(end.x-start.x)*raster.width,dy=(end.y-start.y)*raster.height;
                      const length=Math.hypot(dx,dy);
                      const aligned=Math.min(Math.abs(dx),Math.abs(dy))<=Math.max(5,length*0.04);
                      const steps=Math.max(2,Math.ceil(length/3));
                      let supported=0;
                      for(let i=0;i<=steps;i++){
                        const x=Math.round((start.x+(end.x-start.x)*i/steps)*raster.width);
                        const y=Math.round((start.y+(end.y-start.y)*i/steps)*raster.height);
                        let ink=false;
                        for(let oy=-2;oy<=2&&!ink;oy++)for(let ox=-2;ox<=2;ox++){
                          const xx=x+ox,yy=y+oy;
                          if(xx<0||yy<0||xx>=raster.width||yy>=raster.height)continue;
                          const at=(yy*raster.width+xx)*4;
                          const d=raster.data;
                          if((d[at]+d[at+1]+d[at+2])/3<155&&d[at+3]>150){ink=true;break;}
                        }
                        if(ink)supported++;
                      }
                      const support=supported/(steps+1);
                      if(aligned&&length>=8&&support>=0.7){
                        setTargetTraceProposals(prev=>({...prev,[key]:{points:[start,end],support,status:"proposed"}}));
                      }else{
                        setTargetTraceProposals(prev=>{const next={...prev};delete next[key];return next;});
                        setRouteWarning(`Target trace not proposed: ${!aligned?"not axis-aligned":`insufficient raster ink (${Math.round(support*100)}%)`}. Review the drawing manually.`);
                      }
                    }}>Propose ink-supported extension to selected point</button>}
                    {targetTraceProposals[key]&&<div>
                      <span>Target extension: {Math.round(targetTraceProposals[key].support*100)}% raster ink support — {targetTraceProposals[key].status}; visual hypothesis only.</span>
                      <button type="button" onClick={()=>setTargetTraceProposals(prev=>({...prev,[key]:{...prev[key],status:"approved"}}))}>Approve visual extension</button>
                      <button type="button" onClick={()=>setTargetTraceProposals(prev=>({...prev,[key]:{...prev[key],status:"rejected"}}))}>Reject extension</button>
                    </div>}
                    <button type="button" disabled={!review?.equipment.trim()||!review?.point} onClick={()=>setEndpointReviews(prev=>({...prev,[key]:{equipment:prev[key].equipment.trim(),nozzle:prev[key].nozzle.trim(),side:"",point:prev[key].point,status:"confirmed"}}))}>Confirm inspected endpoint</button>
                    <button type="button" onClick={()=>setEndpointReviews(prev=>({...prev,[key]:{equipment:prev[key]?.equipment??"",nozzle:prev[key]?.nozzle??"",side:"",point:prev[key]?.point,status:"rejected"}}))}>Reject endpoint</button>
                    <span>{review?.status==="confirmed"?`Inspected: ${review.equipment} / point (${Math.round(review.point!.x*1000)}, ${Math.round(review.point!.y*1000)})${review.nozzle?` / nozzle ${review.nozzle}`:""} (not exported as connectivity)`:"Not confirmed"}</span>
                  </div>;
                })}
              </div>
              <button type="button" disabled={!raster||!autoTracePreview.shadowPaths.some((path,index)=>autoTracePreview.shadowReviews[index]==="approved"&&path.length>1)}
                onClick={()=>{
                  if(!raster||!autoTracePreview)return;
                  const existing=autoTracePreview;
                  const approved=existing.shadowPaths.filter((path,index)=>existing.shadowReviews[index]==="approved"&&path.length>1);
                  const extraPaths:Array<Array<{x:number;y:number}>>=[];
                  const extraShadows:Array<Array<{x:number;y:number}>>=[];
                  const reasons:string[]=[];
                  const near=(a:{x:number;y:number},b:{x:number;y:number},px=12)=>
                    Math.hypot((a.x-b.x)*raster.width,(a.y-b.y)*raster.height)<=px;
                  // A candidate must extend the reviewed shadow in its outgoing
                  // direction, rather than rediscovering the already traced pipe.
                  const projection=(origin:{x:number;y:number},p:{x:number;y:number},dx:number,dy:number)=>
                    (p.x-origin.x)*raster.width*dx+(p.y-origin.y)*raster.height*dy;
                  const known=[...existing.paths,...existing.shadowPaths];
                  const overlapsKnown=(candidate:Array<{x:number;y:number}>)=>{
                    const samples=candidate.filter((_,i)=>i%3===0);
                    return samples.length>0&&samples.filter(p=>known.some(path=>path.some(q=>near(p,q,5)))).length/samples.length>0.65;
                  };
                  const seenEnds:Array<{x:number;y:number}>=[];
                  for(const path of approved){
                    const end=path[path.length-1];
                    if(seenEnds.some(p=>near(p,end,12)))continue;
                    seenEnds.push(end);
                    const prev=path[Math.max(0,path.length-5)];
                    const vx=(end.x-prev.x)*raster.width,vy=(end.y-prev.y)*raster.height;
                    const mag=Math.hypot(vx,vy);
                    if(mag<3)continue;
                    const dx=vx/mag,dy=vy/mag;
                    const next=traceRasterFromSeed(raster,end);
                    for(const candidate of next.paths){
                      if(candidate.length<3)continue;
                      const first=candidate[0],last=candidate[candidate.length-1];
                      const oriented=near(last,end,8)&&!near(first,end,8)?[...candidate].reverse():candidate;
                      const progress=projection(end,oriented[oriented.length-1],dx,dy);
                      if(progress<20||overlapsKnown(oriented)||extraPaths.some(p=>near(p[p.length-1],oriented[oriented.length-1],12)))continue;
                      extraPaths.push(oriented);
                    }
                    for(const shadow of next.shadowPaths??[]){
                      if(shadow.length<3)continue;
                      const tip=shadow[shadow.length-1];
                      if(projection(end,tip,dx,dy)<20||known.some(p=>near(p[p.length-1],tip,12))||
                        extraShadows.some(p=>near(p[p.length-1],tip,12)))continue;
                      extraShadows.push(shadow);
                    }
                  }
                  reasons.push(extraPaths.length||extraShadows.length?
                    "Forward-only visual candidates added; all remain unverified.":
                    "No new forward continuation beyond already reviewed geometry; stopped to prevent duplicate loops.");
                  setAutoTracePreview({...existing,paths:[...existing.paths,...extraPaths],shadowPaths:[...existing.shadowPaths,...extraShadows],stopReasons:[...existing.stopReasons,...reasons]});
                }}>Continue from approved endpoints (preview only)</button>
              <details className="pid-technical-details"><summary>About continuation and validation</summary><p>Continuation is a fresh, unverified raster preview. Inspect new strokes before approving; no connectivity or flow direction is inferred.</p></details>
              {/* Detailed technical explanation is available above. */}
              <div style={{display:"none"}}>Continuation is a fresh, unverified raster preview.</div>
              <p style={{display:"none"}}>Continuation is a fresh, unverified raster preview. Inspect new strokes before approving; no connectivity or flow direction is inferred.</p>
              <p>Reviews are temporary for this preview and are not saved as verified connectivity.</p>
            </div>}
          </div>
          <div className="pid-review-actions">
            <button type="button" disabled={!pipeAnchors[selectedLineLabel] || !ocr.geometry?.segments.length}
              onClick={()=>{setTraceLine(selectedLineLabel);const point=pipeAnchors[selectedLineLabel];if(point)focusDrawing(point.x,point.y);}}>Trace visual pipe (provisional)</button>
            <button type="button" disabled={traceLine===null} onClick={()=>{setTraceLine(null);setRouteMode(false);}}>Clear visual trace</button>
          </div>
          <div className="pid-review-actions">
            <button type="button" disabled={!pipeAnchors[selectedLineLabel]} onClick={()=>{setTraceLine(selectedLineLabel);setRoutePoints(previous=>({...previous,[selectedLineLabel]:[]}));setRouteWarning("");setRouteMode(true);const p=pipeAnchors[selectedLineLabel];if(p)focusDrawing(p.x,p.y);}}>Guide pipe route with clicks</button>
            <button type="button" disabled={!routeMode} onClick={()=>setRouteMode(false)}>Finish route</button>
            <button type="button" disabled={!(routePoints[selectedLineLabel]?.length)} onClick={()=>setRoutePoints(previous=>({...previous,[selectedLineLabel]:(previous[selectedLineLabel]??[]).slice(0,-1)}))}>Undo route point</button>
          </div>
          <div className="pid-review-note">
            <div className="pid-table-head"><h3>Pipe connectivity · engineer review</h3><button type="button" onClick={exportConnectivityReview}>Export connectivity JSON</button></div>
            <p className="pid-muted">Record actual equipment endpoints and components from the P&amp;ID. Crossing lines are not connected unless explicitly checked. This is not automatic topology recognition.</p>
            <div className="pid-review-actions">
              <label>From equipment / nozzle <input aria-label="From equipment" placeholder="e.g. V-500 / nozzle" value={connectivityFor(selectedLineLabel).fromEquipment} onChange={event=>updateConnectivity(selectedLineLabel,{fromEquipment:event.target.value})}/></label>
              <label>To equipment / nozzle <input aria-label="To equipment" placeholder="e.g. M-4252 / nozzle" value={connectivityFor(selectedLineLabel).toEquipment} onChange={event=>updateConnectivity(selectedLineLabel,{toEquipment:event.target.value})}/></label>
            </div>
            <div className="pid-review-actions">
              <label>Valves (comma-separated) <input aria-label="Connected valves" value={connectivityFor(selectedLineLabel).valves} onChange={event=>updateConnectivity(selectedLineLabel,{valves:event.target.value})}/></label>
              <label>Instruments (comma-separated) <input aria-label="Connected instruments" value={connectivityFor(selectedLineLabel).instruments} onChange={event=>updateConnectivity(selectedLineLabel,{instruments:event.target.value})}/></label>
              <label>Branches / junctions <input aria-label="Branches and junctions" value={connectivityFor(selectedLineLabel).junctions} onChange={event=>updateConnectivity(selectedLineLabel,{junctions:event.target.value})}/></label>
            </div>
            <div className="pid-review-actions">
              <label>Endpoint inspection <select aria-label="Endpoint inspection" value={connectivityFor(selectedLineLabel).endpointReview} onChange={event=>updateConnectivity(selectedLineLabel,{endpointReview:event.target.value as "unreviewed"|"reviewed"})}><option value="unreviewed">Not reviewed</option><option value="reviewed">Both endpoints inspected</option></select></label>
              <label>Crossings inspection <select aria-label="Crossing inspection" value={connectivityFor(selectedLineLabel).crossings} onChange={event=>updateConnectivity(selectedLineLabel,{crossings:event.target.value as "unreviewed"|"reviewed"})}><option value="unreviewed">Not reviewed</option><option value="reviewed">Crossings / junctions inspected</option></select></label>
            </div>
            {(() => {const record=connectivityFor(selectedLineLabel);const points=routePoints[selectedLineLabel]??[];const legs=Math.max(0,points.length-1);
              const reviews=manualGeometryReviews[selectedLineLabel]??{};
              const complete=legs>0&&Array.from({length:legs},(_,i)=>reviews[i]==="verified").every(Boolean);
              const ready=!!record.fromEquipment.trim()&&!!record.toEquipment.trim()&&record.endpointReview==="reviewed"&&record.crossings==="reviewed"&&complete;
              return <div><p>Route legs manually reviewed: {Array.from({length:legs},(_,i)=>reviews[i]==="verified").filter(Boolean).length}/{legs}. Endpoint and crossing review required before marking the record engineer-reviewed.</p>
                <button type="button" disabled={!ready} onClick={()=>setConnectivityRecords(previous=>({...previous,[selectedLineLabel]:{...connectivityFor(selectedLineLabel),status:"engineer_reviewed"}}))}>Mark connectivity record engineer-reviewed</button>
                <strong> Status: {record.status==="engineer_reviewed"?"Engineer-reviewed assertion":"Draft / not verified"}</strong>
              </div>;
            })()}
          </div>

          {ocr?.geometry && (routePoints[selectedLineLabel]?.length??0)>1 && <div className="pid-review-note">
            <h4>Suggested branch / crossing locations · review required</h4>
            <p className="pid-muted">Candidates combine detected-segment intersections and local raster perpendicular-stroke evidence along the guided route. They can be text, arrows, instrument lines or actual piping. No candidate is accepted automatically.</p>
            {(() => {const candidates=[...proposeBranchCrossings(routePoints[selectedLineLabel]??[],ocr.geometry!.segments),...(raster?proposeRasterBranches(routePoints[selectedLineLabel]??[],raster):[])].filter((p,i,all)=>all.findIndex(q=>Math.hypot(q.x-p.x,q.y-p.y)<0.009)===i);
              const decisions=branchDecisions[selectedLineLabel]??{};
              const reviewed=candidates.filter(p=>decisions[p.id]).length;
              const nextUnreviewed=candidates.findIndex(p=>!decisions[p.id]);
              return <><p>{candidates.length} candidates · {reviewed} reviewed · {candidates.length-reviewed} pending. Classify only after checking the highlighted location against the P&ID.</p>
                {nextUnreviewed>=0&&<button type="button" onClick={()=>{const p=candidates[nextUnreviewed];setInspectedBranch({id:p.id,index:nextUnreviewed+1,x:p.x,y:p.y,line:selectedLineLabel});focusDrawing(p.x,p.y);}}>Inspect next unreviewed · #{nextUnreviewed+1}</button>}
                {candidates.length>0&&nextUnreviewed<0&&<strong>All detected candidates classified. This does not establish that every physical branch was detected.</strong>}
                {candidates.length===0&&<p>No geometric candidates detected. This does not prove there are no branches.</p>}
                {candidates.map((p,index)=><div className="pid-review-actions" key={p.id} style={inspectedBranch?.line===selectedLineLabel&&inspectedBranch.id===p.id?{outline:"2px solid #facc15",outlineOffset:"3px",borderRadius:"6px"}:undefined}>
                  <button type="button" aria-pressed={inspectedBranch?.line===selectedLineLabel&&inspectedBranch.id===p.id} onClick={()=>{setInspectedBranch({id:p.id,index:index+1,x:p.x,y:p.y,line:selectedLineLabel});focusDrawing(p.x,p.y);}}>{inspectedBranch?.line===selectedLineLabel&&inspectedBranch.id===p.id?"● Selected":"Inspect"} #{index+1} · leg {p.routeLeg}</button>
                  <select aria-label={`Classify candidate ${index+1}`} value={decisions[p.id]??""} onChange={event=>{
                    const value=event.target.value as "branch"|"crossing"|"reject"|"";
                    setBranchDecisions(previous=>{const next={...(previous[selectedLineLabel]??{})};if(value)next[p.id]=value;else delete next[p.id];return {...previous,[selectedLineLabel]:next};});
                    setConnectivityRecords(previous=>({...previous,[selectedLineLabel]:{...connectivityFor(selectedLineLabel),status:"draft",crossings:"unreviewed"}}));
                  }}>
                    <option value="">Unreviewed</option><option value="branch">Confirmed connected branch / junction</option><option value="crossing">Crossing without connection</option><option value="reject">False detection</option>
                  </select>
                </div>)}
                <p className="pid-muted">Confirmed branches are stored as reviewed candidate IDs in the connectivity export. Classification is a manual engineering assertion.</p>
              </>;
            })()}
          </div>}
          {routeWarning && <small role="alert">{routeWarning}</small>}
          {routeMode && <small>Start by clicking the first route point. Long horizontal/vertical runs accept two clicks, including minor scan skew. Click every actual corner; diagonal connections remain blocked. Green route is a manual visual annotation, not verified connectivity.</small>}
          {traceLine===selectedLineLabel && guidedAudit && <div className="pid-review-note">
            <strong>Guided route geometry audit (unverified)</strong>
            <p>{guidedAudit.matchedCount} / {guidedAudit.sampleCount} sampled points near detected geometry ({(guidedAudit.coverage*100).toFixed(1)}% coverage). {guidedAudit.matchedSegmentIds.length} nearby detected segments.</p>
            <p>Diagnostic comparison at 0.010 tolerance: {relaxedGuidedAudit ? (relaxedGuidedAudit.coverage*100).toFixed(1) : "—"}% (baseline 0.006). Orange dots mark up to 60 unmatched baseline samples on the drawing.</p>
            {rasterAudit && <p>Direct raster-pixel evidence: {rasterAudit.matchedCount} / {rasterAudit.sampleCount} samples ({(rasterAudit.coverage*100).toFixed(1)}%). {rasterAudit.warning}</p>}
            {centerlineLegs.length>0 && <div className="pid-route-leg-diagnostics">
              <strong>Pipe centerline refinement · candidate preview only</strong>
              <p>{centerlineLegs.filter(leg=>leg.eligible).length} / {centerlineLegs.length} legs pass conservative evidence gates. No offsets are applied to the saved green route.</p>
              <label><input type="checkbox" checked={showCenterlineCandidates} onChange={event=>setShowCenterlineCandidates(event.target.checked)}/> Show proposed centerlines (purple dashed)</label>
              <p>Drag green waypoints to adjust the route. Raster evidence recalculates automatically. Manual review is separate from automated evidence.</p>
              {centerlineLegs.map((leg,position)=><div key={leg.index} className="pid-review-actions">
                <button type="button" aria-pressed={selectedCenterlineLeg === leg.index} onClick={()=>{setSelectedCenterlineLeg(leg.index);setShowCenterlineCandidates(true);}}>Leg {position+1} · {leg.eligible ? "Candidate" : "Blocked"}</button>
                <span>{leg.reason} · automatic: {activeLegReviews[leg.index] ?? "unreviewed"} · manual: {traceLine===null ? "unreviewed" : manualGeometryReviews[traceLine]?.[leg.index] ?? "unreviewed"}</span>
                <button type="button" disabled={!leg.eligible || traceLine === null} onClick={()=>{if(traceLine === null)return;setCenterlineReviews(prev=>({...prev,[traceLine]:{...(prev[traceLine]??{}),[leg.index]:"accepted"}}));}}>Accept geometry</button>
                <button type="button" disabled={traceLine === null} onClick={()=>{if(traceLine === null)return;setCenterlineReviews(prev=>({...prev,[traceLine]:{...(prev[traceLine]??{}),[leg.index]:"rejected"}}));}}>Reject</button>
                <button type="button" disabled={traceLine===null} onClick={()=>{if(traceLine===null)return;setManualGeometryReviews(prev=>({...prev,[traceLine]:{...(prev[traceLine]??{}),[leg.index]:"verified"}}));}}>Verify manual route leg</button>
                <button type="button" disabled={traceLine===null} onClick={()=>{if(traceLine===null)return;setManualGeometryReviews(prev=>({...prev,[traceLine]:{...(prev[traceLine]??{}),[leg.index]:"rejected"}}));}}>Flag manual leg</button>
                <button type="button" onClick={()=>{if(traceLine === null)return;setCenterlineReviews(prev=>{const next={...(prev[traceLine]??{})};delete next[leg.index];return {...prev,[traceLine]:next};});setManualGeometryReviews(prev=>{const next={...(prev[traceLine]??{})};delete next[leg.index];return {...prev,[traceLine]:next};});}}>Clear</button>
              </div>)}
              <small>Manual verification records engineer-reviewed drawing geometry only, even when automatic evidence is blocked. It does not verify pipe identity or connectivity. Moving waypoints clears manual reviews.</small>
              <small>Proposals are independent per straight leg and are deliberately not joined at elbows. This does not verify pipe identity, endpoints or connectivity.</small>
            </div>}
            {legAlignment && <div className="pid-route-leg-diagnostics">
              <strong>Coherent raster-stroke audit · per straight leg</strong>
              {legAlignment.legs.map(leg=><p key={leg.index}>Leg {leg.index}: {(leg.coverage*100).toFixed(1)}% dark-stroke coverage · estimated perpendicular offset {leg.offsetPixels > 0 ? "+" : ""}{leg.offsetPixels} px{leg.ambiguous ? " · ambiguous parallel candidates" : ""}</p>)}
              <small>{legAlignment.warning}</small>
            </div>}
            <p>Higher proximity coverage does not establish pipe identity; no additional segments are accepted automatically.</p>
            <p>{guidedAudit.warning}</p>
          </div>}
          {traceLine===selectedLineLabel && pipeTrace && <small>Visual trace: {pipeTrace.segments.length} detected segments, nearest segment #{pipeTrace.seedSegment ?? "none"}, normalized distance {Number.isFinite(pipeTrace.distance)?pipeTrace.distance.toFixed(4):"N/A"}. {pipeTrace.warning}</small>}
          {pipePickMode && <small>Click the actual pipe on the drawing, not its text or a nearby signal line. This records an engineer-selected point only.</small>}
          {pipeAnchors[selectedLineLabel] && <small>Manual pipe point: x={pipeAnchors[selectedLineLabel].x.toFixed(3)}, y={pipeAnchors[selectedLineLabel].y.toFixed(3)}. Pipe identity and continuity not yet verified.</small>}
          <small>Review status: {lineReviews[selectedLineLabel] ?? "unverified"}. Confirmations verify text only, not piping connectivity.</small>
        </div>}
        {ocr && selectedCandidate !== null && ocr.candidates[selectedCandidate] && <div className="pid-review-panel">
          <strong>Engineer review: {ocr.candidates[selectedCandidate].tag}</strong>
          <label>Corrected tag <input aria-label="Corrected tag" value={draftTag} maxLength={40} onChange={(event) => setDraftTag(event.target.value.toUpperCase())}/></label>
          <button type="button" disabled={!/^[A-Z0-9][A-Z0-9 _/-]{0,39}$/.test(draftTag.trim())}
            onClick={() => setCorrections(previous => ({...previous,[selectedCandidate]:draftTag.trim()}))}>Save corrected tag</button>
          {corrections[selectedCandidate] && <small>Correction: {corrections[selectedCandidate]}</small>}
          <div className="pid-review-actions">
            <button type="button" onClick={() => setReviews(previous => ({...previous, [selectedCandidate]: "correct"}))}>Correct</button>
            <button type="button" onClick={() => setReviews(previous => ({...previous, [selectedCandidate]: "incorrect"}))}>Incorrect</button>
            <button type="button" onClick={() => setReviews(previous => { const next = {...previous}; delete next[selectedCandidate]; return next; })}>Clear review</button>
          </div>
          <small>Local review only. No drawing changes or automatic AI training.</small>
        </div>}
        {ocr && <details className="pid-engineering-drawer"><summary><span><strong>Advanced engineering tools</strong><small>Symbols · raster geometry · topology · line standards · graph exports</small></span><span className="pid-drawer-chevron">Expand tools</span></summary><div className="pid-engineering-drawer-content"> 
        {ocr && <section className="pid-graph-panel">
          <div className="pid-table-head"><h3>Symbol annotation · engineer-assisted</h3>
            <button type="button" className="secondary-button" onClick={exportSymbolAnnotations}>Export symbols JSON</button>
            <button type="button" className="secondary-button" onClick={exportTrainingDataset}>Export training dataset JSON</button>
          </div>
          <p className="pid-muted">Choose a symbol category, then click its center on the drawing. These are manual labels, not automatic symbol recognition.</p>
          <label>Place symbol
            <select aria-label="Symbol placement mode" value={symbolMode} onChange={event => setSymbolMode(event.target.value as typeof symbolMode)}>
              <option value="off">Off · normal review</option>
              <option value="equipment">Equipment</option>
              <option value="valve">Valve</option>
              <option value="instrument">Instrument</option>
              <option value="connector">Off-page connector</option>
            </select>
          </label>
          <div className="pid-symbol-detection-actions">
            <button type="button" disabled={!raster} onClick={()=>{
              if(!raster)return;
              const proposals=detectInstrumentCircles(raster);
              setSymbolProposals(proposals);
              setSymbolDetectionMessage(`${proposals.length} unverified v2 instrument-bubble proposals. Select ? markers on the drawing to accept as manual instrument annotations. False positives are expected.`);
            }}>Detect instrument bubbles · v2</button>
            <button type="button" disabled={!symbolProposals.length} onClick={()=>setSymbolProposals([])}>Clear proposals</button>
            <small role="status">{symbolDetectionMessage}</small>
          </div>
          <p>{symbolAnnotations.length} manually placed symbols · {symbolAnnotations.filter(item=>item.reviewed).length} engineer-reviewed</p>
          <small role="status">{datasetMessage}</small>
          <p className="pid-muted">Set the approximate bounding-box width and height as percentages of the drawing. Review each box on the original P&ID before marking it verified for training. The exported JSON does not contain the image pixels.</p>
          {symbolAnnotations.map((symbol,index) => <div key={index} className="pid-review-actions">
            <span>#{index+1} · {symbol.kind} · ({symbol.x.toFixed(3)}, {symbol.y.toFixed(3)})</span>
            <input aria-label={`Symbol ${index+1} tag`} placeholder="Optional tag" maxLength={40} value={symbol.tag}
              onChange={event => setSymbolAnnotations(previous => previous.map((item,i) => i === index ? {...item,tag:event.target.value.toUpperCase(),reviewed:false} : item))}/>
            <label>Width %<input type="number" min="0.2" max="100" step="0.5" value={Math.round((symbol.width??0.04)*1000)/10} onChange={event=>setSymbolAnnotations(previous=>previous.map((item,i)=>i===index?{...item,width:Math.max(.002,Math.min(1,Number(event.target.value)/100||.002)),reviewed:false}:item))}/></label>
            <label>Height %<input type="number" min="0.2" max="100" step="0.5" value={Math.round((symbol.height??0.04)*1000)/10} onChange={event=>setSymbolAnnotations(previous=>previous.map((item,i)=>i===index?{...item,height:Math.max(.002,Math.min(1,Number(event.target.value)/100||.002)),reviewed:false}:item))}/></label>
            <label><input type="checkbox" checked={symbol.reviewed===true} onChange={event=>setSymbolAnnotations(previous=>previous.map((item,i)=>i===index?{...item,reviewed:event.target.checked}:item))}/> Reviewed for training</label>
            <button type="button" onClick={() => setSymbolAnnotations(previous => previous.filter((_,i) => i !== index))}>Remove</button>
          </div>)}
        </section>}
        {ocr?.geometry && <section className="pid-graph-panel">
          <div className="pid-table-head"><h3>Visual geometry · experimental</h3>
            <label className="pid-geometry-toggle"><input type="checkbox" checked={showGeometry} onChange={event => setShowGeometry(event.target.checked)}/> Show detected segments on drawing</label>
            <label className="pid-geometry-toggle"><input type="checkbox" checked={includeTitleBlock} onChange={event => setIncludeTitleBlock(event.target.checked)}/> Include title-block candidates</label>
          </div>
          <p><strong>{ocr.geometry.count}</strong> horizontal/vertical raster segments detected{ocr.geometry.truncated ? " (limit reached)" : ""}.</p>
          <p className="pid-muted">{ocr.geometry.warning} Text strokes, drawing borders and symbol outlines may be included.</p>
        </section>}
        {ocr?.topology && <section className="pid-graph-panel">
          <div className="pid-table-head"><h3>Topology reconstruction · review proposals</h3>
            <button type="button" className="secondary-button" onClick={exportTopologyReview}>Export topology reviews</button>
          </div>
          <p><strong>{ocr.topology.count}</strong> nearby endpoint pairs · <strong>0</strong> verified connections{ocr.topology.truncated ? " · limit reached" : ""}</p>
          <p className="pid-muted">{ocr.topology.warning} No flow direction or instrument signal type is inferred.</p>
          <p>Reviewed: <strong>{Object.keys(topologyReviews).length}</strong> · Accepted: <strong>{Object.values(topologyReviews).filter(value => value === "accepted").length}</strong> · Rejected: <strong>{Object.values(topologyReviews).filter(value => value === "rejected").length}</strong></p>
          <label className="pid-geometry-toggle">Review endpoint pair
            <select aria-label="Select topology proposal" value={selectedTopology ?? ""} onChange={event => setSelectedTopology(event.target.value === "" ? null : Number(event.target.value))}>
              <option value="">Select a proposal…</option>
              {ocr.topology.proposals.map((proposal, index) => <option key={index} value={index}>#{index + 1} · segments {proposal.segment_a + 1} / {proposal.segment_b + 1}{topologyReviews[index] ? ` · ${topologyReviews[index]}` : ""}</option>)}
            </select>
          </label>
          {selectedTopology !== null && ocr.topology.proposals[selectedTopology] && <div className="pid-review-panel">
            <strong>Proposal #{selectedTopology + 1}</strong>
            <p>Segments #{ocr.topology.proposals[selectedTopology].segment_a + 1} and #{ocr.topology.proposals[selectedTopology].segment_b + 1} · normalized endpoint distance {ocr.topology.proposals[selectedTopology].distance}</p>
            <div className="pid-review-actions">
              <button type="button" onClick={() => setTopologyReviews(previous => ({...previous, [selectedTopology]: "accepted"}))}>Accept as visual continuation</button>
              <button type="button" onClick={() => setTopologyReviews(previous => ({...previous, [selectedTopology]: "rejected"}))}>Reject</button>
              <button type="button" onClick={() => setTopologyReviews(previous => {const next = {...previous}; delete next[selectedTopology]; return next;})}>Clear</button>
            </div>
            <small>Session-only review. Accepted visual continuations do not create verified process or signal edges.</small>
          </div>}
        </section>}
        {ocr?.topology && <section className="pid-graph-panel">
          <div className="pid-table-head"><h3>Connected visual paths · engineer review</h3><button type="button" className="secondary-button" onClick={exportLineNumberAnnotations}>Export line numbers</button><button type="button" className="secondary-button" onClick={exportConnectivityAnnotations}>Export equipment annotations</button></div>
          <p><strong>{visualPaths.length}</strong> grouped paths from accepted endpoint pairs; not verified process or signal connectivity.</p>
          <label className="pid-geometry-toggle">Highlight path
            <select aria-label="Select visual path" value={selectedVisualPath !== null && visualPaths[selectedVisualPath] ? selectedVisualPath : ""}
              onChange={event => setSelectedVisualPath(event.target.value === "" ? null : Number(event.target.value))}>
              <option value="">Select a path…</option>
              {visualPaths.map((path, index) => <option key={index} value={index}>Path #{index + 1} · {path.segmentIds.length} segments · {path.proposalIds.length} accepted pairs</option>)}
            </select>
          </label>
          <div className="pid-review-panel">
            <strong>Line number recognition · site-specific format</strong>
            <label>Line-number regular expression
              <input aria-label="Line number format" value={lineNumberPattern}
                placeholder="Enter approved site line-number regex"
                onChange={event => setLineNumberPattern(event.target.value)} />
            </label>
            <label>Profile name
              <input aria-label="Line standard profile name" maxLength={80} value={standardName}
                onChange={event => setStandardName(event.target.value)}/>
            </label>
            <label>Example line number
              <input aria-label="Line standard example" value={standardExample}
                onChange={event => setStandardExample(event.target.value)}/>
            </label>
            <button type="button" onClick={saveLineStandard}>Save / update standard</button>
            <label>Saved profiles <select aria-label="Saved line standards" value="" onChange={event => {
              const item = savedStandards.find(entry => entry.name === event.target.value);
              if(item){setStandardName(item.name);setLineNumberPattern(item.pattern);setStandardExample(item.example);}
            }}><option value="">Choose profile…</option>
              {savedStandards.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}
            </select></label>
            <button type="button" onClick={() => deleteLineStandard(standardName)}>Delete named profile</button>
            <small>{compiledLinePattern?.test(standardExample.trim()) ? "Example matches format." : "Example does not match format."}</small>
            <small>{lineNumberPattern.trim() && !compiledLinePattern ? "Invalid regex." : `${lineNumberCandidates.length} matching OCR labels.`}</small>
            {standardMessage && <small role="status">{standardMessage}</small>}
            <div className="pid-review-panel">
              <strong>Line OCR diagnostics · unverified</strong>
              <button type="button" onClick={exportVerifiedLineLabels}>Export reviewed OCR line labels</button>
              <p>{(ocr?.line_labels ?? []).length} extracted line-label hypotheses · {lineNumberCandidates.length} match the active standard.</p>
              {!ocr?.line_labels && <small>The current OCR response does not contain line_labels. Rebuild the backend sidecar and rerun OCR.</small>}
              {(ocr?.line_labels ?? []).length === 0 && <small>No line-label hypotheses were extracted. This may indicate OCR recognition or token-grouping limitations.</small>}
              {(ocr?.line_labels ?? []).slice(0, 40).map((item, index) => {
                const matches = compiledLinePattern?.test(item.tag) ?? false;
                return <div key={index} className="pid-review-actions">
                  <span>{item.tag} · OCR {item.confidence.toFixed(0)}% · x={item.box.x.toFixed(3)}, y={item.box.y.toFixed(3)}</span>
                  <button type="button" onClick={() => {
                    inspectLine(index);
                  }}>Inspect on drawing</button>
                  <small>{lineReviews[index] ?? "unverified"}</small>
                  <small>{!compiledLinePattern ? "No active valid standard" : matches ? "Matches standard · unverified" : "Rejected by standard"}</small>
                </div>;
              })}
              {(ocr?.line_labels ?? []).length > 40 && <small>Showing the first 40 hypotheses.</small>}
              <details>
                <summary>Raw Tesseract tokens (before line-number filtering) · {(ocr?.raw_ocr_tokens ?? []).length} shown</summary>
                {!ocr?.raw_ocr_tokens && <p>Raw token diagnostics unavailable. Rebuild backend and rerun OCR.</p>}
                {(ocr?.raw_ocr_tokens ?? []).slice(0, 100).map((token, index) =>
                  <div className="pid-review-actions" key={index}>
                    <code>{token.text}</code>
                    <small>Confidence {token.confidence.toFixed(0)}% · x={token.box.x.toFixed(3)} y={token.box.y.toFixed(3)}</small>
                  </div>)}
                {(ocr?.raw_ocr_tokens ?? []).length > 100 && <small>Showing the first 100 of {(ocr?.raw_ocr_tokens ?? []).length} returned tokens.</small>}
              </details>

            </div>

          </div>
          {selectedVisualPath !== null && <div className="pid-review-panel">
            <strong>Nearby line-number labels · unverified spatial suggestions</strong>
            <p>Only OCR labels matching the configured line-number format are considered. Proximity does not establish line identity or connectivity.</p>
            {spatialSuggestions.filter(item => item.pathIndex === selectedVisualPath).slice(0, 5).map(item =>
              <div key={item.candidateIndex} className="pid-review-actions">
                <span>{item.tag} · normalized distance {item.distance}</span>
                <button type="button" onClick={() => {
                  if (selectedPathKey !== null) setPathLineNumbers(previous => ({...previous, [selectedPathKey]: item.tag}));
                }}>Use as draft line number</button>
              </div>)}
            {!spatialSuggestions.some(item => item.pathIndex === selectedVisualPath) && <small>No matching line-number label close enough to the path endpoints.</small>}
          </div>}
          {selectedPathKey !== null && <div className="pid-review-panel">
            <label>Draft line number (separate from equipment tag)
              <input aria-label="Draft line number" maxLength={80}
                value={pathLineNumbers[selectedPathKey] ?? ""}
                onChange={event => setPathLineNumbers(previous => ({...previous, [selectedPathKey]: event.target.value.toUpperCase()}))}/>
            </label>
            <small>Requires checking the line-number leader/placement and site line list before verification.</small>
          </div>}
          {selectedPathKey !== null && <div className="pid-review-panel">
            <label>Engineer-annotated equipment tag (not automatically verified)
              <input aria-label="Equipment tag for selected visual path" maxLength={40}
                placeholder="e.g. MP02S" value={pathEquipment[selectedPathKey] ?? ""}
                onChange={event => setPathEquipment(previous => ({...previous, [selectedPathKey]: event.target.value.toUpperCase().replace(/[^A-Z0-9_/-]/g, "")}))}/>
            </label>
            <small>Manual annotation only. Does not establish suction/discharge, flow direction, or instrument connectivity.</small>
          </div>}
          {selectedVisualPath !== null && visualPaths[selectedVisualPath] && <p className="pid-muted">Green highlight: segments {visualPaths[selectedVisualPath].segmentIds.map(id => id + 1).join(", ")}. Crossings and flow direction remain unresolved.</p>}
        </section>}
        {ocr && <section className="pid-graph-panel">
          <div className="pid-table-head"><h3>Engineering Graph · draft</h3>
            <button type="button" className="secondary-button" onClick={exportGraphDraft}>Export graph JSON</button>
          </div>
          <p>Nodes: <strong>{graphNodes.length}</strong> · Engineer-verified: <strong>{graphNodes.filter(node => node.verified).length}</strong> · Verified connections: <strong>{verifiedEdges.length}</strong></p>
          <div className="pid-manual-connections">
            <h4>Manual Connection Editor</h4>
            <p className="pid-muted">Both endpoints must be individually classified and confirmed. Drawing notes and unknown OCR candidates cannot be endpoints. Verify the actual connection on the original drawing before saving.</p>
            <label>From object<select value={edgeSource} onChange={event=>setEdgeSource(event.target.value)}><option value="">Select verified object</option>{graphNodes.filter(node=>verifiedNodeIds.has(node.id)).map(node=><option key={node.id} value={node.id}>{node.tag} · {node.kind}</option>)}</select></label>
            <label>To object<select value={edgeTarget} onChange={event=>setEdgeTarget(event.target.value)}><option value="">Select verified object</option>{graphNodes.filter(node=>verifiedNodeIds.has(node.id)).map(node=><option key={node.id} value={node.id}>{node.tag} · {node.kind}</option>)}</select></label>
            <label>Connection type<select value={edgeKind} onChange={event=>setEdgeKind(event.target.value as ManualEdge["kind"])}><option value="process">Process</option><option value="signal">Signal</option><option value="mechanical">Mechanical</option></select></label>
            <button type="button" className="secondary-button" disabled={!verifiedNodeIds.has(edgeSource)||!verifiedNodeIds.has(edgeTarget)||edgeSource===edgeTarget} onClick={()=>{
              const id=[edgeSource,edgeTarget].sort().join("::")+":"+edgeKind;
              if(manualEdges.some(edge=>edge.id===id)){setEdgeMessage("This connection is already recorded.");return;}
              saveManualEdges([...manualEdges,{id,source:edgeSource,target:edgeTarget,kind:edgeKind,verified:true,review_method:"manual_engineer_review"}]);
            }}>Confirm and save connection</button>
            {edgeMessage&&<small role="status">{edgeMessage}</small>}
            {manualEdges.map(edge=><div className="pid-manual-edge-row" key={edge.id}><span>{edge.source} → {edge.target} · {edge.kind}{!verifiedEdges.some(item=>item.id===edge.id)?" · inactive (endpoint unverified)":""}</span><button type="button" onClick={()=>saveManualEdges(manualEdges.filter(item=>item.id!==edge.id))}>Remove</button></div>)}
          </div>
          <p className="pid-muted">This is a draft inventory, not a process-flow model. Manually reviewed categories and original OCR labels are retained in exported nodes. Only classified, confirmed labels count as engineer-verified; piping connectivity remains unverified.</p>
        </section>}
        </div></details>}
        {ocr && <details className="pid-engineering-drawer pid-ocr-drawer"><summary><span><strong>OCR candidate inventory · {ocr.candidates.length} tags</strong><small>Inspect and review extracted equipment or instrument labels</small></span><span className="pid-drawer-chevron">Show candidates</span></summary><div className="pid-engineering-drawer-content">
        {ocr && <div className="pid-ocr-output"><h3>OCR candidates · page {ocr.page} ({ocr.candidates.length})</h3>
          <p className="pid-muted">{ocr.warning}</p>
          <p className="pid-muted">Review each candidate. Decisions remain in this session; they do not train the model or change drawings.</p>
          <details className="pid-knowledge-reference"><summary>Engineering Knowledge Library · starter rules</summary>
            <p>Reference-guided suggestions only. The library does not contain licensed standard diagrams or verified site conventions.</p>
            {pidKnowledgeReferences.map(reference=><p key={reference.name}><strong>{reference.name}</strong> · {reference.scope}. {reference.note}</p>)}
            <p>Rules currently cover common instrument prefixes, candidate line identifiers, drawing notes, M-style equipment tags and PRV labels. Visual symbols, connections and site-specific numbering remain unvalidated.</p>
          </details>
          <div className="pid-candidate-quality">
            <strong>Candidate quality triage · heuristic, not verified</strong>
            <p>Plausible: {candidateCounts.plausible} · Uncertain: {candidateCounts.uncertain} · Reviewed: {reviewedCount} ({correctCount} correct, {rejectedCount} rejected)</p>
            <p>Reviewed candidate precision: {reviewedPrecision===null?"Not measurable yet":reviewedPrecision.toFixed(1)+"%"} · Recall requires a manually annotated ground-truth inventory.</p>
            <label>Show candidates <select value={candidateTierFilter} onChange={event=>setCandidateTierFilter(event.target.value as "all"|"plausible"|"uncertain")}><option value="all">All detections</option><option value="plausible">Plausible technical labels</option><option value="uncertain">Uncertain detections</option></select></label>
            <small>No detection is deleted or auto-confirmed. Classification uses OCR confidence, text shape and bounding-box geometry only.</small>
          </div>
          {ocr.candidates.length ? <div className="pid-tag-list">{ocr.candidates.map((item,index) => ({item,index})).filter(({index})=>candidateTierFilter==="all"||candidateAssessments[index]?.tier===candidateTierFilter).map(({item,index}) =>
            <button type="button" className="pid-tag-row pid-tag-button" key={index} onClick={() => {setSelectedCandidate(index); setDraftTag(corrections[index] ?? item.tag);}}><strong>{item.tag}</strong>
              <span>OCR confidence {item.confidence.toFixed(0)}%</span>
              <small>Position {Math.round(item.box.x * 100)}% × {Math.round(item.box.y * 100)}%{reviews[index] ? ` · ${reviews[index]}` : ""}</small></button>
          )}</div> : <p className="pid-muted">No candidate tags detected. OCR may miss rotated or low-resolution text.</p>}
        </div>}
        </div></details>}
      </section>}
      {result && <div className="pid-results">
        <div className="pid-summary">
          <article><small>Drawing pages</small><strong>{result.pages.length}</strong></article>
          <article><small>Pages with selectable text</small><strong>{textPages}</strong></article>
          <article><small>Candidate tags (text + OCR)</small><strong>{candidateTotal}</strong></article>
        </div>
        {textPages === 0 && !ocr && <div className="pid-notice">No selectable text was found. Run local OCR to attempt recognition of labels in the drawing.</div>}
        <div className="pid-table-head"><h3>Text-layer tag candidates</h3>
          <input aria-label="Filter candidate tags" placeholder="Filter by tag…" value={filter} onChange={(event) => setFilter(event.target.value)}/>
        </div>
        {tags.length > 0 ? <div className="pid-tag-list">{tags.map((entry) =>
          <div className="pid-tag-row" key={entry.tag}><strong>{entry.tag}</strong><span>Page {entry.pages.join(", ")}</span><small>Unverified candidate</small></div>
        )}</div> : <p className="pid-muted">No matching tags in the text layer. OCR results are shown above.</p>}
        <div className="pid-limitations"><strong>Current limitations</strong>
          <ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>}
    </section>
  );
}
