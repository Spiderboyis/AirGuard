"use client";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DepartureResult } from "@/lib/api";

export default function DepartureChart({ dep }: { dep: DepartureResult }) {
  const best: Record<number, number> = {};
  for (const option of dep.options ?? []) {
    best[option.wait_min] = Math.min(best[option.wait_min] ?? Infinity, option.exposure_index);
  }
  const data = Object.entries(best).map(([wait, exposure]) => ({ wait: Number(wait), exposure_index: Math.round(exposure) }));
  const pct = dep.delta?.exposure_index_pct ?? 0;
  const rec = dep.recommended;
  const same = Math.abs(pct) < 0.5 && (dep.delta?.arrival_min ?? 0) === 0;
  const msg = !rec
    ? "No departure recommendation is available."
    : same
      ? "The fastest route leaving now is already the best choice for your settings."
      : `Take route ${String(rec.route_id).slice(1)}${rec.wait_min ? `, leaving ${rec.wait_min} min later` : ""}: estimated exposure ${Math.abs(pct)}% ${pct < 0 ? "lower" : "higher"}, arriving ${dep.delta.arrival_min} min later.`;
  return (
    <div>
      <p className="text-sm">{msg}</p>
      <p className="text-xs text-slate-600">
        Forecasts at +1, +3, +6, +12, and +24 hours, interpolated to 15-minute steps. These are scenario checks, not 15-minute forecasts.
        Sensitivity {dep.preference?.sensitivity}: up to {dep.preference?.max_extra_min} extra min, wait up to {dep.preference?.max_wait_min} min.
      </p>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="wait" label={{ value: "minutes from now", position: "insideBottom", offset: -4 }} />
            <YAxis width={44} />
            <Tooltip />
            <Line type="monotone" dataKey="exposure_index" name="Exposure index" stroke="#1d4ed8" dot={false} />
            {rec && <ReferenceDot x={rec.wait_min} y={Math.round(rec.exposure_index)} r={6} fill="#16a34a" stroke="none" />}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
