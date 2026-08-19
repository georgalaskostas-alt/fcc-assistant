const API_BASE = "http://127.0.0.1:8000";

export type SystemCapabilities = {
  pi_web_api: string;
  local_ai: string;
  simulator?: string;
  plant_write_access: boolean;
  features: string[];
};

export type SimulatorTag = {
  key: string;
  name: string;
  group: string;
  unit: string;
  value: number;
  status?: string;
};

export type SimulatorSnapshot = {
  timestamp: string;
  source: string;
  tags: SimulatorTag[];
};

export type AssistantReply = {
  answer: string;
  model: string;
  evidence_type: string;
  read_only: boolean;
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
  simulatorSnapshot: () => request<SimulatorSnapshot>("/api/v1/simulator/snapshot"),
  demoShift: () => request<Record<string, unknown>>("/api/v1/simulator/demo-shift"),
  askSimulator: (question: string) =>
    request<AssistantReply>("/api/v1/assistant/simulator", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
};
