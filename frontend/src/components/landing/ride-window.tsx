"use client";

import { motion, useReducedMotion } from "motion/react";
import { useId, useLayoutEffect, useMemo, useRef, useState } from "react";

import { Slider } from "@/components/ui/slider";
import type { TripPreview } from "@/lib/api";
import { BANDS, pmColor } from "@/lib/aq";
import { dur, istTime, num } from "@/lib/format";
import { cn } from "@/lib/utils";

const H = 300;
const SLIDE = { type: "spring", stiffness: 260, damping: 32 } as const;
const PAD = { top: 44, right: 92, bottom: 30, left: 40 };

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Measure now (ResizeObserver only reports after the next paint), then follow resizes.
    setW(Math.round(el.getBoundingClientRect().width));
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

/**
 * The ride as a window of time sitting on the forecast for its route. The curve is PM2.5 along the
 * route over the next hours; a ride occupies `duration` minutes of it, and the shaded area under the
 * curve inside the window is what you'd breathe. Slide the window to see other departures.
 */
export function RideWindow({ data, className }: { data: TripPreview; className?: string }) {
  const uid = useId().replace(/:/g, "");
  const reduce = useReducedMotion();
  const [box, width] = useWidth<HTMLDivElement>();
  const { trip, strips } = data;
  const rows = strips.rows;
  const series = strips.corridor;

  const bestIdx = useMemo(
    () => rows.reduce((bi, r, i) => (r.exposure_index < rows[bi].exposure_index ? i : bi), 0),
    [rows],
  );
  const [picked, setPicked] = useState<number | null>(null);
  const sel = picked ?? bestIdx;

  if (!rows.length || series.length < 2) return null;

  const now = rows[0];
  const chosen = rows[sel];
  const t0 = new Date(series[0].t).getTime();
  const t1 = new Date(series[series.length - 1].t).getTime();
  const durMs = strips.duration_min * 60_000;
  const maxPm = Math.max(...series.map((p) => p.high));
  const bandTop = BANDS.find((b) => b.max >= maxPm * 1.08)?.max ?? 300;
  const yMax = Number.isFinite(bandTop) ? Math.max(bandTop, 90) : Math.ceil(maxPm / 50) * 50;

  const W = Math.max(width, 320);
  const iw = W - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const x = (ms: number) => PAD.left + ((ms - t0) / (t1 - t0)) * iw;
  const y = (v: number) => PAD.top + ih - (Math.min(v, yMax) / yMax) * ih;

  const pts = series.map((p) => [x(new Date(p.t).getTime()), y(p.pm25)] as const);
  const line = pts.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)},${b.toFixed(1)}`).join("");
  const area = `${line}L${pts[pts.length - 1][0].toFixed(1)},${y(0)}L${pts[0][0].toFixed(1)},${y(0)}Z`;
  const band =
    series.map((p, i) => `${i ? "L" : "M"}${x(new Date(p.t).getTime()).toFixed(1)},${y(p.high).toFixed(1)}`).join("") +
    [...series].reverse().map((p) => `L${x(new Date(p.t).getTime()).toFixed(1)},${y(p.low).toFixed(1)}`).join("") + "Z";

  const win = (r: (typeof rows)[number]) => {
    const start = new Date(r.depart_at).getTime();
    return { x0: x(start), x1: x(Math.min(start + durMs, t1)) };
  };
  const wNow = win(now);
  const wSel = win(chosen);
  const same = sel === 0;
  const overlap = !same && wSel.x0 < wNow.x1 + 70;

  // Hour ticks in IST.
  // Hour ticks in IST: full IST hours fall on :30 UTC.
  const HOUR = 3_600_000;
  const ticks: number[] = [];
  for (let t = Math.ceil((t0 - HOUR / 2) / HOUR) * HOUR + HOUR / 2; t <= t1; t += HOUR) ticks.push(t);
  const bandLines = BANDS.filter((b) => Number.isFinite(b.max) && b.max < yMax);

  const change = (chosen.exposure_index / now.exposure_index - 1) * 100;

  return (
    <figure className={cn("rounded-2xl border bg-card", className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b px-5 pt-5 pb-4 sm:px-6">
        <div>
          <p className="font-serif text-xl leading-tight sm:text-2xl">
            {trip.origin.name} → {trip.destination.name}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {trip.mode_label} · {strips.label} · {num(strips.distance_km, 1)} km · {dur(strips.duration_min)}
          </p>
        </div>
        <p className="text-xs text-muted-foreground">PM2.5 along this route, next {Math.round((t1 - t0) / 3_600_000)} hours</p>
      </div>

      <div ref={box} className="px-2 pt-2 sm:px-3">
        {width > 0 && (
          <svg width={W} height={H} className="block" role="img"
            aria-label={`Forecast PM2.5 along the route from ${istTime(series[0].t)} to ${istTime(series[series.length - 1].t)}`}>
            <defs>
              <linearGradient id={`g${uid}`} x1={PAD.left} x2={PAD.left + iw} y1={0} y2={0} gradientUnits="userSpaceOnUse">
                {series.map((p, i) => (
                  <stop key={i} offset={`${(i / (series.length - 1)) * 100}%`} style={{ stopColor: pmColor(p.pm25) }} />
                ))}
              </linearGradient>
              <clipPath id={`now${uid}`}>
                <rect x={wNow.x0} y={0} width={Math.max(0, wNow.x1 - wNow.x0)} height={H} />
              </clipPath>
              <clipPath id={`sel${uid}`}>
                <motion.rect initial={false} animate={{ x: wSel.x0, width: Math.max(0, wSel.x1 - wSel.x0) }}
                  transition={SLIDE} y={0} height={H} />
              </clipPath>
            </defs>

            {/* CPCB band zones for context */}
            {BANDS.map((b, i) => {
              const lo = i === 0 ? 0 : BANDS[i - 1].max;
              if (lo >= yMax) return null;
              const hi = Math.min(b.max, yMax);
              return (
                <g key={b.key}>
                  <rect x={PAD.left} width={iw} y={y(hi)} height={y(lo) - y(hi)} fill={b.color} fillOpacity={0.07} />
                  <text x={PAD.left + iw + 10} y={(y(hi) + y(lo)) / 2 + 3.5} fontSize={10.5} fill="var(--muted-foreground)"
                    fontFamily="var(--font-plex-sans)">
                    {b.label}
                  </text>
                </g>
              );
            })}
            {bandLines.map((b) => (
              <g key={b.key}>
                <line x1={PAD.left} x2={PAD.left + iw} y1={y(b.max)} y2={y(b.max)} stroke="var(--border)" />
                <text x={PAD.left - 8} y={y(b.max) + 3.5} textAnchor="end" fontSize={10} fill="var(--muted-foreground)"
                  fontFamily="var(--font-plex-mono)">
                  {b.max}
                </text>
              </g>
            ))}
            <line x1={PAD.left} x2={PAD.left + iw} y1={y(0)} y2={y(0)} stroke="var(--rule)" />

            {/* Forecast range, then the air you'd breathe on each ride, then the curve */}
            <path d={band} fill="var(--foreground)" fillOpacity={0.06} />
            <motion.g
              initial={reduce ? false : { opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.6, delay: 1.2 }}
            >
              <path d={area} fill={`url(#g${uid})`} fillOpacity={0.22} />
              {!same && <path d={area} fill={`url(#g${uid})`} fillOpacity={0.45} clipPath={`url(#now${uid})`} />}
              <path d={area} fill={`url(#g${uid})`} fillOpacity={0.9} clipPath={`url(#sel${uid})`} />
            </motion.g>
            <motion.path
              d={line}
              fill="none"
              stroke={`url(#g${uid})`}
              strokeWidth={3}
              strokeLinejoin="round"
              strokeLinecap="round"
              initial={reduce ? false : { pathLength: 0 }}
              whileInView={{ pathLength: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 1.4, ease: [0.4, 0.1, 0.2, 1] }}
            />
            <motion.path
              d={line}
              fill="none"
              stroke="var(--foreground)"
              strokeOpacity={0.35}
              strokeWidth={1}
              initial={reduce ? false : { pathLength: 0 }}
              whileInView={{ pathLength: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 1.4, ease: [0.4, 0.1, 0.2, 1] }}
            />

            {/* Ride windows */}
            {!same && (
              <g>
                <rect x={wNow.x0} y={PAD.top - 6} width={wNow.x1 - wNow.x0} height={ih + 6} fill="none"
                  stroke="var(--foreground)" strokeOpacity={0.45} strokeDasharray="4 3" rx={3} />
                <text x={wNow.x0 + 6} y={PAD.top - 12} fontSize={11.5} fill="var(--muted-foreground)" fontFamily="var(--font-plex-sans)">
                  Leave now
                </text>
              </g>
            )}
            <g>
              <motion.rect initial={false} animate={{ x: wSel.x0, width: Math.max(0, wSel.x1 - wSel.x0) }}
                transition={SLIDE} y={PAD.top - 6} height={ih + 6} fill="none" stroke="var(--foreground)"
                strokeWidth={1.75} rx={3} />
              <motion.text initial={false} animate={{ x: wSel.x0 + 6, y: overlap ? PAD.top - 26 : PAD.top - 12 }}
                transition={SLIDE} fontSize={11.5} fontWeight={600} fill="var(--foreground)" fontFamily="var(--font-plex-sans)">
                {same ? "Leave now" : `Leave ${istTime(chosen.depart_at)}`}
              </motion.text>
            </g>

            {/* Time axis */}
            {ticks.map((t) => (
              <text key={t} x={x(t)} y={H - 10} textAnchor="middle" fontSize={10.5} fill="var(--muted-foreground)"
                fontFamily="var(--font-plex-mono)">
                {istTime(new Date(t))}
              </text>
            ))}
          </svg>
        )}
      </div>

      <div className="grid gap-5 border-t px-5 py-5 sm:grid-cols-[1fr_1fr_1.3fr] sm:px-6">
        <div>
          <p className="text-xs text-muted-foreground">Leave now</p>
          <p className="mt-1 font-serif text-3xl tabular">{Math.round(now.exposure_index)}</p>
          <p className="text-xs text-muted-foreground">exposure index · avg {Math.round(now.mean_pm25)} µg/m³</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{same ? "Same as now" : `Leave ${istTime(chosen.depart_at)}`}</p>
          <p className="mt-1 flex items-baseline gap-2 font-serif text-3xl tabular">
            {Math.round(chosen.exposure_index)}
            {!same && (
              <span className={cn("font-sans text-base", change < 0 ? "text-good" : "text-muted-foreground")}>
                {change < 0 ? "−" : "+"}
                {Math.abs(change).toFixed(Math.abs(change) < 10 ? 1 : 0)}%
              </span>
            )}
          </p>
          <p className="text-xs text-muted-foreground">
            {same ? "pick a later time below" : `arrive ${dur(chosen.wait_min)} later · avg ${Math.round(chosen.mean_pm25)} µg/m³`}
          </p>
        </div>
        <div className="sm:pl-4">
          <div className="flex items-baseline justify-between">
            <label htmlFor={`s${uid}`} className="text-xs text-muted-foreground">
              Try another departure
            </label>
            <span className="font-mono text-sm tabular">{sel === 0 ? "now" : istTime(chosen.depart_at)}</span>
          </div>
          <Slider
            id={`s${uid}`}
            className="mt-3"
            value={[sel]}
            min={0}
            max={rows.length - 1}
            step={1}
            onValueChange={(v) => setPicked(Array.isArray(v) ? v[0] : (v as number))}
            aria-label="Departure time"
          />
          <div className="mt-2 flex justify-between font-mono text-[10px] text-muted-foreground">
            <span>now</span>
            <button type="button" onClick={() => setPicked(bestIdx)} className="underline-offset-2 hover:underline">
              cleanest: {bestIdx === 0 ? "now" : istTime(rows[bestIdx].depart_at)}
            </button>
            <span>+{Math.round(rows[rows.length - 1].wait_min / 60)} h</span>
          </div>
        </div>
      </div>

      <figcaption className="border-t px-5 py-4 sm:px-6">
        <p className="font-serif text-lg leading-snug">The same commute can mean very different air.</p>
        <p className="mt-1 text-sm text-muted-foreground">
          The curve is the forecast along this route; the boxes are the ride, {dur(strips.duration_min)} long. The shaded
          area inside a box is the air you&apos;d breathe on that ride.{" "}
          {bestIdx === 0
            ? "Right now the air only gets worse from here, so the cleanest time to go is now."
            : `Leaving at ${istTime(rows[bestIdx].depart_at)} is the cleanest option in the next few hours.`}
        </p>
      </figcaption>
    </figure>
  );
}
