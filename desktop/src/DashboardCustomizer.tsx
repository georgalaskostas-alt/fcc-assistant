import { useEffect, useMemo, useState } from "react";
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
} from "./api";

type Props = {
  shift: DemoShiftResponse | null;
  tags: SimulatorTag[];
  scopeUnit?: string;
};

type Point = { Timestamp: string; Value: number };
type UnitWidgetGroup = { unitKey: string; widgets: DashboardWidget[] };

const WIDTH_STEPS: DashboardWidgetLayout["width"][] = [3, 4, 6, 8, 12];
const HEIGHT_STEPS: DashboardWidgetLayout["height"][] = ["compact", "normal", "tall"];

function defaultLayout(widget: DashboardWidget, index: number): DashboardWidgetLayout {
  if (widget.layout) return widget.layout;
  if (widget.type === "trend") return { order: index, width: 12, height: "tall" };
  if (widget.type === "summary") return { order: index, width: 6, height: "normal" };
  return { order: index, width: 4, height: "compact" };
}

function autoLayoutFor(widget: DashboardWidget, index: number, count: number): DashboardWidgetLayout {
  if (count <= 1) {
    return {
      order: index,
      width: 12,
      height: widget.type === "trend" ? "tall" : widget.type === "summary" ? "normal" : "compact",
    };
  }
  if (count === 2) {
    return { order: index, width: 6, height: widget.type === "trend" ? "tall" : "normal" };
  }
  if (count === 3) {
    if (widget.type === "trend") return { order: index, width: 12, height: "tall" };
    return { order: index, width: 6, height: widget.type === "summary" ? "normal" : "compact" };
  }
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

  if (widget.type === "trend") {
    return <><div className="workspace-card-head"><div><span>{widget.unit_key.toUpperCase()}</span><h3>{widget.title}</h3></div><small>{widget.period}</small></div><TrendChart widget={widget} shift={shift} tags={tags} /></>;
  }
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
  const [commandOpen, setCommandOpen] = useState(false);
  const [editLayout, setEditLayout] = useState(false);
  const [autoLayout, setAutoLayout] = useState(() => window.localStorage.getItem("fcc-auto-layout") !== "off");

  function setAutoLayoutPreference(enabled: boolean) {
    setAutoLayout(enabled);
    window.localStorage.setItem("fcc-auto-layout", enabled ? "on" : "off");
  }

  async function load() {
    try {
      setWorkspace(normalizeWorkspace(await api.dashboardWorkspace("default")));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard workspace");
    }
  }

  useEffect(() => { void load(); }, []);

  async function persist(next: DashboardWorkspace) {
    setWorkspace(next);
    setSaving(true);
    try {
      setWorkspace(normalizeWorkspace(await api.saveDashboardWorkspace(next)));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save dashboard layout");
    } finally {
      setSaving(false);
    }
  }

  async function applyCommand() {
    const value = command.trim();
    if (!value) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api.dashboardCommand(value, "default");
      setWorkspace(normalizeWorkspace(response.workspace));
      setCommand("");
      if (response.plan.warnings?.length) setError(response.plan.warnings.join(" · "));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to apply dashboard command");
    } finally {
      setBusy(false);
    }
  }

  function reorder(widgetId: string, delta: number) {
    if (!workspace) return;
    setAutoLayoutPreference(false);
    const widgets = [...workspace.widgets].sort((a, b) => (a.layout?.order ?? 0) - (b.layout?.order ?? 0));
    const from = widgets.findIndex((widget) => widget.id === widgetId);
    const to = Math.max(0, Math.min(widgets.length - 1, from + delta));
    if (from < 0 || from === to) return;
    const [moved] = widgets.splice(from, 1);
    widgets.splice(to, 0, moved);
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
    for (const widget of orderedWidgets) {
      const key = widget.unit_key || "site";
      groups.set(key, [...(groups.get(key) ?? []), widget]);
    }
    return [...groups.entries()].map(([unitKey, widgets]) => ({ unitKey, widgets }));
  }, [orderedWidgets]);

  const unitGroups = useMemo(
    () => scopeUnit === "all" ? allUnitGroups : allUnitGroups.filter((group) => group.unitKey === scopeUnit),
    [allUnitGroups, scopeUnit],
  );

  const unitContainerWidth = scopeUnit !== "all" || unitGroups.length <= 1
    ? "100%"
    : unitGroups.length === 2
      ? "calc(50% - 6px)"
      : "min(100%, 680px)";

  return (
    <div className="workspace-shell">
      <div className="workspace-toolbar">
        <button className={commandOpen ? "workspace-tool active" : "workspace-tool"} onClick={() => setCommandOpen((value) => !value)}><Bot size={15} /> Command</button>
        <button className={editLayout ? "workspace-tool active" : "workspace-tool"} onClick={() => setEditLayout((value) => !value)}><SlidersHorizontal size={15} /> Arrange</button>
        <button className={autoLayout ? "workspace-tool active" : "workspace-tool"} onClick={() => setAutoLayoutPreference(!autoLayout)} title="Automatically resize and reflow widgets">Auto layout {autoLayout ? "ON" : "OFF"}</button>
        <span className="workspace-save-state">{saving ? "Saving…" : "Saved locally"}</span>
      </div>

      {commandOpen && (
        <div className="workspace-command-wrap">
          <div className="workspace-command-bar">
            <Bot size={17} />
            <input autoFocus value={command} onChange={(event) => setCommand(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void applyCommand(); }} placeholder="π.χ. Βάλε τροφοδοσία και αντίδραση για FCC και Hydrocracker" />
            <button className="command-icon-button" title="Local voice input (coming next)" disabled><Mic size={17} /></button>
            <button className="command-send-button" disabled={busy || !command.trim()} onClick={() => void applyCommand()}>{busy ? "…" : <Send size={16} />}</button>
          </div>
          <div className="workspace-safety"><ShieldCheck size={13} /> Layout only · read-only PI/DCS</div>
        </div>
      )}

      {error && <div className="error-banner workspace-error">{error}</div>}

      {unitGroups.length === 0 && orderedWidgets.length > 0 && scopeUnit !== "all" && (
        <div className="widget-empty" style={{ marginTop: 16 }}>No widgets configured for {scopeUnit.toUpperCase()} yet.</div>
      )}

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
