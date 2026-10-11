import type { components } from "./api-types";

export type Schemas = components["schemas"];
export type TripResult = Schemas["TripResult"];
export type TripRequest = Schemas["TripRequest"];
export type RouteScore = Schemas["RouteScore"];
export type DepartureOption = Schemas["DepartureOption"];
export type Decision = Schemas["Decision"];
export type StationsResponse = Schemas["StationsResponse"];
export type StationSummary = Schemas["StationSummary"];
export type GeocodeResult = Schemas["GeocodeResult"];
export type EvalResponse = Schemas["EvalResponse"];
export type EvalRow = Schemas["EvalRow"];
export type ToolCall = Schemas["ToolCall"];
export type ChatResponse = Schemas["ChatResponse"];
export type TripPreview = Schemas["TripPreview"];
export type StripRow = Schemas["StripRow"];
export type Mode = TripRequest["mode"];
export type Sensitivity = TripRequest["sensitivity"];

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "/api").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "offline", "Can't reach the AirGuard server. Is the API running?");
  }
  if (!res.ok) {
    let code = "http_error";
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {}
    throw new ApiError(res.status, code, message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Record<string, unknown>>("/health"),
  meta: () => request<Meta>("/meta"),
  stations: () => request<StationsResponse>("/stations"),
  evaluation: () => request<EvalResponse>("/eval"),
  geocode: (q: string) => request<GeocodeResult[]>(`/geocode?q=${encodeURIComponent(q)}`),
  analyze: (body: TripRequest) => request<TripResult>("/trips/analyze", { method: "POST", body: JSON.stringify(body) }),
  preview: (body: TripRequest) => request<TripPreview>("/trips/preview", { method: "POST", body: JSON.stringify(body) }),
  trip: (id: string) => request<TripResult>(`/trips/${id}`),
};

export interface Meta {
  version: string;
  assumptions: {
    mode_factors: Record<Mode, number>;
    mode_labels: Record<Mode, string>;
    risk_bands: { key: string; label: string; max_pm25: number | null }[];
    interpolation: Record<string, number>;
    decision: {
      minutes_per_10pct: Record<Sensitivity, number>;
      sensitivity_labels: Record<Sensitivity, string>;
      wait_cost_weight: number;
      min_meaningful_reduction_pct: number;
      departure_step_min: number;
      default_window_h: number;
      max_window_h: number;
    };
  };
  attributions: { name: string; url: string; use: string }[];
}

// ---------------------------------------------------------------------------------------------
// Assistant stream (Server-Sent Events over a POST)
// ---------------------------------------------------------------------------------------------
export type AgentEvent =
  | { type: "tool_start"; name: string; input: Record<string, unknown> }
  | { type: "tool_end"; name: string; input: Record<string, unknown>; output: unknown; ms: number; ok: boolean }
  | { type: "token"; text: string }
  | { type: "reset" }
  | ({ type: "done"; ms: number } & ChatResponse & { fallback_reason?: string });

export interface ChatPayload {
  message: string;
  trip_id?: string | null;
  profile?: Schemas["Profile"] | null;
  history?: Schemas["ChatTurn"][];
}

export async function streamChat(body: ChatPayload, onEvent: (e: AgentEvent) => void, signal?: AbortSignal) {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/agent/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    throw new ApiError(0, "offline", "Can't reach the AirGuard server.");
  }
  if (!res.ok || !res.body) {
    let message = `Assistant unavailable (${res.status})`;
    try {
      message = (await res.json())?.error?.message ?? message;
    } catch {}
    throw new ApiError(res.status, "agent_error", message);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const data = chunk
        .split("\n")
        .filter((l) => l.startsWith("data: "))
        .map((l) => l.slice(6))
        .join("\n");
      if (data) onEvent(JSON.parse(data) as AgentEvent);
    }
  }
}
