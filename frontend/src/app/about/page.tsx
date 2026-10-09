"use client";
import { useEffect, useState } from "react";
import { getConfig, type Level } from "@/lib/api";

export default function About() {
  const [levels, setLevels] = useState<Level[]>([]);
  const [factors, setFactors] = useState<Record<string, number>>({});
  const [preferences, setPreferences] = useState<Record<string, number>>({});
  const [err, setErr] = useState("");

  useEffect(() => {
    getConfig()
      .then((config) => {
        setLevels(config.levels);
        setFactors(config.mode_factors);
        setPreferences(config.preferences ?? {});
      })
      .catch((error) => setErr((error as Error).message));
  }, []);

  return (
    <main className="mx-auto max-w-4xl space-y-6 py-3">
      {/* Header */}
      <div className="surface-card p-6">
        <h1 className="font-display text-xl font-semibold tracking-tight text-white">
          How AirGuard Works
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-2xl leading-relaxed">
          AirGuard ranks route and departure options by an exposure index: forecast PM2.5 along each route, times travel time, times a mode factor. It is a relative index for comparing options, not medical advice.
        </p>
      </div>

      {err && (
        <div role="alert" className="rounded-xl bg-rose-500/10 p-4 text-xs text-rose-300 border border-rose-500/20">
          {err}
        </div>
      )}

      {/* Grid of clean documentation sections */}
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Exposure formula */}
        <div className="surface-card p-5 space-y-3">
          <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
            Exposure Index Calculation
          </h2>
          <div className="rounded-lg bg-black/40 p-3 font-mono text-xs text-emerald-400 border border-white/[0.04]">
            Exposure = Σ (PM2.5 × Duration × Mode Factor)
          </div>
          <p className="text-xs text-zinc-400 leading-relaxed">
            The index measures relative inhalation exposure. Comparing route A against route B within the same travel mode gives an estimated percentage exposure reduction.
          </p>
        </div>

        {/* Mode factors */}
        <div className="surface-card p-5 space-y-3">
          <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
            Travel Mode Multipliers
          </h2>
          <p className="text-xs text-zinc-400">
            Relative breathing intake volume per minute (walking = 1.0x):
          </p>
          <div className="grid grid-cols-3 gap-2 font-mono text-center">
            {Object.entries(factors).map(([mode, factor]) => (
              <div key={mode} className="rounded-lg bg-white/[0.03] p-2 border border-white/[0.06]">
                <div className="text-[10px] uppercase text-zinc-500">{mode}</div>
                <div className="text-sm font-semibold text-zinc-200 mt-0.5">{factor}x</div>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-zinc-500">
            Higher exertion like cycling increases respiratory ventilation rate per minute.
          </p>
        </div>

        {/* Air Quality Levels */}
        <div className="surface-card p-5 space-y-3">
          <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
            AirGuard PM2.5 Categories (µg/m³)
          </h2>
          <div className="space-y-1.5 font-mono text-xs">
            {levels.map((lvl, idx) => (
              <div key={lvl.name} className="flex items-center justify-between rounded-md bg-black/30 px-2.5 py-1.5 border border-white/[0.04]">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: lvl.color }} />
                  <span className="text-zinc-300 capitalize text-xs">{lvl.name.replaceAll("_", " ")}</span>
                </div>
                <span className="text-zinc-500 text-xs">
                  {lvl.max === null ? `> ${levels[idx - 1]?.max} µg/m³` : `≤ ${lvl.max} µg/m³`}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Data Sources */}
        <div className="surface-card p-5 space-y-3">
          <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
            Data Sources & Provenance
          </h2>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-white/[0.04]">
              <span className="text-zinc-500">Ground PM2.5:</span>
              <span className="text-zinc-300">OpenAQ (CPCB & DPCC)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-white/[0.04]">
              <span className="text-zinc-500">Weather & CAMS:</span>
              <span className="text-zinc-300">Open-Meteo European CAMS</span>
            </div>
            <div className="flex justify-between py-1 border-b border-white/[0.04]">
              <span className="text-zinc-500">Fire Detection:</span>
              <span className="text-zinc-300">NASA FIRMS (MODIS/VIIRS)</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-zinc-500">Routing:</span>
              <span className="text-zinc-300">OpenRouteService & OSM</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sensitivity explanation */}
      <div className="surface-card p-5 space-y-2">
        <h3 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
          Sensitivity Optimization Preferences
        </h3>
        <p className="text-xs text-zinc-400 leading-relaxed">
          Sensitivity settings determine how many extra minutes of travel time the routing engine accepts for each 10% reduction in PM2.5 exposure
          {Object.keys(preferences).length > 0 && (
            <span className="font-mono text-zinc-300 ml-1">
              ({Object.entries(preferences).map(([k, v]) => `${k}: +${v} min / 10% exposure delta`).join(", ")})
            </span>
          )}
          . A higher sensitivity will accept a longer detour if it significantly avoids high-pollution arterial roads.
        </p>
      </div>
    </main>
  );
}
