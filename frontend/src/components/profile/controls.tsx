"use client";

import { Slider } from "@/components/ui/slider";
import type { Sensitivity } from "@/lib/api";
import { minutes } from "@/lib/format";
import { SENSITIVITY_COPY } from "@/lib/profile";
import { cn } from "@/lib/utils";

const LEVELS: Sensitivity[] = ["normal", "sensitive", "high"];

export function SensitivityPicker({ value, onChange }: { value: Sensitivity; onChange: (s: Sensitivity) => void }) {
  return (
    <div role="radiogroup" aria-label="Sensitivity to air pollution" className="space-y-2">
      {LEVELS.map((s, i) => {
        const on = s === value;
        const c = SENSITIVITY_COPY[s];
        return (
          <button
            key={s}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(s)}
            className={cn(
              "flex w-full items-start gap-3 rounded-lg border bg-card p-3.5 text-left transition-[border-color,box-shadow]",
              on ? "border-foreground/60 ring-1 ring-foreground/25" : "hover:border-foreground/25",
            )}
          >
            <span className="mt-1 flex items-end gap-[3px]" aria-hidden>
              {[0, 1, 2].map((k) => (
                <span
                  key={k}
                  className={cn("w-1 rounded-[1px]", k <= i ? "bg-foreground" : "bg-foreground/15")}
                  style={{ height: 6 + k * 4 }}
                />
              ))}
            </span>
            <span>
              <span className="block text-[15px] font-medium">{c.title}</span>
              <span className="mt-0.5 block text-sm text-muted-foreground">{c.body}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function LimitSlider({
  label,
  hint,
  value,
  onChange,
  max,
  step,
  format = minutes,
}: {
  label: string;
  hint: string;
  value: number;
  onChange: (v: number) => void;
  max: number;
  step: number;
  format?: (v: number) => string;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <p className="text-[15px] font-medium">{label}</p>
          <p className="text-sm text-muted-foreground">{hint}</p>
        </div>
        <span className="font-serif text-2xl tabular">{value === 0 ? "None" : format(value)}</span>
      </div>
      <Slider
        value={[value]}
        min={0}
        max={max}
        step={step}
        onValueChange={(v) => onChange(Array.isArray(v) ? v[0] : (v as number))}
        aria-label={label}
      />
    </div>
  );
}
