import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BookOpen,
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
import { DashboardConversationPanel } from "./DashboardConversationPanel";
import { DashboardCustomizer } from "./DashboardCustomizer";
import { UnitKnowledgeView } from "./UnitKnowledgeView";
import { UnitScopeBar } from "./UnitScopeBar";

type View = "dashboard" | "chat" | "knowledge" | "reports" | "settings";

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
  { id: "knowledge", label: "Knowledge", icon: BookOpen },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "settings", label: "Settings", icon: Settings },
];

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

async function waitForBackend(attempts = 24, delayMs = 250) {
  let lastError: unknown = null;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await api.health();
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) await sleep(delayMs);
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Local backend did not become ready");
}

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
      const health = await waitForBackend();
      const [caps, bridgeSite, runtimeInfo, tagResponse, demo] = await Promise.all([
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
      let detail = err instanceof Error ? err.message : "Unable to connect to the local backend";
      try {
        const diagnostic = await api.backendRuntimeStatus();
        if (diagnostic.last_error) detail = `Backend startup failed: ${diagnostic.last_error}`;
        else if (diagnostic.terminated) detail = "Backend process terminated before becoming ready.";
        else if (!diagnostic.listening) detail = `Backend did not start listening on local port ${diagnostic.port}.`;
        if (diagnostic.recent_output.length) detail += ` · ${diagnostic.recent_output.at(-1)}`;
      } catch {
        // Browser-only development does not expose Tauri invoke; keep network error.
      }
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void api.health()
        .then(() => {
          if (!backendOk) void refresh();
          else setBackendOk(true);
        })
        .catch(() => setBackendOk(false));
    }, 4000);
    return () => window.clearInterval(timer);
  }, [backendOk]);

  const metrics = useMemo(() => tags.map((tag) => latestMetric(tag, shift)), [tags, shift]);
  const activeUnitName = activeUnit === "all"
    ? "All Units"
    : site?.units.find((unit) => unit.key === activeUnit)?.name ?? activeUnit.toUpperCase();

  function processEvidenceForUnit(unitKey: string): Record<string, unknown> {
    if (!shift) return {};
    const unitTagKeys = new Set(tags.filter((tag) => (tag.unit_key ?? tag.group) === unitKey).map((tag) => tag.key));
    return Object.fromEntries(Object.entries(shift.data).filter(([key]) => unitTagKeys.has(key)));
  }

  async function askAssistant() {
    if (!question.trim() || !shift) return;
    setAsking(true);
    setAnswer("");
    try {
      if (!runtime?.state.running) {
        await api.startAiRuntime();
        setRuntime(await api.aiRuntime());
      }
      if (activeUnit !== "all") {
        const response = await api.engineeringAnalyze(activeUnit, question.trim(), {
          source: "simulated development data",
          data_quality: "simulated",
          shift: processEvidenceForUnit(activeUnit),
        });
        setAnswer(response.answer);
      } else {
        const unitKeys = site?.units.map((unit) => unit.key) ?? [];
        const evidenceByUnit = Object.fromEntries(unitKeys.map((unitKey) => [unitKey, {
          source: "simulated development data",
          data_quality: "simulated",
          shift: processEvidenceForUnit(unitKey),
        }]));
        const response = await api.managementAnalyze("refinery", "refinery", unitKeys, question.trim(), evidenceByUnit);
        setAnswer(response.answer);
      }
    } catch (err) {
      setAnswer(`Δεν ήταν δυνατή η ανάλυση: ${err instanceof Error ? err.message : "unknown error"}`);
    } finally {
      setAsking(false);
    }
  }

  async function toggleRuntime() {
    if (!runtime) return;
    setRuntimeBusy(true);
    try {
      if (runtime.state.running) await api.stopAiRuntime();
      else await api.startAiRuntime();
      setRuntime(await api.aiRuntime());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to change local AI runtime state");
    } finally {
      setRuntimeBusy(false);
    }
  }

  const siteName = site?.site ?? "Refinery";
  const siteUnits = site?.units ?? [];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Activity size={25} /></div>
          <div><strong>FCC Assistant</strong><span>LOCAL PROCESS<br />INTELLIGENCE</span></div>
        </div>
        <nav>
          {NAV.map((item) => {
            const Icon = item.icon;
            return <button key={item.id} className={view === item.id ? "nav-item active" : "nav-item"} onClick={() => setView(item.id)}><Icon size={18} />{item.label}</button>;
          })}
        </nav>
        <div className="sidebar-footer">
          <div><ShieldCheck size={15} /> Embedded local AI</div>
          <small>External AI: disabled · Plant writes: disabled</small>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div><h2>{view === "chat" ? "Assistant" : view === "knowledge" ? "Knowledge" : view === "reports" ? "Reports" : view === "settings" ? "Settings" : "Dashboard"}</h2><span>{siteName} · {activeUnitName}</span></div>
          <div className="topbar-actions"><span className={backendOk ? "status-pill online" : "status-pill offline"}>Backend {backendOk ? "online" : "offline"}</span><button className="icon-button" onClick={() => void refresh()} disabled={loading} title="Refresh"><RefreshCw size={17} /></button></div>
        </header>

        <div className="content">
          {error && <div className="error-banner">{error}</div>}
          {view !== "reports" && view !== "settings" && <UnitScopeBar siteName={siteName} units={siteUnits} activeUnit={activeUnit} onChange={changeActiveUnit} />}

          {view === "dashboard" && <>
            <section className="section-head"><div><span className="eyebrow">OPERATING OVERVIEW</span><h1>Operations workspace</h1><p>Dynamic refinery/unit layout · source quality is shown explicitly.</p></div><span className="readonly-pill"><ShieldCheck size={15} /> Read-only mode</span></section>
            {backendOk ? <><DashboardConversationPanel /><DashboardCustomizer shift={shift} tags={tags} scopeUnit={activeUnit} /></> : <div className="placeholder-panel"><Database size={22} /><h3>Starting local backend…</h3><p>The workspace will load automatically when the packaged local service is ready.</p></div>}
          </>}

          {view === "chat" && <section className="assistant-panel">
            <div className="assistant-heading"><Bot size={22} /><div><h3>Local engineering assistant</h3><p>{activeUnit === "all" ? "Cross-unit management intelligence" : `Unit intelligence · ${activeUnitName}`}</p></div></div>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
            <button className="primary-button" disabled={asking || !backendOk} onClick={() => void askAssistant()}>{asking ? "Analyzing…" : "Ask the assistant"}</button>
            {answer && <div className="assistant-answer">{answer}</div>}
          </section>}

          {view === "knowledge" && <UnitKnowledgeView unitKey={activeUnit} unitName={activeUnitName} />}
          {view === "reports" && <section className="placeholder-panel"><FileText size={24} /><h3>Reports</h3><p>Shift and refinery reporting workspace will use the same governed evidence and role scope.</p></section>}
          {view === "settings" && <section className="settings-grid">
            <article className="settings-card"><Database size={20} /><h3>Data sources</h3><div className="settings-row"><span>PI Web API</span><strong>{capabilities?.pi_web_api ?? "unknown"}</strong></div><div className="settings-row"><span>Plant write access</span><strong>{capabilities?.plant_write_access ? "enabled" : "disabled"}</strong></div></article>
            <article className="settings-card"><Bot size={20} /><h3>Local AI</h3><div className="settings-row"><span>Runtime</span><strong>{runtime?.state.runtime ?? "unknown"}</strong></div><div className="settings-row"><span>Status</span><strong>{runtime?.state.running ? "running" : "stopped"}</strong></div><button className="secondary-button" onClick={() => void toggleRuntime()} disabled={runtimeBusy || !backendOk}>{runtimeBusy ? "Working…" : runtime?.state.running ? "Stop local AI" : "Start local AI"}</button></article>
          </section>}

          {view === "dashboard" && metrics.length > 0 && <div className="sr-only" aria-hidden="true">{metrics.map((metric) => `${metric.name} ${fmt(metric.value)}`).join(" · ")}</div>}
        </div>
      </main>
    </div>
  );
}
