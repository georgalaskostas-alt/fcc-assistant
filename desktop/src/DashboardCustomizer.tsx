import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Bot,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Mic,
  Minimize2,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from "lucide-react";
import {
  api,
  DashboardWidget,
  DashboardWidgetLayout,
  DashboardWorkspace,
  DemoShiftResponse,
  SimulatorTag,
  SpeechTranscript,
} from "./api";
import { LocalRecorder, startLocalPcmRecorder } from "./speech";

type Props = {
  shift: DemoShiftResponse | null;
  tags: SimulatorTag[];
  scopeUnit?: string;
};

type Point = { Timestamp: string; Value: number };
type UnitWidgetGroup = { unitKey: string; widgets: DashboardWidget[] };
type VoiceState = "idle" | "listening" | "transcribing" | "executing";
type CachedPreview = { result: SpeechTranscript; audioSize: number; at: number };

const WIDTH_STEPS: DashboardWidgetLayout["width"][] = [3, 4, 6, 8, 12];
const HEIGHT_STEPS: DashboardWidgetLayout["height"][] = ["compact", "normal", "tall"];

function defaultLayout(widget: DashboardWidget, index: number): DashboardWidgetLayout {
  if (widget.layout) return widget.layout;
  if (widget.type === "trend") return { order: index, width: 12, height: "tall" };
  if (widget.type === "summary") return { order: index, width: 6, height: "normal" };
  return { order: index, width: 4, height: "compact" };
}

function autoLayoutFor(widget: DashboardWidget, index: number, count: number): DashboardWidgetLayout {
  if (count <= 1) return { order: index, width: 12, height: widget.type === "trend" ? "tall" : widget.type === "summary" ? "normal" : "compact" };
  if (count === 2) return { order: index, width: 6, height: widget.type === "trend" ? "tall" : "normal" };
  if (count === 3) return widget.type === "trend"
    ? { order: index, width: 12, height: "tall" }
    : { order: index, width: 6, height: widget.type === "summary" ? "normal" : "compact" };
  if (count <= 6) {
    if (widget.type === "trend") return { order: index, width: 8, height: "tall" };
    if (widget.type === "summary") return { order: index, width: 4, height: "normal" };
    return { order: index, width: 4, height: "compact" };
  }
  if (widget.type === "trend") return { order: index, width: 6, height: "normal" };
  if (widget.type === "summary") return { order: index, width: 6, height: "normal" };
  return { order: index, width: 3, height: "compact" };
}

function normalizeWorkspace(workspace: DashboardWorkspace): DashboardWorkspace {
  const widgets = workspace.widgets
    .map((widget, index) => ({ ...widget, layout: defaultLayout(widget, index) }))
    .sort((a, b) => (a.layout?.order ?? 0) - (b.layout?.order ?? 0))
    .map((widget, index) => ({ ...widget, layout: { ...defaultLayout(widget, index), order: index } }));
  return { ...workspace, widgets };
}

function seriesFor(widget: DashboardWidget, shift: DemoShiftResponse | null): Point[][] {
  return widget.tag_keys.map((key) => shift?.data[key]?.Items ?? []);
}

function mean(points: Point[]) {
  if (!points.length) return null;
  return points.reduce((sum, point) => sum + point.Value, 0) / points.length;
}

function latest(points: Point[]) {
  return points.length ? points[points.length - 1].Value : null;
}

function unitFor(key: string, tags: SimulatorTag[]) {
  return tags.find((tag) => tag.key === key)?.unit ?? "";
}

function cleanVoiceTranscript(value: string) {
  return value
    .replace(/^\s*(πρόεδρε|προεδρε)\s*[:;,.-]?\s*/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function TrendChart({ widget, shift, tags }: { widget: DashboardWidget; shift: DemoShiftResponse | null; tags: SimulatorTag[] }) {
  const series = seriesFor(widget, shift);
  const values = series.flat().map((point) => point.Value);
  if (!values.length) return <div className="widget-empty">No data</div>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 0.0001);
  const width = 680;
  const height = 190;
  const pad = 14;
  return (
    <div className="trend-widget-body">
      <div className="trend-latest-row">
        {widget.tag_keys.map((key, index) => {
          const value = latest(series[index] ?? []);
          return <span key={key}><strong>{value == null ? "—" : value.toFixed(1)}</strong> {unitFor(key, tags)}</span>;
        })}
      </div>
      <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-label={`${widget.title} trend`}>
        <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} className="chart-axis" />
        <line x1={pad} y1={pad} x2={pad} y2={height - pad} className="chart-axis" />
        {series.map((points, seriesIndex) => {
          const polyline = points.map((point, index) => {
            const x = pad + (index / Math.max(points.length - 1, 1)) * (width - pad * 2);
            const y = height - pad - ((point.Value - min) / span) * (height - pad * 2);
            return `${x},${y}`;
          }).join(" ");
          return <polyline key={widget.tag_keys[seriesIndex] ?? seriesIndex} points={polyline} className={`chart-line chart-line-${seriesIndex % 3}`} />;
        })}
      </svg>
      <div className="trend-range"><span>{min.toFixed(1)}</span><span>{widget.period}</span><span>{max.toFixed(1)}</span></div>
    </div>
  );
}

function WorkspaceWidgetCard({ widget, shift, tags }: { widget: DashboardWidget; shift: DemoShiftResponse | null; tags: SimulatorTag[] }) {
  const series = useMemo(() => seriesFor(widget, shift), [widget, shift]);
  if (widget.type === "trend") return <><div className="workspace-card-head"><div><span>{widget.unit_key.toUpperCase()}</span><h3>{widget.title}</h3></div><small>{widget.period}</small></div><TrendChart widget={widget} shift={shift} tags={tags} /></>;
  if (widget.type === "average") {
    const value = mean(series[0] ?? []);
    const unit = unitFor(widget.tag_keys[0] ?? "", tags);
    return <><div className="workspace-card-head"><div><span>{widget.unit_key.toUpperCase()}</span><h3>{widget.title}</h3></div><small>{widget.period}</small></div><div className="workspace-kpi-value">{value == null ? "—" : value.toFixed(2)} <small>{unit}</small></div><div className="workspace-kpi-caption">Average over selected period</div></>;
  }
  if (widget.type === "kpi") {
    const value = latest(series[0] ?? []);
    const unit = unitFor(widget.tag_keys[0] ?? "", tags);
    return <><div className="workspace-card-head"><div><span>{widget.unit_key.toUpperCase()}</span><h3>{widget.title}</h3></div><small>LIVE</small></div><div className="workspace-kpi-value">{value == null ? "—" : value.toFixed(1)} <small>{unit}</small></div><div className="workspace-kpi-caption">Latest available value</div></>;
  }
  const summaryItems = tags.slice(0, 4).map((tag) => ({ tag, value: latest(shift?.data[tag.key]?.Items ?? []) }));
  return <><div className="workspace-card-head"><div><span>{widget.unit_key.toUpperCase()}</span><h3>{widget.title}</h3></div><small>SUMMARY</small></div><div className="summary-grid">{summaryItems.map(({ tag, value }) => <div key={tag.key}><span>{tag.name}</span><strong>{value == null ? "—" : value.toFixed(1)} {tag.unit}</strong></div>)}</div></>;
}

export function DashboardCustomizer({ shift, tags, scopeUnit = "all" }: Props) {
  const [workspace, setWorkspace] = useState<DashboardWorkspace | null>(null);
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceHint, setVoiceHint] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [voiceModeEnabled, setVoiceModeEnabled] = useState(false);
  const recorderRef = useRef<LocalRecorder | null>(null);
  const previewTimerRef = useRef<number | null>(null);
  const previewBusyRef = useRef(false);
  const finalizingVoiceRef = useRef(false);
  const lastPreviewRef = useRef<CachedPreview | null>(null);
  const lastReplyRef = useRef<string | null>(null);
  const [editLayout, setEditLayout] = useState(false);
  const [autoLayout, setAutoLayout] = useState(() => window.localStorage.getItem("fcc-auto-layout") !== "off");

  function setAutoLayoutPreference(enabled: boolean) {
    setAutoLayout(enabled);
    window.localStorage.setItem("fcc-auto-layout", enabled ? "on" : "off");
  }

  function voiceTerms() {
    const processTerms = ["FCC", "HCU", "Hydrocracker", "Hydro cracker", "VDU", "Vacuum Distillation", "reaction temperature", "reactor temperature", "feed flow"];
    return Array.from(new Set([...processTerms, ...tags.flatMap((tag) => [tag.key, tag.name, tag.group, tag.unit_key ?? "", tag.semantic_key ?? ""]).filter(Boolean)]));
  }

  function clearPreviewTimer() {
    if (previewTimerRef.current != null) {
      window.clearInterval(previewTimerRef.current);
      previewTimerRef.current = null;
    }
  }

  async function speak(text: string) {
    try { await invoke("speak_text", { text }); } catch { /* optional */ }
  }

  async function load() {
    try {
      setWorkspace(normalizeWorkspace(await api.dashboardWorkspace("default")));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard workspace");
    }
  }

  useEffect(() => { setCommand(""); void load(); }, []);
  useEffect(() => () => { clearPreviewTimer(); void recorderRef.current?.cancel(); }, []);

  async function persist(next: DashboardWorkspace) {
    setWorkspace(next);
    setSaving(true);
    try {
      setWorkspace(normalizeWorkspace(await api.saveDashboardWorkspace(next)));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save dashboard layout");
    } finally { setSaving(false); }
  }

  async function executeCommand(value: string, clearAfter = true): Promise<boolean> {
    const clean = value.trim();
    if (!clean) return false;
    setBusy(true);
    setError(null);
    lastReplyRef.current = null;
    try {
      const response = await api.dashboardCommand(clean, "default");
      setWorkspace(normalizeWorkspace(response.workspace));
      lastReplyRef.current = response.message?.trim() || null;
      if (response.message?.trim()) setVoiceHint(response.message.trim());
      if (clearAfter) setCommand("");
      if (response.plan.warnings?.length) setError(response.plan.warnings.join(" · "));
      window.dispatchEvent(new Event("fcc-dashboard-conversation-updated"));
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to apply dashboard command");
      window.dispatchEvent(new Event("fcc-dashboard-conversation-updated"));
      return false;
    } finally { setBusy(false); }
  }

  async function applyCommand() {
    const submitted = command.trim();
    if (!submitted || busy || voiceState !== "idle" || voiceModeEnabled) return;
    setCommand("");
    setVoiceHint("Εκτελώ…");
    window.dispatchEvent(new CustomEvent("fcc-dashboard-command-submitted", { detail: { command: submitted } }));
    await executeCommand(submitted, false);
  }

  async function previewVoiceTranscript() {
    if (!recorderRef.current || previewBusyRef.current || finalizingVoiceRef.current) return;
    previewBusyRef.current = true;
    try {
      const audio = await recorderRef.current.snapshot();
      if (audio.size < 14000) return;
      const result = await api.transcribeSpeech(audio, "all", voiceTerms(), "partial");
      const cleanedText = cleanVoiceTranscript(result.text);
      lastPreviewRef.current = { result: { ...result, text: cleanedText }, audioSize: audio.size, at: Date.now() };
      if (cleanedText) { setCommand(cleanedText); setVoiceHint(cleanedText); }
    } catch { /* best effort */ } finally { previewBusyRef.current = false; }
  }

  async function startVoiceCycle() {
    if (recorderRef.current || finalizingVoiceRef.current || voiceState !== "idle") return;
    setError(null); setCommand(""); setVoiceModeEnabled(true); setVoiceState("listening"); setVoiceHint("Ακούω"); lastPreviewRef.current = null;
    recorderRef.current = await startLocalPcmRecorder({ silenceMs: 1150, maxDurationMs: 25000, onSilence: () => { void finishVoiceCapture(); } });
    clearPreviewTimer();
    previewTimerRef.current = window.setInterval(() => { void previewVoiceTranscript(); }, 1000);
  }

  async function finishVoiceCapture() {
    if (finalizingVoiceRef.current || !recorderRef.current) return;
    finalizingVoiceRef.current = true; clearPreviewTimer(); setError(null); setVoiceState("transcribing"); setVoiceHint("Επεξεργάζομαι…");
    try {
      const recorder = recorderRef.current; recorderRef.current = null;
      const audio = await recorder.stop();
      const result = await api.transcribeSpeech(audio, "all", voiceTerms(), "final");
      const finalText = cleanVoiceTranscript(result.text); setCommand(finalText);
      if (!finalText || result.confidence_level === "low") {
        setVoiceHint(finalText ? "Χρειάζομαι διευκρίνιση" : "Δεν άκουσα καθαρά");
        await speak("Δεν κατάλαβα καθαρά την εντολή.");
        return;
      }
      setVoiceState("executing"); setVoiceHint("Εκτελώ…");
      window.dispatchEvent(new CustomEvent("fcc-dashboard-command-submitted", { detail: { command: finalText } }));
      const ok = await executeCommand(finalText, false);
      if (ok) { const reply = lastReplyRef.current; setVoiceHint(reply || "Έτοιμο"); await speak(reply || "Έγινε."); }
      else { setVoiceHint("Δεν μπόρεσα να την εκτελέσω"); await speak("Δεν μπόρεσα να εκτελέσω την εντολή."); }
      setCommand("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Voice transcription failed");
      await speak("Υπήρξε πρόβλημα στην επεξεργασία της φωνής.");
    } finally { finalizingVoiceRef.current = false; setVoiceModeEnabled(false); setVoiceState("idle"); }
  }

  async function toggleVoiceMode() {
    setError(null);
    if (voiceModeEnabled || recorderRef.current) {
      clearPreviewTimer(); const recorder = recorderRef.current; recorderRef.current = null;
      if (recorder) await recorder.cancel();
      setVoiceModeEnabled(false); setVoiceState("idle"); setVoiceHint(null); setCommand(""); return;
    }
    try {
      const status = await api.speechStatus();
      if (!status.ready) throw new Error("Το local speech model δεν είναι ακόμη εγκατεστημένο.");
      setCommand(""); await startVoiceCycle();
    } catch (err) {
      setVoiceModeEnabled(false); setVoiceState("idle"); setError(err instanceof Error ? err.message : "Unable to start microphone");
    }
  }

  function reorder(widgetId: string, delta: number) {
    if (!workspace) return;
    setAutoLayoutPreference(false);
    const widgets = [...workspace.widgets].sort((a, b) => (a.layout?.order ?? 0) - (b.layout?.order ?? 0));
    const from = widgets.findIndex((widget) => widget.id === widgetId);
    const to = Math.max(0, Math.min(widgets.length - 1, from + delta));
    if (from < 0 || from === to) return;
    const [moved] = widgets.splice(from, 1); widgets.splice(to, 0, moved);
    void persist(normalizeWorkspace({ ...workspace, widgets }));
  }

  function resize(widgetId: string, direction: number) {
    if (!workspace) return;
    setAutoLayoutPreference(false);
    const widgets = workspace.widgets.map((widget, index) => {
      if (widget.id !== widgetId) return widget;
      const layout = defaultLayout(widget, index);
      const current = Math.max(0, WIDTH_STEPS.indexOf(layout.width));
      const nextWidth = WIDTH_STEPS[Math.max(0, Math.min(WIDTH_STEPS.length - 1, current + direction))];
      const heightIndex = Math.max(0, HEIGHT_STEPS.indexOf(layout.height));
      const nextHeight = HEIGHT_STEPS[Math.max(0, Math.min(HEIGHT_STEPS.length - 1, heightIndex + direction))];
      return { ...widget, layout: { ...layout, width: nextWidth, height: nextHeight } };
    });
    void persist(normalizeWorkspace({ ...workspace, widgets }));
  }

  function removeWidget(widgetId: string) {
    if (!workspace) return;
    void persist(normalizeWorkspace({ ...workspace, widgets: workspace.widgets.filter((widget) => widget.id !== widgetId) }));
  }

  const orderedWidgets = useMemo(() => [...(workspace?.widgets ?? [])].sort((a, b) => (a.layout?.order ?? 0) - (b.layout?.order ?? 0)), [workspace]);
  const allUnitGroups = useMemo<UnitWidgetGroup[]>(() => {
    const groups = new Map<string, DashboardWidget[]>();
    for (const widget of orderedWidgets) { const key = widget.unit_key || "site"; groups.set(key, [...(groups.get(key) ?? []), widget]); }
    return [...groups.entries()].map(([unitKey, widgets]) => ({ unitKey, widgets }));
  }, [orderedWidgets]);
  const unitGroups = useMemo(() => scopeUnit === "all" ? allUnitGroups : allUnitGroups.filter((group) => group.unitKey === scopeUnit), [allUnitGroups, scopeUnit]);
  const unitContainerWidth = scopeUnit !== "all" || unitGroups.length <= 1 ? "100%" : unitGroups.length === 2 ? "calc(50% - 6px)" : "min(100%, 680px)";
  const microphoneLabel = voiceModeEnabled ? "Stop current voice command" : "Speak one command";
  const idleReply = voiceState === "idle" && voiceHint && !["Ακούω", "Επεξεργάζομαι…", "Εκτελώ…"].includes(voiceHint) ? voiceHint : null;
  const inlineKind = error ? "error" : voiceState === "transcribing" || voiceState === "executing" ? "processing" : voiceState === "listening" ? "listening" : idleReply ? "success" : "idle";
  const inlineText = error ?? (voiceState === "transcribing" ? "Επεξεργάζομαι" : null) ?? (voiceState === "executing" ? "Εκτελώ" : null) ?? (voiceState === "listening" ? (command.trim() ? "Ακούω" : "Μίλα") : null) ?? idleReply;

  return (
    <div className="workspace-shell">
      <div className="workspace-command-wrap" style={{ position: "sticky", top: 0, zIndex: 30, paddingTop: 8, paddingBottom: 8, background: "linear-gradient(180deg, rgba(6,14,27,.98) 0%, rgba(6,14,27,.94) 82%, rgba(6,14,27,0) 100%)" }}>
        <div className={`workspace-command-bar voice-command-bar voice-command-${inlineKind}`}>
          <Bot size={17} />
          <input value={command} onChange={(event) => setCommand(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); void applyCommand(); } }} placeholder={scopeUnit === "all" ? "Πες ή γράψε τι θέλεις να δεις σε όλες τις μονάδες…" : `Πες ή γράψε τι θέλεις να δεις στο ${scopeUnit.toUpperCase()}…`} aria-label="Workspace command" />
          {inlineText && (
            <div className={`voice-inline-state voice-inline-${inlineKind}`} role={error ? "alert" : "status"} title={inlineText}>
              {voiceState === "listening" ? <span className="voice-waveform" aria-hidden="true"><i /><i /><i /><i /></span> : voiceState === "transcribing" || voiceState === "executing" ? <span className="voice-orbit" aria-hidden="true" /> : <span className="voice-inline-dot" aria-hidden="true" />}
              <span>{inlineText}</span>
            </div>
          )}
          <button className={`command-icon-button voice-${voiceState} ${voiceModeEnabled ? "voice-mode-enabled" : ""}`} title={microphoneLabel} onClick={() => void toggleVoiceMode()}><Mic size={17} /></button>
          <button className="command-send-button" disabled={busy || !command.trim() || voiceState !== "idle" || voiceModeEnabled} onClick={() => void applyCommand()}>{busy ? "…" : <Send size={16} />}</button>
        </div>
        <div className="workspace-safety"><ShieldCheck size={13} /> Current scope: {scopeUnit === "all" ? "All Units" : scopeUnit.toUpperCase()} · Local voice · read-only PI/DCS</div>
      </div>

      <div className="workspace-toolbar">
        <button className={editLayout ? "workspace-tool active" : "workspace-tool"} onClick={() => setEditLayout((value) => !value)}><SlidersHorizontal size={15} /> Arrange</button>
        <button className={autoLayout ? "workspace-tool active" : "workspace-tool"} onClick={() => setAutoLayoutPreference(!autoLayout)} title="Automatically resize and reflow widgets">Auto layout {autoLayout ? "ON" : "OFF"}</button>
        <span className="workspace-save-state">{saving ? "Saving…" : "Saved locally"}</span>
      </div>

      {unitGroups.length === 0 && orderedWidgets.length > 0 && scopeUnit !== "all" && <div className="widget-empty" style={{ marginTop: 16 }}>No widgets configured for {scopeUnit.toUpperCase()} yet.</div>}
      {unitGroups.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-start", marginTop: 10 }}>
          {unitGroups.map((group) => {
            const showGroupChrome = scopeUnit === "all" && allUnitGroups.length > 1;
            return (
              <section key={group.unitKey} style={{ width: unitContainerWidth, flexGrow: 1, minWidth: showGroupChrome ? 420 : 0, border: showGroupChrome ? "1px solid #1f2b36" : "none", borderRadius: 14, padding: showGroupChrome ? 12 : 0, background: showGroupChrome ? "rgba(15,22,29,.45)" : "transparent" }}>
                {showGroupChrome && <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "0 2px 10px" }}><div><span className="eyebrow">PROCESS UNIT</span><h3 style={{ marginTop: 3 }}>{group.unitKey.toUpperCase()}</h3></div><small style={{ color: "#607287", fontSize: 9 }}>{group.widgets.length} widgets</small></div>}
                <div className={editLayout ? "workspace-render-grid editing" : "workspace-render-grid"} style={{ marginTop: showGroupChrome ? 0 : 10 }}>
                  {group.widgets.map((widget, index) => {
                    const globalIndex = orderedWidgets.findIndex((item) => item.id === widget.id);
                    const layout = autoLayout ? autoLayoutFor(widget, index, group.widgets.length) : defaultLayout(widget, globalIndex);
                    return (
                      <article className={`workspace-card workspace-card-${widget.type} workspace-height-${layout.height}`} style={{ gridColumn: `span ${layout.width}` }} key={widget.id}>
                        {editLayout && <div className="workspace-card-controls"><button title="Move left" disabled={globalIndex === 0 || saving} onClick={() => reorder(widget.id, -1)}><ChevronLeft size={14} /></button><button title="Move right" disabled={globalIndex === orderedWidgets.length - 1 || saving} onClick={() => reorder(widget.id, 1)}><ChevronRight size={14} /></button><button title="Make smaller" disabled={saving} onClick={() => resize(widget.id, -1)}><Minimize2 size={14} /></button><button title="Make larger" disabled={saving} onClick={() => resize(widget.id, 1)}><Maximize2 size={14} /></button><button className="danger" title="Remove from workspace" disabled={saving} onClick={() => removeWidget(widget.id)}><X size={14} /></button></div>}
                        <WorkspaceWidgetCard widget={{ ...widget, layout }} shift={shift} tags={tags} />
                      </article>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
