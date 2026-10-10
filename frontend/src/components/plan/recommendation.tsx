"use client";

import { motion } from "motion/react";

import { ConfidenceMeter, RiskBadge } from "@/components/air/air";
import type { TripResult } from "@/lib/api";
import { dur, istTime, minutes, signedMin, signedPct } from "@/lib/format";
import { SENSITIVITY_COPY } from "@/lib/profile";

function headline(t: TripResult) {
  const d = t.decision;
  const rec = d.recommended;
  switch (d.kind) {
    case "stay":
      return { big: "Leave now", small: `on the fastest route, ${rec.label}` };
    case "route":
      return { big: "Leave now", small: `but take ${rec.label}` };
    case "wait":
      return { big: `Leave at ${istTime(rec.depart_at)}`, small: `same route, ${rec.label}` };
    default:
      return { big: `Leave at ${istTime(rec.depart_at)}`, small: `and take ${rec.label}` };
  }
}

export function Recommendation({ trip }: { trip: TripResult }) {
  const d = trip.decision;
  const rec = d.recommended;
  const h = headline(trip);
  const cut = d.delta.exposure_index_pct;
  const sens = SENSITIVITY_COPY[trip.sensitivity].short.toLowerCase();
  const lowest = d.lowest;
  const cleanerElsewhere = lowest.exposure_index < rec.exposure_index - 0.5;
  const lowestOutsideLimits =
    lowest.wait_min > trip.limits.max_wait_min ||
    lowest.duration_min - d.baseline.duration_min > trip.limits.max_extra_min;

  return (
    <motion.section
      key={trip.trip_id}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.2, 0.7, 0.2, 1] }}
      className="space-y-4"
      aria-live="polite"
    >
      <div>
        <p className="text-xs font-medium tracking-[0.12em] text-muted-foreground uppercase">Recommendation</p>
        <h2 className="mt-1 font-serif text-[2.1rem] leading-[1.05] tracking-[-0.015em]">{h.big}</h2>
        <p className="mt-1 text-[15px] text-muted-foreground">{h.small}</p>
      </div>

      <dl className="grid grid-cols-3 divide-x rounded-lg border bg-card">
        <div className="px-3 py-2.5">
          <dt className="text-[11px] text-muted-foreground">Exposure</dt>
          <dd className={`font-serif text-2xl tabular ${cut < 0 ? "text-good" : ""}`}>{d.kind === "stay" ? "—" : signedPct(cut)}</dd>
        </div>
        <div className="px-3 py-2.5">
          <dt className="text-[11px] text-muted-foreground">Arrival</dt>
          <dd className="font-serif text-2xl tabular">{d.kind === "stay" ? "On time" : signedMin(d.delta.arrival_min)}</dd>
        </div>
        <div className="px-3 py-2.5">
          <dt className="text-[11px] text-muted-foreground">Trip time</dt>
          <dd className="font-serif text-2xl tabular">{dur(rec.duration_min)}</dd>
        </div>
      </dl>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <span className="inline-flex items-center gap-1.5">
          <span className="tabular font-mono">{Math.round(rec.mean_pm25)}</span>
          <span className="text-muted-foreground">µg/m³ avg</span>
        </span>
        <RiskBadge risk={rec.risk} />
        <ConfidenceMeter value={rec.confidence} />
      </div>

      <p className="text-sm leading-relaxed text-muted-foreground">
        {d.kind === "stay" ? (
          <>No later departure or other route cuts your exposure enough to be worth the extra time for a {sens} profile.</>
        ) : (
          <>
            {Math.abs(Math.round(cut))}% less exposure for {minutes(d.delta.arrival_min)} later is worth it for a {sens} profile
            {d.delta.wait_min > 0 ? " (waiting counts half, since you can wait indoors)" : ""}.
          </>
        )}{" "}
        Exposure index {Math.round(d.baseline.exposure_index)} → {Math.round(rec.exposure_index)}, forecast range{" "}
        {Math.round(rec.exposure_low)}–{Math.round(rec.exposure_high)}.
        {cleanerElsewhere && (
          <>
            {" "}
            The cleanest option ({istTime(lowest.depart_at)}, {lowest.label}, {signedPct(
              (lowest.exposure_index / d.baseline.exposure_index - 1) * 100,
            )}) {lowestOutsideLimits ? "falls outside your time limits" : "saves too little for the extra time"}.
          </>
        )}
      </p>
    </motion.section>
  );
}
