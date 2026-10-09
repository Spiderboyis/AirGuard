"use client";
import type { Route } from "@/lib/api";

export default function RouteCards({
  routes, selected, recommendedId, onSelect,
}: {
  routes: Route[];
  selected: string | null;
  recommendedId?: string | null;
  onSelect: (id: string) => void;
}) {
  const fastest = routes.find((route) => route.is_fastest) ?? routes[0];
  return (
    <div className="space-y-2">
      {routes.map((route) => {
        const extra = route.duration_min - fastest.duration_min;
        const pct = fastest.exposure_index ? ((route.exposure_index - fastest.exposure_index) / fastest.exposure_index) * 100 : 0;
        return (
          <button
            key={route.id}
            onClick={() => onSelect(route.id)}
            className={`w-full rounded-lg border bg-white p-3 text-left ${selected === route.id ? "border-blue-600 ring-1 ring-blue-600" : "border-slate-300"}`}
          >
            <div className="flex justify-between gap-2">
              <span className="font-medium">Route {route.id.slice(1)}</span>
              <span className="text-right text-xs text-slate-600">
                {route.id === recommendedId && "Recommended "}
                {route.is_cleanest && "Lowest exposure "}
                {route.is_fastest && "· Fastest"}
              </span>
            </div>
            <div className="mt-1 text-sm">{route.duration_min} min ({extra > 0 ? `+${extra.toFixed(0)} min` : "fastest"}) · {route.distance_km} km</div>
            <div className="text-sm">Exposure index {route.exposure_index.toFixed(0)} ({Math.abs(pct) < 0.5 ? "same as fastest" : `${pct > 0 ? "+" : ""}${pct.toFixed(0)}% vs fastest`})</div>
            <div className="text-xs text-slate-600">Average PM2.5 {route.mean_pm25} µg/m³ · AirGuard level: {route.risk.replaceAll("_", " ")} · data reliability {route.confidence}</div>
          </button>
        );
      })}
    </div>
  );
}
