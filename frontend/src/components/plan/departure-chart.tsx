"use client";

import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TripResult } from "@/lib/api";
import { istTime } from "@/lib/format";

const ROUTE_DASH = ["", "5 4", "1.5 3"];

export function DepartureChart({ trip, selected }: { trip: TripResult; selected: string }) {
  const { rows, routeIds, labels } = useMemo(() => {
    const byWait = new Map<number, Record<string, number | string>>();
    const ids: string[] = [];
    const lbl: Record<string, string> = {};
    for (const o of trip.departures) {
      if (!ids.includes(o.route_id)) ids.push(o.route_id);
      lbl[o.route_id] = o.label;
      const row = byWait.get(o.wait_min) ?? { wait: o.wait_min, t: istTime(o.depart_at) };
      row[o.route_id] = o.exposure_index;
      if (o.route_id === selected) row.band = [o.exposure_low, o.exposure_high] as unknown as number;
      byWait.set(o.wait_min, row);
    }
    return { rows: [...byWait.values()].sort((a, b) => Number(a.wait) - Number(b.wait)), routeIds: ids, labels: lbl };
  }, [trip, selected]);

  const rec = trip.decision.recommended;
  const base = trip.decision.baseline;

  return (
    <figure className="space-y-2">
      <figcaption className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium">Exposure by departure time</span>
        <span className="text-xs text-muted-foreground">lower is better · IST</span>
      </figcaption>
      <div className="h-44 w-full">
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="t"
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              minTickGap={28}
              padding={{ left: 4, right: 12 }}
              tick={{ fontSize: 10, fill: "var(--muted-foreground)", fontFamily: "var(--font-plex-mono)" }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={44}
              tick={{ fontSize: 10, fill: "var(--muted-foreground)", fontFamily: "var(--font-plex-mono)" }}
              domain={["auto", "auto"]}
            />
            <Tooltip
              cursor={{ stroke: "var(--rule)" }}
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
                fontFamily: "var(--font-plex-sans)",
              }}
              formatter={(v, name) =>
                name === "band"
                  ? [Array.isArray(v) ? `${Math.round(Number(v[0]))}–${Math.round(Number(v[1]))}` : "", "Range"]
                  : [Math.round(Number(v)), labels[String(name)] ?? String(name)]
              }
              labelFormatter={(l) => `Leave at ${l}`}
            />
            <Area dataKey="band" stroke="none" fill="var(--foreground)" fillOpacity={0.07} isAnimationActive={false} />
            {routeIds.map((id, i) => (
              <Line
                key={id}
                dataKey={id}
                type="monotone"
                dot={false}
                stroke="var(--foreground)"
                strokeOpacity={id === selected ? 1 : 0.35}
                strokeWidth={id === selected ? 2 : 1.4}
                strokeDasharray={ROUTE_DASH[i % 3]}
                isAnimationActive={false}
              />
            ))}
            <ReferenceDot x={istTime(base.depart_at)} y={base.exposure_index} r={3.5} fill="var(--card)"
              stroke="var(--foreground)" strokeWidth={1.5} />
            <ReferenceDot x={istTime(rec.depart_at)} y={rec.exposure_index} r={5} fill="var(--aq-good)"
              stroke="var(--card)" strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        {routeIds.map((id, i) => (
          <span key={id} className="inline-flex items-center gap-1.5">
            <svg width="18" height="6" aria-hidden>
              <line x1="0" y1="3" x2="18" y2="3" stroke="currentColor" strokeWidth="1.6" strokeDasharray={ROUTE_DASH[i % 3]} />
            </svg>
            {labels[id]}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-aq-good" /> recommended
        </span>
      </div>
    </figure>
  );
}
