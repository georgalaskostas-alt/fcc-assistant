import { useEffect, useState } from "react";
import { Bot, LayoutDashboard, ShieldCheck } from "lucide-react";
import { api, DashboardWorkspace } from "./api";

export function DashboardCustomizer() {
  const [workspace, setWorkspace] = useState<DashboardWorkspace | null>(null);
  const [command, setCommand] = useState("Βάλε γράφημα με την τροφοδοσία FCC για 8h");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setWorkspace(await api.dashboardWorkspace("default"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard workspace");
    }
  }

  useEffect(() => {
    void load();
  }, []);

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
    <article className="panel dashboard-customizer">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">NATURAL-LANGUAGE WORKSPACE</span>
          <h3>Πες μου πώς θέλεις την οθόνη</h3>
        </div>
        <Bot size={20} />
      </div>

      <p>Παράδειγμα: «Βάλε γράφημα τροφοδοσίας 8h, μέσο όρο O₂ και σύνοψη FCC.»</p>
      <div className="dashboard-command-row">
        <input
          value={command}
          onChange={(event) => setCommand(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void applyCommand();
          }}
          placeholder="Πες τι θέλεις να προσθέσω στο dashboard…"
        />
        <button className="primary-button" disabled={busy || !command.trim()} onClick={() => void applyCommand()}>
          {busy ? "Applying…" : "Apply"}
        </button>
      </div>
      <div className="security-chip"><ShieldCheck size={15} /><span>Αλλάζει μόνο το workspace · δεν γράφει στο PI/DCS</span></div>
      {error && <div className="error-banner">{error}</div>}

      <div className="workspace-widget-list">
        {(workspace?.widgets ?? []).map((widget) => (
          <div className="workspace-widget" key={widget.id}>
            <LayoutDashboard size={16} />
            <div>
              <strong>{widget.title}</strong>
              <span>{widget.type} · {widget.unit_key.toUpperCase()} · {widget.period}</span>
            </div>
          </div>
        ))}
        {workspace && workspace.widgets.length === 0 && <small>Δεν υπάρχουν ακόμη custom widgets.</small>}
      </div>
    </article>
  );
}
