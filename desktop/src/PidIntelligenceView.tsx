import { useState } from "react";
import { FileSearch, ShieldCheck, Upload } from "lucide-react";
import { api, PidInspectionResult } from "./api";
import "./PidIntelligenceView.css";

export function PidIntelligenceView() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PidInspectionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

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
