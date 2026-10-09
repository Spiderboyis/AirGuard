"use client";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { evalMetrics, type EvalRow } from "@/lib/api";

export default function Eval() {
  const [rows, setRows] = useState<EvalRow[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => { evalMetrics().then(setRows).catch((error) => setErr((error as Error).message)); }, []);
  const data = rows.map((row) => ({
    horizon: `+${row.horizon_h}h`,
    Model: row.mae,
    Persistence: row.baseline_persistence_mae,
    "Hour-of-day mean": row.baseline_hourly_mean_mae,
  }));
  const version = rows[0]?.model_version ?? "";
  const synthetic = version.includes("synthetic");
  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4">
      <h1 className="text-xl font-semibold">Forecast accuracy on a held-out window</h1>
      {err && <p role="alert" className="text-sm text-red-700">{err}</p>}
      {!err && rows.length === 0 && <p className="text-sm text-slate-600">No evaluation rows yet. Run the training script first.</p>}
      {version && <p className="text-sm">Model version: {version}</p>}
      {synthetic && <p className="text-sm text-amber-700">These rows are from synthetic local data, not a Delhi backtest. Run the real backfill and training, then set MODEL_VERSION to that run, to replace them.</p>}
      <p className="text-sm">Mean absolute error in µg/m³ (lower is better), on data the model never saw during training or tuning. The hour-of-day baseline uses India Standard Time.</p>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="horizon" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="Model" fill="#1d4ed8" />
            <Bar dataKey="Persistence" fill="#9ca3af" />
            <Bar dataKey="Hour-of-day mean" fill="#d1d5db" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left">
              <th>Horizon</th><th>MAE</th><th>RMSE</th><th>80% range covers</th><th>Avg width</th><th>Samples</th><th>Beats both baselines</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.horizon_h}>
                <td>+{row.horizon_h}h</td>
                <td>{row.mae}</td>
                <td>{row.rmse}</td>
                <td>{row.interval_coverage == null ? "–" : `${Math.round(row.interval_coverage * 100)}%`}</td>
                <td>{row.interval_width ?? "–"}</td>
                <td>{row.n_samples}</td>
                <td>{row.mae < row.baseline_persistence_mae && row.mae < row.baseline_hourly_mean_mae ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-600">A 10th-to-90th percentile range should cover about 80% of held-out observations. If coverage is far from that, say so rather than calling the range calibrated. Route differences are estimates under the exposure engine&apos;s assumptions, not a measured change in what a person inhaled.</p>
    </main>
  );
}
