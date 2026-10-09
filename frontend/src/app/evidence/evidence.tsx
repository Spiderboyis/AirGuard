"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Skeleton } from "@/components/ui/skeleton";
import { api, type EvalRow } from "@/lib/api";
import { istDateTime } from "@/lib/format";

const SERIES = [
  { key: "mae", name: "AirGuard", fill: "var(--foreground)" },
  { key: "baseline_persistence_mae", name: "Last reading", fill: "var(--rule)" },
  { key: "baseline_hourly_mean_mae", name: "Usual for that hour", fill: "color-mix(in oklab, var(--rule) 55%, transparent)" },
  { key: "baseline_cams_mae", name: "CAMS model", fill: "var(--aq-moderate)" },
] as const;

function pctBetter(model: number, base?: number | null) {
  if (!base) return null;
  return Math.round((1 - model / base) * 100);
}

function MaeChart({ rows, delayed }: { rows: EvalRow[]; delayed?: boolean }) {
  const data = rows.map((r) => ({ ...r, h: r.horizon_h === 0 ? "now" : `+${r.horizon_h} h` }));
  const series = delayed ? SERIES.filter((s) => s.key !== "baseline_persistence_mae") : SERIES;
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }} barGap={2} barCategoryGap="22%">
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="h" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)", fontFamily: "var(--font-plex-mono)" }} />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
            formatter={(v) => [`${Number(v).toFixed(1)} µg/m³`]}
          />
          <Legend iconType="square" iconSize={9} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.fill} radius={[2, 2, 0, 0]} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MetricsTable({ rows, delayed }: { rows: EvalRow[]; delayed?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="py-2 font-normal">Horizon</th>
            <th className="py-2 text-right font-normal">MAE</th>
            <th className="py-2 text-right font-normal">RMSE</th>
            {!delayed && <th className="py-2 text-right font-normal">vs last reading</th>}
            <th className="py-2 text-right font-normal">vs hour average</th>
            <th className="py-2 text-right font-normal">vs CAMS</th>
            <th className="py-2 text-right font-normal">80% range hit</th>
            <th className="py-2 text-right font-normal">Samples</th>
          </tr>
        </thead>
        <tbody className="font-mono tabular">
          {rows.map((r) => {
            const cells = [
              !delayed ? pctBetter(r.mae, r.baseline_persistence_mae) : undefined,
              pctBetter(r.mae, r.baseline_hourly_mean_mae),
              pctBetter(r.mae, r.baseline_cams_mae),
            ];
            return (
              <tr key={`${r.mode}-${r.horizon_h}`} className="border-b">
                <td className="py-2.5 font-sans">{r.horizon_h === 0 ? "Now (nowcast)" : `+${r.horizon_h} h`}</td>
                <td className="py-2.5 text-right font-medium">{r.mae.toFixed(1)}</td>
                <td className="py-2.5 text-right">{r.rmse.toFixed(1)}</td>
                {cells.map((c, i) =>
                  c === undefined ? null : (
                    <td key={i} className={`py-2.5 text-right ${c != null && c > 0 ? "text-good" : "text-destructive"}`}>
                      {c == null ? "—" : `${c > 0 ? "−" : "+"}${Math.abs(c)}%`}
                    </td>
                  ),
                )}
                <td className="py-2.5 text-right">{r.interval_coverage != null ? `${Math.round(r.interval_coverage * 100)}%` : "—"}</td>
                <td className="py-2.5 text-right text-muted-foreground">{r.n_samples.toLocaleString("en-IN")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted-foreground">
        Percentages are AirGuard&apos;s error relative to each baseline: green means AirGuard was more accurate.
      </p>
    </div>
  );
}

export function EvidenceBody() {
  const { data, isLoading, isError } = useQuery({ queryKey: ["eval"], queryFn: api.evaluation });

  if (isLoading) return <Skeleton className="mt-12 h-80 w-full" />;
  if (isError || !data?.metrics.length)
    return (
      <p className="mt-12 rounded-lg border p-5 text-sm text-muted-foreground">
        No evaluation yet. Train the model with <code className="font-mono">make train</code> and this page fills in.
      </p>
    );

  const normal = data.metrics.filter((m) => m.mode === "normal");
  const delayed = data.metrics.filter((m) => m.mode === "delayed");

  return (
    <div className="mt-12 space-y-16">
      <dl className="grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-4">
        {[
          ["Model", data.model_version ?? "—"],
          ["Stations", String(data.n_stations ?? "—")],
          ["Trained on data up to", data.train_end ? istDateTime(data.train_end) : "—"],
          ["Tested on", data.test_start && data.test_end ? `${istDateTime(data.test_start)} – ${istDateTime(data.test_end)}` : "—"],
        ].map(([k, v]) => (
          <div key={k} className="bg-card p-4">
            <dt className="text-xs text-muted-foreground">{k}</dt>
            <dd className="mt-1 text-sm font-medium break-words">{v}</dd>
          </div>
        ))}
      </dl>

      <section className="space-y-6">
        <div className="max-w-2xl">
          <h2 className="font-serif text-3xl tracking-[-0.01em]">When the station is reporting</h2>
          <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
            Mean absolute error in µg/m³ for each forecast horizon. The baselines are: repeat the last reading;
            the station&apos;s average for that hour of day; and the raw CAMS global model forecast at the station.
          </p>
        </div>
        <MaeChart rows={normal} />
        <MetricsTable rows={normal} />
      </section>

      {delayed.length > 0 && (
        <section className="space-y-6">
          <div className="max-w-2xl">
            <h2 className="font-serif text-3xl tracking-[-0.01em]">When the station&apos;s feed is delayed</h2>
            <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
              CPCB feeds sometimes arrive hours or days late. In this test the station&apos;s own readings are
              hidden and the model has to estimate it from CAMS, weather and any neighbours still reporting. This
              is the mode the app uses for stations shown as estimated on the map.
            </p>
          </div>
          <MaeChart rows={delayed} delayed />
          <MetricsTable rows={delayed} delayed />
        </section>
      )}

      <section className="grid gap-10 border-t pt-10 md:grid-cols-2">
        <div>
          <h3 className="font-medium">How the test works</h3>
          <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
            The data is split by time, never at random: the model is trained on the earlier months, its uncertainty
            range is set on the following week, and it is scored on the final two weeks. A 24-hour gap separates
            training from what follows so no reading leaks across. One XGBoost model is trained per horizon, across
            all stations.
          </p>
        </div>
        <div>
          <h3 className="font-medium">What this does and doesn&apos;t show</h3>
          <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
            These numbers measure the forecast at monitoring stations. Values along a route are interpolated between
            stations and are less certain, which is why every route carries a confidence score. The exposure index
            is an estimate under stated assumptions, not a measured dose.
          </p>
        </div>
      </section>
      {data.notes && <p className="text-xs text-muted-foreground">Model notes: {data.notes}</p>}
    </div>
  );
}
