import { useEffect, useMemo, useRef, useState } from "react";
import { Bug, MessageSquareText, RefreshCw, TerminalSquare } from "lucide-react";
import "./DashboardConversationPanel.css";

type ConversationTurn = {
  user?: string;
  assistant?: string;
  action?: string;
  unit?: string | null;
};

type TraceEvent = {
  ts?: string;
  stage?: string;
  payload?: Record<string, unknown>;
};

type DebugPayload = {
  conversation?: ConversationTurn[];
  events?: TraceEvent[];
};

const DEBUG_URL = "http://127.0.0.1:8765/api/v1/debug/dashboard?workspace=default&limit=100";

function eventSummary(event: TraceEvent) {
  const payload = event.payload ?? {};
  const command = typeof payload.command === "string" ? payload.command : "";
  const error = typeof payload.error === "string" ? payload.error : "";
  const message = typeof payload.message === "string" ? payload.message : "";
  const route = typeof payload.route === "string" ? payload.route : "";
  const bits = [command, route ? `route=${route}` : "", error || message].filter(Boolean);
  return bits.join(" · ");
}

export function DashboardConversationPanel() {
  const [payload, setPayload] = useState<DebugPayload>({});
  const [mode, setMode] = useState<"conversation" | "console">("conversation");
  const [open, setOpen] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  async function refresh() {
    setRefreshing(true);
    try {
      const response = await fetch(DEBUG_URL);
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      setPayload(await response.json() as DebugPayload);
    } catch {
      // This panel is diagnostic only; it must never interfere with dashboard execution.
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 1500);
    return () => window.clearInterval(timer);
  }, []);

  const conversation = payload.conversation ?? [];
  const events = payload.events ?? [];
  const importantEvents = useMemo(
    () => events.filter((event) => {
      const stage = event.stage ?? "";
      return stage.includes("command") || stage.includes("agent") || stage.includes("runtime") || stage.includes("error");
    }),
    [events],
  );

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [conversation.length, importantEvents.length, mode]);

  return (
    <section className={`dashboard-conversation-panel ${open ? "open" : "collapsed"}`}>
      <header className="dashboard-conversation-head">
        <div className="dashboard-conversation-title">
          <MessageSquareText size={17} />
          <div><strong>Conversation</strong><span>Persistent local command history</span></div>
        </div>
        <div className="dashboard-conversation-actions">
          <button className={mode === "conversation" ? "active" : ""} onClick={() => setMode("conversation")}><MessageSquareText size={14} /> Chat</button>
          <button className={mode === "console" ? "active" : ""} onClick={() => setMode("console")}><TerminalSquare size={14} /> Console</button>
          <button title="Refresh inspector" onClick={() => void refresh()}><RefreshCw className={refreshing ? "spin" : ""} size={14} /></button>
          <button onClick={() => setOpen((value) => !value)}>{open ? "Collapse" : "Expand"}</button>
        </div>
      </header>

      {open && <div className="dashboard-conversation-scroll" ref={scrollRef}>
        {mode === "conversation" ? (
          conversation.length ? conversation.map((turn, index) => <div className="conversation-turn" key={`${index}-${turn.user ?? ""}`}>
            <div className="conversation-message user"><span>You</span><p>{turn.user || "—"}</p></div>
            <div className="conversation-message assistant"><span>FCC Assistant</span><p>{turn.assistant || "—"}</p>{turn.action && <small>{turn.action}{turn.unit ? ` · ${turn.unit}` : ""}</small>}</div>
          </div>) : <div className="conversation-empty">No conversation recorded yet.</div>
        ) : (
          importantEvents.length ? importantEvents.map((event, index) => {
            const stage = event.stage ?? "event";
            const isError = stage.includes("error") || stage.includes("rejected");
            return <div className={`console-line ${isError ? "error" : ""}`} key={`${event.ts ?? index}-${stage}`}>
              <span className="console-time">{event.ts ? new Date(event.ts).toLocaleTimeString() : "--:--:--"}</span>
              <strong>{stage}</strong>
              <code>{eventSummary(event) || JSON.stringify(event.payload ?? {})}</code>
            </div>;
          }) : <div className="conversation-empty"><Bug size={16} /> No diagnostic events yet.</div>
        )}
      </div>}
    </section>
  );
}
