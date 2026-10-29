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
    setOcrBusy(true); setOcrError(null); setOcr(null);
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
      setError(err instanceof Error ? err.message : "PDF inspection failed");
    } finally {
      setBusy(false);
    }
  }

  const tags = (result?.candidate_tags ?? []).filter((entry) =>
    entry.tag.toLowerCase().includes(filter.trim().toLowerCase()),
  );
  const textPages = result?.pages.filter((entry) => entry.text_available).length ?? 0;

  return (
    <section className="pid-workspace">
      <div className="pid-intro">
        <div><span className="eyebrow">P&ID INTELLIGENCE · PHASE 1</span>
          <h2>PDF drawing inspection</h2>
          <p>Read-only candidate tag discovery from the PDF text layer. No topology or design corrections are inferred.</p>
        </div>
        <span className="pid-readonly"><ShieldCheck size={16}/> Read-only</span>
      </div>

      <div className="pid-upload-panel">
        <FileSearch size={27}/>
        <div><strong>Choose a P&ID PDF</strong><p>Local processing · PDF up to 20 MB and 100 pages. Use only documents authorized for this environment.</p></div>
        <label className="pid-file-picker"><Upload size={16}/> Select PDF
          <input type="file" accept=".pdf,application/pdf" onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setResult(null);
            setOcr(null);
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
        <div className="pid-table-head"><h3>Drawing preview</h3><span className="pid-muted">Local PDF viewer · original file unchanged</span></div>
        <iframe title="P&ID PDF preview" src={previewUrl} className="pid-pdf-frame"/>
        <div className="pid-ocr-controls">
          <label>OCR page <input type="number" min={1} max={result?.pages.length ?? 100} value={page}
            onChange={(event) => { setPage(Number(event.target.value)); setOcr(null); }}/></label>
          <button type="button" className="secondary-button" disabled={!result || ocrBusy || page < 1 || page > result.pages.length}
            onClick={() => void runOcr()}>{ocrBusy ? "Running local OCR…" : "Run local OCR on page"}</button>
          <small>Optional local Tesseract OCR. No cloud processing.</small>
        </div>
        {ocrError && <div role="alert" className="error-banner">{ocrError}</div>}
        {ocr && <div className="pid-ocr-output"><h3>OCR candidates · page {ocr.page} ({ocr.candidates.length})</h3>
          <p className="pid-muted">{ocr.warning}</p>
          {ocr.candidates.length ? <div className="pid-tag-list">{ocr.candidates.map((item,index) =>
            <div className="pid-tag-row" key={index}><strong>{item.tag}</strong>
              <span>OCR confidence {item.confidence.toFixed(0)}%</span>
              <small>Position {Math.round(item.box.x * 100)}% × {Math.round(item.box.y * 100)}%</small></div>
          )}</div> : <p className="pid-muted">No candidate tags detected. OCR may miss rotated or low-resolution text.</p>}
        </div>}
      </section>}
      {result && <div className="pid-results">
        <div className="pid-summary">
          <article><small>PDF pages</small><strong>{result.pages.length}</strong></article>
          <article><small>Pages with selectable text</small><strong>{textPages}</strong></article>
          <article><small>Candidate tags</small><strong>{result.candidate_tags.length}</strong></article>
        </div>
        {textPages === 0 && <div className="pid-notice">No selectable text was found. This may be a scanned drawing; visual/OCR recognition is not implemented in this phase.</div>}
        <div className="pid-table-head"><h3>Unverified tag candidates</h3>
          <input aria-label="Filter candidate tags" placeholder="Filter by tag…" value={filter} onChange={(event) => setFilter(event.target.value)}/>
        </div>
        {tags.length > 0 ? <div className="pid-tag-list">{tags.map((entry) =>
          <div className="pid-tag-row" key={entry.tag}><strong>{entry.tag}</strong><span>Page {entry.pages.join(", ")}</span><small>Unverified candidate</small></div>
        )}</div> : <p className="pid-muted">No matching candidate tags were found in the available PDF text layer.</p>}
        <div className="pid-limitations"><strong>Current limitations</strong>
          <ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>}
    </section>
  );
}
