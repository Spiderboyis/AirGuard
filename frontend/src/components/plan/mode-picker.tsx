"use client";

import { BikeIcon, CarIcon, FootprintsIcon, MotorbikeIcon, type LucideIcon } from "lucide-react";

import type { Mode } from "@/lib/api";
import { MODE_LABEL } from "@/lib/profile";
import { cn } from "@/lib/utils";

export const MODE_ICON: Record<Mode, LucideIcon> = {
  walk: FootprintsIcon,
  cycle: BikeIcon,
  two_wheeler: MotorbikeIcon,
  car: CarIcon,
};

const MODES: Mode[] = ["walk", "cycle", "two_wheeler", "car"];

export function ModePicker({ value, onChange }: { value: Mode; onChange: (m: Mode) => void }) {
  return (
    <div role="radiogroup" aria-label="Travel mode" className="grid grid-cols-4 gap-1 rounded-lg border bg-muted/50 p-1">
      {MODES.map((m) => {
        const Icon = MODE_ICON[m];
        const on = m === value;
        return (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(m)}
            className={cn(
              "flex flex-col items-center gap-1 rounded-md py-1.5 text-[11px] transition-colors",
              on ? "bg-card text-foreground shadow-sm ring-1 ring-foreground/10" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-4" strokeWidth={on ? 2.2 : 1.8} />
            {MODE_LABEL[m]}
          </button>
        );
      })}
    </div>
  );
}
