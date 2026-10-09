"use client";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { evalMetrics, type EvalRow } from "@/lib/api";

export default function Eval() {
  const [rows, setRows] = useState<EvalRow[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    evalMetrics()
      .then(setRows)
      .catch((error) => setErr((error as Error).message));
  }, []);

  const data = rows.map((row) => ({
    horizon: `+${row.horizon_h}h`,
    "XGBoost Model": row.mae,
    Persistence: row.baseline_persistence_mae,
    "Hourly Mean Baseline": row.baseline_hourly_mean_mae,
  }));

  const version = rows[0]?.model_version ?? "";
  const synthetic = version.includes("synthetic");

  return (
    <main className="mx-auto max-w-5xl space-y-5 py-3">
      {/* Header */}
      <div className="surface-card p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="font-display text-xl font-semibold tracking-tight text-white">
              Forecast Accuracy Benchmark
            </h1>
            <p className="text-xs text-zinc-400 mt-1 max-w-xl leading-relaxed">
              Mean absolute error (MAE) measured on out-of-sample Delhi PM2.5 observations across 5 forecast horizons. Lower is better.
            </p>
          </div>
          {version && (
            <div className="font-mono text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.08] text-zinc-300 self-start sm:self-auto">
              Model: {version}
            </div>
          )}
        </div>
      </div>

      {err && (
        <div role="alert" className="rounded-xl bg-rose-500/10 p-4 text-xs text-rose-300 border border-rose-500/20">
          {err}
        </div>
      )}

      {synthetic && (
        <div className="rounded-xl bg-amber-500/10 p-4 text-xs text-amber-300 border border-amber-500/20">
          Showing initial baseline rows. Run real backfill and model training to update with live station data.
        </div>
      )}

      {/* Bar Chart */}
      <div className="surface-card p-6">
        <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-400 mb-4">
          Model Error vs Standard Baselines (MAE in µg/m³)
        </h2>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
              <XAxis dataKey="horizon" stroke="#71717a" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#71717a" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#161820",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: "8px",
                  fontSize: "11px",
                  color: "#f4f4f5",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "12px" }} />
              <Bar dataKey="XGBoost Model" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Persistence" fill="#52525b" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Hourly Mean Baseline" fill="#27272a" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Metrics Table */}
      <div className="surface-card p-6 overflow-hidden">
        <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-400 mb-4">
          Detailed Horizon Performance
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-white/[0.08] text-zinc-400 pb-2">
                <th className="py-2.5 pr-4 font-semibold">Horizon</th>
                <th className="py-2.5 pr-4 font-semibold">MAE (µg/m³)</th>
                <th className="py-2.5 pr-4 font-semibold">RMSE</th>
                <th className="py-2.5 pr-4 font-semibold">80% Interval Coverage</th>
                <th className="py-2.5 pr-4 font-semibold">Avg Width</th>
                <th className="py-2.5 pr-4 font-semibold">Samples</th>
                <th className="py-2.5 font-semibold text-right">Beats Baselines</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {rows.map((row) => {
                const beats =
                  row.mae < row.baseline_persistence_mae && row.mae < row.baseline_hourly_mean_mae;
                return (
                  <tr key={row.horizon_h} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 pr-4 font-semibold text-white">+{row.horizon_h}h</td>
                    <td className="py-3 pr-4 text-emerald-400 font-medium">{row.mae.toFixed(1)}</td>
                    <td className="py-3 pr-4 text-zinc-300">{row.rmse.toFixed(1)}</td>
                    <td className="py-3 pr-4 text-zinc-300">
                      {row.interval_coverage == null ? "–" : `${Math.round(row.interval_coverage * 100)}%`}
                    </td>
                    <td className="py-3 pr-4 text-zinc-400">{row.interval_width ?? "–"}</td>
                    <td className="py-3 pr-4 text-zinc-400">{row.n_samples}</td>
                    <td className="py-3 text-right">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                          beats
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-zinc-800 text-zinc-400 border border-zinc-700"
                        }`}
                      >
                        {beats ? "Yes" : "No"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
