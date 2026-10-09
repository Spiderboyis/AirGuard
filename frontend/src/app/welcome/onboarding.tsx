"use client";

import { ArrowLeftIcon, ArrowRightIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";

import { Logo } from "@/components/brand/logo";
import { MODE_ICON } from "@/components/plan/mode-picker";
import { PlaceSearch } from "@/components/plan/place-search";
import { LimitSlider, SensitivityPicker } from "@/components/profile/controls";
import { Button } from "@/components/ui/button";
import type { Mode, Sensitivity } from "@/lib/api";
import { useProfile, type Place } from "@/lib/profile";
import { cn } from "@/lib/utils";

const MINUTES_PER_10PCT: Record<Sensitivity, number> = { normal: 4, sensitive: 7, high: 10 };

const MODES: { key: Mode; title: string; note: string }[] = [
  { key: "walk", title: "Walk", note: "On foot, all or most of the way" },
  { key: "cycle", title: "Cycle", note: "Bicycle or e-bike" },
  { key: "two_wheeler", title: "Two-wheeler", note: "Scooter or motorbike" },
  { key: "car", title: "Car", note: "Windows up, AC on recirculate" },
];

const STEPS = ["You", "Travel", "Sensitivity", "Flexibility", "Usual trip"] as const;

const noopSubscribe = () => () => {};

/** The saved profile lives in localStorage, so the form renders only in the browser. */
export function Onboarding() {
  const onClient = useSyncExternalStore(noopSubscribe, () => true, () => false);
  return onClient ? <OnboardingForm /> : <div className="min-h-dvh" />;
}

function OnboardingForm() {
  const router = useRouter();
  const profile = useProfile();
  const [step, setStep] = useState(0);
  const [dir, setDir] = useState(1);
  const [name, setName] = useState(profile.name);
  const [mode, setMode] = useState<Mode>(profile.mode);
  const [sensitivity, setSensitivity] = useState<Sensitivity>(profile.sensitivity);
  const [maxExtra, setMaxExtra] = useState(profile.maxExtraMin);
  const [maxWait, setMaxWait] = useState(profile.maxWaitMin);
  const [from, setFrom] = useState<Place | null>(profile.usualFrom);
  const [to, setTo] = useState<Place | null>(profile.usualTo);

  const last = STEPS.length - 1;
  const go = (n: number) => {
    setDir(n > step ? 1 : -1);
    setStep(n);
  };
  const finish = () => {
    profile.update({
      onboarded: true,
      name: name.trim(),
      mode,
      sensitivity,
      maxExtraMin: maxExtra,
      maxWaitMin: maxWait,
      usualFrom: from,
      usualTo: to,
    });
    router.push("/plan");
  };

  // Live example of the decision rule: what a 30-minute wait must buy for this profile.
  const needFor30 = Math.ceil(((0.5 * 30) / MINUTES_PER_10PCT[sensitivity]) * 10);

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex h-16 items-center justify-between px-4 sm:px-6">
        <Link href="/" aria-label="AirGuard home">
          <Logo />
        </Link>
        <button
          type="button"
          onClick={finish}
          className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          Skip setup
        </button>
      </header>

      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col px-4 pt-6 pb-10 sm:pt-12">
        <div className="mb-10">
          <div className="flex gap-1.5" aria-hidden>
            {STEPS.map((s, i) => (
              <div key={s} className="h-[3px] flex-1 overflow-hidden rounded-full bg-foreground/10">
                <motion.div
                  className="h-full bg-foreground"
                  initial={false}
                  animate={{ width: i <= step ? "100%" : "0%" }}
                  transition={{ duration: 0.35, ease: [0.2, 0.7, 0.2, 1] }}
                />
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Step {step + 1} of {STEPS.length} · {STEPS[step]}
          </p>
        </div>

        <div className="relative flex-1">
          <AnimatePresence mode="wait" custom={dir} initial={false}>
            <motion.section
              key={step}
              custom={dir}
              initial={{ opacity: 0, x: 24 * dir }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 * dir }}
              transition={{ duration: 0.25, ease: [0.2, 0.7, 0.2, 1] }}
              className="space-y-6"
            >
              {step === 0 && (
                <>
                  <h1 className="font-serif text-4xl leading-[1.08] tracking-[-0.015em] text-balance sm:text-5xl">
                    The same commute can mean very different air.
                  </h1>
                  <p className="text-[17px] leading-relaxed text-muted-foreground">
                    AirGuard checks the PM2.5 forecast along each route for the next few hours and tells you which
                    way to go and when to leave. Four quick questions tailor that advice to you. Your answers stay in
                    this browser.
                  </p>
                  <label className="block space-y-2">
                    <span className="text-[15px] font-medium">What should we call you? <span className="font-normal text-muted-foreground">(optional)</span></span>
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      maxLength={40}
                      placeholder="Riya"
                      autoFocus
                      className="h-11 w-full rounded-lg border bg-card px-3 text-[15px] outline-none focus:border-foreground/40 focus:ring-3 focus:ring-ring/20"
                    />
                  </label>
                </>
              )}

              {step === 1 && (
                <>
                  <StepTitle title="How do you usually get around?" sub="We plan routes for this mode by default. You can switch any time." />
                  <div role="radiogroup" aria-label="Usual travel mode" className="grid grid-cols-2 gap-2.5">
                    {MODES.map((m) => {
                      const Icon = MODE_ICON[m.key];
                      const on = mode === m.key;
                      return (
                        <button
                          key={m.key}
                          type="button"
                          role="radio"
                          aria-checked={on}
                          onClick={() => setMode(m.key)}
                          className={cn(
                            "flex flex-col items-start gap-6 rounded-xl border bg-card p-4 text-left transition-[border-color,box-shadow]",
                            on ? "border-foreground/60 ring-1 ring-foreground/25" : "hover:border-foreground/25",
                          )}
                        >
                          <Icon className="size-6" strokeWidth={1.6} />
                          <span>
                            <span className="block text-[15px] font-medium">{m.title}</span>
                            <span className="block text-sm text-muted-foreground">{m.note}</span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </>
              )}

              {step === 2 && (
                <>
                  <StepTitle
                    title="How does polluted air affect you?"
                    sub="This changes how much time AirGuard trades for cleaner air. It never changes the pollution numbers."
                  />
                  <SensitivityPicker value={sensitivity} onChange={setSensitivity} />
                </>
              )}

              {step === 3 && (
                <>
                  <StepTitle title="How flexible is your trip?" sub="Set your limits. AirGuard never suggests anything beyond them." />
                  <div className="space-y-8 rounded-xl border bg-card p-5">
                    <LimitSlider
                      label="Extra time on the road"
                      hint="For a longer but cleaner route"
                      value={maxExtra}
                      onChange={setMaxExtra}
                      max={45}
                      step={5}
                    />
                    <LimitSlider
                      label="Latest you'd leave"
                      hint="Waiting for the air to clear"
                      value={maxWait}
                      onChange={setMaxWait}
                      max={240}
                      step={15}
                    />
                  </div>
                  <p className="rounded-lg bg-muted/70 p-3.5 text-sm leading-relaxed">
                    For example, AirGuard would ask you to wait 30 minutes only if it cuts your exposure by at
                    least <strong className="font-semibold tabular">{needFor30}%</strong>
                    {maxWait < 30 ? <> — but you&apos;ve said you can&apos;t wait that long, so it won&apos;t.</> : "."}
                  </p>
                </>
              )}

              {step === 4 && (
                <>
                  <StepTitle title="Do you make one trip most days?" sub="Save it and the planner opens ready to go. Optional." />
                  <div className="space-y-1.5">
                    <PlaceSearch label="From" marker="origin" value={from} onChange={setFrom} placeholder="Home" allowLocate />
                    <PlaceSearch label="To" marker="destination" value={to} onChange={setTo} placeholder="College, office, school…" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Riya cycles from Hauz Khas to North Campus at 8 AM. Yours might be a school run or a metro
                    connection — anything inside Delhi NCR works.
                  </p>
                </>
              )}
            </motion.section>
          </AnimatePresence>
        </div>

        <nav className="mt-10 flex items-center justify-between">
          <Button variant="ghost" size="lg" onClick={() => go(step - 1)} disabled={step === 0} className={cn(step === 0 && "invisible")}>
            <ArrowLeftIcon /> Back
          </Button>
          {step < last ? (
            <Button size="lg" className="h-11 px-5 text-[15px]" onClick={() => go(step + 1)}>
              Continue <ArrowRightIcon />
            </Button>
          ) : (
            <Button size="lg" className="h-11 px-5 text-[15px]" onClick={finish}>
              {from && to ? "Plan this trip" : "Open the planner"} <ArrowRightIcon />
            </Button>
          )}
        </nav>
      </main>
    </div>
  );
}

function StepTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="space-y-2">
      <h1 className="font-serif text-[2rem] leading-[1.1] tracking-[-0.01em] sm:text-4xl">{title}</h1>
      <p className="text-[15px] leading-relaxed text-muted-foreground">{sub}</p>
    </div>
  );
}
