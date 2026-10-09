"use client";
import type { Route } from "@/lib/api";

export default function RouteCards({
  routes,
  selected,
  recommendedId,
  onSelect,
}: {
  routes: Route[];
  selected: string | null;
  recommendedId?: string | null;
  onSelect: (id: string) => void;
}) {
  const fastest = routes.find((route) => route.is_fastest) ?? routes[0];

  const getRiskDot = (risk: string) => {
    const r = risk.toLowerCase();
    if (r.includes("good") || r.includes("satisfactory")) return "bg-emerald-400";
    if (r.includes("moderate")) return "bg-amber-400";
    return "bg-rose-400";
  };

  return (
    <div className="space-y-2.5 mt-1">
      <div className="flex items-center justify-between px-1 text-xs text-zinc-400">
        <span className="font-medium text-zinc-300">Route Options ({routes.length})</span>
        <span className="text-[11px] text-zinc-500">Ranked by PM2.5 inhalation</span>
      </div>

      <div className="space-y-2">
        {routes.map((route, idx) => {
          const extra = route.duration_min - fastest.duration_min;
          const pct = fastest.exposure_index
            ? ((route.exposure_index - fastest.exposure_index) / fastest.exposure_index) * 100
            : 0;
          const isSelected = selected === route.id;
          const isRec = route.id === recommendedId;

          return (
            <button
              key={route.id}
              onClick={() => onSelect(route.id)}
              className={`w-full rounded-xl border p-3.5 text-left transition-all ${
                isSelected
                  ? isRec
                    ? "border-emerald-500/80 bg-emerald-950/20"
                    : "border-zinc-400 bg-zinc-800/30"
                  : "border-white/[0.08] bg-[#14161f] hover:border-white/[0.16] hover:bg-[#181a24]"
              }`}
            >
              {/* Header */}
              <div className="flex justify-between items-center mb-2.5">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-md bg-white/[0.06] font-mono text-[11px] font-semibold text-zinc-300">
                    {String.fromCharCode(65 + idx)}
                  </span>
                  <span className="text-sm font-medium text-zinc-200">
                    Route {route.id.replace(/^r/i, "")}
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {isRec && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 border border-emerald-500/25 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
                      Recommended
                    </span>
                  )}
                  {route.is_cleanest && !isRec && (
                    <span className="inline-flex items-center rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-[11px] font-medium text-emerald-400">
                      Lowest Exposure
                    </span>
                  )}
                  {route.is_fastest && (
                    <span className="inline-flex items-center rounded-full bg-zinc-800 border border-zinc-700 px-2 py-0.5 text-[11px] font-medium text-zinc-400">
                      Fastest
                    </span>
                  )}
                </div>
              </div>

              {/* Data Grid */}
              <div className="grid grid-cols-2 gap-3 pb-2.5 border-b border-white/[0.06]">
                <div>
                  <div className="text-[11px] text-zinc-500">Travel Time</div>
                  <div className="flex items-baseline gap-1 mt-0.5">
                    <span className="text-xl font-semibold tracking-tight text-white font-display">
                      {route.duration_min}
                    </span>
                    <span className="text-xs text-zinc-400">min</span>
                  </div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">
                    {extra > 0 ? `+${extra.toFixed(0)} min` : "Fastest"} · {route.distance_km} km
                  </div>
                </div>

                <div>
                  <div className="text-[11px] text-zinc-500">PM2.5 Exposure</div>
                  <div className="flex items-baseline gap-1 mt-0.5">
                    <span className="text-xl font-semibold tracking-tight text-white font-display">
                      {route.exposure_index.toFixed(0)}
                    </span>
                    <span className="text-xs text-zinc-400">score</span>
                  </div>
                  <div className="mt-0.5">
                    {pct < -0.5 ? (
                      <span className="text-[11px] font-medium text-emerald-400">
                        {Math.abs(pct).toFixed(0)}% lower exposure
                      </span>
                    ) : pct > 0.5 ? (
                      <span className="text-[11px] text-rose-400">
                        +{pct.toFixed(0)}% higher
                      </span>
                    ) : (
                      <span className="text-[11px] text-zinc-500">Baseline</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Footer row */}
              <div className="mt-2.5 flex items-center justify-between text-[11px] text-zinc-400">
                <span className="flex items-center gap-1.5">
                  <span className={`h-1.5 w-1.5 rounded-full ${getRiskDot(route.risk)}`} />
                  <span>{route.mean_pm25} µg/m³ · {route.risk.replaceAll("_", " ")}</span>
                </span>
                <span className="text-zinc-500 font-mono">
                  Confidence {(route.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
