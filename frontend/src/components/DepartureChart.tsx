"use client";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DepartureResult } from "@/lib/api";

export default function DepartureChart({ dep }: { dep: DepartureResult }) {
  const best: Record<number, number> = {};
  for (const option of dep.options ?? []) {
    best[option.wait_min] = Math.min(best[option.wait_min] ?? Infinity, option.exposure_index);
  }
  const data = Object.entries(best).map(([wait, exposure]) => ({
    wait: Number(wait),
    exposure_index: Math.round(exposure),
  }));

  const pct = dep.delta?.exposure_index_pct ?? 0;
  const rec = dep.recommended;
  const same = Math.abs(pct) < 0.5 && (dep.delta?.arrival_min ?? 0) === 0;

  const msg = !rec
    ? "No departure recommendation is available."
    : same
      ? "The fastest route leaving immediately is already optimal for your preferences."
      : `Recommended: Take Route ${String(rec.route_id).slice(1)}${rec.wait_min ? ` in ${rec.wait_min} min` : ""}. Exposure is ${Math.abs(pct)}% ${pct < 0 ? "lower" : "higher"}, arriving ${dep.delta?.arrival_min ?? 0} min later.`;

  return (
    <div className="surface-card p-4 mt-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
          Departure Timing Optimization
        </h3>
        <span className="text-[11px] font-mono text-zinc-500">
          24h Forecast
        </span>
      </div>

      {/* Recommendation Banner */}
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3 mb-3">
        <p className="text-xs font-medium text-emerald-300 leading-relaxed">
          {msg}
        </p>
      </div>

      {/* Line Chart */}
      <div className="h-40 -ml-3 pr-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis
              dataKey="wait"
              stroke="#71717a"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={(val) => `+${val}m`}
            />
            <YAxis
              width={36}
              stroke="#71717a"
              fontSize={10}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#161820",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "8px",
                fontSize: "11px",
                color: "#f4f4f5",
                boxShadow: "0 10px 25px rgba(0,0,0,0.4)",
              }}
              formatter={(value: unknown) => [`${value} Exposure Index`, "Exposure"]}
              labelFormatter={(label) => `Depart in +${label} min`}
            />
            <Line
              type="monotone"
              dataKey="exposure_index"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 2.5, fill: "#10b981" }}
              activeDot={{ r: 5, fill: "#34d399", stroke: "#111318", strokeWidth: 2 }}
            />
            {rec && (
              <ReferenceDot
                x={rec.wait_min}
                y={Math.round(rec.exposure_index)}
                r={5}
                fill="#34d399"
                stroke="#111318"
                strokeWidth={2}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-1 flex items-center justify-between text-[11px] text-zinc-500">
        <span>Departure delay (minutes)</span>
        <span>Green node: Recommended departure</span>
      </div>
    </div>
  );
}
