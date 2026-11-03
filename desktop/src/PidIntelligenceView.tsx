import { useEffect, useRef, useState } from "react";
import { FileSearch, ShieldCheck, Upload } from "lucide-react";
import { api, PidInspectionResult, PidOcrResult } from "./api";
import "./PidIntelligenceView.css";
import { reconstructVisualPaths } from "./pidVisualPaths";
import { suggestPathTags } from "./pidSpatialSuggestions";

export function PidIntelligenceView() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PidInspectionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [ocr, setOcr] = useState<PidOcrResult | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);
  const [selectedLineLabel, setSelectedLineLabel] = useState<number | null>(null);
  const [showAllLineBoxes, setShowAllLineBoxes] = useState(false);
  const [showEquipmentBoxes, setShowEquipmentBoxes] = useState(false);
  const drawingRef = useRef<HTMLDivElement | null>(null);
  const lineReviewRef = useRef<HTMLDivElement | null>(null);
  const [lineReviews, setLineReviews] = useState<Record<number, "correct" | "rejected">>({});
  const [lineCorrections, setLineCorrections] = useState<Record<number, string>>({});
  const [lineDraft, setLineDraft] = useState("");
  const [pipePickMode, setPipePickMode] = useState(false);
  const [pipeAnchors, setPipeAnchors] = useState<Record<number,{x:number;y:number}>>({});


  const [reviews, setReviews] = useState<Record<number, "correct" | "incorrect">>({});
  const [corrections, setCorrections] = useState<Record<number, string>>({});
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
  const [symbolAnnotations, setSymbolAnnotations] = useState<Array<{x:number;y:number;kind:"equipment" | "valve" | "instrument" | "connector";tag:string}>>([]);
  const [topologyReviews, setTopologyReviews] = useState<Record<number, "accepted" | "rejected">>({});
  const [ocrBusy, setOcrBusy] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  useEffect(() => {
    if (!file) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function inspectLine(index: number) {
    const label = ocr?.line_labels?.[index];
    if (!label) return;
    setSelectedLineLabel(index);
    setLineDraft(lineCorrections[index] ?? label.tag);
    const container = drawingRef.current;
    if (container) {
      container.scrollIntoView({behavior:"smooth",block:"center"});
      const image = container.querySelector("img");
      if (image) {
        const centerX = (label.box.x + label.box.width / 2) * image.clientWidth;
        const centerY = (label.box.y + label.box.height / 2) * image.clientHeight;
        container.scrollTo({left:Math.max(0,centerX-container.clientWidth/2),
          top:Math.max(0,centerY-container.clientHeight/2),behavior:"smooth"});
      }
    }
  }
  async function runOcr() {
    if (!file || ocrBusy) return;
    setOcrBusy(true); setOcrError(null); setOcr(null); setSelectedLineLabel(null); setLineReviews({}); setLineCorrections({}); setPipeAnchors({}); setPipePickMode(false); setPipeAnchors({}); setPipePickMode(false); setSelectedCandidate(null); setReviews({}); setCorrections({}); setTopologyReviews({}); setSelectedTopology(null); setPathEquipment({}); setPathLineNumbers({}); setSymbolAnnotations([]); setSymbolMode("off"); setSelectedVisualPath(null);
    try { setOcr(await api.ocrPidPage(file, page)); }
    catch (err) { setOcrError(err instanceof Error ? err.message : "OCR failed"); }
    finally { setOcrBusy(false); }
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
  const graphNodes = (ocr?.candidates ?? []).filter((_, index) => reviews[index] !== "incorrect").map((item, index) => {
    const originalIndex = ocr!.candidates.indexOf(item);
    return {
      id: `p${ocr!.page}-ocr-${originalIndex}`,
      kind: "unknown" as const,
      tag: corrections[originalIndex] ?? item.tag,
      original_tag: item.tag,
      page: ocr!.page,
      box: [item.box.x, item.box.y, item.box.width, item.box.height],
      verified: reviews[originalIndex] === "correct",
      source: "ocr" as const,
      confidence: item.confidence,
    };
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
  const spatialSuggestions = suggestPathTags(visualPaths, ocr?.geometry?.segments ?? [], ocr?.line_labels ?? [])
    .filter(item => lineNumberCandidates.some(candidate => candidate.index === item.candidateIndex));
  const selectedPathKey = selectedVisualPath !== null && visualPaths[selectedVisualPath] ? visualPaths[selectedVisualPath].segmentIds.join(",") : null;
  const graphDraft = { schema_version: 1, read_only: true, nodes: graphNodes, edges: [] as never[],
    warning: "No process or signal connections have been established. OCR alone cannot prove topology." };
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
      source:"local_ocr", connectivity_status:"not_verified", manual_pipe_point:pipeAnchors[index] ?? null, association_status:pipeAnchors[index] ? "engineer_selected_point_unverified_continuity" : "not_associated",
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
    <section className="pid-workspace">
      <div className="pid-intro">
        <div><span className="eyebrow">P&ID INTELLIGENCE · PHASE 1</span>
          <h2>P&ID drawing inspection</h2>
          <p>Read-only discovery of candidate tags from PDFs and photos. OCR results require verification; no diagram topology is inferred.</p>
        </div>
        <span className="pid-readonly"><ShieldCheck size={16}/> Read-only</span>
      </div>

      <div className="pid-upload-panel">
        <FileSearch size={27}/>
        <div><strong>Choose a P&ID PDF or photo</strong><p>Local processing · PDF, PNG or JPEG up to 20 MB. Use only documents authorized for this environment.</p></div>
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
        <div className="pid-table-head"><h3>Drawing preview</h3><span className="pid-muted">Local drawing viewer · original file unchanged</span></div>
        {file?.type.startsWith("image/") ? <img src={previewUrl} alt="P&ID drawing photo" className="pid-photo-preview"/> : <iframe title="P&ID PDF preview" src={previewUrl} className="pid-pdf-frame"/>}
        <div className="pid-ocr-controls">
          <label>OCR page <input type="number" min={1} max={result?.pages.length ?? 100} value={page}
            onChange={(event) => { setPage(Number(event.target.value)); setOcr(null); }}/></label>
          <button type="button" className="secondary-button" disabled={!result || ocrBusy || page < 1 || page > result.pages.length}
            onClick={() => void runOcr()}>{ocrBusy ? "Running local OCR…" : "Run local OCR on page"}</button>
          <small>Optional local Tesseract OCR. No cloud processing.</small>
        </div>
        {ocrError && <div role="alert" className="error-banner">{ocrError}</div>}
        {ocr?.preview_png_base64 && <div className="pid-annotated">
          <div className="pid-table-head"><h3>OCR visual verification · page {ocr.page}</h3><span className="pid-muted">Boxes indicate unverified OCR candidates</span></div>
          <div className="pid-annotated-image" ref={drawingRef} onClick={event => {
            if (pipePickMode && selectedLineLabel !== null) {
              if ((event.target as HTMLElement).closest("button")) return;
              const canvas=event.currentTarget.querySelector(".pid-image-canvas");
              const bounds=canvas?.getBoundingClientRect();
              if (!bounds?.width || !bounds.height) return;
              const x=Math.max(0,Math.min(1,(event.clientX-bounds.left)/bounds.width));
              const y=Math.max(0,Math.min(1,(event.clientY-bounds.top)/bounds.height));
              setPipeAnchors(previous=>({...previous,[selectedLineLabel]:{x,y}}));
              setPipePickMode(false);
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
            <div className="pid-overlay-controls">
              <label><input type="checkbox" checked={showAllLineBoxes} onChange={event => setShowAllLineBoxes(event.target.checked)}/> Show all unverified line OCR boxes</label>
              <label><input type="checkbox" checked={showEquipmentBoxes} onChange={event => setShowEquipmentBoxes(event.target.checked)}/> Show equipment/instrument OCR boxes</label>
            </div>
            <div className="pid-image-canvas">
            <img alt={`Rendered P&ID page ${ocr.page} for visual OCR verification`} src={`data:image/png;base64,${ocr.preview_png_base64}`}/>
            {showGeometry && ocr.geometry && <svg className="pid-geometry-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Unverified visual line segments">
              {ocr.geometry.segments.filter(segment => includeTitleBlock || segment.region_hint !== "title_block_candidate").map((segment, index) => <line key={index}
                x1={segment.x1 * 1000} y1={segment.y1 * 1000}
                x2={segment.x2 * 1000} y2={segment.y2 * 1000}
                stroke="#00b8ff" strokeWidth="1.5" vectorEffect="non-scaling-stroke" opacity="0.8" />)}
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
            {symbolAnnotations.map((symbol, index) => <span key={index} className="pid-manual-symbol" style={{left:`${symbol.x*100}%`,top:`${symbol.y*100}%`}} title={`Manual ${symbol.kind}: ${symbol.tag || "unlabeled"}`}>{symbol.kind === "valve" ? "V" : symbol.kind === "instrument" ? "I" : symbol.kind === "connector" ? "C" : "E"}</span>)}
            {showEquipmentBoxes && ocr.candidates.map((item,index) => <button key={index} type="button"
              title={`${item.tag} · OCR ${item.confidence.toFixed(0)}% · not verified`}
              aria-label={`Inspect candidate ${item.tag}`}
              onClick={() => {setSelectedCandidate(index); setDraftTag(corrections[index] ?? item.tag);}}
              className={`pid-ocr-box ${selectedCandidate === index ? "pid-ocr-box-active" : ""}`}
              style={{left:`${item.box.x*100}%`,top:`${item.box.y*100}%`,width:`${Math.max(item.box.width*100,0.5)}%`,height:`${Math.max(item.box.height*100,0.5)}%`}} />)}
            </div>
          </div>
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
          <div className="pid-review-actions">
            <button type="button" disabled={!compiledLinePattern?.test(lineDraft.trim())} onClick={() => {
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
          <div className="pid-review-actions">
            <button type="button" disabled={lineReviews[selectedLineLabel] !== "correct"} onClick={() => {
              setPipePickMode(true);
              drawingRef.current?.scrollIntoView({behavior:"smooth",block:"center"});
            }}>Select pipe location on drawing</button>
            <button type="button" disabled={!pipeAnchors[selectedLineLabel]} onClick={() => {
              setPipeAnchors(previous=>{const next={...previous};delete next[selectedLineLabel];return next;});
              setPipePickMode(false);
            }}>Clear pipe location</button>
          </div>
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
        {ocr && <section className="pid-graph-panel">
          <div className="pid-table-head"><h3>Symbol annotation · engineer-assisted</h3>
            <button type="button" className="secondary-button" onClick={exportSymbolAnnotations}>Export symbols JSON</button>
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
          <p>{symbolAnnotations.length} manually placed symbols</p>
          {symbolAnnotations.map((symbol,index) => <div key={index} className="pid-review-actions">
            <span>#{index+1} · {symbol.kind} · ({symbol.x.toFixed(3)}, {symbol.y.toFixed(3)})</span>
            <input aria-label={`Symbol ${index+1} tag`} placeholder="Optional tag" maxLength={40} value={symbol.tag}
              onChange={event => setSymbolAnnotations(previous => previous.map((item,i) => i === index ? {...item,tag:event.target.value.toUpperCase()} : item))}/>
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
          <p>Nodes: <strong>{graphNodes.length}</strong> · Engineer-verified: <strong>{graphNodes.filter(node => node.verified).length}</strong> · Connections: <strong>0</strong></p>
          <p className="pid-muted">This is a draft inventory, not a process-flow model. No piping or signal connections are inferred from OCR. Incorrect candidates are excluded; corrected labels are retained with their originals.</p>
        </section>}
        {ocr && <div className="pid-ocr-output"><h3>OCR candidates · page {ocr.page} ({ocr.candidates.length})</h3>
          <p className="pid-muted">{ocr.warning}</p>
          <p className="pid-muted">Review each candidate. Decisions remain in this session; they do not train the model or change drawings.</p>
          {ocr.candidates.length ? <div className="pid-tag-list">{ocr.candidates.map((item,index) =>
            <button type="button" className="pid-tag-row pid-tag-button" key={index} onClick={() => {setSelectedCandidate(index); setDraftTag(corrections[index] ?? item.tag);}}><strong>{item.tag}</strong>
              <span>OCR confidence {item.confidence.toFixed(0)}%</span>
              <small>Position {Math.round(item.box.x * 100)}% × {Math.round(item.box.y * 100)}%{reviews[index] ? ` · ${reviews[index]}` : ""}</small></button>
          )}</div> : <p className="pid-muted">No candidate tags detected. OCR may miss rotated or low-resolution text.</p>}
        </div>}
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
