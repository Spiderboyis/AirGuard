"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { DepartureStrips } from "@/components/landing/departure-strips";
import { RouteAnatomy } from "@/components/landing/route-anatomy";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type TripRequest } from "@/lib/api";
import { pmColor } from "@/lib/aq";
import { useProfile } from "@/lib/profile";

/** The trip every visitor sees: a student cycling from Hauz Khas to Delhi University's North Campus. */
const DEMO_TRIP: TripRequest = {
  origin: { lat: 28.55337, lon: 77.19485, name: "Hauz Khas" },
  destination: { lat: 28.68815, lon: 77.21004, name: "North Campus" },
  mode: "cycle",
  sensitivity: "sensitive",
  window_h: 4,
  max_extra_min: 15,
  max_wait_min: 240,
};

function usePreview() {
  return useQuery({ queryKey: ["preview", DEMO_TRIP], queryFn: () => api.preview(DEMO_TRIP), staleTime: 5 * 60_000 });
}

function useStations() {
  return useQuery({ queryKey: ["stations"], queryFn: api.stations, refetchInterval: 10 * 60_000 });
}

export function PlanButton({ label = "Plan a trip", className }: { label?: string; className?: string }) {
  const router = useRouter();
  const onboarded = useProfile((s) => s.onboarded);
  return (
    <Button size="lg" className={className ?? "h-12 px-6 text-[15px]"} onClick={() => router.push(onboarded ? "/plan" : "/welcome")}>
      {label} <ArrowRightIcon />
    </Button>
  );
}

/** One line, set like a newspaper dateline, built from the live station data. */
export function Dateline() {
  const { data } = useStations();
  const city = useMemo(() => {
    const s = data?.stations ?? [];
    if (!s.length) return null;
    const vals = s.map((x) => x.pm25_now).sort((a, b) => a - b);
    return { median: vals[Math.floor(vals.length / 2)], live: s.filter((x) => x.measured).length, total: s.length };
  }, [data]);
  if (!data || !city) return <div className="h-5" />;
  const when = new Date(data.now).toLocaleString("en-IN", {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata",
  });
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
      <span className="font-medium text-foreground">Delhi</span>
      <span aria-hidden>·</span>
      <span className="tabular">{when} IST</span>
      <span aria-hidden>—</span>
      <span>
        median PM2.5{" "}
        <span className="inline-flex items-center gap-1.5 font-medium text-foreground tabular">
          <span className="inline-block size-2 rounded-[2px]" style={{ background: pmColor(city.median) }} />
          {Math.round(city.median)} µg/m³
        </span>{" "}
        across {city.total} stations, {city.live} reporting live.
      </span>
    </p>
  );
}

export function HeroFigure() {
  const { data, isError } = usePreview();
  if (isError)
    return (
      <div className="flex h-72 items-center justify-center rounded-2xl border bg-card p-6 text-center text-sm text-muted-foreground">
        The live forecast isn&apos;t reachable right now. Start the API and refresh.
      </div>
    );
  if (!data) return <Skeleton className="h-[420px] w-full rounded-2xl" />;
  return <DepartureStrips data={data} />;
}

export function AnatomySection() {
  const preview = usePreview();
  const stations = useStations();
  if (!preview.data || !stations.data) return <Skeleton className="h-[480px] w-full rounded-2xl" />;
  return <RouteAnatomy data={preview.data} stations={stations.data.stations} />;
}

export function EvidenceBlock() {
  const { data } = useQuery({ queryKey: ["eval"], queryFn: api.evaluation });
  const rows = (data?.metrics ?? []).filter((m) => m.mode === "normal");
  if (!rows.length) return null;
  const h6 = rows.find((r) => r.horizon_h === 6) ?? rows[Math.floor(rows.length / 2)];
  const vsPersist = h6.baseline_persistence_mae ? Math.round((1 - h6.mae / h6.baseline_persistence_mae) * 100) : null;
  const vsCams = h6.baseline_cams_mae ? Math.round((1 - h6.mae / h6.baseline_cams_mae) * 100) : null;
  return (
    <>
      <p className="mt-4 max-w-2xl font-serif text-2xl leading-snug sm:text-[1.75rem]">
        Six hours ahead, it&apos;s {vsPersist}% more accurate than assuming the air stays as it is, and {vsCams}% more
        accurate than the global CAMS model.
      </p>
      <p className="mt-3 max-w-2xl text-[15px] text-muted-foreground">
        Mean absolute error in µg/m³ on the two most recent weeks, which the model never saw in training, across{" "}
        {data?.n_stations} stations. Lower is better.
      </p>
      <div className="mt-8 overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="py-2 font-normal">Forecast for</th>
              <th className="py-2 text-right font-normal">AirGuard</th>
              <th className="py-2 text-right font-normal">Last reading</th>
              <th className="py-2 text-right font-normal">Usual for that hour</th>
              <th className="py-2 text-right font-normal">CAMS model</th>
            </tr>
          </thead>
          <tbody className="tabular font-mono">
            {rows.map((r) => (
              <tr key={r.horizon_h} className="border-b">
                <td className="py-2.5 font-sans">+{r.horizon_h} h</td>
                <td className="py-2.5 text-right font-medium">{r.mae.toFixed(1)}</td>
                <td className="py-2.5 text-right text-muted-foreground">{r.baseline_persistence_mae?.toFixed(1)}</td>
                <td className="py-2.5 text-right text-muted-foreground">{r.baseline_hourly_mean_mae?.toFixed(1)}</td>
                <td className="py-2.5 text-right text-muted-foreground">{r.baseline_cams_mae?.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Link href="/evidence" className="mt-5 inline-block text-sm underline underline-offset-4">
        Full evaluation, including when station feeds are delayed
      </Link>
    </>
  );
}
