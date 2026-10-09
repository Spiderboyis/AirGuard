import Link from "next/link";

import { SiteFooter } from "@/components/site/site-footer";
import { SiteHeader } from "@/components/site/site-header";

import { EvidenceTeaser, HeroActions, HeroMap, LiveFacts } from "./home-client";

const STEPS = [
  {
    n: "01",
    title: "Forecast",
    body: "Every hour a model trained on a year of CPCB, DPCC and IMD readings, weather, the CAMS model and crop-fire detections forecasts PM2.5 at each station for the next 24 hours.",
  },
  {
    n: "02",
    title: "Score every 200 m",
    body: "Each route is cut into 200-metre pieces. Each piece gets the forecast for the minute you would reach it, blended from the nearest stations, with a confidence that drops as stations get farther away.",
  },
  {
    n: "03",
    title: "Decide",
    body: "Departures are checked every 15 minutes across the next hours. You get the cleanest option that fits your limits. Your sensitivity changes the trade-off, never the pollution numbers.",
  },
  {
    n: "04",
    title: "Explain",
    body: "An assistant built on the Strands Agents SDK answers follow-up questions using only numbers that AirGuard's tools return, and shows each tool call it made.",
  },
];

const PRINCIPLES = [
  ["A number is never shown alone", "Every exposure figure comes with a forecast range and a confidence score."],
  ["Delays are labelled", "When a station's feed is late, its value is marked as a model estimate, not a reading."],
  ["Checked against simple baselines", "The forecast is backtested on held-out weeks against persistence, the hour-of-day average and raw CAMS."],
  ["Guidance, not diagnosis", "AirGuard compares options within one way of travelling. It doesn't give medical advice."],
];

export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader className="sticky top-0" />

      <main>
        {/* Hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 pt-12 pb-16 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:pt-20">
          <div>
            <p className="text-xs font-medium tracking-[0.14em] text-muted-foreground uppercase">
              Delhi NCR · PM2.5 · Commute planner
            </p>
            <h1 className="mt-4 font-serif text-[3.2rem] leading-[0.98] tracking-[-0.02em] sm:text-7xl">
              Same commute.
              <br />
              <span className="italic">Less smoke.</span>
            </h1>
            <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted-foreground">
              AirGuard reads the PM2.5 forecast along every route you could take in the next few hours, then tells
              you which way to go and when to leave. Built for people who cycle, walk, or do the school run in Delhi.
            </p>
            <HeroActions />
            <LiveFacts />
          </div>
          <HeroMap />
        </section>

        {/* How it works */}
        <section className="rule-top">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <h2 className="font-serif text-3xl tracking-[-0.01em] sm:text-4xl">How it works</h2>
              <Link href="/method" className="text-sm underline underline-offset-4">Read the method</Link>
            </div>
            <ol className="mt-10 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((s) => (
                <li key={s.n} className="border-t border-foreground pt-4">
                  <span className="font-mono text-xs text-muted-foreground">{s.n}</span>
                  <h3 className="mt-2 text-lg font-medium">{s.title}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Principles */}
        <section className="rule-top bg-paper">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[1fr_2fr]">
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.01em] sm:text-4xl">Honest about what it knows</h2>
              <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">
                Delhi has a few dozen reference monitors for a city of more than twenty million people. Most of a
                route is far from any of them, so AirGuard says how sure it is every time.
              </p>
            </div>
            <dl className="grid gap-x-10 gap-y-8 sm:grid-cols-2">
              {PRINCIPLES.map(([t, b]) => (
                <div key={t}>
                  <dt className="font-medium">{t}</dt>
                  <dd className="mt-1.5 text-[15px] leading-relaxed text-muted-foreground">{b}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <EvidenceTeaser />
      </main>

      <SiteFooter />
    </div>
  );
}
