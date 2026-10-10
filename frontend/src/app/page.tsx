import Link from "next/link";

import { BandRule } from "@/components/air/band-rule";
import { ScrollBand } from "@/components/air/scroll-band";
import { SiteFooter } from "@/components/site/site-footer";
import { SiteHeader } from "@/components/site/site-header";

import { AnatomySection, Dateline, EvidenceBlock, HeroFigure, PlanButton } from "./home-client";

const WONT = [
  ["Show a number without its range.", "Every exposure figure comes with a forecast range and a confidence score."],
  ["Call the air “safe”.", "It tells you which option means less exposure, never that some amount is fine."],
  ["Compare cycling with driving.", "Breathing rates differ by mode, so options are only compared within one way of travelling."],
  ["Invent a number.", "The assistant can only repeat numbers its tools returned; anything else is caught and replaced."],
  ["Hide a delayed feed.", "When a station's data runs late, its value is marked as a model estimate."],
  ["Give medical advice.", "It's exposure guidance. If air pollution affects your health, talk to a doctor."],
];

function SectionHead({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div>
      <BandRule className="mb-5 w-12" />
      <h2 className="font-serif text-3xl tracking-[-0.01em] sm:text-4xl">{title}</h2>
      {children}
    </div>
  );
}

export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col">
      <ScrollBand />
      <SiteHeader className="sticky top-0" />

      <main>
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-4 pt-14 pb-16 sm:px-6 lg:pt-20">
          <div className="grid gap-8 lg:grid-cols-12 lg:items-end">
            <h1 className="font-serif text-[2.6rem] leading-[1.04] tracking-[-0.02em] text-balance sm:text-6xl lg:col-span-8 lg:text-[4.1rem]">
              Delhi&apos;s air changes by the hour and by the street. Your commute can too.
            </h1>
            <div className="lg:col-span-4 lg:pb-2">
              <p className="text-[17px] leading-relaxed text-muted-foreground">
                Pick a trip. AirGuard checks each route, 200 metres at a time, for every departure in the next few
                hours, and shows you where the smoke thins out.
              </p>
              <div className="mt-6 flex flex-wrap items-center gap-3">
                <PlanButton />
                <Link href="/evidence" className="inline-flex h-12 items-center px-2 text-[15px] underline-offset-4 hover:underline">
                  How accurate is it?
                </Link>
              </div>
            </div>
          </div>
          <div className="mt-12 border-y py-3">
            <Dateline />
          </div>
          <div className="mt-8">
            <HeroFigure />
          </div>
        </section>

        {/* How AirGuard reads a route */}
        <section className="border-t">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
            <SectionHead title="How AirGuard reads a route">
              <p className="mt-3 max-w-2xl text-[15px] text-muted-foreground">
                The same ride as above, leaving now. Numbers on the map match the notes.
              </p>
            </SectionHead>
            <div className="mt-10">
              <AnatomySection />
            </div>
          </div>
        </section>

        {/* What it won't do */}
        <section className="border-t bg-paper">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[1fr_1.6fr] lg:py-20">
            <SectionHead title="Honest about what it knows">
              <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">
                Delhi has a few dozen reference monitors for a city of more than twenty million people. Most of a route
                is far from any of them, so AirGuard says how sure it is every time.
              </p>
            </SectionHead>
            <div>
              <p className="mb-2 text-sm text-muted-foreground">AirGuard won&apos;t:</p>
              <ul className="border-t">
                {WONT.map(([t, b]) => (
                  <li key={t} className="grid gap-1 border-b py-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] sm:gap-6">
                    <span className="font-serif text-xl leading-snug">{t}</span>
                    <span className="text-[15px] leading-relaxed text-muted-foreground">{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Evidence */}
        <section className="border-t">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
            <SectionHead title="Tested on weeks it never saw" />
            <EvidenceBlock />
          </div>
        </section>

        {/* Closing */}
        <section className="border-t">
          <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 px-4 py-16 sm:px-6 lg:flex-row lg:items-end lg:justify-between lg:py-20">
            <div>
              <p className="font-serif text-5xl leading-none tracking-[-0.02em] sm:text-6xl">Same commute. Less smoke.</p>
              <p className="mt-4 text-[15px] text-muted-foreground">
                Takes a minute to set up. Your profile stays in your browser.
              </p>
            </div>
            <PlanButton />
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
