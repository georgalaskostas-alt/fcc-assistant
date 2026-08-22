import { useEffect, useMemo, useState } from "react";
import { Bot, Mic, Send, ShieldCheck } from "lucide-react";
import { api, DashboardWidget, DashboardWorkspace, DemoShiftResponse, SimulatorTag } from "./api";

type Props = {
  shift: DemoShiftResponse | null;
  tags: SimulatorTag[];
};

type Point = { Timestamp: string; Value: number };

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
    return (
      <article className="workspace-card workspace-card-trend">
        <div className="workspace-card-head"><div><span>{widget.unit_key.toUpperCase()}</span><h3>{widget.title}</h3></div><small>{widget.period}</small></div>
        <TrendChart widget={widget} shift={shift} tags={tags} />
      </article>
    );
  }

  if (widget.type === "average") {
    const value = mean(series[0] ?? []);
    const unit = unitFor(widget.tag_keys[0] ?? "", tags);
    return (
      <article className="workspace-card workspace-card-kpi">
        <div className="workspace-card-head"><div><span>{widget.unit_key.toUpperCase()}</span><h3>{widget.title}</h3></div><small>{widget.period}</small></div>
        <div className="workspace-kpi-value">{value == null ? "—" : value.toFixed(2)} <small>{unit}</small></div>
        <div className="workspace-kpi-caption">Average over selected period</div>
      </article>
    );
  }

  if (widget.type === "kpi") {
    const value = latest(series[0] ?? []);
    const unit = unitFor(widget.tag_keys[0] ?? "", tags);
    return (
      <article className="workspace-card workspace-card-kpi">
        <div className="workspace-card-head"><div><span>{widget.unit_key.toUpperCase()}</span><h3>{widget.title}</h3></div><small>LIVE</small></div>
        <div className="workspace-kpi-value">{value == null ? "—" : value.toFixed(1)} <small>{unit}</small></div>
        <div className="workspace-kpi-caption">Latest available value</div>
      </article>
    );
  }

  const unitTags = tags.filter((tag) => tag.group || widget.unit_key === "fcc");
  const summaryItems = unitTags.slice(0, 4).map((tag) => ({ tag, value: latest(shift?.data[tag.key]?.Items ?? []) }));
  return (
    <article className="workspace-card workspace-card-summary">
      <div className="workspace-card-head"><div><span>{widget.unit_key.toUpperCase()}</span><h3>{widget.title}</h3></div><small>SUMMARY</small></div>
      <div className="summary-grid">
        {summaryItems.map(({ tag, value }) => <div key={tag.key}><span>{tag.name}</span><strong>{value == null ? "—" : value.toFixed(1)} {tag.unit}</strong></div>)}
      </div>
    </article>
  );
}

export function DashboardCustomizer({ shift, tags }: Props) {
  const [workspace, setWorkspace] = useState<DashboardWorkspace | null>(null);
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setWorkspace(await api.dashboardWorkspace("default"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard workspace");
    }
  }

  useEffect(() => { void load(); }, []);

  async function applyCommand() {
    const value = command.trim();
    if (!value) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api.dashboardCommand(value, "default");
      setWorkspace(response.workspace);
      setCommand("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to apply dashboard command");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workspace-shell">
      <div className="workspace-command-bar">
        <Bot size={17} />
        <input
          value={command}
          onChange={(event) => setCommand(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") void applyCommand(); }}
          placeholder="Πες τι θέλεις να αλλάξω στην οθόνη…"
        />
        <button className="command-icon-button" title="Local voice input (coming next)" disabled><Mic size={17} /></button>
        <button className="command-send-button" disabled={busy || !command.trim()} onClick={() => void applyCommand()}>
          {busy ? "…" : <Send size={16} />}
        </button>
      </div>
      <div className="workspace-safety"><ShieldCheck size={13} /> Workspace only · read-only PI/DCS</div>
      {error && <div className="error-banner workspace-error">{error}</div>}

      {(workspace?.widgets.length ?? 0) > 0 && (
        <div className="workspace-render-grid">
          {workspace?.widgets.map((widget) => <WorkspaceWidgetCard key={widget.id} widget={widget} shift={shift} tags={tags} />)}
        </div>
      )}
    </div>
  );
}
