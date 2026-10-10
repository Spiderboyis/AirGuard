"use client";

import Link from "next/link";
import { useMemo } from "react";

import type { StationSummary, TripPreview } from "@/lib/api";
import { pmColor } from "@/lib/aq";
import { istTime } from "@/lib/format";

const W = 640;
const H = 560;
const PAD = 34;

type Seg = TripPreview["trip"]["routes"][number]["segments"][number];

/** Equirectangular projection fitted to the box: fine at city scale. */
function projector(points: number[][]) {
  const lats = points.map((p) => p[1]);
  const lons = points.map((p) => p[0]);
  const k = Math.cos(((Math.min(...lats) + Math.max(...lats)) / 2) * (Math.PI / 180));
  const [x0, x1] = [Math.min(...lons) * k, Math.max(...lons) * k];
  const [y0, y1] = [Math.min(...lats), Math.max(...lats)];
  const s = Math.min((W - 2 * PAD) / (x1 - x0 || 1), (H - 2 * PAD) / (y1 - y0 || 1));
  const ox = (W - (x1 - x0) * s) / 2;
  const oy = (H - (y1 - y0) * s) / 2;
  return ([lon, lat]: number[]) => [ox + (lon * k - x0) * s, H - (oy + (lat - y0) * s)] as const;
}

function mid(seg: Seg) {
  return seg.line[Math.floor(seg.line.length / 2)];
}

export function RouteAnatomy({ data, stations }: { data: TripPreview; stations: StationSummary[] }) {
  const { trip } = data;
  const fig = useMemo(() => {
    const main = trip.routes.find((r) => r.route_id === trip.decision.recommended.route_id) ?? trip.routes[0];
    const others = trip.routes.filter((r) => r.route_id !== main.route_id);
    const alt = others.sort((a, b) => Math.abs(b.exposure_index - main.exposure_index) - Math.abs(a.exposure_index - main.exposure_index))[0];
    const routePts = [...main.segments, ...(alt?.segments ?? [])].flatMap((s) => s.line);
    const lons = routePts.map((p) => p[0]);
    const lats = routePts.map((p) => p[1]);
    const m = 0.012; // ~1.2 km margin for nearby stations
    const near = stations.filter(
      (s) => s.lon > Math.min(...lons) - m && s.lon < Math.max(...lons) + m && s.lat > Math.min(...lats) - m && s.lat < Math.max(...lats) + m,
    );
    const project = projector([...routePts, ...near.map((s) => [s.lon, s.lat])]);

    // 1: the worst stretch; 2: the stretch furthest from any monitor (skipping ones next to 1).
    const worstIdx = main.segments.reduce((bi, s, i, a) => (s.pm25 > a[bi].pm25 ? i : bi), 0);
    const byDistance = main.segments.map((s, i) => [s.station_km, i] as const).sort((a, b) => b[0] - a[0]);
    const farIdx = (byDistance.find(([, i]) => Math.abs(i - worstIdx) > 8) ?? byDistance[0])[1];
    const minutesTo = (idx: number) => main.segments.slice(0, idx).reduce((a, s) => a + s.minutes, 0) + main.segments[idx].minutes / 2;
    const worstAt = new Date(new Date(main.depart_at).getTime() + minutesTo(worstIdx) * 60_000);
    const altMid = alt ? mid(alt.segments[Math.floor(alt.segments.length / 2)]) : null;

    return { main, alt, near, project, worstIdx, farIdx, worstAt, altMid };
  }, [trip, stations]);

  const { main, alt, near, project, worstIdx, farIdx, worstAt, altMid } = fig;
  const path = (line: number[][]) => line.map((p) => project(p).map((v) => v.toFixed(1)).join(",")).join(" ");
  const markers = [
    { n: 1, at: project(mid(main.segments[worstIdx])) },
    { n: 2, at: project(mid(main.segments[farIdx])) },
    ...(altMid ? [{ n: 3, at: project(altMid) }] : []),
  ];
  const o = project([trip.origin.lon, trip.origin.lat]);
  const d = project([trip.destination.lon, trip.destination.lat]);
  const worst = main.segments[worstIdx];
  const far = main.segments[farIdx];
  const altMin = alt ? alt.duration_min - main.duration_min : 0;
  const altPct = alt ? (alt.exposure_index / main.exposure_index - 1) * 100 : 0;

  return (
    <div className="grid gap-10 lg:grid-cols-[1.15fr_1fr] lg:gap-14">
      <figure className="rounded-2xl border bg-card p-3 sm:p-4">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="The route, coloured by forecast PM2.5, with monitoring stations">
          {alt && (
            <g>
              {alt.segments.map((s, i) => (
                <polyline key={i} points={path(s.line)} fill="none" stroke="var(--foreground)" strokeOpacity={0.22}
                  strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
              ))}
            </g>
          )}
          <g>
            {main.segments.map((s, i) => (
              <polyline key={i} points={path(s.line)} fill="none" stroke="var(--card)" strokeWidth={9}
                strokeLinecap="round" strokeLinejoin="round" />
            ))}
            {main.segments.map((s, i) => (
              <polyline key={`c${i}`} points={path(s.line)} fill="none" stroke={pmColor(s.pm25)} strokeWidth={5.5}
                strokeLinecap="round" strokeLinejoin="round" />
            ))}
          </g>
          <g>
            {near.map((s) => {
              const [x, y] = project([s.lon, s.lat]);
              return s.measured ? (
                <rect key={s.id} x={x - 4.5} y={y - 4.5} width={9} height={9} fill={pmColor(s.pm25_now)} stroke="var(--foreground)" strokeWidth={1.2}>
                  <title>{`${s.name}: ${Math.round(s.pm25_now)} µg/m³ (measured)`}</title>
                </rect>
              ) : (
                <rect key={s.id} x={x - 4} y={y - 4} width={8} height={8} fill="var(--card)" stroke="var(--foreground)" strokeOpacity={0.55} strokeWidth={1.2}>
                  <title>{`${s.name}: ${Math.round(s.pm25_now)} µg/m³ (estimated, feed delayed)`}</title>
                </rect>
              );
            })}
          </g>
          <circle cx={o[0]} cy={o[1]} r={7} fill="var(--card)" stroke="var(--foreground)" strokeWidth={3} />
          <circle cx={d[0]} cy={d[1]} r={7} fill="var(--foreground)" />
          <text x={o[0] + 12} y={o[1] + 4} fontSize={13} fill="var(--foreground)" fontFamily="var(--font-plex-sans)">
            {trip.origin.name}
          </text>
          <text x={d[0] + 12} y={d[1] + 4} fontSize={13} fill="var(--foreground)" fontFamily="var(--font-plex-sans)">
            {trip.destination.name}
          </text>
          {markers.map((m) => (
            <g key={m.n} transform={`translate(${m.at[0]},${m.at[1]})`}>
              <circle r={11} fill="var(--foreground)" stroke="var(--card)" strokeWidth={2.5} />
              <text textAnchor="middle" dy={4} fontSize={11} fontWeight={600} fill="var(--background)" fontFamily="var(--font-plex-mono)">
                {m.n}
              </text>
            </g>
          ))}
        </svg>
        <figcaption className="flex flex-wrap gap-x-5 gap-y-1 px-1 pt-2 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2 border border-foreground bg-aq-satisfactory" /> monitor, live reading
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2 border border-foreground/55 bg-card" /> monitor, feed delayed
          </span>
          {alt && (
            <span className="inline-flex items-center gap-1.5">
              <span className="h-[3px] w-4 rounded-full bg-foreground/25" /> another route
            </span>
          )}
        </figcaption>
      </figure>

      <ol className="space-y-7 self-center">
        <li className="grid grid-cols-[1.75rem_1fr] gap-3">
          <Num n={1} />
          <p className="text-[15px] leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">Every 200 metres gets its own forecast.</span> The worst stretch
            of this ride is <span className="text-foreground tabular">{Math.round(worst.pm25)} µg/m³</span>, at the
            moment you&apos;d reach it ({istTime(worstAt)}), not an average for the whole city.
          </p>
        </li>
        <li className="grid grid-cols-[1.75rem_1fr] gap-3">
          <Num n={2} />
          <p className="text-[15px] leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">Confidence falls away from monitors.</span> Here the nearest
            station is <span className="text-foreground tabular">{far.station_km.toFixed(1)} km</span> off, so this
            stretch scores <span className="text-foreground tabular">{far.confidence.toFixed(2)}</span>, and the app
            says so.
          </p>
        </li>
        {alt && (
          <li className="grid grid-cols-[1.75rem_1fr] gap-3">
            <Num n={3} />
            <p className="text-[15px] leading-relaxed text-muted-foreground">
              <span className="font-medium text-foreground">Other roads are scored too.</span> Going {alt.label} takes{" "}
              <span className="text-foreground tabular">{Math.abs(Math.round(altMin))} min {altMin >= 0 ? "longer" : "less"}</span>{" "}
              with <span className="text-foreground tabular">{Math.abs(altPct).toFixed(0)}% {altPct >= 0 ? "more" : "less"}</span>{" "}
              exposure.
            </p>
          </li>
        )}
        <li className="grid grid-cols-[1.75rem_1fr] gap-3">
          <Num n={alt ? 4 : 3} muted />
          <p className="text-[15px] leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">Then every departure is checked,</span> every 15 minutes for the
            next few hours. Your sensitivity decides whether a cleaner option is worth the extra time; it never changes
            the pollution numbers.{" "}
            <Link href="/method" className="whitespace-nowrap text-foreground underline underline-offset-4">
              Read the method
            </Link>
          </p>
        </li>
      </ol>
    </div>
  );
}

function Num({ n, muted = false }: { n: number; muted?: boolean }) {
  return (
    <span
      className={
        muted
          ? "flex size-6 items-center justify-center rounded-full border font-mono text-[11px] font-semibold"
          : "flex size-6 items-center justify-center rounded-full bg-foreground font-mono text-[11px] font-semibold text-background"
      }
    >
      {n}
    </span>
  );
}
