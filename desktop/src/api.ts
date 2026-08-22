const API_BASE = "http://127.0.0.1:8000";

export type SystemCapabilities = {
  pi_web_api: string;
  local_ai: string;
  local_ai_runtime?: string;
  external_ai?: boolean;
  plant_write_access: boolean;
  features: string[];
};

export type BridgeUnitTag = {
  key: string;
  label: string;
  unit: string;
  aliases: string[];
  semantic_key?: string;
};

export type BridgeUnit = {
  key: string;
  name: string;
  tags: BridgeUnitTag[];
};

export type BridgeSite = {
  contract_version: string;
  site: string;
  read_only: boolean;
  units: BridgeUnit[];
};

export type SimulatorTag = {
  key: string;
  name: string;
  group: string;
  unit: string;
  unit_key?: string;
  semantic_key?: string;
};

export type SimulatorTagsResponse = {
  mode: string;
  scope?: string;
  count: number;
  items: SimulatorTag[];
};

export type DemoShiftResponse = {
  mode: string;
  scope?: string;
  read_only: boolean;
  data: Record<string, { Items: Array<{ Timestamp: string; Value: number }> }>;
};

export type AssistantReply = {
  mode: string;
  read_only: boolean;
  model: string;
  answer: string;
};

export type RuntimeState = {
  running: boolean;
  pid: number | null;
  binary_path: string;
  model_path: string;
  endpoint: string;
  runtime: string;
  local_only: boolean;
};

export type RuntimeInfo = {
  readiness: Record<string, unknown>;
  state: RuntimeState;
};

export type DashboardWidgetLayout = {
  order: number;
  width: 3 | 4 | 6 | 8 | 12;
  height: "compact" | "normal" | "tall";
};

export type DashboardWidget = {
  id: string;
  type: "kpi" | "trend" | "average" | "summary";
  title: string;
  unit_key: string;
  tag_keys: string[];
  period: string;
  layout?: DashboardWidgetLayout;
};

export type DashboardWorkspace = {
  workspace: string;
  title: string;
  widgets: DashboardWidget[];
};

export type DashboardCommandResponse = {
  plan: {
    action: string;
    widget?: DashboardWidget;
    widgets?: DashboardWidget[];
    warnings?: string[];
    read_only: boolean;
  };
  workspace: DashboardWorkspace;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; mode: string }>("/health"),
  capabilities: () => request<SystemCapabilities>("/api/v1/system/capabilities"),
  bridgeSite: () => request<BridgeSite>("/bridge/v1/site"),
  aiStatus: () => request<Record<string, unknown>>("/api/v1/ai/status"),
  aiRuntime: () => request<RuntimeInfo>("/api/v1/ai/runtime"),
  startAiRuntime: () => request<RuntimeState>("/api/v1/ai/runtime/start", { method: "POST" }),
  stopAiRuntime: () => request<RuntimeState>("/api/v1/ai/runtime/stop", { method: "POST" }),
  simulatorTags: () => request<SimulatorTagsResponse>("/api/v1/site-simulator/tags"),
  demoShift: () => request<DemoShiftResponse>("/api/v1/site-simulator/demo-shift"),
  analyze: (question: string, evidence: Record<string, unknown>) =>
    request<AssistantReply>("/api/v1/ai/analyze", {
      method: "POST",
      body: JSON.stringify({ question, evidence }),
    }),
  dashboardWorkspace: (workspace = "default") =>
    request<DashboardWorkspace>(`/api/v1/dashboard/workspaces/${encodeURIComponent(workspace)}`),
  saveDashboardWorkspace: (workspace: DashboardWorkspace) =>
    request<DashboardWorkspace>(`/api/v1/dashboard/workspaces/${encodeURIComponent(workspace.workspace)}`, {
      method: "PUT",
      body: JSON.stringify({ title: workspace.title, widgets: workspace.widgets }),
    }),
  dashboardCommand: (command: string, workspace = "default") =>
    request<DashboardCommandResponse>("/api/v1/dashboard/command", {
      method: "POST",
      body: JSON.stringify({ command, workspace }),
    }),
};
