"use client";

import { ConfidenceMeter, ExposureStrip, RiskBadge } from "@/components/air/air";
import type { TripResult } from "@/lib/api";
import { dur, num } from "@/lib/format";
import { cn } from "@/lib/utils";

export function RouteList({
  trip,
  selected,
  onSelect,
}: {
  trip: TripResult;
  selected: string;
  onSelect: (id: string) => void;
}) {
  const recId = trip.decision.recommended.route_id;
  const fastestId = trip.decision.baseline.route_id;
  const minExp = Math.min(...trip.routes.map((r) => r.exposure_index));

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium">Routes if you leave now</span>
        <span className="text-xs text-muted-foreground">{trip.mode_label}</span>
      </div>
      <ul className="space-y-2">
        {trip.routes.map((r) => {
          const on = r.route_id === selected;
          const rel = minExp > 0 ? (r.exposure_index / minExp - 1) * 100 : 0;
          return (
            <li key={r.route_id}>
              <button
                type="button"
                onClick={() => onSelect(r.route_id)}
                aria-pressed={on}
                className={cn(
                  "w-full rounded-lg border bg-card p-3 text-left transition-[border-color,box-shadow]",
                  on ? "border-foreground/50 ring-1 ring-foreground/20" : "hover:border-foreground/25",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{r.label}</span>
                    </div>
                    <div className="mt-0.5 flex gap-2 text-xs text-muted-foreground">
                      {r.route_id === recId && <span className="font-medium text-good">Recommended</span>}
                      {r.route_id === fastestId && <span>Fastest</span>}
                      <span className="tabular">{num(r.distance_km, 1)} km</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-serif text-xl leading-none tabular">{dur(r.duration_min)}</div>
                  </div>
                </div>
                <ExposureStrip segments={r.segments} className="mt-3" height={8} />
                <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className="flex items-center gap-3">
                    <span>
                      <span className="text-muted-foreground">Index </span>
                      <span className="font-mono tabular">{Math.round(r.exposure_index)}</span>
                      {rel > 0.5 && <span className="ml-1 text-muted-foreground tabular">(+{Math.round(rel)}%)</span>}
                    </span>
                    <RiskBadge risk={r.risk} label={`${Math.round(r.mean_pm25)} µg/m³`} />
                  </span>
                  <ConfidenceMeter value={r.confidence} />
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
