import type { Metadata } from "next";

import { SiteFooter } from "@/components/site/site-footer";
import { SiteHeader } from "@/components/site/site-header";

import { EvidenceBody } from "./evidence";

export const metadata: Metadata = { title: "Evidence" };

export default function EvidencePage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader className="sticky top-0" />
      <main className="mx-auto w-full max-w-5xl px-4 pt-12 pb-20 sm:px-6">
        <p className="text-xs font-medium tracking-[0.14em] text-muted-foreground uppercase">Evidence</p>
        <h1 className="mt-3 max-w-3xl font-serif text-5xl leading-[1.02] tracking-[-0.02em]">
          How good is the forecast?
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-muted-foreground">
          Every route and departure recommendation rests on a station-level PM2.5 forecast. Here is how that forecast
          did on the most recent weeks of data, which the model never saw while training, compared with three simple
          ways of guessing.
        </p>
        <EvidenceBody />
      </main>
      <SiteFooter />
    </div>
  );
}
