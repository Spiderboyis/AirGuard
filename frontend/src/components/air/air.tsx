"use client";

import { band, bandByKey, BANDS } from "@/lib/aq";
import { cn } from "@/lib/utils";

/** A route drawn as a strip: each segment's width is time spent, its colour the PM2.5 there. */
export function ExposureStrip({
  segments,
  className,
  height = 10,
}: {
  segments: { pm25: number; minutes: number }[];
  className?: string;
  height?: number;
}) {
  const total = segments.reduce((s, x) => s + x.minutes, 0) || 1;
  // Merge neighbours in the same band so the strip reads as stretches, not noise.
  const runs: { color: string; minutes: number }[] = [];
  for (const s of segments) {
    const c = band(s.pm25).color;
    const last = runs[runs.length - 1];
    if (last && last.color === c) last.minutes += s.minutes;
    else runs.push({ color: c, minutes: s.minutes });
  }
  return (
    <div
      className={cn("flex w-full overflow-hidden rounded-[3px] ring-1 ring-foreground/5", className)}
      style={{ height }}
      role="img"
      aria-label="PM2.5 along the route, coloured by air-quality band"
    >
      {runs.map((r, i) => (
        <div key={i} style={{ width: `${(r.minutes / total) * 100}%`, background: r.color }} />
      ))}
    </div>
  );
}

export function RiskBadge({ risk, label, className }: { risk: string; label?: string; className?: string }) {
  const b = bandByKey(risk);
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", className)}>
      <span className="size-2 rounded-full" style={{ background: b.color }} />
      {label ?? b.label}
    </span>
  );
}

export function PmDot({ pm25, className }: { pm25: number; className?: string }) {
  return <span className={cn("inline-block size-2.5 rounded-full", className)} style={{ background: band(pm25).color }} />;
}

export function confidenceWord(c: number) {
  return c >= 0.7 ? "High" : c >= 0.5 ? "Medium" : "Low";
}

/** Five ticks, like a signal meter. Always shown with a word and the number. */
export function ConfidenceMeter({ value, className, showLabel = true }: { value: number; className?: string; showLabel?: boolean }) {
  const filled = Math.max(1, Math.round(value * 5));
  return (
    <span className={cn("inline-flex items-center gap-2", className)} title={`Confidence ${value.toFixed(2)}`}>
      <span className="flex items-end gap-[2px]" aria-hidden>
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className={cn("w-[3px] rounded-[1px]", i < filled ? "bg-foreground" : "bg-foreground/15")}
            style={{ height: 5 + i * 2 }}
          />
        ))}
      </span>
      {showLabel && (
        <span className="text-xs text-muted-foreground">
          {confidenceWord(value)} <span className="tabular font-mono">{value.toFixed(2)}</span>
        </span>
      )}
    </span>
  );
}

export function AqLegend({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex h-1.5 overflow-hidden rounded-full">
        {BANDS.map((b) => (
          <div key={b.key} className="flex-1" style={{ background: b.color }} />
        ))}
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground tabular font-mono">
        {compact ? (
          <>
            <span>0</span>
            <span>60</span>
            <span>120</span>
            <span>250+ µg/m³</span>
          </>
        ) : (
          BANDS.map((b) => (
            <span key={b.key} className="flex-1 text-center">
              {b.label}
            </span>
          ))
        )}
      </div>
    </div>
  );
}
