import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bot,
  Database,
  FileText,
  Gauge,
  MessageSquare,
  RefreshCw,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { api, BridgeSite, DemoShiftResponse, RuntimeInfo, SimulatorTag, SystemCapabilities } from "./api";
import { DashboardCustomizer } from "./DashboardCustomizer";
import { UnitScopeBar } from "./UnitScopeBar";

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
  const [site, setSite] = useState<BridgeSite | null>(null);
  const [activeUnit, setActiveUnit] = useState(() => window.localStorage.getItem("fcc-active-unit") || "all");
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [tags, setTags] = useState<SimulatorTag[]>([]);
  const [shift, setShift] = useState<DemoShiftResponse | null>(null);
  const [backendOk, setBackendOk] = useState(false);
  const [loading, setLoading] = useState(true);
  const [runtimeBusy, setRuntimeBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("Τι σημαντικό συνέβη στη βάρδια;");
  const [answer, setAnswer] = useState<string>("");
  const [asking, setAsking] = useState(false);

  function changeActiveUnit(unitKey: string) {
    setActiveUnit(unitKey);
    window.localStorage.setItem("fcc-active-unit", unitKey);
  }

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [health, caps, bridgeSite, runtimeInfo, tagResponse, demo] = await Promise.all([
        api.health(),
        api.capabilities(),
        api.bridgeSite(),
        api.aiRuntime(),
        api.simulatorTags(),
        api.demoShift(),
      ]);
      setBackendOk(health.status === "ok");
      setCapabilities(caps);
      setSite(bridgeSite);
      setRuntime(runtimeInfo);
      setTags(tagResponse.items);
      setShift(demo);

      if (activeUnit !== "all" && !bridgeSite.units.some((unit) => unit.key === activeUnit)) {
        changeActiveUnit("all");
      }
    } catch (err) {
      setBackendOk(false);
      setError(err instanceof Error ? err.message : "Unable to connect to the local backend");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void api.health().then(() => setBackendOk(true)).catch(() => setBackendOk(false));
    }, 4000);
    return () => window.clearInterval(timer);
  }, []);

  const metrics = useMemo(() => tags.map((tag) => latestMetric(tag, shift)), [tags, shift]);
  const activeUnitName = activeUnit === "all"
    ? "All Units"
    : site?.units.find((unit) => unit.key === activeUnit)?.name ?? activeUnit.toUpperCase();

  async function askAssistant() {
    if (!question.trim() || !shift) return;
    setAsking(true);
    setAnswer("");
    try {
      if (!runtime?.state.running) {
        await api.startAiRuntime();
        setRuntime(await api.aiRuntime());
      }
      const response = await api.analyze(question.trim(), {
        analysis_scope: activeUnit === "all" ? "refinery_scope" : "unit_scope",
        selected_unit: activeUnit,
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

  async function setAiRunning(run: boolean) {
    setRuntimeBusy(true);
    setError(null);
    try {
      if (run) await api.startAiRuntime(); else await api.stopAiRuntime();
      setRuntime(await api.aiRuntime());
      setCapabilities(await api.capabilities());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to change local AI state");
    } finally {
      setRuntimeBusy(false);
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
          <div className="security-chip"><ShieldCheck size={16} /><span>Embedded local AI</span></div>
          <small>External AI: disabled · Plant writes: disabled</small>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <h1>{NAV.find((item) => item.id === view)?.label}</h1>
            <p>{site?.site ?? "Operations workspace"} · {activeUnitName}</p>
          </div>
          <div className="top-actions">
            <span className={backendOk ? "status-dot ok" : "status-dot bad"}>{backendOk ? "Backend online" : "Backend offline"}</span>
            <button className="icon-button" onClick={() => void refresh()} disabled={loading}><RefreshCw size={17} /></button>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}

        {view === "dashboard" && (
          <section className="content">
            <div className="hero-row compact-hero">
              <div>
                <span className="eyebrow">OPERATING OVERVIEW</span>
                <h2>Operations workspace</h2>
                <p>Dynamic refinery/unit layout · simulated development data.</p>
              </div>
              <div className="read-only-badge"><ShieldCheck size={17} /> Read-only mode</div>
            </div>

            <UnitScopeBar
              siteName={site?.site ?? "Refinery"}
              units={site?.units ?? []}
              activeUnit={activeUnit}
              onChange={changeActiveUnit}
            />

            <DashboardCustomizer shift={shift} tags={tags} scopeUnit={activeUnit} />
          </section>
        )}

        {view === "chat" && (
          <section className="content chat-layout">
            <div className="chat-intro">
              <span className="eyebrow">EMBEDDED LOCAL AI</span>
              <h2>Ask about operations</h2>
              <p>Scope: {activeUnitName}. Το local model λαμβάνει μόνο τα structured process data που χρειάζεται.</p>
            </div>
            <div className="chat-card">
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ρώτησε κάτι για τη λειτουργία…" />
              <div className="chat-actions">
                <span><ShieldCheck size={15} /> No external AI · data stays local</span>
                <button className="primary-button" onClick={() => void askAssistant()} disabled={asking || !shift}>{asking ? "Analyzing…" : "Analyze"}</button>
              </div>
              {answer && <div className="assistant-answer"><div className="answer-avatar"><Bot size={20} /></div><div><strong>FCC Assistant</strong><p>{answer}</p></div></div>}
            </div>
          </section>
        )}

        {view === "reports" && (
          <section className="content">
            <div className="hero-row"><div><span className="eyebrow">REPORTING</span><h2>{activeUnitName} report preview</h2><p>Πρώτη έκδοση του report πριν συνδεθεί το πραγματικό PI.</p></div></div>
            <article className="panel report-panel">
              <div className="report-header"><div><h3>07:00–15:00 Shift</h3><span>{activeUnitName}</span></div><FileText size={22} /></div>
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
            <div className="hero-row"><div><span className="eyebrow">LOCAL CONFIGURATION</span><h2>System settings</h2><p>Πραγματικά PI στοιχεία και μοντέλα παραμένουν μόνο τοπικά.</p></div></div>
            <div className="settings-grid">
              <article className="panel"><div className="panel-heading"><div><h3>PI Web API</h3><p>Read-only plant data source</p></div><Database size={20} /></div><div className="setting-line"><span>Status</span><strong>{capabilities?.pi_web_api ?? "not configured"}</strong></div></article>
              <article className="panel">
                <div className="panel-heading"><div><h3>Embedded local AI</h3><p>llama.cpp · localhost only · no Ollama</p></div><Bot size={20} /></div>
                <div className="setting-line"><span>Assets</span><strong>{capabilities?.local_ai ?? "not ready"}</strong></div>
                <div className="setting-line"><span>Runtime</span><strong>{runtime?.state.running ? `Running (PID ${runtime.state.pid})` : "Stopped"}</strong></div>
                <button className="primary-button" disabled={runtimeBusy} onClick={() => void setAiRunning(!runtime?.state.running)}>
                  {runtime?.state.running ? "Stop local AI" : "Start local AI"}
                </button>
              </article>
              <article className="panel"><div className="panel-heading"><div><h3>Security</h3><p>Process protection boundary</p></div><ShieldCheck size={20} /></div><div className="setting-line"><span>External AI</span><strong>Disabled</strong></div><div className="setting-line"><span>Plant writes</span><strong>Disabled</strong></div></article>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}