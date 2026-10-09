"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { AqLegend } from "@/components/air/air";
import { AirMap } from "@/components/map/air-map";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { band, WHO_24H } from "@/lib/aq";
import { istTime } from "@/lib/format";
import { useProfile } from "@/lib/profile";

export function HeroActions() {
  const router = useRouter();
  const onboarded = useProfile((s) => s.onboarded);
  return (
    <div className="mt-8 flex flex-wrap items-center gap-3">
      <Button size="lg" className="h-12 px-6 text-[15px]" onClick={() => router.push(onboarded ? "/plan" : "/welcome")}>
        Plan a trip <ArrowRightIcon />
      </Button>
      <Link
        href="/evidence"
        className="inline-flex h-12 items-center px-3 text-[15px] underline-offset-4 hover:underline"
      >
        See how accurate it is
      </Link>
    </div>
  );
}

function useCity() {
  const { data } = useQuery({ queryKey: ["stations"], queryFn: api.stations, refetchInterval: 10 * 60_000 });
  return useMemo(() => {
    const s = data?.stations ?? [];
    if (!s.length) return null;
    const vals = s.map((x) => x.pm25_now).sort((a, b) => a - b);
    return {
      median: vals[Math.floor(vals.length / 2)],
      live: s.filter((x) => x.measured).length,
      total: s.length,
      now: data!.now,
      stations: s,
    };
  }, [data]);
}

export function LiveFacts() {
  const city = useCity();
  if (!city) return <div className="mt-10 h-[68px]" />;
  const b = band(city.median);
  return (
    <dl className="mt-10 grid max-w-lg grid-cols-3 divide-x border-y py-3 text-sm">
      <div className="pr-4">
        <dt className="text-xs text-muted-foreground">Delhi now, median</dt>
        <dd className="mt-0.5 flex items-baseline gap-1.5">
          <span className="font-serif text-2xl tabular">{Math.round(city.median)}</span>
          <span className="text-xs text-muted-foreground">µg/m³</span>
        </dd>
      </div>
      <div className="px-4">
        <dt className="text-xs text-muted-foreground">vs WHO 24-h guideline</dt>
        <dd className="mt-0.5 flex items-baseline gap-1.5">
          <span className="font-serif text-2xl tabular">{(city.median / WHO_24H).toFixed(1)}×</span>
          <span className="size-2 self-center rounded-full" style={{ background: b.color }} />
        </dd>
      </div>
      <div className="pl-4">
        <dt className="text-xs text-muted-foreground">Stations</dt>
        <dd className="mt-0.5 flex items-baseline gap-1.5">
          <span className="font-serif text-2xl tabular">{city.total}</span>
          <span className="text-xs text-muted-foreground">{city.live} live</span>
        </dd>
      </div>
    </dl>
  );
}

export function HeroMap() {
  const city = useCity();
  return (
    <figure className="relative">
      <div className="aspect-[10/9] overflow-hidden rounded-2xl border bg-muted sm:aspect-[6/5]">
        <AirMap stations={city?.stations} interactive={false} />
      </div>
      <figcaption className="absolute right-3 bottom-3 left-3 flex items-end justify-between gap-3 sm:right-4 sm:bottom-4 sm:left-4">
        <div className="w-52 rounded-lg border bg-popover/95 p-2.5 shadow-sm backdrop-blur">
          <p className="mb-1.5 text-[11px] font-medium">PM2.5 at {city ? istTime(city.now) : "—"} IST</p>
          <AqLegend compact />
        </div>
        <span className="rounded-md bg-popover/90 px-2 py-1 text-[10px] text-muted-foreground backdrop-blur">
          Every dot is a monitoring station
        </span>
      </figcaption>
    </figure>
  );
}

export function EvidenceTeaser() {
  const { data } = useQuery({ queryKey: ["eval"], queryFn: api.evaluation });
  const rows = (data?.metrics ?? []).filter((m) => m.mode === "normal");
  if (!rows.length) return null;
  return (
    <section className="rule-top">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <h2 className="font-serif text-3xl tracking-[-0.01em] sm:text-4xl">Tested on weeks it never saw</h2>
            <p className="mt-2 max-w-xl text-[15px] text-muted-foreground">
              Mean absolute error in µg/m³ on the held-out test period, across {data?.n_stations} stations. Lower is better.
            </p>
          </div>
          <Link href="/evidence" className="text-sm underline underline-offset-4">Full evaluation</Link>
        </div>
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
      </div>
    </section>
  );
}
