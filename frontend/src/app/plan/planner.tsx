"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRightIcon, ArrowUpDownIcon, CircleAlertIcon, LoaderIcon, SparklesIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useMemo, useState, useSyncExternalStore } from "react";

import { AqLegend } from "@/components/air/air";
import { AirMap, type MapRoute } from "@/components/map/air-map";
import { Assistant } from "@/components/plan/assistant";
import { DepartureChart } from "@/components/plan/departure-chart";
import { ModePicker } from "@/components/plan/mode-picker";
import { PlaceSearch } from "@/components/plan/place-search";
import { Recommendation } from "@/components/plan/recommendation";
import { RouteList } from "@/components/plan/route-list";
import { ProfileSheet } from "@/components/profile/profile-sheet";
import { SiteHeader } from "@/components/site/site-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, type Mode, type TripResult } from "@/lib/api";
import { WHO_24H } from "@/lib/aq";
import { istDateTime, istTime } from "@/lib/format";
import { useProfile, type Place } from "@/lib/profile";
import { cn } from "@/lib/utils";

const QUICK_TRIPS: { from: Place; to: Place; mode: Mode; label: string }[] = [
  {
    label: "Hauz Khas → DU North Campus",
    from: { name: "Hauz Khas Village", lat: 28.55337, lon: 77.19485 },
    to: { name: "DU North Campus", lat: 28.68815, lon: 77.21004 },
    mode: "cycle",
  },
  {
    label: "Lajpat Nagar → Connaught Place",
    from: { name: "Lajpat Nagar", lat: 28.56899, lon: 77.24083 },
    to: { name: "Connaught Place", lat: 28.63177, lon: 77.21938 },
    mode: "two_wheeler",
  },
  {
    label: "Mayur Vihar → India Gate",
    from: { name: "Mayur Vihar Phase 1", lat: 28.61193, lon: 77.29592 },
    to: { name: "India Gate", lat: 28.61293, lon: 77.22949 },
    mode: "walk",
  },
];

type Tab = "plan" | "ask";

const noopSubscribe = () => () => {};

export function Planner() {
  const profile = useProfile();
  const [from, setFrom] = useState<Place | null>(null);
  const [to, setTo] = useState<Place | null>(null);
  const [mode, setMode] = useState<Mode>("cycle");
  const [trip, setTrip] = useState<TripResult | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [view, setView] = useState<"now" | "recommended">("recommended");
  const [tab, setTab] = useState<Tab>("plan");

  // Fill the form from the profile saved in this browser. It is unknown during the server render,
  // so apply it once, on the first client render.
  const onClient = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const [applied, setApplied] = useState(false);
  if (onClient && !applied) {
    setApplied(true);
    setMode(profile.mode);
    if (profile.usualFrom) setFrom(profile.usualFrom);
    if (profile.usualTo) setTo(profile.usualTo);
  }

  const stations = useQuery({ queryKey: ["stations"], queryFn: api.stations, refetchInterval: 10 * 60_000 });

  const analyze = useMutation({
    mutationFn: (args: { from: Place; to: Place; mode: Mode }) =>
      api.analyze({
        origin: { lat: args.from.lat, lon: args.from.lon, name: args.from.name },
        destination: { lat: args.to.lat, lon: args.to.lon, name: args.to.name },
        mode: args.mode,
        sensitivity: profile.sensitivity,
        max_extra_min: profile.maxExtraMin,
        max_wait_min: profile.maxWaitMin,
        window_h: Math.min(6, Math.max(1, Math.ceil(profile.maxWaitMin / 60))),
      }),
    onSuccess: (t) => {
      setTrip(t);
      setSelected(t.decision.recommended.route_id);
      setView("recommended");
    },
  });

  const run = (f = from, t = to, m = mode) => {
    if (f && t) analyze.mutate({ from: f, to: t, mode: m });
  };

  const rec = trip?.decision.recommended;
  const showsLater = !!rec && rec.wait_min > 0;

  const mapRoutes: MapRoute[] = useMemo(() => {
    if (!trip) return [];
    return trip.routes.map((r) => ({
      id: r.route_id,
      selected: r.route_id === selected,
      recommended: r.route_id === trip.decision.recommended.route_id,
      segments:
        view === "recommended" && r.route_id === trip.recommended_route.route_id
          ? trip.recommended_route.segments
          : r.segments,
    }));
  }, [trip, selected, view]);

  const city = useMemo(() => {
    const s = stations.data?.stations ?? [];
    if (!s.length) return null;
    const vals = s.map((x) => x.pm25_now).sort((a, b) => a - b);
    const median = vals[Math.floor(vals.length / 2)];
    return { median, live: s.filter((x) => x.measured).length, total: s.length };
  }, [stations.data]);

  return (
    <div className="flex min-h-dvh flex-col lg:h-dvh lg:overflow-hidden">
      <SiteHeader compact />
      <div className="grid min-h-0 flex-1 lg:grid-cols-[440px_1fr] lg:grid-rows-[minmax(0,1fr)]">
        {/* Map */}
        <main className="relative h-[44vh] border-b lg:order-2 lg:h-auto lg:border-b-0">
          <AirMap
            stations={stations.data?.stations}
            routes={mapRoutes}
            origin={trip?.origin ?? from}
            destination={trip?.destination ?? to}
            onRouteClick={setSelected}
          />
          <div className="pointer-events-none absolute inset-x-3 top-3 flex items-start justify-between gap-3">
            {showsLater && trip ? (
              <div className="pointer-events-auto flex rounded-lg border bg-popover/95 p-0.5 text-xs shadow-sm backdrop-blur">
                {(["now", "recommended"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setView(v)}
                    className={cn(
                      "rounded-md px-2.5 py-1.5 transition-colors",
                      view === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {v === "now" ? `Leaving now (${istTime(trip.now)})` : `Leaving ${istTime(rec!.depart_at)}`}
                  </button>
                ))}
              </div>
            ) : (
              <span />
            )}
          </div>
          <div className="pointer-events-none absolute bottom-3 left-3 w-56 rounded-lg border bg-popover/95 p-2.5 shadow-sm backdrop-blur">
            <p className="mb-1.5 text-[11px] font-medium">PM2.5 (µg/m³)</p>
            <AqLegend compact />
            <p className="mt-2 text-[10px] leading-snug text-muted-foreground">
              Faded dots: station feed delayed, value estimated by the model.
            </p>
          </div>
        </main>

        {/* Panel */}
        <aside
          className={cn(
            "flex min-h-0 flex-col bg-paper lg:order-1 lg:border-r",
            tab === "plan" ? "lg:overflow-y-auto" : "lg:overflow-hidden",
          )}
        >
          {/* Tabs stay at the top of the panel so the assistant is always one click away. */}
          <div
            role="tablist"
            aria-label="Planner views"
            className="sticky top-0 z-20 flex shrink-0 gap-1 border-b bg-paper/95 px-4 pt-3 backdrop-blur sm:px-5"
          >
            {(
              [
                ["plan", "Plan"],
                ["ask", "Ask AirGuard"],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                role="tab"
                aria-selected={tab === k}
                onClick={() => setTab(k)}
                className={cn(
                  "-mb-px flex items-center gap-1.5 border-b-2 px-2.5 pb-2.5 text-sm transition-colors",
                  tab === k ? "border-foreground text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {k === "ask" && <SparklesIcon className="size-3.5" />}
                {label}
              </button>
            ))}
          </div>

          <div className={cn("space-y-5 p-4 sm:p-5", tab !== "plan" && "hidden")}>
            <form
              className="space-y-2.5"
              onSubmit={(e) => {
                e.preventDefault();
                run();
              }}
            >
              <div className="relative space-y-1.5">
                <PlaceSearch label="From" marker="origin" value={from} onChange={setFrom} placeholder="Home, a metro station…" allowLocate />
                <PlaceSearch label="To" marker="destination" value={to} onChange={setTo} placeholder="Office, college…" />
                <button
                  type="button"
                  aria-label="Swap origin and destination"
                  onClick={() => {
                    setFrom(to);
                    setTo(from);
                  }}
                  className="absolute top-1/2 right-[-6px] z-10 -translate-y-1/2 rounded-full border bg-card p-1.5 text-muted-foreground shadow-sm hover:text-foreground"
                >
                  <ArrowUpDownIcon className="size-3.5" />
                </button>
              </div>
              <ModePicker value={mode} onChange={setMode} />
              <Button type="submit" size="lg" className="h-11 w-full text-[15px]" disabled={!from || !to || analyze.isPending}>
                {analyze.isPending ? (
                  <>
                    <LoaderIcon className="animate-spin" /> Checking routes and departure times…
                  </>
                ) : (
                  "Find the cleaner way"
                )}
              </Button>
              <ProfileSheet onChanged={() => trip && run()} />
            </form>

            <AnimatePresence mode="wait">
              {analyze.isPending ? (
                <motion.div key="loading" exit={{ opacity: 0 }} className="space-y-4 pt-2">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-10 w-3/4" />
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-40 w-full" />
                </motion.div>
              ) : analyze.isError ? (
                <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
                  <p className="flex items-center gap-2 font-medium text-destructive">
                    <CircleAlertIcon className="size-4" /> Couldn&apos;t plan this trip
                  </p>
                  <p className="mt-1 text-muted-foreground">{(analyze.error as ApiError).message}</p>
                  <Button variant="outline" size="sm" className="mt-3" onClick={() => run()}>
                    Try again
                  </Button>
                </motion.div>
              ) : trip ? (
                <motion.div key={trip.trip_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-7 pt-2">
                  <Recommendation trip={trip} />
                  <button
                    type="button"
                    onClick={() => setTab("ask")}
                    className="flex w-full items-center gap-3 rounded-lg border bg-card px-3.5 py-3 text-left transition-colors hover:border-foreground/30"
                  >
                    <SparklesIcon className="size-4 shrink-0" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">Questions about this trip?</span>
                      <span className="block text-xs text-muted-foreground">Ask AirGuard why, how sure it is, or what if you leave now</span>
                    </span>
                    <ArrowRightIcon className="size-4 shrink-0 text-muted-foreground" />
                  </button>
                  <DepartureChart trip={trip} selected={selected} />
                  <RouteList trip={trip} selected={selected} onSelect={setSelected} />
                  <p className="border-t pt-3 text-xs leading-relaxed text-muted-foreground">
                    Forecast issued {istDateTime(trip.data.forecast_issued_at)} IST · model{" "}
                    <span className="font-mono">{trip.data.model_version}</span> · {trip.data.stations - trip.data.stations_delayed} of{" "}
                    {trip.data.stations} stations reporting live, the rest estimated.{" "}
                    {trip.data.snapshot && "Frozen demo snapshot. "}
                    <Link href="/method" className="underline underline-offset-4">How this is calculated</Link>
                  </p>
                </motion.div>
              ) : (
                <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 pt-2">
                  {city && (
                    <div className="rounded-lg border bg-card p-4">
                      <p className="text-xs text-muted-foreground">Delhi right now, median of {city.total} stations</p>
                      <p className="mt-1 font-serif text-4xl tabular">
                        {Math.round(city.median)} <span className="font-sans text-base text-muted-foreground">µg/m³</span>
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {(city.median / WHO_24H).toFixed(1)}× the WHO 24-hour guideline. {city.live} stations reporting live.
                      </p>
                    </div>
                  )}
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Try a common trip</p>
                    <ul className="space-y-1.5">
                      {QUICK_TRIPS.map((q) => (
                        <li key={q.label}>
                          <button
                            type="button"
                            onClick={() => {
                              setFrom(q.from);
                              setTo(q.to);
                              setMode(q.mode);
                              run(q.from, q.to, q.mode);
                            }}
                            className="flex w-full items-center justify-between rounded-lg border bg-card px-3 py-2.5 text-left text-sm hover:border-foreground/25"
                          >
                            {q.label}
                            <span className="text-xs text-muted-foreground">{q.mode.replace("_", "-")}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Assistant: fills the panel, message box pinned to the bottom. */}
          <div className={cn("flex h-[78svh] min-h-0 flex-col gap-3 p-4 sm:p-5 lg:h-auto lg:flex-1", tab !== "ask" && "hidden")}>
            <div className="flex shrink-0 items-center gap-3 rounded-lg border bg-card px-3 py-2.5">
              {trip ? (
                <>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {trip.origin.name ?? "Origin"} → {trip.destination.name ?? "Destination"}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {trip.mode_label} · planned {istTime(trip.now)} IST
                    </span>
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => setTab("plan")}>
                    Change trip
                  </Button>
                </>
              ) : (
                <>
                  <span className="min-w-0 flex-1 text-xs text-muted-foreground">
                    Plan a trip to ask about its routes and timing, or ask a general question below.
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => setTab("plan")}>
                    Plan a trip
                  </Button>
                </>
              )}
            </div>
            <Assistant key={trip?.trip_id ?? "no-trip"} tripId={trip?.trip_id ?? null} className="min-h-0 flex-1" />
          </div>
        </aside>
      </div>
    </div>
  );
}
