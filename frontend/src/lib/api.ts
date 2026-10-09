const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Mode = "walk" | "cycle" | "car";
export type Pt = { lat: number; lon: number };
export type Segment = { lat: number; lon: number; pm25: number; minutes: number; line: number[][] };
export type Route = {
  id: string; duration_min: number; distance_km: number; exposure_index: number; mean_pm25: number;
  risk: string; confidence: number; segments: Segment[]; geometry: number[][];
  is_cleanest: boolean; is_fastest: boolean;
};
export type ToolCall = { name: string; input: unknown; output: string | null };
export type EvalRow = {
  horizon_h: number; mae: number; rmse: number;
  baseline_persistence_mae: number; baseline_hourly_mean_mae: number; n_samples: number;
  model_version: string; interval_coverage: number | null; interval_width: number | null;
};
export type Level = { name: string; max: number | null; color: string };
export type AppConfig = {
  levels: Level[];
  mode_factors: Record<string, number>;
  preferences?: Record<string, number>;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API + path, { headers: { "content-type": "application/json" }, ...init });
  } catch {
    throw new Error("The AirGuard API is not reachable. Start it with uvicorn, or open this page with ?offline=1.");
  }
  const text = await response.text();
  let body: { error?: { message?: string } } | null = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(text || "Request failed");
  }
  if (!response.ok) throw new Error(body?.error?.message ?? "Request failed");
  return body as T;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const geocode = (q: string) => call<Pt>(`/geocode?q=${encodeURIComponent(q)}`);
export const scoreRoutes = (b: unknown) =>
  call<{ routes: Route[]; data_age_min: number | null; mode_factor: number }>("/routes/score", post(b));
export const bestDeparture = (b: unknown) => call<DepartureResult>("/departure/best", post(b));
export const analyzeTrip = (b: unknown) =>
  call<{
    trip_id: string;
    routes: { routes: Route[]; data_age_min: number | null; mode_factor: number };
    departure: DepartureResult;
    snapshot: { captured_at: string; data_age_at_capture_min: number | null } | null;
  }>("/trips/analyze", post(b));
export const chat = (b: unknown) =>
  call<{ answer: string; tool_calls: ToolCall[]; cached: boolean }>("/agent/chat", post(b));
export const evalMetrics = () => call<EvalRow[]>("/eval");
export const getConfig = () => call<AppConfig>("/config");

export type DepartureOption = {
  wait_min: number;
  route_id: string;
  duration_min: number;
  exposure_index: number;
  confidence?: number;
};
export type DepartureResult = {
  options: DepartureOption[];
  recommended: DepartureOption & { extra_min?: number };
  delta: { exposure_index_pct: number; arrival_min: number };
  preference: { sensitivity: string; max_extra_min: number; max_wait_min: number; minutes_per_10pct?: number };
};
