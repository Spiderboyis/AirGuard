"use client";

import { useQuery } from "@tanstack/react-query";

import { Skeleton } from "@/components/ui/skeleton";
import { api, type Mode, type Sensitivity } from "@/lib/api";
import { bandByKey } from "@/lib/aq";
import { SENSITIVITY_COPY } from "@/lib/profile";

const MODE_NOTE: Record<Mode, string> = {
  walk: "Light activity (baseline)",
  cycle: "Moderate activity, about twice the breathing rate of walking",
  two_wheeler: "Seated, open to the street",
  car: "Seated, windows up; assumed in-cabin level about 60% of outside",
};

/** One block of the Method page, rendered from GET /meta so it always matches the code. */
export function Assumptions({ part }: { part: "modes" | "bands" | "decision" | "credits" }) {
  const { data, isLoading } = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  if (isLoading || !data) return <Skeleton className="mt-4 h-28 w-full" />;
  const a = data.assumptions;

  if (part === "modes")
    return (
      <table className="mt-5 w-full text-sm">
        <tbody>
          {(Object.keys(a.mode_factors) as Mode[]).map((m) => (
            <tr key={m} className="border-b">
              <td className="py-2.5 font-medium">{a.mode_labels[m]}</td>
              <td className="py-2.5 text-muted-foreground">{MODE_NOTE[m]}</td>
              <td className="py-2.5 text-right font-mono tabular">× {a.mode_factors[m]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );

  if (part === "bands") {
    return (
      <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {a.risk_bands.map((b, i) => {
          const lo = i === 0 ? 0 : (a.risk_bands[i - 1].max_pm25 ?? 0) + 1;
          const range = b.max_pm25 == null ? `${lo}+` : `${lo}–${b.max_pm25}`;
          return (
            <div key={b.key} className="flex items-center gap-3 rounded-lg border bg-card p-3">
              <span className="h-8 w-1.5 rounded-full" style={{ background: bandByKey(b.key).color }} />
              <span>
                <span className="block text-sm font-medium">{b.label}</span>
                <span className="block font-mono text-xs text-muted-foreground">{range} µg/m³</span>
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  if (part === "decision")
    return (
      <table className="mt-5 w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="py-2 font-normal">Sensitivity</th>
            <th className="py-2 text-right font-normal">Minutes per 10% less exposure</th>
            <th className="py-2 text-right font-normal">To wait 30 min, needs</th>
          </tr>
        </thead>
        <tbody>
          {(Object.keys(a.decision.minutes_per_10pct) as Sensitivity[]).map((s) => {
            const k = a.decision.minutes_per_10pct[s];
            const need = Math.ceil(((a.decision.wait_cost_weight * 30) / k) * 10);
            return (
              <tr key={s} className="border-b">
                <td className="py-2.5">{SENSITIVITY_COPY[s].short}</td>
                <td className="py-2.5 text-right font-mono tabular">{k}</td>
                <td className="py-2.5 text-right font-mono tabular">−{need}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );

  return (
    <ul className="mt-4 space-y-2 text-sm">
      {data.attributions.map((x) => (
        <li key={x.name} className="flex flex-wrap justify-between gap-x-4 border-b pb-2">
          <a href={x.url} target="_blank" rel="noreferrer" className="font-medium underline-offset-4 hover:underline">
            {x.name}
          </a>
          <span className="text-muted-foreground">{x.use}</span>
        </li>
      ))}
    </ul>
  );
}
