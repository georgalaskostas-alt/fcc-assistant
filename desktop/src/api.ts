const API_BASE = "http://127.0.0.1:8000";

export type SystemCapabilities = {
  pi_web_api: string;
  local_ai: string;
  plant_write_access: boolean;
  features: string[];
};

export type SimulatorTag = {
  key: string;
  name: string;
  group: string;
  unit: string;
};

export type SimulatorTagsResponse = {
  mode: string;
  count: number;
  items: SimulatorTag[];
};

export type DemoShiftResponse = {
  mode: string;
  read_only: boolean;
  data: Record<string, { Items: Array<{ Timestamp: string; Value: number }> }>;
};

export type AssistantReply = {
  mode: string;
  read_only: boolean;
  model: string;
  answer: string;
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
  aiStatus: () => request<Record<string, unknown>>("/api/v1/ai/status"),
  simulatorTags: () => request<SimulatorTagsResponse>("/api/v1/simulator/tags"),
  demoShift: () => request<DemoShiftResponse>("/api/v1/simulator/demo-shift"),
  analyze: (question: string, evidence: Record<string, unknown>) =>
    request<AssistantReply>("/api/v1/ai/analyze", {
      method: "POST",
      body: JSON.stringify({ question, evidence }),
    }),
};
