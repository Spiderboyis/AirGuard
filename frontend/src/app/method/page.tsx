import type { Metadata } from "next";

import { SiteFooter } from "@/components/site/site-footer";
import { SiteHeader } from "@/components/site/site-header";

import { Assumptions } from "./assumptions";

export const metadata: Metadata = { title: "Method" };

export default function MethodPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader className="sticky top-0" />
      <main className="mx-auto w-full max-w-3xl px-4 pt-12 pb-20 sm:px-6">
        <p className="text-xs font-medium tracking-[0.14em] text-muted-foreground uppercase">Method</p>
        <h1 className="mt-3 font-serif text-5xl leading-[1.02] tracking-[-0.02em]">How AirGuard decides</h1>
        <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
          Every number in the app comes from deterministic code: a forecast model, an interpolation step and an
          exposure calculation. The assistant only chooses which of these tools to call and explains what they
          return. This page lists every assumption, read live from the code that uses it.
        </p>

        <article className="mt-12 space-y-12 text-[16px] leading-relaxed [&_h2]:font-serif [&_h2]:text-3xl [&_h2]:tracking-[-0.01em] [&_p]:mt-3 [&_p]:text-muted-foreground">
          <section>
            <h2>1. Forecast at each station</h2>
            <p>
              AirGuard uses about 75 PM2.5 monitors across Delhi NCR: CPCB, DPCC, IMD and state board stations, the US
              Embassy monitor and a few low-cost sensors, all via OpenAQ. Every hour it forecasts each one for now
              and +1, +3, +6, +12 and +24 hours using gradient-boosted trees (XGBoost). Inputs are the station&apos;s
              recent readings, neighbouring stations, the CAMS global PM2.5 forecast, wind, humidity, temperature,
              boundary-layer height and crop fires detected upwind by NASA FIRMS in the two days before.
            </p>
            <p>
              Each forecast carries an 80% range, set from how wrong the model was on a recent calibration week.
              When a station&apos;s feed is delayed, its own readings are left out and the model estimates it from
              everything else; such values are marked as estimated.
            </p>
          </section>

          <section>
            <h2>2. Along the route</h2>
            <p>
              Routes come from OpenStreetMap via OSRM, up to three per trip. Each is cut into 200-metre pieces, and
              each piece is given the time you would reach it. PM2.5 there is interpolated in time between forecast
              hours, then in space from the six nearest stations with inverse-distance weighting.
            </p>
            <p>
              Confidence for each piece combines how far the nearest station is and how wide the forecast range is.
              A route&apos;s confidence is the time-weighted average of its pieces.
            </p>
          </section>

          <section>
            <h2>3. The exposure index</h2>
            <p>For each route and departure time:</p>
            <pre className="mt-4 overflow-x-auto rounded-lg border bg-card p-4 font-mono text-sm text-foreground">
              exposure index = Σ  PM2.5(piece) × hours on piece × mode factor
            </pre>
            <p>
              The result is in µg·h/m³. It is a model estimate, not a measured dose. Mode factors scale for how hard
              you breathe and how enclosed you are, so AirGuard only compares options within one mode.
            </p>
            <Assumptions part="modes" />
          </section>

          <section>
            <h2>4. Trip air level</h2>
            <p>
              The trip&apos;s average PM2.5 is labelled using CPCB&apos;s PM2.5 bands. CPCB defines them for 24-hour
              averages; using them for a trip average is our simplification, so the app calls this an air level, not
              an AQI.
            </p>
            <Assumptions part="bands" />
          </section>

          <section>
            <h2>5. Choosing what to recommend</h2>
            <p>
              Departures are checked every 15 minutes across the window you allow. The baseline is the fastest route
              leaving now. Another option is recommended only if the exposure it saves is worth the time it costs
              you, and only within your limits:
            </p>
            <pre className="mt-4 overflow-x-auto rounded-lg border bg-card p-4 font-mono text-sm text-foreground">
{`cost  = extra minutes on the road + 0.5 × minutes waited
worth = minutes per 10% (your sensitivity) × reduction % / 10
recommend the lowest-exposure option where cost ≤ worth`}
            </pre>
            <p>
              Waiting counts half because you can wait indoors. Reductions under 5% are treated as noise. Your
              sensitivity changes only this trade-off. The pollution estimate is the same for everyone.
            </p>
            <Assumptions part="decision" />
          </section>

          <section>
            <h2>6. The assistant</h2>
            <p>
              The assistant is built with the Strands Agents SDK, an open-source agent framework from AWS. It has six
              tools: the current time, place search, the saved trip analysis, a point forecast, route scoring and the
              departure search. Before an answer is shown, every number in it is checked against the numbers the
              tools returned. If any number can&apos;t be traced, the answer is replaced by a fixed explanation of the
              saved analysis, and the app says so.
            </p>
          </section>

          <section>
            <h2>7. Known limits</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-muted-foreground">
              <li>Monitors are sparse; most of a route is interpolated, and roadside levels can be higher than any nearby station.</li>
              <li>Travel times come from OpenStreetMap routing without live traffic.</li>
              <li>Forecasts run to 24 hours ahead, and departures are planned up to 6 hours ahead from now.</li>
              <li>Mode factors are assumptions from published breathing rates, not measurements of you.</li>
              <li>This is general guidance, not medical advice.</li>
            </ul>
          </section>

          <section>
            <h2>Data and credits</h2>
            <Assumptions part="credits" />
          </section>
        </article>
      </main>
      <SiteFooter />
    </div>
  );
}
