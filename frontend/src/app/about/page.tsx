"use client";
import { useEffect, useState } from "react";
import { getConfig, type Level } from "@/lib/api";

export default function About() {
  const [levels, setLevels] = useState<Level[]>([]);
  const [factors, setFactors] = useState<Record<string, number>>({});
  const [preferences, setPreferences] = useState<Record<string, number>>({});
  const [err, setErr] = useState("");
  useEffect(() => {
    getConfig().then((config) => {
      setLevels(config.levels);
      setFactors(config.mode_factors);
      setPreferences(config.preferences ?? {});
    }).catch((error) => setErr((error as Error).message));
  }, []);
  return (
    <main className="mx-auto max-w-3xl space-y-3 p-4 text-sm">
      <h1 className="text-xl font-semibold">How AirGuard works, and what it cannot tell you</h1>
      {err && <p role="alert" className="text-red-700">{err}</p>}
      <p>AirGuard ranks route and departure options by an <b>exposure index</b>: forecast PM2.5 along each route, times travel time, times a mode factor. It is a relative index for comparing options. It is not a measured dose and it is not medical advice.</p>
      <h2 className="font-semibold">Forecasts</h2>
      <p>A model forecasts PM2.5 at stations at +1, +3, +6, +12 and +24 hours, and the app interpolates between those points. Departure steps of 15 minutes are scenario evaluations, not 15-minute forecasts. The Evaluation page shows accuracy against simple baselines and how often the forecast range covers what happened. Call that range calibrated only when coverage is near 80%.</p>
      <h2 className="font-semibold">AirGuard levels (µg/m³)</h2>
      <p>These are AirGuard&apos;s own levels for the average forecast PM2.5 on a route. They are not official AQI categories. CPCB&apos;s PM2.5 categories are defined on 24-hour averages, so they are not applied to a single trip.</p>
      <ul className="list-disc pl-5">
        {levels.map((level, index) => (
          <li key={level.name}>{level.name.replaceAll("_", " ")}: {level.max === null ? `above ${levels[index - 1]?.max}` : `up to ${level.max}`}</li>
        ))}
      </ul>
      <h2 className="font-semibold">Mode factors</h2>
      <p>Relative breathing intake per minute, walking = 1: {Object.entries(factors).map(([name, factor]) => `${name} ${factor}`).join(", ") || "loading…"}. These are illustrative assumptions, so compare options within one mode and do not read across modes. Metro is not offered because the routing profiles used here have no transit mode.</p>
      <h2 className="font-semibold">Sensitivity</h2>
      <p>Sensitivity never changes the exposure estimate. It changes how many extra minutes the recommendation will accept for each 10% reduction in exposure{Object.keys(preferences).length ? `: ${Object.entries(preferences).map(([name, minutes]) => `${name} ${minutes}`).join(", ")}` : ""}.</p>
      <h2 className="font-semibold">Data reliability</h2>
      <p>The reliability score is 0.6 times a distance term plus 0.4 times a forecast-interval term. Distance uses inverse-distance weighting of the four nearest stations, power 2, on segments of about 200 m. It is a heuristic, not a probability that the estimate is right. It falls as the nearest station gets farther away and as the forecast range gets wider.</p>
      <h2 className="font-semibold">Limits</h2>
      <p>Delhi has few stations, so values between stations are interpolated. The engine assumes a steady speed along the route and ignores street-level differences such as a junction versus a park. Departure planning compares leaving now with waiting up to 4 hours by default (the API accepts up to 6). A scheduled clock time such as tomorrow at 8 AM is not supported.</p>
      <h2 className="font-semibold">Sources</h2>
      <p>Air quality: OpenAQ. Weather: Open-Meteo, with CAMS. Fires: NASA FIRMS. Maps: © OpenStreetMap contributors, tiles via OpenFreeMap. Routing: OpenRouteService. A public OSRM server is used only when no OpenRouteService key is configured.</p>
      <p>Guidance only, not medical advice. For health questions, talk to a doctor.</p>
    </main>
  );
}
