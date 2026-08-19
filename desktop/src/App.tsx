import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bot,
  ChartNoAxesCombined,
  Database,
  FileText,
  Gauge,
  MessageSquare,
  RefreshCw,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { api, DemoShiftResponse, SimulatorTag, SystemCapabilities } from "./api";

type View = "dashboard" | "chat" | "reports" | "settings";

type CardMetric = {
  key: string;
  name: string;
  unit: string;
  value: number | null;
  delta: number | null;
};

const NAV: Array<{ id: View; label: string; icon: typeof Gauge }> = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "chat", label: "Assistant", icon: MessageSquare },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "settings", label: "Settings", icon: Settings },
];

function latestMetric(tag: SimulatorTag, shift: DemoShiftResponse | null): CardMetric {
  const items = shift?.data[tag.key]?.Items ?? [];
  if (!items.length) return { key: tag.key, name: tag.name, unit: tag.unit, value: null, delta: null };
  const first = items[0]?.Value ?? null;
  const last = items.at(-1)?.Value ?? null;
  return {
    key: tag.key,
    name: tag.name,
    unit: tag.unit,
    value: last,
    delta: first != null && last != null ? last - first : null,
  };
}

function fmt(value: number | null, digits = 1) {
  return value == null ? "—" : value.toFixed(digits);
}

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [capabilities, setCapabilities] = useState<SystemCapabilities | null>(null);
  const [tags, setTags] = useState<SimulatorTag[]>([]);
  const [shift, setShift] = useState<DemoShiftResponse | null>(null);
  const [backendOk, setBackendOk] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("Τι σημαντικό συνέβη στη βάρδια;");
  const [answer, setAnswer] = useState<string>("");
  const [asking, setAsking] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [health, caps, tagResponse, demo] = await Promise.all([
        api.health(),
        api.capabilities(),
        api.simulatorTags(),
        api.demoShift(),
      ]);
      setBackendOk(health.status === "ok");
      setCapabilities(caps);
      setTags(tagResponse.items);
      setShift(demo);
    } catch (err) {
      setBackendOk(false);
      setError(err instanceof Error ? err.message : "Unable to connect to the local backend");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const metrics = useMemo(() => tags.map((tag) => latestMetric(tag, shift)), [tags, shift]);
  const highlights = metrics.filter((metric) => ["feed_flow", "reactor_temp", "regen_temp", "regen_o2", "naphtha_rate", "lcco_rate"].includes(metric.key));

  async function askAssistant() {
    if (!question.trim() || !shift) return;
    setAsking(true);
    setAnswer("");
    try {
      const response = await api.analyze(question.trim(), {
        analysis_scope: "simulated_shift",
        source: "FCC simulator - development data only",
        shift: shift.data,
      });
      setAnswer(response.answer);
    } catch (err) {
      setAnswer(`Δεν ήταν δυνατή η ανάλυση: ${err instanceof Error ? err.message : "unknown error"}`);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Activity size={22} /></div>
          <div><strong>FCC Assistant</strong><span>Local Process Intelligence</span></div>
        </div>
        <nav>
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={view === item.id ? "nav-item active" : "nav-item"} onClick={() => setView(item.id)}>
                <Icon size={18} /> <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="security-chip"><ShieldCheck size={16} /><span>Local-only AI</span></div>
          <small>Plant write access: disabled</small>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <h1>{NAV.find((item) => item.id === view)?.label}</h1>
            <p>FCC unit · development simulator</p>
          </div>
          <div className="top-actions">
            <span className={backendOk ? "status-dot ok" : "status-dot bad"}>{backendOk ? "Backend online" : "Backend offline"}</span>
            <button className="icon-button" onClick={() => void refresh()} disabled={loading}><RefreshCw size={17} /></button>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}

        {view === "dashboard" && (
          <section className="content">
            <div className="hero-row">
              <div>
                <span className="eyebrow">OPERATING OVERVIEW</span>
                <h2>FCC shift snapshot</h2>
                <p>Τα παρακάτω δεδομένα είναι simulated και υπάρχουν για development/testing.</p>
              </div>
              <div className="read-only-badge"><ShieldCheck size={17} /> Read-only mode</div>
            </div>

            <div className="metric-grid">
              {highlights.map((metric) => (
                <article className="metric-card" key={metric.key}>
                  <div className="metric-title"><span>{metric.name}</span><ChartNoAxesCombined size={17} /></div>
                  <div className="metric-value">{fmt(metric.value)} <small>{metric.unit}</small></div>
                  <div className={metric.delta != null && metric.delta > 0 ? "delta up" : "delta down"}>
                    Shift Δ {metric.delta == null ? "—" : `${metric.delta >= 0 ? "+" : ""}${metric.delta.toFixed(2)} ${metric.unit}`}
                  </div>
                </article>
              ))}
            </div>

            <div className="panel-grid">
              <article className="panel">
                <div className="panel-heading"><div><span className="eyebrow">DATA SOURCE</span><h3>System status</h3></div><Database size={20} /></div>
                <div className="status-list">
                  <div><span>Backend</span><strong>{backendOk ? "Connected" : "Offline"}</strong></div>
                  <div><span>PI Web API</span><strong>{capabilities?.pi_web_api ?? "unknown"}</strong></div>
                  <div><span>Local AI</span><strong>{capabilities?.local_ai ?? "unknown"}</strong></div>
                  <div><span>Simulator</span><strong>Available</strong></div>
                </div>
              </article>

              <article className="panel event-panel">
                <div className="panel-heading"><div><span className="eyebrow">DEMO EVENT</span><h3>Expected pattern</h3></div><Activity size={20} /></div>
                <p>Μετά την 4η ώρα του simulated shift υπάρχει ελεγχόμενη άνοδος regenerator temperature, πτώση O₂ και πτώση LCCO.</p>
                <button className="primary-button" onClick={() => setView("chat")}><Bot size={17} /> Ask the assistant</button>
              </article>
            </div>
          </section>
        )}

        {view === "chat" && (
          <section className="content chat-layout">
            <div className="chat-intro">
              <span className="eyebrow">LOCAL AI</span>
              <h2>Ask about the FCC shift</h2>
              <p>Η απάντηση βασίζεται μόνο στα simulated process data που στέλνονται στο local model.</p>
            </div>
            <div className="chat-card">
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ρώτησε κάτι για τη βάρδια…" />
              <div className="chat-actions">
                <span><ShieldCheck size={15} /> Data stays on this laptop</span>
                <button className="primary-button" onClick={() => void askAssistant()} disabled={asking || !shift}>{asking ? "Analyzing…" : "Analyze shift"}</button>
              </div>
              {answer && <div className="assistant-answer"><div className="answer-avatar"><Bot size={20} /></div><div><strong>FCC Assistant</strong><p>{answer}</p></div></div>}
            </div>
          </section>
        )}

        {view === "reports" && (
          <section className="content">
            <div className="hero-row"><div><span className="eyebrow">REPORTING</span><h2>Shift report preview</h2><p>Πρώτη έκδοση του report πριν συνδεθεί το πραγματικό PI.</p></div></div>
            <article className="panel report-panel">
              <div className="report-header"><div><h3>07:00–15:00 Shift</h3><span>Simulated FCC</span></div><FileText size={22} /></div>
              <div className="report-table">
                <div className="report-row report-head"><span>Variable</span><span>End value</span><span>Shift change</span></div>
                {metrics.map((metric) => (
                  <div className="report-row" key={metric.key}><span>{metric.name}</span><span>{fmt(metric.value)} {metric.unit}</span><span>{metric.delta == null ? "—" : `${metric.delta >= 0 ? "+" : ""}${metric.delta.toFixed(2)} ${metric.unit}`}</span></div>
                ))}
              </div>
            </article>
          </section>
        )}

        {view === "settings" && (
          <section className="content">
            <div className="hero-row"><div><span className="eyebrow">LOCAL CONFIGURATION</span><h2>System settings</h2><p>Προς το παρόν οι πραγματικές PI ρυθμίσεις μένουν κενές.</p></div></div>
            <div className="settings-grid">
              <article className="panel"><div className="panel-heading"><div><h3>PI Web API</h3><p>Read-only plant data source</p></div><Database size={20} /></div><div className="setting-line"><span>Status</span><strong>{capabilities?.pi_web_api ?? "not configured"}</strong></div></article>
              <article className="panel"><div className="panel-heading"><div><h3>Local AI runtime</h3><p>localhost only</p></div><Bot size={20} /></div><div className="setting-line"><span>Status</span><strong>{capabilities?.local_ai ?? "not configured"}</strong></div></article>
              <article className="panel"><div className="panel-heading"><div><h3>Security</h3><p>Process protection boundary</p></div><ShieldCheck size={20} /></div><div className="setting-line"><span>Plant writes</span><strong>Disabled</strong></div></article>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
