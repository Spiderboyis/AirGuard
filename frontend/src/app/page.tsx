"use client";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import DepartureChart from "@/components/DepartureChart";
import RouteCards from "@/components/RouteCards";
import { analyzeTrip, geocode, getConfig, type DepartureResult, type Level, type Mode, type Route, type ToolCall } from "@/lib/api";

const RouteMap = dynamic(() => import("@/components/RouteMap"), { ssr: false });

type SavedChat = { question: string; answer: string; tool_calls: ToolCall[] };

export default function Home() {
  const [from, setFrom] = useState("Hauz Khas");
  const [to, setTo] = useState("DU North Campus");
  const [mode, setMode] = useState<Mode>("cycle");
  const [sens, setSens] = useState("normal");
  const [demo, setDemo] = useState(false);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [age, setAge] = useState<number | null>(null);
  const [factor, setFactor] = useState<number | null>(null);
  const [dep, setDep] = useState<DepartureResult | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [tripId, setTripId] = useState<string | null>(null);
  const [maxExtra, setMaxExtra] = useState(15);
  const [maxWait, setMaxWait] = useState(120);
  const [snap, setSnap] = useState<string | null>(null);
  const [levels, setLevels] = useState<Level[]>([]);
  const [offline, setOffline] = useState(false);
  const [offlineChat, setOfflineChat] = useState<SavedChat[]>([]);

  useEffect(() => {
    try { setSens(localStorage.getItem("sens") ?? "normal"); } catch { /* private mode */ }
  }, []);
  useEffect(() => {
    getConfig().then((config) => setLevels(config.levels)).catch((error) => {
      if (!new URLSearchParams(window.location.search).get("offline")) {
        setErr("Could not load the level settings: " + (error as Error).message);
      }
    });
  }, []);
  useEffect(() => {
    if (!new URLSearchParams(window.location.search).get("offline")) return;
    fetch("/demo/trip1.json").then((response) => {
      if (!response.ok) throw new Error("missing");
      return response.json();
    }).then((file) => {
      const request = file.request ?? {};
      setOffline(true);
      setDemo(true);
      setLevels(file.levels ?? []);
      setOfflineChat(file.chat ?? []);
      setRoutes(file.routes?.routes ?? []);
      setAge(null);
      setFactor(file.routes?.mode_factor ?? null);
      setSnap(file.snapshot?.captured_at ?? null);
      setDep(file.departure ?? null);
      if (request.from) setFrom(request.from);
      if (request.to) setTo(request.to);
      if (request.mode) setMode(request.mode);
      if (request.sensitivity) setSens(request.sensitivity);
      if (request.max_extra_min != null) setMaxExtra(request.max_extra_min);
      if (request.max_wait_min != null) setMaxWait(request.max_wait_min);
      const recommended = file.departure?.recommended?.route_id as string | undefined;
      setSel(recommended ?? file.routes?.routes?.find((route: Route) => route.is_cleanest)?.id ?? null);
      setErr("");
    }).catch(() => setErr("The offline demo file is missing. Run python scripts/seed_local.py."));
  }, []);

  const saveSens = (value: string) => {
    setSens(value);
    try { localStorage.setItem("sens", value); } catch { /* private mode */ }
  };

  async function go() {
    setBusy(true);
    setErr("");
    try {
      const origin = await geocode(from);
      const destination = await geocode(to);
      const analyzed = await analyzeTrip({
        origin, destination, mode, demo, sensitivity: sens, max_extra_min: maxExtra, max_wait_min: maxWait,
      });
      setTripId(analyzed.trip_id);
      setSnap(analyzed.snapshot?.captured_at ?? null);
      setRoutes(analyzed.routes.routes);
      setAge(analyzed.routes.data_age_min);
      setFactor(analyzed.routes.mode_factor);
      setDep(analyzed.departure);
      setSel(analyzed.departure.recommended?.route_id ?? analyzed.routes.routes.find((route) => route.is_cleanest)?.id ?? null);
    } catch (error) {
      setErr((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto grid max-w-6xl gap-4 p-4 lg:grid-cols-[minmax(0,400px)_minmax(0,1fr)]">
      <section className="space-y-3">
        <h1 className="text-xl font-semibold">Plan a lower-exposure trip</h1>
        <p className="text-sm text-slate-600">Delhi NCR only. Compare routes and departure times for one mode. The exposure index is a relative estimate, not a measured dose.</p>
        <input className="w-full rounded border border-slate-300 bg-white p-2" value={from} onChange={(event) => setFrom(event.target.value)} aria-label="From" />
        <input className="w-full rounded border border-slate-300 bg-white p-2" value={to} onChange={(event) => setTo(event.target.value)} aria-label="To" />
        <div className="flex gap-2">
          <select className="flex-1 rounded border border-slate-300 bg-white p-2" value={mode} onChange={(event) => setMode(event.target.value as Mode)} aria-label="Mode">
            <option value="walk">Walk</option><option value="cycle">Cycle</option><option value="car">Car</option>
          </select>
          <select className="flex-1 rounded border border-slate-300 bg-white p-2" value={sens} onChange={(event) => saveSens(event.target.value)} aria-label="Sensitivity">
            <option value="normal">Normal</option>
            <option value="sensitive">Sensitive to air pollution</option>
            <option value="high">Very sensitive</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={demo} onChange={(event) => setDemo(event.target.checked)} /> Demo mode (frozen data)
        </label>
        <div className="flex gap-2 text-sm">
          <label className="flex-1">Add at most
            <select className="mt-1 w-full rounded border border-slate-300 bg-white p-2" value={maxExtra} onChange={(event) => setMaxExtra(Number(event.target.value))}>
              {[0, 5, 10, 15, 30].map((minutes) => <option key={minutes} value={minutes}>{minutes} min</option>)}
            </select>
          </label>
          <label className="flex-1">Wait at most
            <select className="mt-1 w-full rounded border border-slate-300 bg-white p-2" value={maxWait} onChange={(event) => setMaxWait(Number(event.target.value))}>
              {[0, 30, 60, 120, 180].map((minutes) => <option key={minutes} value={minutes}>{minutes} min</option>)}
            </select>
          </label>
        </div>
        <button className="w-full rounded bg-blue-600 p-2 text-white disabled:opacity-50" disabled={busy || offline} onClick={go}>{busy ? "Working…" : "Compare routes"}</button>
        {err && <p role="alert" className="text-sm text-red-700">{err}</p>}
        {snap && <p className="text-sm text-amber-700">Demo snapshot, captured {new Date(snap).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST. Not live data.</p>}
        {offline && <p className="text-sm text-slate-600">Offline demo: saved results only. Compare routes and live chat are switched off.</p>}
        {!snap && age !== null && <p className={`text-sm ${age > 180 ? "text-amber-700" : "text-slate-600"}`}>Air readings are about {age} minutes old (median across stations){age > 180 ? ", so estimates are less reliable" : ""}.</p>}
        {factor !== null && routes.length > 0 && <p className="text-xs text-slate-600">Comparing {mode} only. Mode factor {factor} is an illustrative assumption, not a measurement.</p>}
        {routes.length === 0 && !busy && !err && <p className="text-sm text-slate-600">Enter two places in Delhi NCR, then compare routes.</p>}
        {routes.length > 0 && <RouteCards routes={routes} selected={sel} recommendedId={dep?.recommended?.route_id} onSelect={setSel} />}
        {dep && <DepartureChart dep={dep} />}
        <ChatPanel sens={sens} mode={mode} demo={demo || offline} tripId={tripId} maxExtra={maxExtra} maxWait={maxWait} offline={offline} saved={offlineChat} />
      </section>
      <section className="min-h-[420px]">
        {levels.length > 0 && <RouteMap routes={routes} selected={sel} levels={levels} />}
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
          {levels.map((level, index) => (
            <span key={level.name} className="inline-flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: level.color }} />
              {level.name.replaceAll("_", " ")} {level.max === null ? `above ${levels[index - 1]?.max}` : `up to ${level.max}`}
            </span>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-600">Segment colour is the AirGuard level of the forecast PM2.5 (µg/m³). Estimates are guidance, not medical advice. Scheduled clock times such as tomorrow at 8 AM are not supported; the app compares leaving now with waiting.</p>
      </section>
      <footer className="text-xs text-slate-500 lg:col-span-2">
        Data: OpenAQ, Open-Meteo (CAMS), NASA FIRMS. Maps © OpenStreetMap contributors, style by OpenFreeMap. Routing by OpenRouteService, with a public OSRM fallback when no key is set. <a className="underline" href="/eval">Evaluation</a> · <a className="underline" href="/about">About and limits</a>
      </footer>
    </main>
  );
}
