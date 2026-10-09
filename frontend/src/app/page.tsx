"use client";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import DepartureChart from "@/components/DepartureChart";
import RouteCards from "@/components/RouteCards";
import LocationInput from "@/components/LocationInput";
import {
  analyzeTrip,
  geocode,
  getConfig,
  type DepartureResult,
  type Level,
  type Mode,
  type Route,
  type ToolCall,
} from "@/lib/api";

const RouteMap = dynamic(() => import("@/components/RouteMap"), { ssr: false });

type SavedChat = { question: string; answer: string; tool_calls: ToolCall[] };

const POPULAR_PRESETS = [
  { label: "CP → Cyber Hub", from: "Connaught Place, New Delhi", to: "DLF Cyber Hub, Gurgaon" },
  { label: "Anand Vihar → Airport", from: "Anand Vihar, Delhi", to: "Indira Gandhi International Airport, Delhi" },
  { label: "Noida 62 → AIIMS", from: "Sector 62 Noida", to: "AIIMS New Delhi" },
  { label: "Rohini → CP", from: "Rohini Sector 13, Delhi", to: "Connaught Place, New Delhi" },
];

export default function Home() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [mode, setMode] = useState<Mode>("cycle");
  const [sens, setSens] = useState("normal");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("sens");
      if (saved) setSens(saved);
    } catch {
      /* private mode */
    }
  }, []);
  const [demo, setDemo] = useState(false);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [age, setAge] = useState<number | null>(null);
  const [, setFactor] = useState<number | null>(null);
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
  const [showConfig, setShowConfig] = useState(false);

  useEffect(() => {
    getConfig()
      .then((config) => setLevels(config.levels))
      .catch((error) => {
        if (!new URLSearchParams(window.location.search).get("offline")) {
          setErr("Could not load level settings: " + (error as Error).message);
        }
      });
  }, []);

  useEffect(() => {
    if (!new URLSearchParams(window.location.search).get("offline")) return;
    fetch("/demo/trip1.json")
      .then((response) => {
        if (!response.ok) throw new Error("missing");
        return response.json();
      })
      .then((file) => {
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
        setSel(
          recommended ?? file.routes?.routes?.find((route: Route) => route.is_cleanest)?.id ?? null
        );
        setErr("");
      })
      .catch(() => setErr("The offline demo file is missing. Run python scripts/seed_local.py."));
  }, []);

  const saveSens = (value: string) => {
    setSens(value);
    try {
      localStorage.setItem("sens", value);
    } catch {
      /* private mode */
    }
  };

  const swapLocations = () => {
    const temp = from;
    setFrom(to);
    setTo(temp);
  };

  const applyPreset = (preset: (typeof POPULAR_PRESETS)[0]) => {
    setFrom(preset.from);
    setTo(preset.to);
  };

  async function go() {
    if (!from.trim() || !to.trim()) {
      setErr("Please specify both starting origin and destination.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const origin = await geocode(from);
      const destination = await geocode(to);
      const analyzed = await analyzeTrip({
        origin,
        destination,
        mode,
        demo,
        sensitivity: sens,
        max_extra_min: maxExtra,
        max_wait_min: maxWait,
      });
      setTripId(analyzed.trip_id);
      setSnap(analyzed.snapshot?.captured_at ?? null);
      setRoutes(analyzed.routes.routes);
      setAge(analyzed.routes.data_age_min);
      setFactor(analyzed.routes.mode_factor);
      setDep(analyzed.departure);
      setSel(
        analyzed.departure.recommended?.route_id ??
          analyzed.routes.routes.find((route) => route.is_cleanest)?.id ??
          null
      );
    } catch (error) {
      setErr((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid gap-5 lg:grid-cols-[430px_1fr] xl:grid-cols-[460px_1fr] lg:h-[calc(100vh-5.5rem)]">
      {/* Left Column: Command & Intelligence Console */}
      <section className="surface-card flex flex-col h-full overflow-y-auto p-4 sm:p-5 space-y-4">
        {/* Header & Description */}
        <div className="space-y-1.5 border-b border-white/[0.06] pb-3.5">
          <h1 className="font-display text-lg font-semibold tracking-tight text-white">
            Plan Route
          </h1>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Compare route options across Delhi NCR and minimize your PM2.5 exposure using hourly station forecasts.
          </p>

          {/* Presets */}
          <div className="pt-2">
            <div className="flex flex-wrap gap-1.5">
              {POPULAR_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  className="rounded-md bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] px-2 py-1 text-[11px] text-zinc-300 hover:text-white transition-colors"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Origin & Destination Inputs with Swap */}
        <div className="space-y-2">
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-zinc-400 pl-0.5">
              Starting point
            </label>
            <LocationInput
              value={from}
              onChange={setFrom}
              placeholder="Enter start location or metro station"
              ariaLabel="Starting point"
              iconType="origin"
            />
          </div>

          {/* Swap Button */}
          <div className="flex justify-center -my-1 z-10 relative">
            <button
              type="button"
              onClick={swapLocations}
              className="flex h-6 w-6 items-center justify-center rounded-full bg-[#161822] border border-white/[0.08] text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.06] transition-colors"
              title="Swap start and destination"
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
              </svg>
            </button>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-medium text-zinc-400 pl-0.5">
              Destination
            </label>
            <LocationInput
              value={to}
              onChange={setTo}
              placeholder="Enter destination"
              ariaLabel="Destination"
              iconType="destination"
            />
          </div>
        </div>

        {/* Transit Mode: Minimalist Segmented Control */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-medium text-zinc-400 pl-0.5">
            Travel mode
          </label>
          <div className="grid grid-cols-3 gap-1 rounded-xl bg-[#14161f] p-1 border border-white/[0.08]">
            {(
              [
                { id: "walk", label: "Walk", icon: "🚶" },
                { id: "cycle", label: "Cycle", icon: "🚲" },
                { id: "car", label: "Car", icon: "🚗" },
              ] as const
            ).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setMode(item.id)}
                className={`flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium transition-colors ${
                  mode === item.id
                    ? "bg-[#222530] text-white shadow-sm font-semibold"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Preferences Toggle */}
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-2.5">
          <button
            type="button"
            onClick={() => setShowConfig(!showConfig)}
            className="flex w-full items-center justify-between text-xs text-zinc-300 hover:text-white transition-colors"
          >
            <span className="flex items-center gap-2">
              <span>Preferences</span>
              <span className="text-[11px] text-zinc-500 font-mono">
                ({sens}, +{maxExtra}m detour, {maxWait}m wait)
              </span>
            </span>
            <span className="text-[10px] text-zinc-500">{showConfig ? "▲" : "▼"}</span>
          </button>

          {showConfig && (
            <div className="mt-3 space-y-3 pt-2 border-t border-white/[0.06]">
              {/* Sensitivity */}
              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400">Sensitivity</label>
                <div className="grid grid-cols-3 gap-1 text-xs">
                  {[
                    { id: "normal", label: "Normal" },
                    { id: "sensitive", label: "Sensitive" },
                    { id: "high", label: "Very Sensitive" },
                  ].map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => saveSens(s.id)}
                      className={`rounded-lg py-1 text-xs transition-colors border ${
                        sens === s.id
                          ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300 font-medium"
                          : "bg-white/[0.02] border-white/[0.06] text-zinc-400 hover:text-zinc-200"
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Time bounds */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400">Max extra travel time</label>
                  <select
                    className="w-full rounded-lg border border-white/[0.08] bg-[#14161f] p-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-400"
                    value={maxExtra}
                    onChange={(e) => setMaxExtra(Number(e.target.value))}
                  >
                    {[0, 5, 10, 15, 30].map((m) => (
                      <option key={m} value={m}>
                        +{m} min
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400">Max departure wait</label>
                  <select
                    className="w-full rounded-lg border border-white/[0.08] bg-[#14161f] p-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-400"
                    value={maxWait}
                    onChange={(e) => setMaxWait(Number(e.target.value))}
                  >
                    {[0, 30, 60, 120, 180].map((m) => (
                      <option key={m} value={m}>
                        {m} min
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Demo checkbox */}
              <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer pt-1">
                <input
                  type="checkbox"
                  className="rounded bg-zinc-800 border-white/[0.1] text-emerald-500 focus:ring-0"
                  checked={demo}
                  onChange={(event) => setDemo(event.target.checked)}
                />
                <span className="text-[11px]">Use frozen demo dataset snapshot</span>
              </label>
            </div>
          )}
        </div>

        {/* Primary Action Button */}
        <button
          className="w-full rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-2.5 px-4 text-sm transition-all shadow-sm disabled:opacity-40 disabled:pointer-events-none active:scale-[0.99]"
          disabled={busy || offline}
          onClick={go}
        >
          {busy ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="h-4 w-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span>Analyzing Routes...</span>
            </span>
          ) : (
            "Compare Routes"
          )}
        </button>

        {/* Status & Error Messages */}
        <div className="space-y-2">
          {err && (
            <div className="rounded-xl bg-rose-500/10 p-3 text-xs text-rose-300 border border-rose-500/20">
              {err}
            </div>
          )}
          {snap && (
            <p className="text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 font-mono">
              Demo snapshot captured {new Date(snap).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST.
            </p>
          )}
          {offline && (
            <p className="text-[11px] text-zinc-400 bg-white/[0.04] p-2 rounded-lg font-mono">
              Offline demo: saved results only.
            </p>
          )}
          {!snap && age !== null && (
            <div className="flex items-center justify-between text-[11px] text-zinc-400 px-1 font-mono">
              <span className="flex items-center gap-1.5">
                <span className={`h-1.5 w-1.5 rounded-full ${age > 180 ? "bg-amber-400" : "bg-emerald-400"}`} />
                <span>Station Data</span>
              </span>
              <span className={age > 180 ? "text-amber-400" : "text-emerald-400"}>
                {age} min old
              </span>
            </div>
          )}

          {routes.length === 0 && !busy && !err && (
            <div className="rounded-xl border border-white/[0.06] p-6 text-center text-xs text-zinc-500">
              Enter locations above or select a preset to evaluate clean-air paths.
            </div>
          )}
        </div>

        {/* Route Cards */}
        {routes.length > 0 && (
          <RouteCards
            routes={routes}
            selected={sel}
            recommendedId={dep?.recommended?.route_id}
            onSelect={setSel}
          />
        )}

        {/* Departure Chart */}
        {dep && <DepartureChart dep={dep} />}

        {/* Assistant */}
        <div className="pt-1">
          <ChatPanel
            sens={sens}
            mode={mode}
            demo={demo || offline}
            tripId={tripId}
            fromPlace={from}
            toPlace={to}
            maxExtra={maxExtra}
            maxWait={maxWait}
            offline={offline}
            saved={offlineChat}
          />
        </div>
      </section>

      {/* Right Column: Map */}
      <section className="surface-card flex flex-col min-h-[500px] lg:h-full overflow-hidden p-2 relative">
        {levels.length > 0 && (
          <div className="flex-1 rounded-xl overflow-hidden">
            <RouteMap
              routes={routes}
              selected={sel}
              levels={levels}
              onSelect={setSel}
            />
          </div>
        )}

        {/* Footer */}
        <footer className="mt-2 px-3 py-1 text-[11px] text-zinc-500 border-t border-white/[0.06] flex items-center justify-between">
          <span>Sources: OpenAQ, CAMS, NASA FIRMS, OpenStreetMap</span>
          <div className="flex items-center gap-4">
            <a className="hover:text-zinc-300 transition-colors" href="/eval">
              Evaluation
            </a>
            <a className="hover:text-zinc-300 transition-colors" href="/about">
              Documentation
            </a>
          </div>
        </footer>
      </section>
    </main>
  );
}
