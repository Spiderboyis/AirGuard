"use client";

import { UserRoundIcon } from "lucide-react";

import { LimitSlider, SensitivityPicker } from "@/components/profile/controls";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { minutes } from "@/lib/format";
import { SENSITIVITY_COPY, useProfile } from "@/lib/profile";

export function ProfileSummary() {
  const p = useProfile();
  return (
    <span className="truncate">
      {SENSITIVITY_COPY[p.sensitivity].short} · up to {minutes(p.maxExtraMin)} extra · wait ≤ {minutes(p.maxWaitMin)}
    </span>
  );
}

export function ProfileSheet({ onChanged }: { onChanged?: () => void }) {
  const p = useProfile();
  return (
    <Sheet onOpenChange={(open) => !open && onChanged?.()}>
      <SheetTrigger
        className="flex w-full items-center gap-2 rounded-md px-1 py-1 text-left text-xs text-muted-foreground hover:text-foreground"
        aria-label="Edit your profile"
      >
        <UserRoundIcon className="size-3.5 shrink-0" />
        <ProfileSummary />
        <span className="ml-auto shrink-0 underline underline-offset-4">Edit</span>
      </SheetTrigger>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="font-serif text-2xl font-normal">Your profile</SheetTitle>
          <SheetDescription>
            These settings change how much time AirGuard trades for cleaner air. They never change the pollution
            numbers. Saved in this browser only.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-8 px-4 pb-8">
          <section className="space-y-3">
            <h3 className="text-sm font-medium">How does polluted air affect you?</h3>
            <SensitivityPicker value={p.sensitivity} onChange={(sensitivity) => p.update({ sensitivity })} />
          </section>
          <LimitSlider
            label="Extra time on the road"
            hint="A longer but cleaner route"
            value={p.maxExtraMin}
            onChange={(maxExtraMin) => p.update({ maxExtraMin })}
            max={45}
            step={5}
          />
          <LimitSlider
            label="Latest you'd leave"
            hint="Waiting for the air to clear"
            value={p.maxWaitMin}
            onChange={(maxWaitMin) => p.update({ maxWaitMin })}
            max={240}
            step={15}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
