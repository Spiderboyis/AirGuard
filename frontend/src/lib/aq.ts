/**
 * Air-quality scale used everywhere in the UI. Bands follow CPCB's PM2.5 breakpoints (µg/m³);
 * colours are CSS variables defined in globals.css so they adapt to light and dark themes.
 */

export const WHO_24H = 15; // WHO 2021 24-hour PM2.5 guideline, µg/m³

export const BANDS = [
  { key: "good", label: "Good", max: 30, color: "var(--aq-good)" },
  { key: "satisfactory", label: "Satisfactory", max: 60, color: "var(--aq-satisfactory)" },
  { key: "moderate", label: "Moderate", max: 90, color: "var(--aq-moderate)" },
  { key: "poor", label: "Poor", max: 120, color: "var(--aq-poor)" },
  { key: "very_poor", label: "Very poor", max: 250, color: "var(--aq-very-poor)" },
  { key: "severe", label: "Severe", max: Infinity, color: "var(--aq-severe)" },
] as const;

export type BandKey = (typeof BANDS)[number]["key"];

export function band(pm25: number) {
  return BANDS.find((b) => pm25 <= b.max) ?? BANDS[BANDS.length - 1];
}

export function bandByKey(key: string) {
  return BANDS.find((b) => b.key === key) ?? BANDS[0];
}

/** Hex values for MapLibre (which can't read CSS variables). Light and dark variants. */
export const BAND_HEX = {
  light: ["#3f9a5b", "#97b83a", "#dfb12c", "#e3822e", "#cf3f2e", "#8a1c3e"],
  dark: ["#4fae6c", "#a6c64a", "#e6bd3c", "#ec8d3a", "#e2513f", "#b33a5f"],
};

/** MapLibre `step` expression colouring a numeric pm25 property by band. */
export function bandStepExpression(prop: string, dark: boolean): unknown[] {
  const c = dark ? BAND_HEX.dark : BAND_HEX.light;
  return ["step", ["get", prop], c[0], 30.001, c[1], 60.001, c[2], 90.001, c[3], 120.001, c[4], 250.001, c[5]];
}

export function bandHex(pm25: number, dark = false) {
  const i = BANDS.findIndex((b) => pm25 <= b.max);
  return (dark ? BAND_HEX.dark : BAND_HEX.light)[i < 0 ? 5 : i];
}
