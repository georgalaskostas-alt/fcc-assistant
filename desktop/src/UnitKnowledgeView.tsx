import { useEffect, useMemo, useState } from "react";
import { BookOpen, CheckCircle2, FileSearch, Upload, Wrench } from "lucide-react";
import { api, ManualSearchItem, UnitKnowledge } from "./api";
import "./UnitKnowledgeView.css";

type Props = {
  unitKey: string;
  unitName: string;
};

export function UnitKnowledgeView({ unitKey, unitName }: Props) {
  const [knowledge, setKnowledge] = useState<UnitKnowledge | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ManualSearchItem[]>([]);
  const [searching, setSearching] = useState(false);

  const approvedOverrides = useMemo(
    () => (knowledge?.overrides ?? []).filter((item) => item.status === "approved"),
    [knowledge],
  );
  const approvedRevamps = useMemo(
    () => (knowledge?.revamps ?? []).filter((item) => item.status === "approved"),
    [knowledge],
  );

  async function load() {
    if (unitKey === "all") return;
    setLoading(true);
    try {
      setKnowledge(await api.unitKnowledge(unitKey));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load unit knowledge");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [unitKey]);

  async function upload(file: File | null) {
    if (!file || unitKey === "all") return;
    setUploading(true);
    try {
      await api.uploadManual(unitKey, file, file.name);
      await load();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Manual upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function search() {
    const value = query.trim();
    if (!value || unitKey === "all") return;
    setSearching(true);
    try {
      const response = await api.searchManuals(unitKey, value);
      setResults(response.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Manual search failed");
    } finally {
      setSearching(false);
    }
  }

  if (unitKey === "all") {
    return (
      <section className="knowledge-empty">
        <BookOpen size={32} />
        <h2>Select a process unit</h2>
        <p>Unit Knowledge is versioned per unit. Select FCC, Hydrocracker or another configured unit to manage manuals, revamps and approved operating knowledge.</p>
      </section>
    );
  }

  return (
    <section className="knowledge-shell">
      <div className="knowledge-hero">
        <div>
          <span className="eyebrow">UNIT KNOWLEDGE</span>
          <h2>{unitName}</h2>
          <p>Local manuals, revamps and engineer-approved operating knowledge.</p>
        </div>
        <div className={`knowledge-status ${knowledge?.knowledge_status === "approved" ? "approved" : "draft"}`}>
          {knowledge?.knowledge_status === "approved" ? <CheckCircle2 size={16} /> : <BookOpen size={16} />}
          {loading ? "Loading…" : (knowledge?.knowledge_status ?? "draft").toUpperCase()}
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="knowledge-action-row">
        <label className="knowledge-upload">
          <Upload size={16} /> {uploading ? "Uploading…" : "Add local manual"}
          <input
            type="file"
            accept=".pdf,.txt,.md,.markdown"
            disabled={uploading}
            onChange={(event) => void upload(event.target.files?.[0] ?? null)}
          />
        </label>
        <div className="knowledge-search">
          <FileSearch size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => { if (event.key === "Enter") void search(); }}
            placeholder="Search inside local manuals…"
          />
          <button onClick={() => void search()} disabled={searching || !query.trim()}>{searching ? "…" : "Search"}</button>
        </div>
      </div>

      <div className="knowledge-grid">
        <article className="knowledge-panel accent-blue">
          <div className="knowledge-panel-head"><BookOpen size={19} /><div><span>DOCUMENTS</span><h3>Manuals</h3></div></div>
          <div className="knowledge-list">
            {(knowledge?.manuals ?? []).length === 0 && <p className="knowledge-muted">No manuals loaded yet.</p>}
            {(knowledge?.manuals ?? []).map((manual) => (
              <div className="knowledge-row" key={manual.id}>
                <div><strong>{manual.title}</strong><span>{manual.revision || "No revision"}</span></div>
                <span className={`mini-status ${manual.status}`}>{manual.status}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="knowledge-panel accent-amber">
          <div className="knowledge-panel-head"><Wrench size={19} /><div><span>CONFIGURATION</span><h3>Revamps</h3></div></div>
          <div className="knowledge-list">
            {approvedRevamps.length === 0 && <p className="knowledge-muted">No approved revamp context.</p>}
            {approvedRevamps.map((revamp) => (
              <div className="knowledge-row stacked" key={revamp.id}>
                <strong>{revamp.title}</strong><span>{revamp.description}</span><small>Effective {revamp.effective_from}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="knowledge-panel accent-violet wide">
          <div className="knowledge-panel-head"><CheckCircle2 size={19} /><div><span>CURRENT PRACTICE</span><h3>Approved engineering overrides</h3></div></div>
          <div className="knowledge-list">
            {approvedOverrides.length === 0 && <p className="knowledge-muted">No approved operating overrides.</p>}
            {approvedOverrides.map((item) => (
              <div className="override-row" key={item.id}>
                <div><strong>{item.subject}</strong><span>{item.reason}</span></div>
                <div className="override-values"><span>Manual: {item.manual_value || "—"}</span><strong>Current: {item.current_value}</strong></div>
              </div>
            ))}
          </div>
        </article>
      </div>

      {results.length > 0 && (
        <article className="knowledge-panel search-results accent-cyan">
          <div className="knowledge-panel-head"><FileSearch size={19} /><div><span>LOCAL RETRIEVAL</span><h3>Manual search results</h3></div></div>
          <div className="knowledge-list">
            {results.map((item, index) => (
              <div className="knowledge-row stacked" key={`${item.storage_id ?? "result"}-${item.chunk_id ?? index}`}>
                <strong>{item.page ? `Page ${item.page}` : `Result ${index + 1}`}</strong>
                <span>{String(item.text ?? "")}</span>
              </div>
            ))}
          </div>
        </article>
      )}
    </section>
  );
}
