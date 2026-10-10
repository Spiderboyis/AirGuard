"use client";

import { motion, useReducedMotion } from "motion/react";

import type { StripRow, TripPreview } from "@/lib/api";
import { pmColor } from "@/lib/aq";
import { dur, istTime, num } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Merge neighbouring segments of near-identical colour so each row is a handful of DOM nodes. */
function runs(row: StripRow) {
  const total = row.minutes.reduce((a, b) => a + b, 0) || 1;
  const out: { pm: number; w: number }[] = [];
  row.pm25.forEach((pm, i) => {
    const w = (row.minutes[i] / total) * 100;
    const last = out[out.length - 1];
    if (last && Math.abs(last.pm - pm) < 0.6) {
      last.pm = (last.pm * last.w + pm * w) / (last.w + w);
      last.w += w;
    } else out.push({ pm, w });
  });
  return out;
}

const SCALE_TICKS = [30, 60, 90, 120];

export function DepartureStrips({ data, className }: { data: TripPreview; className?: string }) {
  const reduce = useReducedMotion();
  const { trip, strips } = data;
  const rows = strips.rows;
  if (!rows.length) return null;

  const now = rows[0];
  const best = rows.reduce((a, b) => (b.exposure_index < a.exposure_index ? b : a), now);
  const rec = trip.decision.recommended;
  const recWait = rec.route_id === strips.route_id ? rec.wait_min : null;
  const change = (r: StripRow) => (r.exposure_index / now.exposure_index - 1) * 100;
  const bestCut = -change(best);
  const lastTime = istTime(rows[rows.length - 1].depart_at);
  const origin = trip.origin.name ?? "Start";
  const destination = trip.destination.name ?? "End";

  return (
    <figure className={cn("rounded-2xl border bg-card", className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4 border-b px-5 pt-5 pb-4 sm:px-6">
        <div>
          <p className="font-serif text-xl leading-tight sm:text-2xl">
            {origin} → {destination}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {trip.mode_label} · {strips.label} · {num(strips.distance_km, 1)} km · {dur(strips.duration_min)}
          </p>
        </div>
        <div className="w-56">
          <div className="flex h-2 overflow-hidden rounded-full">
            {Array.from({ length: 24 }, (_, i) => (
              <span key={i} className="flex-1" style={{ background: pmColor(10 + i * 7) }} />
            ))}
          </div>
          <div className="relative mt-1 h-3 font-mono text-[10px] text-muted-foreground">
            {SCALE_TICKS.map((t) => (
              <span key={t} className="absolute -translate-x-1/2" style={{ left: `${((t - 10) / (23 * 7)) * 100}%` }}>
                {t}
              </span>
            ))}
            <span className="absolute right-0 translate-x-0">µg/m³</span>
          </div>
        </div>
      </div>

      <div className="px-5 pt-4 pb-5 sm:px-6">
        <div className="grid grid-cols-[3.25rem_1fr_3.5rem] items-end gap-x-3 pb-2 text-[11px] text-muted-foreground">
          <span>Leave</span>
          <span className="flex justify-between">
            <span className="truncate">{origin}</span>
            <span className="truncate text-right">{destination}</span>
          </span>
          <span className="text-right">vs now</span>
        </div>

        <motion.ol
          className="space-y-[3px]"
          aria-label="PM2.5 along the route for each departure time"
          initial={reduce ? false : "hidden"}
          whileInView="shown"
          viewport={{ once: true, amount: 0.25 }}
        >
          {rows.map((r, i) => {
            const isBest = r === best && best !== now;
            const isRec = recWait === r.wait_min;
            const c = change(r);
            return (
              <li
                key={r.wait_min}
                className="group grid grid-cols-[3.25rem_1fr_3.5rem] items-center gap-x-3"
                title={`Leave ${istTime(r.depart_at)}: average ${Math.round(r.mean_pm25)} µg/m³, exposure index ${Math.round(r.exposure_index)}`}
              >
                <span
                  className={cn(
                    "font-mono text-[11px] tabular",
                    isBest || isRec ? "font-medium text-foreground" : "text-muted-foreground",
                  )}
                >
                  {i === 0 ? "now" : istTime(r.depart_at)}
                </span>
                <div className="relative h-3.5 overflow-hidden rounded-[2px] bg-muted">
                  {/* One trigger for the whole chart (on the list); each row plays its ride slightly after the last. */}
                  <motion.div
                    className="flex h-full"
                    variants={{
                      hidden: { clipPath: "inset(0 100% 0 0)" },
                      shown: {
                        clipPath: "inset(0 0% 0 0)",
                        transition: { duration: 1.1, delay: 0.1 + i * 0.045, ease: [0.35, 0.1, 0.25, 1] },
                      },
                    }}
                  >
                    {runs(r).map((s, j) => (
                      <span key={j} className="h-full" style={{ width: `${s.w}%`, background: pmColor(s.pm) }} />
                    ))}
                  </motion.div>
                  {(isBest || isRec) && (
                    <span className="pointer-events-none absolute inset-0 rounded-[2px] ring-[1.5px] ring-foreground ring-inset" />
                  )}
                </div>
                <span
                  className={cn(
                    "text-right font-mono text-[11px] tabular",
                    i === 0 ? "text-muted-foreground" : c < -0.5 ? "text-good" : c > 0.5 ? "text-muted-foreground" : "text-muted-foreground",
                    isBest && "font-medium",
                  )}
                >
                  {i === 0 ? "—" : `${c < 0 ? "−" : "+"}${Math.abs(c).toFixed(c > -10 && c < 10 ? 1 : 0)}%`}
                </span>
              </li>
            );
          })}
        </motion.ol>

        <figcaption className="mt-5 grid gap-3 border-t pt-4 sm:grid-cols-[1fr_auto] sm:items-end">
          <div>
            <p className="font-serif text-lg leading-snug">The same commute can mean very different air.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {bestCut >= 1 ? (
                <>
                  Leaving at <span className="font-medium text-foreground">{istTime(best.depart_at)}</span> instead of now
                  means {bestCut.toFixed(bestCut < 10 ? 1 : 0)}% less exposure on the same road.
                </>
              ) : (
                <>Right now the air only gets worse until {lastTime}, so the cleanest time to take this ride is now.</>
              )}{" "}
              Each row is one departure; each sliver of colour is 200 metres of the ride.
            </p>
          </div>
          <p className="font-mono text-[11px] text-muted-foreground sm:text-right">
            Live forecast · {trip.data.model_version}
          </p>
        </figcaption>
      </div>
    </figure>
  );
}
