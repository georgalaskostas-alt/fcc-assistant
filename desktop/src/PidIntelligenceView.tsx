import { useEffect, useState } from "react";
import { FileSearch, ShieldCheck, Upload } from "lucide-react";
import { api, PidInspectionResult, PidOcrResult } from "./api";
import "./PidIntelligenceView.css";

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
  const [reviews, setReviews] = useState<Record<number, "correct" | "incorrect">>({});
  const [corrections, setCorrections] = useState<Record<number, string>>({});
  const [draftTag, setDraftTag] = useState("");
  const [ocrBusy, setOcrBusy] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  useEffect(() => {
    if (!file) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  async function runOcr() {
    if (!file || ocrBusy) return;
    setOcrBusy(true); setOcrError(null); setOcr(null); setSelectedCandidate(null); setReviews({}); setCorrections({});
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
            setOcr(null);
            setReviews({});
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
          <div className="pid-annotated-image">
            <img alt={`Rendered P&ID page ${ocr.page} for visual OCR verification`} src={`data:image/png;base64,${ocr.preview_png_base64}`}/>
            {ocr.candidates.map((item,index) => <button key={index} type="button"
              title={`${item.tag} · OCR ${item.confidence.toFixed(0)}% · not verified`}
              aria-label={`Inspect candidate ${item.tag}`}
              onClick={() => {setSelectedCandidate(index); setDraftTag(corrections[index] ?? item.tag);}}
              className={`pid-ocr-box ${selectedCandidate === index ? "pid-ocr-box-active" : ""}`}
              style={{left:`${item.box.x*100}%`,top:`${item.box.y*100}%`,width:`${Math.max(item.box.width*100,0.5)}%`,height:`${Math.max(item.box.height*100,0.5)}%`}} />)}
          </div>
          {selectedCandidate !== null && ocr.candidates[selectedCandidate] && <div className="pid-ocr-selection">
            Candidate: <strong>{ocr.candidates[selectedCandidate].tag}</strong> · OCR confidence {ocr.candidates[selectedCandidate].confidence.toFixed(0)}% · Requires engineer verification
          </div>}
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
